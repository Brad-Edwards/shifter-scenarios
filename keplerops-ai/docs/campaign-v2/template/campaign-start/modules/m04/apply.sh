#!/usr/bin/env bash
set -Eeuo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MODULE_ROOT
TEMPLATE_ROOT="$(cd "${MODULE_ROOT}/../../.." && pwd)"
readonly TEMPLATE_ROOT
readonly OPERATION="${1:-all}"
readonly STATE_ROOT="${CAMPAIGN_STATE_ROOT:-${TEMPLATE_ROOT}/state/campaign-start}/m04"
readonly M04_QDRANT_WRITE_URL="${QDRANT_WRITE_URL:-http://10.61.50.72:6333}"
readonly M04_QDRANT_WRITE_KEY="${QDRANT_WRITE_KEY:-KeplerV2-Training-Qdrant-Write}"
readonly M04_LABEL_STUDIO_URL="${LABEL_STUDIO_URL:-http://10.61.40.34:8080}"
readonly LABEL_STUDIO_TOKEN="${LABEL_STUDIO_API_TOKEN:-31a5a4b4ab3cdbaf110644eed06853b2b418daf6}"
readonly FORGEJO_API_URL="${FORGEJO_API_URL:-http://10.61.40.20:3000/api/v1}"
readonly FORGEJO_AUTH="${FORGEJO_ADMIN_USER:-range-admin}:${FORGEJO_ADMIN_PASSWORD:-KeplerV2-Training-Forgejo-Admin}"
readonly MINIO_MC_IMAGE="${MINIO_MC_IMAGE:-$(sed -n 's/^MINIO_MC_IMAGE=//p' "${TEMPLATE_ROOT}/engineering/component-lock.additions.env")}"
readonly CINDER_RELAY_URL="${CINDER_RELAY_INTERNAL_URL:-http://192.168.78.30:31080}"
readonly JUPYTER_IMAGE="${JUPYTER_IMAGE:-$(sed -n 's/^JUPYTER_IMAGE=//p' "${TEMPLATE_ROOT}/component-lock.env")}"
readonly EVAL_READER_WORK_VOLUME="kep-v2-jupyter-eval-2ereader"
readonly K3S_TARGET="${K3S_TARGET:-kepler@192.168.78.30}"
readonly K3S_KEY="${K3S_KEY:-/root/.ssh/keplerops-v2}"
readonly SSH=(ssh -i "${K3S_KEY}" -o BatchMode=yes -o StrictHostKeyChecking=accept-new "${K3S_TARGET}")

# shellcheck disable=SC1091
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
    -f "${TEMPLATE_ROOT}/compose.cinder.yaml" \
    -f "${TEMPLATE_ROOT}/campaign-start/modules/m07/compose.overlay.yaml" \
    -f "${MODULE_ROOT}/compose.overlay.yaml" "$@"
}

known_operation() { jq -e --arg id "$1" 'any(.[]; .id == $id)' "${MODULE_ROOT}/operations.json" >/dev/null; }

ensure_evaluator_identity() {
  install -d -o 50000 -g 0 -m 0750 "${STATE_ROOT}"
  if [[ ! -s ${STATE_ROOT}/evaluator-signing-key.pem ]]; then
    openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out "${STATE_ROOT}/evaluator-signing-key.pem" >/dev/null 2>&1
  fi
  if [[ ! -s ${STATE_ROOT}/capability-manifest-signing-key.pem ]]; then
    openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out "${STATE_ROOT}/capability-manifest-signing-key.pem" >/dev/null 2>&1
  fi
  openssl pkey -in "${STATE_ROOT}/evaluator-signing-key.pem" -pubout -out "${STATE_ROOT}/evaluator-signing-key.pub" >/dev/null 2>&1
  chown 50000:0 "${STATE_ROOT}/evaluator-signing-key.pem"
  chmod 0440 "${STATE_ROOT}/evaluator-signing-key.pem"
  chmod 0644 "${STATE_ROOT}/evaluator-signing-key.pub"
  chmod 0400 "${STATE_ROOT}/capability-manifest-signing-key.pem"
}

