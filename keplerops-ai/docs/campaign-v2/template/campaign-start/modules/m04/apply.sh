#!/usr/bin/env bash
set -Eeuo pipefail

readonly MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly TEMPLATE_ROOT="$(cd "${MODULE_ROOT}/../../.." && pwd)"
readonly OPERATION="${1:-all}"
readonly QDRANT_WRITE_URL="${QDRANT_WRITE_URL:-http://10.61.50.72:6333}"
readonly QDRANT_WRITE_KEY="${QDRANT_WRITE_KEY:-KeplerV2-Training-Qdrant-Write}"
readonly LABEL_STUDIO_URL="${LABEL_STUDIO_URL:-http://10.61.40.34:8080}"
readonly LABEL_STUDIO_TOKEN="${LABEL_STUDIO_API_TOKEN:-31a5a4b4ab3cdbaf110644eed06853b2b418daf6}"
readonly MINIO_MC_IMAGE="${MINIO_MC_IMAGE:-$(sed -n 's/^MINIO_MC_IMAGE=//p' "${TEMPLATE_ROOT}/engineering/component-lock.additions.env")}"
readonly CINDER_RELAY_URL="${CINDER_RELAY_INTERNAL_URL:-http://192.168.78.30:31080}"
readonly JUPYTER_IMAGE="${JUPYTER_IMAGE:-$(sed -n 's/^JUPYTER_IMAGE=//p' "${TEMPLATE_ROOT}/component-lock.env")}"
readonly K3S_TARGET="${K3S_TARGET:-kepler@192.168.78.30}"
readonly K3S_KEY="${K3S_KEY:-/root/.ssh/keplerops-v2}"

# shellcheck source=../../../seeding/config.env
source "${TEMPLATE_ROOT}/seeding/config.env"

