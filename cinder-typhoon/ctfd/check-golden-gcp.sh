#!/usr/bin/env bash
set -euo pipefail
umask 077

if [[ $# -ne 1 || ! $1 =~ ^[a-z0-9][a-z0-9-]{0,11}$ ]]; then
  echo "usage: $0 SHORT_RUN_LABEL" >&2
  exit 2
fi

label=$1
script_root=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
pack_root=$(CDPATH='' cd -- "$script_root/.." && pwd)
repo_root=$(git -C "$pack_root" rev-parse --show-toplevel)
platform_root=${CINDER_SHIFTER_ROOT:-}
project=${CINDER_GCP_PROJECT:-prod-mgau4w}
zone=${CINDER_GCP_ZONE:-us-central1-a}
account=${CINDER_GCP_ACCOUNT:-bedwards@paloaltonetworks.com}
source_instance=${CINDER_TRAINING_INSTANCE:-cinder-training-golden}
machine_image="cinder-$label-ct511-base"
instance="cinder-$label-ct511"
keep=${CINDER_KEEP_TEST_RANGE:-0}

if [[ -z $platform_root ]] || ! git -C "$platform_root" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "CINDER_SHIFTER_ROOT must name a clean Shifter platform checkout" >&2
  exit 2
fi
[[ -z $(git -C "$platform_root" status --porcelain) ]] || {
  echo "Shifter platform checkout must be clean so only committed source is transferred" >&2
  exit 2
}
[[ -z $(git -C "$repo_root" status --porcelain) ]] || {
  echo "scenario checkout must be clean so the golden run is commit-reproducible" >&2
  exit 2
}

transfer=$(mktemp -d /tmp/cinder-ct511.XXXXXX)
image_created=0
instance_created=0
cleanup() {
  local status=$?
  rm -rf -- "$transfer"
  if [[ $keep != 1 ]]; then
    if [[ $instance_created == 1 ]]; then
      gcloud compute instances delete "$instance" \
        --project "$project" --zone "$zone" --account "$account" --quiet >/dev/null 2>&1 || true
    fi
    if [[ $image_created == 1 ]]; then
      gcloud compute machine-images delete "$machine_image" \
        --project "$project" --account "$account" --quiet >/dev/null 2>&1 || true
    fi
  fi
  exit "$status"
}
trap cleanup EXIT

python3 "$pack_root/challenges/catalog.py" --check >/dev/null
python3 "$script_root/import_catalog.py" \
  --scorer-origin https://cinder-scorer.golden.invalid \
  --output "$transfer/event-content.json" >/dev/null
git -C "$platform_root" archive --format=tar HEAD shifter > "$transfer/platform.tar"
install -m 0600 "$script_root/golden_acceptance.py" "$transfer/golden_acceptance.py"
install -m 0600 "$script_root/CinderDeliveryGolden.test.tsx" "$transfer/CinderDeliveryGolden.test.tsx"
install -m 0700 "$script_root/run-golden-acceptance-remote.sh" "$transfer/run-golden-acceptance-remote.sh"

gcloud compute machine-images create "$machine_image" \
  --project "$project" --account "$account" \
  --source-instance "$source_instance" --source-instance-zone "$zone" \
  --description "Temporary shifter-scenarios issue 268 verification image" >/dev/null
image_created=1
gcloud compute instances create "$instance" \
  --project "$project" --zone "$zone" --account "$account" \
  --source-machine-image "$machine_image" \
  --network-interface=subnet=cinder-training-carrier,no-address \
  --tags=cinder-training-carrier \
  --labels managed-by=shifter-scenarios,purpose=issue-verification,issue=268 >/dev/null
instance_created=1

for attempt in $(seq 1 60); do
  if gcloud compute ssh "$instance" \
    --project "$project" --zone "$zone" --account "$account" --tunnel-through-iap \
    --command 'test -f /var/lib/cinder-training-carrier-ready' >/dev/null 2>&1; then
    break
  fi
  [[ $attempt -lt 60 ]] || { echo "disposable golden copy did not become ready" >&2; exit 1; }
  sleep 5
done

gcloud compute ssh "$instance" \
  --project "$project" --zone "$zone" --account "$account" --tunnel-through-iap \
  --command 'install -d -m 0700 /tmp/cinder-ct511-input' >/dev/null
gcloud compute scp "$transfer/platform.tar" "$transfer/event-content.json" \
  "$transfer/golden_acceptance.py" "$transfer/CinderDeliveryGolden.test.tsx" \
  "$transfer/run-golden-acceptance-remote.sh" \
  "$instance:/tmp/cinder-ct511-input/" \
  --project "$project" --zone "$zone" --account "$account" --tunnel-through-iap >/dev/null

gcloud compute ssh "$instance" \
  --project "$project" --zone "$zone" --account "$account" --tunnel-through-iap \
  --command 'bash /tmp/cinder-ct511-input/run-golden-acceptance-remote.sh'

printf '{"catalog_sha256":"%s","platform_commit":"%s","scenario_commit":"%s"}\n' \
  "$(sha256sum "$pack_root/challenges/challenges.yaml" | cut -d' ' -f1)" \
  "$(git -C "$platform_root" rev-parse HEAD)" \
  "$(git -C "$repo_root" rev-parse HEAD)"