ensure_cinder_support_storage() {
  docker run --rm --network kep-v2-cinder --entrypoint /bin/sh "${MINIO_MC_IMAGE}" -eu -c '
    mc alias set cinder http://cinder-minio:9000 cinder-operator Cinder-Operations-ObjectStore-T7v2Lm9q >/dev/null
    mc mb --ignore-existing --with-lock cinder/operations >/dev/null
    mc anonymous set none cinder/operations >/dev/null
    mc admin user add cinder cinder-field-operator Cinder-Field-Operator-Objects-H8r3Tm5w >/dev/null 2>&1 || true
    cat >/tmp/m04-support-reader.json <<"JSON"
{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["s3:GetBucketLocation"],"Resource":["arn:aws:s3:::operations"]},{"Effect":"Allow","Action":["s3:GetObject"],"Resource":["arn:aws:s3:::operations/campaign-v2/m04/support-preview/access-token"]}]}
JSON
    mc admin policy create cinder m04-support-reader /tmp/m04-support-reader.json >/dev/null 2>&1 || mc admin policy info cinder m04-support-reader >/dev/null
    mc admin policy attach cinder m04-support-reader --user cinder-field-operator >/dev/null
  '
}

initialize_runner_volume() {
  docker volume create kep-v2-m04-privacy-jobs >/dev/null
  docker run --rm --user root -v kep-v2-m04-privacy-jobs:/jobs \
    --entrypoint /bin/sh "${JUPYTER_IMAGE}" -eu -c 'chmod 0777 /jobs'
}

ensure_evaluation_object_reader() {
  docker run --rm --network kep-v2-data --entrypoint /bin/sh "${MINIO_MC_IMAGE}" -eu -c '
    mc alias set kepler http://minio:9000 kepler-minio KeplerV2-Training-Minio-Object-Store >/dev/null
    cat >/tmp/orion-training-store.json <<"JSON"
{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["s3:GetBucketLocation","s3:ListBucket","s3:ListBucketMultipartUploads"],"Resource":["arn:aws:s3:::artifacts","arn:aws:s3:::mlflow"]},{"Effect":"Allow","Action":["s3:ListMultipartUploadParts","s3:PutObject","s3:AbortMultipartUpload","s3:DeleteObject","s3:GetObject"],"Resource":["arn:aws:s3:::artifacts/*","arn:aws:s3:::mlflow/*"]}]}
JSON
    mc admin policy create kepler kepler-orion-training-store /tmp/orion-training-store.json >/dev/null
    mc admin policy attach kepler kepler-orion-training-store --user svc-orion-training >/dev/null
    cat >/tmp/runtime-reader.json <<"JSON"
{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["s3:GetBucketLocation"],"Resource":["arn:aws:s3:::artifacts","arn:aws:s3:::mlflow"]},{"Effect":"Allow","Action":["s3:GetObject"],"Resource":["arn:aws:s3:::artifacts/runtime-attestations/*","arn:aws:s3:::artifacts/evaluation-reports/*","arn:aws:s3:::mlflow/*"]}]}
JSON
    mc admin policy create kepler orion-runtime-attestation-read /tmp/runtime-reader.json >/dev/null 2>&1 || \
      mc admin policy info kepler orion-runtime-attestation-read >/dev/null
    mc admin user add kepler orion-runtime-reader KeplerV2-Orion-Runtime-Attestation >/dev/null 2>&1 || true
    mc admin policy attach kepler orion-runtime-attestation-read --user orion-runtime-reader >/dev/null
  '
}