log() { printf '[campaign-m04] %s\n' "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }

compose() {
  docker compose --project-directory "${TEMPLATE_ROOT}" \
    --env-file "${TEMPLATE_ROOT}/component-lock.env" \
    --env-file "${TEMPLATE_ROOT}/engineering/component-lock.additions.env" \
    -f "${TEMPLATE_ROOT}/compose.foundation.yaml" \
    -f "${TEMPLATE_ROOT}/compose.enterprise.yaml" \
    -f "${TEMPLATE_ROOT}/compose.engineering.yaml" \
    -f "${MODULE_ROOT}/compose.overlay.yaml" "$@"
}

known_operation() { jq -e --arg id "$1" 'any(.[]; .id == $id)' "${MODULE_ROOT}/operations.json" >/dev/null; }

deploy_research_service() {
  compose up -d --no-deps support-review-browser orion-research >/dev/null
  docker exec kep-v2-pdns-auth pdnsutil replace-rrset keplerops.lab research A 60 10.61.10.2 >/dev/null
  docker exec kep-v2-pdns-recursor rec_control wipe-cache 'keplerops.lab$' >/dev/null
  {
    cat "${TEMPLATE_ROOT}/config/caddy/Caddyfile"
    cat "${MODULE_ROOT}/runtime/Caddyfile.fragment"
  } | docker exec -i kep-v2-caddy sh -eu -c 'cat >/tmp/Caddyfile.campaign-m04'
  docker exec kep-v2-caddy caddy reload --config /tmp/Caddyfile.campaign-m04 --adapter caddyfile >/dev/null
  for _ in $(seq 1 60); do
    curl -kfsS --resolve research.keplerops.lab:443:10.61.10.2 \
      https://research.keplerops.lab/health/ready >/dev/null 2>&1 && return
    sleep 2
  done
  die 'Orion Evaluation Research did not become ready'
}

seed_enterprise_records() {
  QDRANT_URL="${QDRANT_WRITE_URL}" QDRANT_WRITE_KEY="${QDRANT_WRITE_KEY}" \
  LABEL_STUDIO_URL="${LABEL_STUDIO_URL}" LABEL_STUDIO_API_TOKEN="${LABEL_STUDIO_TOKEN}" \
    python3 "${MODULE_ROOT}/runtime/seed_enterprise.py" "$1"
}

seed_workhub_record() {
  compose exec -T -e M04_OPERATION="$1" \
    -e M04_PAYLOAD="$(base64 -w0 "${MODULE_ROOT}/payloads/$1.json")" \
    redmine bundle exec rails runner /dev/stdin < "${MODULE_ROOT}/runtime/seed_redmine.rb"
}

seed_runtime_attestation() (
  local workspace metadata mlflow_run release runtime pods services model_sha process_digest service_digest object_key token
  workspace="$(mktemp -d)"
  trap 'rm -rf "${workspace}"' EXIT
  metadata="$(curl -fsS http://192.168.78.30:30083/v1/models/orion-release-risk)"
  ssh -i "${K3S_KEY}" -o BatchMode=yes -o StrictHostKeyChecking=accept-new "${K3S_TARGET}" \
    'sudo cat /var/lib/keplerops-platform/current-release/release.json' >"${workspace}/release.json"
  ssh -i "${K3S_KEY}" -o BatchMode=yes "${K3S_TARGET}" \
    'sudo k3s kubectl -n orion-runtime get inferenceservice orion-release-risk -o json' >"${workspace}/runtime.json"
  ssh -i "${K3S_KEY}" -o BatchMode=yes "${K3S_TARGET}" \
    'sudo k3s kubectl -n orion-runtime get pods -l serving.kserve.io/inferenceservice=orion-release-risk -o json' >"${workspace}/pods.json"
  ssh -i "${K3S_KEY}" -o BatchMode=yes "${K3S_TARGET}" \
    'sudo k3s kubectl -n orion-runtime get services -o json' >"${workspace}/services.json"
  printf '%s\n' "${metadata}" >"${workspace}/metadata.json"
  mlflow_run="$(jq -er '.mlflow_run_id' "${workspace}/metadata.json")"
  curl -fsS -u 'svc-orion-training:KeplerV2-Training-MLflow-Service' \
    "http://10.61.40.36:5000/api/2.0/mlflow/runs/get?run_id=${mlflow_run}" >"${workspace}/mlflow-run.json"

  model_sha="$(jq -er '.model_sha256 | select(test("^[0-9a-f]{64}$"))' "${workspace}/metadata.json")"
  jq -e --arg digest "${model_sha}" --slurpfile release "${workspace}/release.json" \
    '.model_sha256 == $digest and .mlflow_run_id == $release[0].model.mlflow_run_id and .lakefs_commit == $release[0].dataset.commit and $release[0].model.onnx_digest == $digest' \
    "${workspace}/metadata.json" >/dev/null || die 'live model metadata does not match the signed release record'
  jq -e --arg digest "${model_sha}" --slurpfile release "${workspace}/release.json" '
    .metadata.annotations["keplerops.lab/model-digest"] == $digest and
    .metadata.annotations["keplerops.lab/release-revision"] == $release[0].runtime.kserve_revision and
    any(.status.conditions[]?; .type == "Ready" and .status == "True")
  ' "${workspace}/runtime.json" >/dev/null || die 'KServe runtime does not match the signed release record'
  process_digest="$(jq -cS '[.items[] | {name:.metadata.name,containers:[.spec.containers[] | {name,image,command,args}],image_ids:[.status.containerStatuses[]?.imageID]}]' "${workspace}/pods.json" | sha256sum | awk '{print $1}')"
  service_digest="$(jq -cS '[.items[] | {name:.metadata.name,clusterIP:.spec.clusterIP,ports:.spec.ports}]' "${workspace}/services.json" | sha256sum | awk '{print $1}')"
  jq -n --arg process "${process_digest}" --arg services "${service_digest}" \
    --arg model "${model_sha}" --slurpfile metadata "${workspace}/metadata.json" \
    --slurpfile release "${workspace}/release.json" --slurpfile runtime "${workspace}/runtime.json" \
    --slurpfile mlflow "${workspace}/mlflow-run.json" '{
      process_digest:$process,
      service_inventory_digest:$services,
      model_digest:$model,
      airflow_run_id:$release[0].training.run_id,
      mlflow_run_id:$metadata[0].mlflow_run_id,
      mlflow_model_version:$metadata[0].mlflow_model_version,
      lakefs_commit:$metadata[0].lakefs_commit,
      minio_model_uri:$mlflow[0].run.info.artifact_uri,
      serving_revision:$runtime[0].metadata.annotations["keplerops.lab/release-revision"],
      serving_image:$runtime[0].spec.predictor.containers[0].image,
      runtime_reference:"FLAG{bd34a72ac3b180db}"
    }' >"${workspace}/attestation.json"
  object_key="runtime-attestations/${model_sha}.json"

  docker run --rm --network kep-v2-data -v "${workspace}/attestation.json:/attestation.json:ro" \
    "${MINIO_MC_IMAGE}" sh -eu -c "
      mc alias set kepler http://minio:9000 kepler-minio KeplerV2-Training-Minio-Object-Store >/dev/null
      mc mb --ignore-existing kepler/artifacts >/dev/null
      cat >/tmp/runtime-reader.json <<'JSON'
      {\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Action\":[\"s3:GetBucketLocation\"],\"Resource\":[\"arn:aws:s3:::artifacts\"]},{\"Effect\":\"Allow\",\"Action\":[\"s3:GetObject\"],\"Resource\":[\"arn:aws:s3:::artifacts/runtime-attestations/*\"]}]}
JSON
      mc admin policy create kepler orion-runtime-attestation-read /tmp/runtime-reader.json >/dev/null
      mc admin user add kepler orion-runtime-reader KeplerV2-Orion-Runtime-Attestation >/dev/null 2>&1 || true
      mc admin policy attach kepler orion-runtime-attestation-read --user orion-runtime-reader >/dev/null
      mc cp /attestation.json 'kepler/artifacts/${object_key}' >/dev/null
      mc anonymous set none kepler/artifacts >/dev/null
    "

  ssh -i "${K3S_KEY}" -o BatchMode=yes "${K3S_TARGET}" 'sudo k3s kubectl apply -f -' <<'YAML' >/dev/null
apiVersion: v1
kind: ServiceAccount
metadata: {name: evaluation-reader, namespace: orion-runtime}
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata: {name: evaluation-reader, namespace: orion-runtime}
rules:
  - apiGroups: [""]
    resources: ["pods", "services", "endpoints"]
    verbs: ["get", "list"]
  - apiGroups: ["serving.kserve.io"]
    resources: ["inferenceservices"]
    verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata: {name: evaluation-reader, namespace: orion-runtime}
subjects:
  - {kind: ServiceAccount, name: evaluation-reader, namespace: orion-runtime}
roleRef: {apiGroup: rbac.authorization.k8s.io, kind: Role, name: evaluation-reader}
YAML
  token="$(ssh -i "${K3S_KEY}" -o BatchMode=yes "${K3S_TARGET}" 'sudo k3s kubectl -n orion-runtime create token evaluation-reader --duration=168h')"
  ssh -i "${K3S_KEY}" -o BatchMode=yes "${K3S_TARGET}" 'sudo cat /var/lib/rancher/k3s/server/tls/server-ca.crt' >"${workspace}/k3s-ca.crt"
  printf '%s\n' "${token}" >"${workspace}/k3s-token"
  cat >"${workspace}/README.md" <<EOF
# Orion Runtime Lineage Review

The live release-risk metadata is available at http://192.168.78.30:30083/v1/models/orion-release-risk.
Use the scoped Kubernetes token and CA in this directory against https://192.168.78.30:6443 for namespace orion-runtime.
The object-store credential can read runtime-attestations/<live-model-sha256>.json from the artifacts bucket but cannot list that bucket.

Object endpoint: http://minio:9000
Access key: orion-runtime-reader
Secret key: KeplerV2-Orion-Runtime-Attestation
EOF
  docker volume create 'kep-v2-jupyter-eval.reader' >/dev/null
  docker run --rm --user root -v 'kep-v2-jupyter-eval.reader:/work' -v "${workspace}:/seed:ro" \
    "${JUPYTER_IMAGE}" sh -eu -c '
      install -d -m 0750 -o 1000 -g 100 /work/orion-runtime-lineage
      install -m 0640 -o 1000 -g 100 /seed/README.md /work/orion-runtime-lineage/README.md
      install -m 0600 -o 1000 -g 100 /seed/k3s-token /work/orion-runtime-lineage/k3s-token
      install -m 0644 -o 1000 -g 100 /seed/k3s-ca.crt /work/orion-runtime-lineage/k3s-ca.crt
    '
)

ensure_support_relay_basket() {
  local state="${TEMPLATE_ROOT}/state/campaign-start/m04/m04-support-render.token" response
  install -d -m 0750 "$(dirname "${state}")"
  if [[ ! -s ${state} ]]; then
    response="$(curl -fsS -X POST -H 'Host: relay.cinder.cinder.lab' \
      -H 'Content-Type: application/json' --data '{"capacity":100}' \
      "${CINDER_RELAY_URL}/api/baskets/m04-support-render")"
    jq -er '.token' <<<"${response}" >"${state}"
    chmod 0600 "${state}"
  fi
  docker exec --user root kep-v2-cinder-jupyter install -d -m 0750 -o jovyan -g users /home/jovyan/work/support-review
  docker cp "${state}" kep-v2-cinder-jupyter:/home/jovyan/work/support-review/access-token
  docker exec --user root kep-v2-cinder-jupyter chown jovyan:users /home/jovyan/work/support-review/access-token
  docker exec --user root kep-v2-cinder-jupyter chmod 0600 /home/jovyan/work/support-review/access-token
}

seed_privacy_notebooks() {
  docker volume create 'kep-v2-jupyter-eval.reader' >/dev/null
  docker run --rm --user root \
    -v 'kep-v2-jupyter-eval.reader:/work' \
    -v "${MODULE_ROOT}/payloads:/seed:ro" \
    "${JUPYTER_IMAGE}" sh -eu -c '
      install -d -m 0750 -o 1000 -g 100 /work/orion-privacy-research
      for notebook in privacy-calibration individual-membership cohort-membership; do
        install -m 0640 -o 1000 -g 100 "/seed/${notebook}.ipynb" "/work/orion-privacy-research/${notebook}.ipynb"
      done
    '
}

seed_protected_support_context() { seed_enterprise_records "$1"; }
seed_protected_routing_section() { seed_enterprise_records "$1"; }
seed_privacy_calibration_project() { seed_enterprise_records "$1"; seed_privacy_notebooks; }
seed_individual_membership_job() { seed_enterprise_records "$1"; seed_privacy_notebooks; }
seed_cohort_membership_job() { seed_enterprise_records "$1"; seed_privacy_notebooks; }
seed_compatibility_matrix() { seed_enterprise_records "$1"; }
seed_runtime_lineage_attestation() { seed_enterprise_records "$1"; seed_runtime_attestation; }
seed_factuality_reference_region() { seed_workhub_record "$1"; seed_enterprise_records "$1"; }
seed_parser_compatibility_issue() { seed_workhub_record "$1"; }
seed_capability_audit() { seed_workhub_record "$1"; }
seed_release_workflow_fixture() { seed_workhub_record "$1"; }
seed_support_render_workflow() { seed_enterprise_records "$1"; ensure_support_relay_basket; }
seed_neighbor_archive() { seed_enterprise_records "$1"; }

apply_one() {
  local id=$1 handler
  known_operation "${id}" || die "unknown operation: ${id}"
  case "${id}" in
    kep-m04-a) handler=seed_protected_support_context ;;
    kep-m04-b) handler=seed_protected_routing_section ;;
    kep-m04-c) handler=seed_privacy_calibration_project ;;
    kep-m04-d) handler=seed_individual_membership_job ;;
    kep-m04-e) handler=seed_cohort_membership_job ;;
    kep-m04-f) handler=seed_compatibility_matrix ;;
    kep-m04-g) handler=seed_runtime_lineage_attestation ;;
    kep-m04-h) handler=seed_factuality_reference_region ;;
    kep-m04-i) handler=seed_parser_compatibility_issue ;;
    kep-m04-j) handler=seed_capability_audit ;;
    kep-m04-k) handler=seed_release_workflow_fixture ;;
    kep-m04-l) handler=seed_support_render_workflow ;;
    kep-m04-m) handler=seed_neighbor_archive ;;
    *) die "missing apply dispatch: ${id}" ;;
  esac
  declare -F "${handler}" >/dev/null || die "missing handler: ${handler}"
  "${handler}" "${id}"
  log "reconciled ${id} into native enterprise services"
}

main() {
  local command id
  for command in base64 curl docker jq python3; do command -v "${command}" >/dev/null || die "missing command: ${command}"; done
  deploy_research_service
  if [[ ${OPERATION} != all ]]; then apply_one "${OPERATION}"; return; fi
  while IFS= read -r id; do apply_one "${id}"; done < <(jq -r '.[].id' "${MODULE_ROOT}/operations.json")
}

main "$@"
