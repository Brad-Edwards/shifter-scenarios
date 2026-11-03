#!/usr/bin/env bash
set -euo pipefail
umask 077

if [[ $# -ne 1 || ! $1 =~ ^[a-z0-9][a-z0-9-]{0,11}$ ]]; then
  echo "usage: $0 SHORT_RUN_LABEL" >&2
  exit 2
fi

label=$1
project=${CINDER_GCP_PROJECT:-prod-mgau4w}
zone=${CINDER_GCP_ZONE:-us-central1-a}
remote_root=${CINDER_REMOTE_ROOT:-/opt/cinder-typhoon}
kepler_image="cinder-$label-k-base"
arwc_image="cinder-$label-a-base"
kepler_instances=("cinder-$label-k1" "cinder-$label-k2" "cinder-$label-k3")
arwc_instances=("cinder-$label-a1" "cinder-$label-a2" "cinder-$label-a3")
firewall_rules=("cinder-$label-link-1" "cinder-$label-link-2" "cinder-$label-link-3")
transfer_dir=$(mktemp -d /tmp/cinder-three-range.XXXXXX)
keep=${CINDER_KEEP_TEST_RANGES:-0}

remote() {
  local instance=$1
  local command=$2
  gcloud compute ssh "$instance" \
    --project "$project" --zone "$zone" --tunnel-through-iap \
    --command "$command"
}

cleanup() {
  local status=$?
  rm -rf -- "$transfer_dir"
  if [[ $keep != 1 ]]; then
    gcloud compute firewall-rules delete "${firewall_rules[@]}" \
      --project "$project" --quiet >/dev/null 2>&1 || true
    gcloud compute instances delete \
      "${kepler_instances[@]}" "${arwc_instances[@]}" \
      --project "$project" --zone "$zone" --quiet >/dev/null 2>&1 || true
    gcloud compute machine-images delete "$kepler_image" "$arwc_image" \
      --project "$project" --quiet >/dev/null 2>&1 || true
  fi
  exit "$status"
}
trap cleanup EXIT

wait_all() {
  local failed=0
  local pid
  for pid in "$@"; do
    wait "$pid" || failed=1
  done
  ((failed == 0))
}

echo "stage=create-machine-images"
gcloud compute machine-images create "$kepler_image" \
  --project "$project" --source-instance cinder-keplerops-golden \
  --source-instance-zone "$zone" >/dev/null
gcloud compute machine-images create "$arwc_image" \
  --project "$project" --source-instance cinder-arwc-golden \
  --source-instance-zone "$zone" >/dev/null

echo "stage=create-range-copies"
pids=()
for instance in "${kepler_instances[@]}"; do
  gcloud compute instances create "$instance" \
    --project "$project" --zone "$zone" --source-machine-image "$kepler_image" \
    --network-interface=subnet=cinder-keplerops-carrier,no-address \
    --tags=cinder-keplerops-carrier \
    --labels=managed-by=shifter-scenarios,purpose=issue-verification,issue=267 >/dev/null &
  pids+=("$!")
done
for index in 0 1 2; do
  instance=${arwc_instances[$index]}
  gcloud compute instances create "$instance" \
    --project "$project" --zone "$zone" --source-machine-image "$arwc_image" \
    --network-interface=subnet=cinder-arwc-carrier,no-address \
    --tags=cinder-arwc-carrier,"cinder-$label-pair-$((index + 1))" \
    --labels=managed-by=shifter-scenarios,purpose=issue-verification,issue=267 >/dev/null &
  pids+=("$!")
done
wait_all "${pids[@]}"

echo "stage=configure-pair-firewalls"
for index in 0 1 2; do
  kepler_ip=$(gcloud compute instances describe "${kepler_instances[$index]}" \
    --project "$project" --zone "$zone" --format='value(networkInterfaces[0].networkIP)')
  [[ $kepler_ip =~ ^10\.[0-9]+\.[0-9]+\.[0-9]+$ ]] \
    || { echo "invalid KeplerOps copy address" >&2; exit 1; }
  gcloud compute firewall-rules create "${firewall_rules[$index]}" \
    --project "$project" --network cinder-arwc-golden --direction INGRESS \
    --action ALLOW --rules tcp:443 --source-ranges "$kepler_ip/32" \
    --target-tags "cinder-$label-pair-$((index + 1))" \
    --description "Temporary issue 267 paired-range verification" >/dev/null
done

echo "stage=wait-for-ssh"
for instance in "${kepler_instances[@]}" "${arwc_instances[@]}"; do
  for attempt in $(seq 1 60); do
    if remote "$instance" "test -d '$remote_root'" >/dev/null 2>&1; then
      break
    fi
    if [[ $attempt -eq 60 ]]; then
      echo "SSH did not become ready: $instance" >&2
      exit 1
    fi
    sleep 5
  done
done

echo "stage=install-verifier"
for index in 0 1 2; do
  instance=${kepler_instances[$index]}
  gcloud compute scp \
    "$(dirname -- "$0")/verify-range-isolation.py" \
    "$instance:/tmp/verify-range-isolation.py" \
    --project "$project" --zone "$zone" --tunnel-through-iap >/dev/null
  remote "$instance" \
    "sudo install -m 0755 /tmp/verify-range-isolation.py '$remote_root/build/keplerops/verify-range-isolation.py' && rm -f /tmp/verify-range-isolation.py" >/dev/null
  arwc=${arwc_instances[$index]}
  gcloud compute scp \
    "$(dirname -- "$0")/../arwc/restore-pristine.sh" \
    "$arwc:/tmp/arwc-restore-pristine.sh" \
    --project "$project" --zone "$zone" --tunnel-through-iap >/dev/null
  remote "$arwc" \
    "sudo install -m 0755 /tmp/arwc-restore-pristine.sh '$remote_root/build/arwc/restore-pristine.sh' && rm -f /tmp/arwc-restore-pristine.sh" >/dev/null
done

echo "stage=independent-range-generation"
pids=()
for index in 0 1 2; do
  kepler=${kepler_instances[$index]}
  arwc=${arwc_instances[$index]}
  arwc_ip=$(gcloud compute instances describe "$arwc" \
    --project "$project" --zone "$zone" --format='value(networkInterfaces[0].networkIP)')
  remote "$kepler" \
    "set -u; cd '$remote_root/build/keplerops'; sudo docker compose down -v --remove-orphans >/dev/null 2>&1 || true; sudo find .operator -mindepth 1 -delete || exit 1; printf 'ARWC_CARRIER_ADDRESS=%s\n' '$arwc_ip' | sudo tee .env >/dev/null; sudo bash ./generate-operator-material.sh >/var/tmp/cinder-$label-generate.log 2>&1 || { echo 'FAIL: $kepler credential generation' >&2; sudo tail -n 80 /var/tmp/cinder-$label-generate.log >&2; exit 1; }; sudo bash ./restore-pristine.sh >/var/tmp/cinder-$label-reset.log 2>&1 || { echo 'FAIL: $kepler reset' >&2; sudo tail -n 120 /var/tmp/cinder-$label-reset.log >&2; exit 1; }" &
  pids+=("$!")
  remote "$arwc" \
    "set -u; cd '$remote_root/build/arwc'; sudo docker compose down -v --remove-orphans >/dev/null 2>&1 || true; sudo find .operator -mindepth 1 -delete || exit 1; printf 'ARWC_CARRIER_ADDRESS=%s\n' '$arwc_ip' | sudo tee .env >/dev/null; sudo bash ./restore-pristine.sh >/var/tmp/cinder-$label-reset.log 2>&1 || { echo 'FAIL: $arwc reset' >&2; sudo tail -n 120 /var/tmp/cinder-$label-reset.log >&2; exit 1; }" &
  pids+=("$!")
done
wait_all "${pids[@]}"

echo "stage=pair-ranges"
for index in 0 1 2; do
  kepler=${kepler_instances[$index]}
  arwc=${arwc_instances[$index]}
  pair_dir="$transfer_dir/pair-$index"
  mkdir -p "$pair_dir"
  remote "$kepler" \
    "sudo install -m 0644 '$remote_root/build/keplerops/.operator/tls/ca.crt' /tmp/cinder-keplerops-ca.crt" >/dev/null
  remote "$arwc" \
    "sudo install -m 0644 '$remote_root/build/arwc/.operator/tls/ca.crt' /tmp/cinder-arwc-ca.crt" >/dev/null
  gcloud compute scp "$kepler:/tmp/cinder-keplerops-ca.crt" "$pair_dir/keplerops-ca.crt" \
    --project "$project" --zone "$zone" --tunnel-through-iap >/dev/null
  gcloud compute scp "$arwc:/tmp/cinder-arwc-ca.crt" "$pair_dir/arwc-ca.crt" \
    --project "$project" --zone "$zone" --tunnel-through-iap >/dev/null
  gcloud compute scp "$pair_dir/keplerops-ca.crt" "$arwc:/tmp/cinder-keplerops-ca.crt" \
    --project "$project" --zone "$zone" --tunnel-through-iap >/dev/null
  gcloud compute scp "$pair_dir/arwc-ca.crt" "$kepler:/tmp/cinder-arwc-ca.crt" \
    --project "$project" --zone "$zone" --tunnel-through-iap >/dev/null
  remote "$arwc" \
    "sudo install -m 0644 /tmp/cinder-keplerops-ca.crt '$remote_root/build/arwc/.operator/integration/keplerops-ca.crt'; sudo rm -f /tmp/cinder-keplerops-ca.crt /tmp/cinder-arwc-ca.crt; cd '$remote_root/build/arwc'; sudo docker compose up -d --force-recreate a-connector >/dev/null" >/dev/null
  remote "$kepler" \
    "sudo install -m 0644 /tmp/cinder-arwc-ca.crt '$remote_root/build/keplerops/.operator/integration/arwc-ca.crt'; sudo rm -f /tmp/cinder-arwc-ca.crt /tmp/cinder-keplerops-ca.crt; cd '$remote_root/build/keplerops'; sudo docker compose up -d --force-recreate a-connector >/dev/null" >/dev/null
done

echo "stage=credential-certificate-assertion-replay"
for source_index in 0 1 2; do
  for target_index in 0 1 2; do
    [[ $source_index == "$target_index" ]] && continue
    source_kepler=${kepler_instances[$source_index]}
    target_kepler=${kepler_instances[$target_index]}
    target_arwc=${arwc_instances[$target_index]}
    foreign_credentials="/tmp/cinder-$label-foreign-$source_index.json"
    foreign_assertion="/tmp/cinder-$label-assertion-$source_index.json"
    foreign_certificate="/tmp/cinder-$label-certificate-$source_index.crt"

    remote "$source_kepler" \
      "sudo cat '$remote_root/build/keplerops/.operator/range-seed/runtime-credentials.json'" \
      | remote "$target_kepler" "umask 077; cat > '$foreign_credentials'"
    remote "$source_kepler" \
      "sudo docker exec --user rowan cinder-keplerops-k-dev curl -sS --cacert /home/rowan/.local/share/keplerops/ca.crt -H 'Content-Type: application/json' --data-binary '{\"audience\":\"fieldkest-support\",\"subject\":\"urn:fieldkest:pairwise:7c0e4f2a-2e62-4d80-a279-1fdb4f02b6c7\",\"tenant\":\"TEN-ARWC-047\"}' https://support.keplerops.test/federation/retained-support/assertions" \
      | remote "$target_kepler" "umask 077; cat > '$foreign_assertion'"
    remote "$target_kepler" \
      "cd '$remote_root/build/keplerops'; sudo python3 ./verify-range-isolation.py '$foreign_credentials' --foreign-assertion '$foreign_assertion'; rm -f '$foreign_credentials' '$foreign_assertion'" \
      >/dev/null

    remote "$source_kepler" \
      "sudo cat '$remote_root/build/keplerops/.operator/integration/support-delivery.crt'" \
      | remote "$target_arwc" "umask 077; cat > '$foreign_certificate'"
    remote "$target_arwc" \
      "if sudo openssl verify -CAfile '$remote_root/build/arwc/.operator/integration/keplerops-ca.crt' '$foreign_certificate' >/dev/null 2>&1; then echo 'foreign certificate unexpectedly trusted' >&2; exit 1; fi; rm -f '$foreign_certificate'"
  done
done

run_acceptance() {
  local index=$1
  local operation=$2
  local kepler=${kepler_instances[$index]}
  remote "$kepler" \
    "set -eu; cd '$remote_root'; reset_identity=\$(sudo docker inspect --format={{.Id}} cinder-keplerops-k-dev); sudo python3 build/participant-runner/run.py --phase keplerops --operation '$operation' --development --cross-segment --reset-identity \"\$reset_identity\" --report '/var/tmp/cinder-$label-$operation.json' >/var/tmp/cinder-$label-$operation.log 2>&1"
}

summarize_acceptance_failure() {
  local index=$1
  local operation=$2
  local kepler=${kepler_instances[$index]}
  remote "$kepler" \
    "sudo python3 -c 'import json,sys; document=json.load(open(sys.argv[1])); boundary=document.get(\"boundary\") or {}; evidence=document.get(\"evidence\", {}).get(\"events\", []); completion=boundary.get(\"completion_evidence\") or {}; print(json.dumps({\"range\": sys.argv[2], \"operation\": document.get(\"operation\"), \"result\": document.get(\"result\"), \"failure\": document.get(\"failure\"), \"boundary_status\": boundary.get(\"status\"), \"failures\": boundary.get(\"failures\"), \"errors\": boundary.get(\"errors\"), \"skipped\": boundary.get(\"skipped\"), \"violations\": boundary.get(\"violations\", []), \"failed_subtests\": completion.get(\"failed_subtests\", []), \"last_test_method\": evidence[-1].get(\"test_method\") if evidence else None}, sort_keys=True))' '/var/tmp/cinder-$label-$operation.json' '$kepler'" \
    || echo "unable to read acceptance report for $kepler" >&2
}

wait_acceptance_all() {
  local operation=$1
  shift
  local pids=("$@")
  local failed=0
  local index
  for index in 0 1 2; do
    if ! wait "${pids[$index]}"; then
      echo "FAIL: ${kepler_instances[$index]} $operation acceptance" >&2
      summarize_acceptance_failure "$index" "$operation" >&2
      failed=1
    fi
  done
  ((failed == 0))
}

verify_transition() {
  local index=$1
  local transition=$2
  local arwc=${arwc_instances[$index]}
  remote "$arwc" \
    "sudo docker exec -i --user fieldlink cinder-arwc-connector python3 - '$transition' < '$remote_root/build/participant-runner/verify-arwc-transition.py' >/var/tmp/cinder-$label-$transition.log 2>&1"
}

echo "stage=three-range-package-known-solutions"
pids=()
for index in 0 1 2; do
  run_acceptance "$index" delivery-package & pids+=("$!")
done
wait_acceptance_all delivery-package "${pids[@]}"
for index in 0 1 2; do verify_transition "$index" package-activation; done

echo "stage=channel-token-replay"
for source_index in 0 1 2; do
  for target_index in 0 1 2; do
    [[ $source_index == "$target_index" ]] && continue
    source_kepler=${kepler_instances[$source_index]}
    target_kepler=${kepler_instances[$target_index]}
    foreign_credentials="/tmp/cinder-$label-foreign-$source_index.json"
    foreign_channel="/tmp/cinder-$label-channel-$source_index.json"
    remote "$source_kepler" \
      "sudo cat '$remote_root/build/keplerops/.operator/range-seed/runtime-credentials.json'" \
      | remote "$target_kepler" "umask 077; cat > '$foreign_credentials'"
    remote "$source_kepler" \
      "sudo docker exec --user fieldkest-registry cinder-keplerops-registry cat /var/lib/fieldkest-registry/published/delivery/channel-credential.json" \
      | remote "$target_kepler" "umask 077; cat > '$foreign_channel'"
    remote "$target_kepler" \
      "cd '$remote_root/build/keplerops'; sudo python3 ./verify-range-isolation.py '$foreign_credentials' --foreign-channel '$foreign_channel'; rm -f '$foreign_credentials' '$foreign_channel'" \
      >/dev/null
  done
done

echo "stage=reset-before-diagnostic"
pids=()
for index in 0 1 2; do
  remote "${arwc_instances[$index]}" \
    "cd '$remote_root/build/arwc' && sudo bash ./restore-pristine.sh >/var/tmp/cinder-$label-diagnostic-reset.log 2>&1" & pids+=("$!")
  remote "${kepler_instances[$index]}" \
    "cd '$remote_root/build/keplerops' && sudo bash ./restore-pristine.sh >/var/tmp/cinder-$label-diagnostic-reset.log 2>&1" & pids+=("$!")
done
wait_all "${pids[@]}"

echo "stage=three-range-diagnostic-known-solutions"
pids=()
for index in 0 1 2; do
  run_acceptance "$index" delivery-diagnostic & pids+=("$!")
done
wait_acceptance_all delivery-diagnostic "${pids[@]}"
for index in 0 1 2; do verify_transition "$index" diagnostic-execution; done

echo "stage=diagnostic-receipt-replay"
for source_index in 0 1 2; do
  for target_index in 0 1 2; do
    [[ $source_index == "$target_index" ]] && continue
    source_kepler=${kepler_instances[$source_index]}
    source_arwc=${arwc_instances[$source_index]}
    target_kepler=${kepler_instances[$target_index]}
    foreign_credentials="/tmp/cinder-$label-foreign-$source_index.json"
    foreign_receipt="/tmp/cinder-$label-receipt-$source_index.json"
    remote "$source_kepler" \
      "sudo cat '$remote_root/build/keplerops/.operator/range-seed/runtime-credentials.json'" \
      | remote "$target_kepler" "umask 077; cat > '$foreign_credentials'"
    remote "$source_arwc" \
      "sudo docker exec --user arwc-connector cinder-arwc-connector sh -c 'file=\$(find /var/lib/fieldlink-connector/receipts -name \"DIAG-ARWC-*.json\" -type f -print -quit); test -n \"\$file\"; cat \"\$file\"'" \
      | remote "$target_kepler" "umask 077; cat > '$foreign_receipt'"
    remote "$target_kepler" \
      "cd '$remote_root/build/keplerops'; sudo python3 ./verify-range-isolation.py '$foreign_credentials' --foreign-receipt '$foreign_receipt'; rm -f '$foreign_credentials' '$foreign_receipt'" \
      >/dev/null
  done
done

echo "stage=three-range-service-contracts"
pids=()
for index in 0 1 2; do
  kepler=${kepler_instances[$index]}
  arwc=${arwc_instances[$index]}
  CINDER_KEPLEROPS_INSTANCE="$kepler" CINDER_ARWC_INSTANCE="$arwc" \
    bash "$(dirname -- "$0")/check-service-contracts-gcp.sh" "$label-$((index + 1))" &
  pids+=("$!")
done
wait_all "${pids[@]}"

echo "PASS: three independent GCP ranges; credentials, certificates, assertions, channel tokens, cookies, and diagnostic receipts are range-bound; both carriers and service contracts pass"