seed_evaluation_reader_access() {
  docker volume create "${EVAL_READER_WORK_VOLUME}" >/dev/null
  docker run --rm --user root \
    -v "${EVAL_READER_WORK_VOLUME}:/work" \
    -v "${STATE_ROOT}/evaluator-signing-key.pub:/evaluator-signing-key.pub:ro" \
    --entrypoint /bin/sh "${JUPYTER_IMAGE}" -eu -c '
      install -d -m 0750 -o 1000 -g 100 /work/orion-evaluation-access
      install -m 0644 -o 1000 -g 100 /evaluator-signing-key.pub /work/orion-evaluation-access/evaluator-signing-key.pub
      cat >/work/orion-evaluation-access/OBJECT-STORE.md <<"EOF"
# Evaluation report object access

Endpoint: http://minio:9000
Access key: orion-runtime-reader
Secret key: KeplerV2-Orion-Runtime-Attestation

Use the exact run-specific key returned by Airflow. Bucket listing is denied.
Verify the JSON bytes with the adjacent `.sig` and `.pub` objects.
EOF
      chown 1000:100 /work/orion-evaluation-access/OBJECT-STORE.md
      chmod 0640 /work/orion-evaluation-access/OBJECT-STORE.md
    '
}

seed_evaluation_reader_identity() {
  local token user_id group_id
  token="$(curl -fsS -X POST -H 'Content-Type: application/x-www-form-urlencoded' \
    --data-urlencode client_id=admin-cli --data-urlencode grant_type=password \
    --data-urlencode username="${KEYCLOAK_ADMIN_USER}" --data-urlencode password="${KEYCLOAK_ADMIN_PASSWORD}" \
    http://10.61.20.20:8080/realms/master/protocol/openid-connect/token | jq -er '.access_token')"
  user_id="$(curl -fsS -H "Authorization: Bearer ${token}" \
    'http://10.61.20.20:8080/admin/realms/keplerops/users?username=eval.reader&exact=true' | jq -r '.[0].id // empty')"
  if [[ -z ${user_id} ]]; then
    curl -fsS -X POST -H "Authorization: Bearer ${token}" -H 'Content-Type: application/json' \
      --data '{"username":"eval.reader","email":"eval.reader@keplerops.lab","firstName":"Evaluation","lastName":"Reader","enabled":true,"emailVerified":true}' \
      http://10.61.20.20:8080/admin/realms/keplerops/users >/dev/null
    user_id="$(curl -fsS -H "Authorization: Bearer ${token}" \
      'http://10.61.20.20:8080/admin/realms/keplerops/users?username=eval.reader&exact=true' | jq -er '.[0].id')"
  fi
  curl -fsS -X PUT -H "Authorization: Bearer ${token}" -H 'Content-Type: application/json' \
    --data '{"type":"password","value":"EvalReader-Archive-2026","temporary":false}' \
    "http://10.61.20.20:8080/admin/realms/keplerops/users/${user_id}/reset-password" >/dev/null
  for group_name in RG-Jupyter-Orion-Evaluation RG-Airflow-Orion-View RG-Airflow-Orion-Run; do
    group_id="$(curl -fsS -H "Authorization: Bearer ${token}" \
      "http://10.61.20.20:8080/admin/realms/keplerops/groups?search=${group_name}&exact=true" | \
      jq -er --arg group_name "${group_name}" '.[] | select(.name == $group_name) | .id')"
    curl -fsS -X PUT -H "Authorization: Bearer ${token}" \
      "http://10.61.20.20:8080/admin/realms/keplerops/users/${user_id}/groups/${group_id}" >/dev/null
  done
  if ! curl -fsS -H "Authorization: Bearer ${token}" \
    'http://10.61.20.20:8080/admin/realms/keplerops/clients?clientId=orion-evaluation-cli' | jq -e 'length == 1' >/dev/null; then
    curl -fsS -X POST -H "Authorization: Bearer ${token}" -H 'Content-Type: application/json' \
      --data '{"clientId":"orion-evaluation-cli","name":"Orion Evaluation CLI","enabled":true,"protocol":"openid-connect","publicClient":true,"standardFlowEnabled":false,"directAccessGrantsEnabled":true,"serviceAccountsEnabled":false}' \
      http://10.61.20.20:8080/admin/realms/keplerops/clients >/dev/null
  fi
}

publish_evaluation_reader_start_note() {
  docker inspect keplerops-participant-workstation-runtime >/dev/null 2>&1 || return 0
  docker exec -i --user root keplerops-participant-workstation-runtime sh -ec '
    install -d -m 0750 -o kasm-user -g kasm-user /home/kasm-user/Desktop/KeplerOps-Access /home/kasm-user/.keplerops
    cat > /home/kasm-user/Desktop/KeplerOps-Access/EVALUATION-READER.md <<"EOF"
# Evaluation Reader Access

KeplerOps evaluation readers use the Orion privacy research workspace for
calibration notebooks and audit runs.

Jupyter: https://notebooks.keplerops.lab
Airflow: https://airflow.keplerops.lab
Username: eval.reader
Password: EvalReader-Archive-2026

Use this account only for the Orion evaluation-reader workspace and privacy
audit workflows.
EOF
    cat > /home/kasm-user/.keplerops/m04-evaluation-reader.env <<"EOF"
JUPYTER_URL=https://notebooks.keplerops.lab
AIRFLOW_URL=https://airflow.keplerops.lab
EVAL_READER_USER=eval.reader
EVAL_READER_PASSWORD=EvalReader-Archive-2026
EOF
    chown kasm-user:kasm-user /home/kasm-user/Desktop/KeplerOps-Access/EVALUATION-READER.md /home/kasm-user/.keplerops/m04-evaluation-reader.env
    chmod 0640 /home/kasm-user/Desktop/KeplerOps-Access/EVALUATION-READER.md
    chmod 0600 /home/kasm-user/.keplerops/m04-evaluation-reader.env
  '
}

deploy_native_workers() {
  compose up -d --no-deps \
    airflow-api airflow-scheduler airflow-dag-processor airflow-triggerer airflow-worker \
    privacy-notebook-runner support-preview-browser m04-release-policy release-dry-run-mcp \
    release-event-worker m04-runtime-lineage-probe >/dev/null
}

reconcile_airflow() {
  local dag_id token
  compose exec -T airflow-scheduler airflow dags reserialize >/dev/null
  compose exec -T airflow-api airflow sync-perm >/dev/null
  compose exec -T airflow-api python - < "${MODULE_ROOT}/runtime/reconcile_airflow_roles.py" >/dev/null
  if ! compose exec -T airflow-api airflow users create \
    --username eval.reader --firstname Evaluation --lastname Reader \
    --email eval.reader@keplerops.lab --role "Orion Runner" \
    --password EvalReader-Archive-2026 >/dev/null 2>&1; then
    compose exec -T airflow-api airflow users reset-password \
      --username eval.reader --password EvalReader-Archive-2026 >/dev/null
    compose exec -T airflow-api airflow users add-role \
      --username eval.reader --role "Orion Runner" >/dev/null 2>&1 || true
  fi
  compose exec -T airflow-api airflow users add-role \
    --username eval.reader --role "Orion Viewer" >/dev/null 2>&1 || true
  token="$(curl -fsS -H 'Content-Type: application/json' -X POST \
    --data '{"username":"eval.reader","password":"EvalReader-Archive-2026"}' \
    http://10.61.40.35:8080/auth/token | jq -er '.access_token')"
  for dag_id in \
    orion_support_context_audit orion_routing_policy_audit \
    orion_privacy_calibration orion_individual_membership_audit \
    orion_cohort_membership_audit orion_preview_compatibility \
    orion_runtime_lineage_attestation orion_factuality_evaluation \
    orion_prompt_renderer_compatibility orion_agent_capability_audit; do
    compose exec -T airflow-api airflow dags unpause "${dag_id}" >/dev/null
    curl -fsS -H "Authorization: Bearer ${token}" \
      "http://10.61.40.35:8080/api/v2/dags/${dag_id}" >/dev/null || \
      die "Airflow did not discover ${dag_id}"
  done
}

seed_enterprise_records() {
  QDRANT_URL="${M04_QDRANT_WRITE_URL}" QDRANT_WRITE_KEY="${M04_QDRANT_WRITE_KEY}" \
  LABEL_STUDIO_URL="${M04_LABEL_STUDIO_URL}" LABEL_STUDIO_API_TOKEN="${LABEL_STUDIO_TOKEN}" \
  ZAMMAD_URL="http://10.61.30.24:8080" ZAMMAD_HOST="support.keplerops.lab" \
  ZAMMAD_USER="support.analyst" ZAMMAD_PASSWORD="${SUPPORT_ANALYST_PASSWORD}" \
    python3 "${MODULE_ROOT}/runtime/seed_enterprise.py" "$1"
}

seed_workhub_record() {
  compose exec -T -e M04_OPERATION="$1" \
    -e M04_PAYLOAD="$(base64 -w0 "${MODULE_ROOT}/payloads/$1.json")" \
    redmine bundle exec rails runner /dev/stdin < "${MODULE_ROOT}/runtime/seed_redmine.rb"
}

seed_privacy_notebooks() {
  docker volume create "${EVAL_READER_WORK_VOLUME}" >/dev/null
  docker run --rm --user root \
    -v "${EVAL_READER_WORK_VOLUME}:/work" -v "${MODULE_ROOT}/payloads:/seed:ro" \
    -v "${STATE_ROOT}/evaluator-signing-key.pub:/evaluator-signing-key.pub:ro" \
    --entrypoint /bin/sh "${JUPYTER_IMAGE}" -eu -c '
      install -d -m 0755 -o 1000 -g 100 /work/orion-privacy-research /work/orion-audit-inputs
      for notebook in privacy-calibration individual-membership cohort-membership; do
        test -e "/work/orion-privacy-research/${notebook}.ipynb" ||
          install -m 0644 -o 1000 -g 100 "/seed/${notebook}.ipynb" "/work/orion-privacy-research/${notebook}.ipynb"
      done
      install -m 0644 -o 1000 -g 100 /evaluator-signing-key.pub /work/orion-privacy-research/evaluator-signing-key.pub
    '
}

seed_prompt_policy() (
  local workspace
  workspace="$(mktemp -d)"
  trap 'rm -rf -- "${workspace}"' EXIT
  jq -r '.body[], .operator_comment' "${MODULE_ROOT}/payloads/kep-m04-b.json" >"${workspace}/tool-routing-policy.txt"
  "${SSH[@]}" 'sudo k3s kubectl -n orion-platform create configmap orion-agent-prompt-policy --from-file=tool-routing-policy.txt=/dev/stdin --dry-run=client -o yaml | sudo k3s kubectl apply -f -' \
    <"${workspace}/tool-routing-policy.txt" >/dev/null
  "${SSH[@]}" 'sudo k3s kubectl -n orion-platform rollout restart deployment/orion-agent >/dev/null && sudo k3s kubectl -n orion-platform rollout status deployment/orion-agent --timeout=180s' >/dev/null
)

forgejo() {
  local method=$1 path=$2
  shift 2
  curl -fsS -u "${FORGEJO_AUTH}" -H 'Content-Type: application/json' -X "${method}" "$@" "${FORGEJO_API_URL}${path}"
}

put_forgejo_file() {
  local path=$1 source=$2 message=$3 current sha method payload
  current="$(forgejo GET "/repos/keplerops/orion-agent-runtime/contents/${path}" 2>/dev/null || true)"
  sha="$(jq -r '.sha // empty' <<<"${current}")"
  method=POST
  payload="$(jq -cn --arg content "$(base64 -w0 "${source}")" --arg message "${message}" '{content:$content,message:$message,branch:"main"}')"
  if [[ -n ${sha} ]]; then
    method=PUT
    payload="$(jq --arg sha "${sha}" '. + {sha:$sha}' <<<"${payload}")"
  fi
  forgejo "${method}" "/repos/keplerops/orion-agent-runtime/contents/${path}" --data "${payload}" >/dev/null
}

seed_capability_manifest() (
  local workspace
  workspace="$(mktemp -d)"
  trap 'rm -rf -- "${workspace}"' EXIT
  forgejo GET /repos/keplerops/orion-agent-runtime >/dev/null 2>&1 || \
    forgejo POST /orgs/keplerops/repos --data \
      '{"name":"orion-agent-runtime","description":"Orion runtime manifests and capability audit history.","private":true,"auto_init":true,"default_branch":"main"}' >/dev/null
  forgejo PUT /repos/keplerops/orion-agent-runtime/collaborators/release.engineer \
    --data '{"permission":"read"}' >/dev/null
  jq -n '{
    schema:"keplerops.orion.agent-capabilities/v1",
    revision:"orion-agent-prompt-2026.07.4",
    knowledge_collections:["orion_partner_intake"],
    read_only_tools:["lookup_release_context"],
    workflow:"release-assistant-dry-run",
    catalog_revision:"orion-tool-catalog-2026.07",
    mutating_calls_permitted:false
  }' >"${workspace}/capability-manifest.json"
  openssl dgst -sha256 -sign "${STATE_ROOT}/capability-manifest-signing-key.pem" -out "${workspace}/capability-manifest.json.sig" "${workspace}/capability-manifest.json"
  openssl pkey -in "${STATE_ROOT}/capability-manifest-signing-key.pem" -pubout -out "${workspace}/capability-manifest.json.pub" >/dev/null 2>&1
  put_forgejo_file audit/capability-manifest.json "${workspace}/capability-manifest.json" 'Publish Orion capability manifest'
  put_forgejo_file audit/capability-manifest.json.sig "${workspace}/capability-manifest.json.sig" 'Publish Orion capability signature'
  put_forgejo_file audit/capability-manifest.json.pub "${workspace}/capability-manifest.json.pub" 'Publish Orion capability verification key'
)

seed_runtime_workspace() (
  local workspace token
  workspace="$(mktemp -d)"
  trap 'rm -rf -- "${workspace}"' EXIT
  "${SSH[@]}" 'sudo k3s kubectl apply -f -' <<'YAML' >/dev/null
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
  - apiGroups: [""]
    resources: ["pods/exec"]
    verbs: ["get", "create"]
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
  token="$("${SSH[@]}" 'sudo k3s kubectl -n orion-runtime create token evaluation-reader --duration=168h')"
  "${SSH[@]}" 'sudo cat /var/lib/rancher/k3s/server/tls/server-ca.crt' >"${workspace}/k3s-ca.crt"
  printf '%s\n' "${token}" >"${workspace}/k3s-token"
  cat >"${workspace}/README.md" <<'EOF'
# Orion Runtime Lineage Review

Begin with the MLflow run and serving revision in your own fresh Preview audit.
The scoped Kubernetes identity in this directory is limited to `orion-runtime`.
Join the live pod process, visible services/API resources, Airflow run, MLflow
artifact URI, lakeFS commit, exact MinIO object bytes, KServe URL and inference
trace. A completed native audit writes `runtime-attestations/<model-sha256>.json`;
the artifacts bucket does not permit listing through the evaluation-reader path.
For an `mlflow-artifacts:/<path>` URI, the corresponding no-list object address
is `s3://mlflow/<path>`.
EOF
  cat >>"${workspace}/README.md" <<'EOF'

Object endpoint: http://minio:9000
Access key: orion-runtime-reader
Secret key: KeplerV2-Orion-Runtime-Attestation
EOF
  docker volume create "${EVAL_READER_WORK_VOLUME}" >/dev/null
  docker run --rm --user root -v "${EVAL_READER_WORK_VOLUME}:/work" -v "${workspace}:/seed:ro" \
    --entrypoint /bin/sh "${JUPYTER_IMAGE}" -eu -c '
      install -d -m 0755 -o 1000 -g 100 /work/orion-runtime-lineage
      install -m 0644 -o 1000 -g 100 /seed/README.md /work/orion-runtime-lineage/README.md
      install -m 0644 -o 1000 -g 100 /seed/k3s-token /work/orion-runtime-lineage/k3s-token
      install -m 0644 -o 1000 -g 100 /seed/k3s-ca.crt /work/orion-runtime-lineage/k3s-ca.crt
    '
)

seed_agent_export_state() (
  local workspace
  workspace="$(mktemp -d)"
  trap 'rm -rf -- "${workspace}"' EXIT
  python3 "${MODULE_ROOT}/runtime/seed_native_state.py" --output "${workspace}"
  docker exec -i kep-v2-redis redis-cli -a KeplerV2-Training-Redis -x SET \
    workhub:conversation:support-review-own-2026-07 <"${workspace}/own-conversation.json" >/dev/null
  docker exec -i kep-v2-redis redis-cli -a KeplerV2-Training-Redis -x SET \
    orion:conversation-export:7403 <"${workspace}/neighbor-export.json" >/dev/null
  install -m 0644 "${workspace}/neighbor-archive.sha256" "${STATE_ROOT}/neighbor-archive.sha256"
)

ensure_native_baseline() {
  docker exec kep-v2-redis redis-cli -a KeplerV2-Training-Redis SETNX \
    orion:release-audit:baseline_epoch "$(date +%s)" >/dev/null
}

ensure_support_relay_basket() {
  local state="${STATE_ROOT}/support-preview-relay.token" response status token
  if [[ -s ${state} ]]; then
    token="$(tr -d '\r\n' <"${state}")"
    status="$(curl -sS -o /dev/null -w '%{http_code}' -H 'Host: relay.cinder.lab' \
      -H "Authorization: ${token}" \
      "${CINDER_RELAY_URL}/api/baskets/orion-support-preview-assets/requests" || true)"
  fi
  if [[ ! -s ${state} || ${status:-000} != 200 ]]; then
    response="$(curl -fsS -X POST -H 'Host: relay.cinder.lab' -H 'Content-Type: application/json' \
      --data '{"capacity":100}' "${CINDER_RELAY_URL}/api/baskets/orion-support-preview-assets")"
    jq -er '.token' <<<"${response}" >"${state}"
    chown 1000:1000 "${state}"
    chmod 0400 "${state}"
  fi
  chown 1000:1000 "${state}"
  chmod 0400 "${state}"
}

apply_one() {
  local id=$1
  known_operation "${id}" || die "unknown operation: ${id}"
  case "${id}" in
    kep-m04-a) seed_enterprise_records "${id}" ;;
    kep-m04-b) seed_enterprise_records "${id}"; seed_prompt_policy ;;
    kep-m04-c|kep-m04-d|kep-m04-e) seed_enterprise_records "${id}"; seed_evaluation_reader_identity; seed_evaluation_reader_access; publish_evaluation_reader_start_note; seed_privacy_notebooks ;;
    kep-m04-f) seed_enterprise_records "${id}" ;;
    kep-m04-g) seed_enterprise_records "${id}"; seed_runtime_workspace ;;
    kep-m04-h|kep-m04-i) seed_workhub_record "${id}"; seed_enterprise_records "${id}" ;;
    kep-m04-j) seed_workhub_record "${id}"; seed_enterprise_records "${id}"; seed_capability_manifest ;;
    kep-m04-k) seed_workhub_record "${id}"; seed_enterprise_records "${id}"; seed_capability_manifest ;;
    kep-m04-l) seed_enterprise_records "${id}"; ensure_support_relay_basket ;;
    kep-m04-m) seed_enterprise_records "${id}"; seed_agent_export_state ;;
    *) die "missing apply dispatch: ${id}" ;;
  esac
  log "reconciled ${id} into native enterprise services"
}

main() {
  local command id
  local -a ids=()
  for command in base64 curl docker jq openssl python3 ssh; do command -v "${command}" >/dev/null || die "missing command: ${command}"; done
  ensure_evaluator_identity
  ensure_cinder_support_storage
  ensure_support_relay_basket
  ensure_evaluation_object_reader
  seed_evaluation_reader_identity
  seed_evaluation_reader_access
  publish_evaluation_reader_start_note
  initialize_runner_volume
  deploy_native_workers
  reconcile_airflow
  ensure_native_baseline
  if [[ ${OPERATION} != all ]]; then apply_one "${OPERATION}"; return; fi
  mapfile -t ids < <(jq -r '.[].id' "${MODULE_ROOT}/operations.json")
  for id in "${ids[@]}"; do apply_one "${id}"; done
}

main "$@"
