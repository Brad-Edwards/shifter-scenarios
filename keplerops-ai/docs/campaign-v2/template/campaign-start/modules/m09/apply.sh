#!/usr/bin/env bash
set -Eeuo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MODULE_ROOT
TEMPLATE_ROOT="$(cd "${MODULE_ROOT}/../../.." && pwd)"
readonly TEMPLATE_ROOT
readonly OPERATION="${1:-all}"
readonly STATE_ROOT="${CAMPAIGN_STATE_ROOT:-${TEMPLATE_ROOT}/state/campaign-start}/m09"
readonly FORGEJO_API_URL="${FORGEJO_API_URL:-http://10.61.40.20:3000/api/v1}"
readonly FORGEJO_ADMIN_AUTH="${FORGEJO_ADMIN_AUTH:-range-admin:KeplerV2-Training-Forgejo-Admin}"
readonly CINDER_FORGEJO_API_URL="${CINDER_FORGEJO_API_URL:-http://10.61.90.30:3000/api/v1}"
readonly HARBOR_API_URL="${HARBOR_API_URL:-http://10.61.40.32:8080/api/v2.0}"
readonly MLFLOW_URL="${MLFLOW_URL:-http://10.61.40.36:5000}"
readonly MLFLOW_ADMIN_AUTH="${MLFLOW_ADMIN_AUTH:-range-admin:KeplerV2-Training-MLflow-Admin}"
readonly RABBIT_API="${RABBITMQ_MANAGEMENT_URL:-http://10.61.50.12:15672/api}"
readonly RELAY_URL="${CINDER_RELAY_INTERNAL_URL:-https://relay.cinder.lab}"
readonly K3S01_SSH_TARGET="${K3S01_SSH_TARGET:-kepler@192.168.78.30}"
readonly K3S01_SSH_KEY="${K3S01_SSH_KEY:-/root/.ssh/keplerops-v2}"
readonly SSH=(ssh -i "${K3S01_SSH_KEY}" -o BatchMode=yes -o StrictHostKeyChecking=accept-new)
readonly M09_PARTICIPANT_USER="${M09_PARTICIPANT_USER:-svc-orion-release-runner}"
readonly M09_PARTICIPANT_PASSWORD="${M09_PARTICIPANT_PASSWORD:-KeplerV2-M09-Release-Runner-2026}"
readonly M09_PARTICIPANT_EMAIL="${M09_PARTICIPANT_EMAIL:-svc-orion-release-runner@keplerops.lab}"
readonly -a M09_DAG_IDS=(
  orion_visible_release_evaluation
  orion_candidate_registration
  orion_lineage_resolution
  orion_candidate_approval
  orion_image_compatibility_decision
  orion_release_signing
  orion_production_canary_promotion
  orion_upstream_release_intake
  orion_import_exception_review
  orion_upstream_mirror_sync
  orion_mirror_review
  orion_staging_reconciliation
)

log() { printf '[campaign-m09] %s\n' "$*" >&2; }
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
    -f "${TEMPLATE_ROOT}/campaign-start/modules/m08/compose.overlay.yaml" \
    -f "${MODULE_ROOT}/compose.overlay.yaml" "$@"
}

forgejo() {
  local base=$1 auth=$2 method=$3 path=$4
  shift 4
  curl -fsS --user "${auth}" -H 'Content-Type: application/json' -X "${method}" "$@" "${base}${path}"
}

ensure_repo() {
  local base=$1 auth=$2 owner=$3 repo=$4 description=$5 private=$6
  if ! forgejo "${base}" "${auth}" GET "/repos/${owner}/${repo}" >/dev/null 2>&1; then
    if [[ ${owner} == cinder-operator ]]; then
      forgejo "${base}" "${auth}" POST /user/repos --data \
        "$(jq -cn --arg name "${repo}" --arg description "${description}" --argjson private "${private}" \
        '{name:$name,description:$description,private:$private,auto_init:true,default_branch:"main"}')" >/dev/null
    else
      forgejo "${base}" "${auth}" POST "/orgs/${owner}/repos" --data \
        "$(jq -cn --arg name "${repo}" --arg description "${description}" --argjson private "${private}" \
        '{name:$name,description:$description,private:$private,auto_init:true,default_branch:"main"}')" >/dev/null
    fi
  fi
}

ensure_forgejo_user() {
  local username=$1 password=$2 email=$3
  if ! forgejo "${FORGEJO_API_URL}" "${FORGEJO_ADMIN_AUTH}" GET "/users/${username}" >/dev/null 2>&1; then
    forgejo "${FORGEJO_API_URL}" "${FORGEJO_ADMIN_AUTH}" POST /admin/users --data \
      "$(jq -cn --arg username "${username}" --arg password "${password}" --arg email "${email}" \
      '{username:$username,password:$password,email:$email,must_change_password:false,restricted:false,visibility:"private"}')" >/dev/null
  else
    forgejo "${FORGEJO_API_URL}" "${FORGEJO_ADMIN_AUTH}" PATCH "/admin/users/${username}" --data \
      "$(jq -cn --arg password "${password}" '{password:$password,must_change_password:false,active:true}')" >/dev/null
  fi
}

grant_repo() {
  local owner=$1 repo=$2 username=$3 permission=${4:-read}
  forgejo "${FORGEJO_API_URL}" "${FORGEJO_ADMIN_AUTH}" PUT "/repos/${owner}/${repo}/collaborators/${username}" \
    --data "$(jq -cn --arg permission "${permission}" '{permission:$permission}')" >/dev/null
}

grant_cinder_repo() {
  local owner=$1 repo=$2 username=$3 permission=${4:-read}
  forgejo "${CINDER_FORGEJO_API_URL}" 'cinder-operator:Cinder-Operations-Git-K3m7Pq4x' \
    PUT "/repos/${owner}/${repo}/collaborators/${username}" \
    --data "$(jq -cn --arg permission "${permission}" '{permission:$permission}')" >/dev/null
}

put_file() {
  local base=$1 auth=$2 owner=$3 repo=$4 path=$5 source=$6 message=$7 existing sha method payload
  existing="$(forgejo "${base}" "${auth}" GET "/repos/${owner}/${repo}/contents/${path}" 2>/dev/null || true)"
  sha="$(jq -r '.sha // empty' <<<"${existing}")"
  method=POST
  payload="$(jq -cn --arg content "$(base64 -w0 "${source}")" --arg message "${message}" \
    '{content:$content,message:$message,branch:"main"}')"
  if [[ -n ${sha} ]]; then
    method=PUT
    payload="$(jq --arg sha "${sha}" '. + {sha:$sha}' <<<"${payload}")"
  fi
  forgejo "${base}" "${auth}" "${method}" "/repos/${owner}/${repo}/contents/${path}" --data "${payload}" >/dev/null
}

seed_file() {
  local base=$1 auth=$2 owner=$3 repo=$4 path=$5 source=$6 message=$7
  if forgejo "${base}" "${auth}" GET "/repos/${owner}/${repo}/contents/${path}" >/dev/null 2>&1; then
    return
  fi
  put_file "$@"
}

ensure_issue_label() {
  local repo=$1 name=$2 color=$3 description=$4 labels
  labels="$(forgejo "${FORGEJO_API_URL}" "${FORGEJO_ADMIN_AUTH}" GET "/repos/keplerops/${repo}/labels")"
  jq -e --arg name "${name}" 'any(.[]; .name == $name)' <<<"${labels}" >/dev/null && return
  forgejo "${FORGEJO_API_URL}" "${FORGEJO_ADMIN_AUTH}" POST "/repos/keplerops/${repo}/labels" --data \
    "$(jq -cn --arg name "${name}" --arg color "${color}" --arg description "${description}" \
    '{name:$name,color:$color,description:$description}')" >/dev/null
}

mlflow_admin() {
  local method=$1 path=$2
  shift 2
  curl -fsS --user "${MLFLOW_ADMIN_AUTH}" -H 'Content-Type: application/json' -X "${method}" "$@" "${MLFLOW_URL}${path}"
}

ensure_mlflow_user() {
  local username=$1 password=$2 encoded payload
  encoded="$(jq -rn --arg value "${username}" '$value|@uri')"
  payload="$(jq -cn --arg username "${username}" --arg password "${password}" \
    '{username:$username,password:$password}')"
  if mlflow_admin GET "/api/2.0/mlflow/users/get?username=${encoded}" >/dev/null 2>&1; then
    mlflow_admin PATCH /api/2.0/mlflow/users/update-password --data "${payload}" >/dev/null
  else
    mlflow_admin POST /api/2.0/mlflow/users/create --data "${payload}" >/dev/null
  fi
  mlflow_admin PATCH /api/2.0/mlflow/users/update-admin --data \
    "$(jq -cn --arg username "${username}" '{username:$username,is_admin:false}')" >/dev/null
}

ensure_mlflow_experiment() {
  local name=$1 experiments experiment_id
  experiments="$(mlflow_admin POST /api/2.0/mlflow/experiments/search --data '{"max_results":1000}')"
  experiment_id="$(jq -r --arg name "${name}" \
    '.experiments[]? | select(.name == $name) | .experiment_id' <<<"${experiments}" | head -n1)"
  if [[ -z ${experiment_id} ]]; then
    experiment_id="$(mlflow_admin POST /api/2.0/mlflow/experiments/create --data \
      "$(jq -cn --arg name "${name}" '{name:$name}')" | jq -er '.experiment_id')"
  fi
  printf '%s\n' "${experiment_id}"
}

ensure_mlflow_permission() {
  local resource=$1 identifier_key=$2 identifier=$3 username=$4 permission=$5
  local encoded_id encoded_user path payload
  encoded_id="$(jq -rn --arg value "${identifier}" '$value|@uri')"
  encoded_user="$(jq -rn --arg value "${username}" '$value|@uri')"
  path="/api/2.0/mlflow/${resource}/permissions"
  payload="$(jq -cn --arg key "${identifier_key}" --arg identifier "${identifier}" \
    --arg username "${username}" --arg permission "${permission}" \
    '{username:$username,permission:$permission} + {($key):$identifier}')"
  if mlflow_admin GET "${path}/get?${identifier_key}=${encoded_id}&username=${encoded_user}" >/dev/null 2>&1; then
    mlflow_admin PATCH "${path}/update" --data "${payload}" >/dev/null
  else
    mlflow_admin POST "${path}/create" --data "${payload}" >/dev/null
  fi
}

ensure_mlflow_access() {
  local attempt experiment experiment_id models
  for attempt in $(seq 1 60); do
    curl -fsS "${MLFLOW_URL}/health" >/dev/null 2>&1 && break
    (( attempt < 60 )) || die 'MLflow did not become ready for m09 access reconciliation'
    sleep 2
  done
  ensure_mlflow_user "${M09_PARTICIPANT_USER}" "${M09_PARTICIPANT_PASSWORD}"
  for experiment in 'Orion Release Risk Training' 'Orion Model Integrity Reviews' 'Orion Release Operations'; do
    experiment_id="$(ensure_mlflow_experiment "${experiment}")"
    ensure_mlflow_permission experiments experiment_id "${experiment_id}" "${M09_PARTICIPANT_USER}" READ
  done
  models="$(mlflow_admin GET '/api/2.0/mlflow/registered-models/search?max_results=1000')"
  if jq -e 'any(.registered_models[]?; .name == "Orion Release Risk")' <<<"${models}" >/dev/null; then
    ensure_mlflow_permission registered-models name 'Orion Release Risk' "${M09_PARTICIPANT_USER}" READ
  fi
}

ensure_forgejo_state() {
  ensure_repo "${CINDER_FORGEJO_API_URL}" 'cinder-operator:Cinder-Operations-Git-K3m7Pq4x' \
    cinder-operator orion-model-releases 'Cinder upstream Orion model releases.' false
  ensure_repo "${FORGEJO_API_URL}" 'range-admin:KeplerV2-Training-Forgejo-Admin' \
    keplerops orion-release-approvals 'Orion candidate release approvals.' true
  ensure_repo "${FORGEJO_API_URL}" 'range-admin:KeplerV2-Training-Forgejo-Admin' \
    keplerops orion-model-review 'Orion internal model mirror review queue.' true
  ensure_repo "${FORGEJO_API_URL}" 'range-admin:KeplerV2-Training-Forgejo-Admin' \
    keplerops orion-platform 'Orion GitOps deployment manifests.' true
  ensure_repo "${FORGEJO_API_URL}" 'range-admin:KeplerV2-Training-Forgejo-Admin' \
    keplerops orion-release-suite 'Orion release evaluation and lineage controls.' true
  ensure_forgejo_user "${M09_PARTICIPANT_USER}" "${M09_PARTICIPANT_PASSWORD}" "${M09_PARTICIPANT_EMAIL}"
  grant_repo keplerops orion-release-suite "${M09_PARTICIPANT_USER}" read
  grant_cinder_repo cinder-operator orion-model-releases cinder-field-operator write
  put_file "${CINDER_FORGEJO_API_URL}" 'cinder-operator:Cinder-Operations-Git-K3m7Pq4x' \
    cinder-operator orion-model-releases README.md "${MODULE_ROOT}/payloads/UPSTREAM_RELEASE.md" 'Publish upstream release requirements'
  seed_file "${CINDER_FORGEJO_API_URL}" 'cinder-operator:Cinder-Operations-Git-K3m7Pq4x' \
    cinder-operator orion-model-releases channels/orion-compatible.json \
    "${MODULE_ROOT}/payloads/upstream-channel-baseline.json" 'Seed the ordinary Orion compatibility channel'
  put_file "${FORGEJO_API_URL}" 'range-admin:KeplerV2-Training-Forgejo-Admin' \
    keplerops orion-release-approvals README.md "${MODULE_ROOT}/payloads/ORION_RELEASE_RUNBOOK.md" 'Publish Orion release runbook'
  put_file "${FORGEJO_API_URL}" 'range-admin:KeplerV2-Training-Forgejo-Admin' \
    keplerops orion-model-review README.md "${MODULE_ROOT}/payloads/ORION_RELEASE_RUNBOOK.md" 'Publish Orion review handoff'
  put_file "${FORGEJO_API_URL}" 'range-admin:KeplerV2-Training-Forgejo-Admin' \
    keplerops orion-release-suite visible-suite.json "${MODULE_ROOT}/payloads/visible-suite.json" 'Publish visible Orion release suite'
  put_file "${FORGEJO_API_URL}" 'range-admin:KeplerV2-Training-Forgejo-Admin' \
    keplerops orion-release-suite approved-lineage.json "${MODULE_ROOT}/payloads/approved-lineage.json" 'Publish approved Orion lineage'
  ensure_issue_label orion-release-approvals release-approved 2da44e 'Release Engineering approval recorded'
  ensure_issue_label orion-model-review load-approved 2da44e 'Reviewer authorized isolated smoke loading'
}

ensure_harbor_state() {
  local project
  for project in orion-candidates orion-review; do
    curl -fsS --user 'admin:KeplerV2-Training-Harbor' -H 'Content-Type: application/json' \
      -X POST --data "$(jq -cn --arg name "${project}" '{project_name:$name,public:false,metadata:{auto_scan:"false"}}')" \
      "${HARBOR_API_URL}/projects" >/dev/null 2>&1 || true
  done
  if ! curl -fsS --user 'admin:KeplerV2-Training-Harbor' "${HARBOR_API_URL}/labels?scope=g&page_size=100" | \
      jq -e 'any(.[]; .name == "orion-release-compatible")' >/dev/null; then
    curl -fsS --user 'admin:KeplerV2-Training-Harbor' -H 'Content-Type: application/json' -X POST \
      --data '{"name":"orion-release-compatible","description":"Legacy Orion serving compatibility","color":"#2da44e","scope":"g"}' \
      "${HARBOR_API_URL}/labels" >/dev/null
  fi

}

ensure_rabbit_state() {
  local auth='kepler:KeplerV2-Training-Rabbit'
  for queue in orion.review.m09-import orion.review.m09-results orion.review.m09-review-results; do
    curl -fsS --user "${auth}" -H 'Content-Type: application/json' -X PUT \
      --data '{"durable":true,"auto_delete":false,"arguments":{}}' \
      "${RABBIT_API}/queues/keplerops/${queue}" >/dev/null
  done
  curl -fsS --user "${auth}" -H 'Content-Type: application/json' -X PUT \
    --data '{"configure":"^orion\\.review\\.(review01|integration01|results(\\.[A-Za-z0-9][A-Za-z0-9._:-]{2,127})?|m09-(import|results|review-results))$","write":"^amq\\.default$","read":"^orion\\.review\\.(review01|integration01|results(\\.[A-Za-z0-9][A-Za-z0-9._:-]{2,127})?|m09-(import|results|review-results))$"}' \
    "${RABBIT_API}/permissions/keplerops/svc-review-verification" >/dev/null
}

ensure_relay_basket() {
  local basket=$1 token_file response token
  token_file="${STATE_ROOT}/relay/${basket}.token"
  install -d -m 0750 "$(dirname "${token_file}")"
  if [[ -s ${token_file} ]]; then
    token="$(<"${token_file}")"
    if curl -fsS -H "Authorization: ${token}" \
        "${RELAY_URL}/api/baskets/${basket}" >/dev/null 2>&1; then
      return
    fi
  fi
  response="$(curl -fsS -X POST -H 'Content-Type: application/json' \
    --data '{"capacity":100}' "${RELAY_URL}/api/baskets/${basket}")"
  jq -er '.token' <<<"${response}" >"${token_file}"
  chmod 0600 "${token_file}"
}

ensure_opa_policy() {
  [[ -r ${K3S01_SSH_KEY} ]] || die "k3s SSH key is unavailable: ${K3S01_SSH_KEY}"
  "${SSH[@]}" "${K3S01_SSH_TARGET}" 'cat >/tmp/m09.rego' <"${MODULE_ROOT}/payloads/m09.rego"
  "${SSH[@]}" "${K3S01_SSH_TARGET}" sudo bash -s <<'REMOTE'
set -Eeuo pipefail
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
k3s kubectl -n orion-platform create configmap m09-release-policy \
  --from-file=m09.rego=/tmp/m09.rego --dry-run=client -o yaml | k3s kubectl apply -f - >/dev/null
rm -f /tmp/m09.rego
deployment="$(k3s kubectl -n orion-platform get deployment opa -o json)"
arg_count="$(jq '[.spec.template.spec.containers[] | select(.name == "opa") | .args[] | select(. == "/m09-policy/m09.rego")] | length' <<<"${deployment}")"
mount_count="$(jq '[.spec.template.spec.containers[] | select(.name == "opa") | .volumeMounts[] | select(.name == "m09-policy" and .mountPath == "/m09-policy")] | length' <<<"${deployment}")"
volume_count="$(jq '[.spec.template.spec.volumes[] | select(.name == "m09-policy" and .configMap.name == "m09-release-policy")] | length' <<<"${deployment}")"
if [[ ${arg_count} -gt 1 || ${mount_count} -gt 1 || ${volume_count} -gt 1 ]]; then
  printf 'OPA has a duplicate m09 policy mount: args=%s mounts=%s volumes=%s\n' \
    "${arg_count}" "${mount_count}" "${volume_count}" >&2
  exit 1
fi
if [[ ${arg_count} == 0 ]]; then
  k3s kubectl -n orion-platform patch deployment opa --type=json -p='[
    {"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"/m09-policy/m09.rego"}
  ]' >/dev/null
fi
if [[ ${mount_count} == 0 ]]; then
  k3s kubectl -n orion-platform patch deployment opa --type=json -p='[
    {"op":"add","path":"/spec/template/spec/containers/0/volumeMounts/-","value":{"name":"m09-policy","mountPath":"/m09-policy","readOnly":true}}
  ]' >/dev/null
fi
if [[ ${volume_count} == 0 ]]; then
  k3s kubectl -n orion-platform patch deployment opa --type=json -p='[
    {"op":"add","path":"/spec/template/spec/volumes/-","value":{"name":"m09-policy","configMap":{"name":"m09-release-policy"}}}
  ]' >/dev/null
fi
k3s kubectl -n orion-platform patch service opa --type=merge -p='{"spec":{"type":"NodePort","ports":[{"name":"http","port":8181,"targetPort":"http","nodePort":30082}]}}' >/dev/null
k3s kubectl -n orion-platform rollout restart deployment/opa >/dev/null
k3s kubectl -n orion-platform rollout status deployment/opa --timeout=5m >/dev/null
curl -fsS http://192.168.78.30:30082/health >/dev/null
REMOTE
}

capture_upstream_baseline() {
  local path="${STATE_ROOT}/upstream-channel-baseline.json" response
  [[ -s ${path} ]] && return
  response="$(forgejo "${CINDER_FORGEJO_API_URL}" 'cinder-operator:Cinder-Operations-Git-K3m7Pq4x' GET \
    /repos/cinder-operator/orion-model-releases/contents/channels/orion-compatible.json)"
  jq -er '.content | gsub("\\n"; "") | @base64d | fromjson' <<<"${response}" >"${path}"
  chmod 0640 "${path}"
}

reconcile_airflow_access() {
  docker exec kep-v2-airflow-api airflow sync-perm >/dev/null
  docker exec kep-v2-airflow-api python /opt/airflow/config/reconcile_airflow_roles.py >/dev/null
  docker exec kep-v2-airflow-api airflow users create \
    --username "${M09_PARTICIPANT_USER}" --firstname Orion --lastname Release \
    --role 'Orion Release Runner' --email "${M09_PARTICIPANT_EMAIL}" \
    --password "${M09_PARTICIPANT_PASSWORD}" >/dev/null 2>&1 || \
    docker exec kep-v2-airflow-api airflow users reset-password \
      --username "${M09_PARTICIPANT_USER}" --password "${M09_PARTICIPANT_PASSWORD}" >/dev/null
  docker exec kep-v2-airflow-api airflow users add-role \
    --username "${M09_PARTICIPANT_USER}" --role 'Orion Release Runner' >/dev/null 2>&1 || true
  local stale_role
  for stale_role in Admin 'Orion Runner' 'Orion Viewer' 'Orion Integrity Runner'; do
    docker exec kep-v2-airflow-api airflow users remove-role \
      --username "${M09_PARTICIPANT_USER}" --role "${stale_role}" >/dev/null 2>&1 || true
  done

  local runner_token='' dag denied_status
  runner_token="$(curl -fsS -H 'Content-Type: application/json' -X POST \
    --data "$(jq -cn --arg username "${M09_PARTICIPANT_USER}" --arg password "${M09_PARTICIPANT_PASSWORD}" \
      '{username:$username,password:$password}')" \
    http://10.61.40.35:8080/auth/token | jq -er '.access_token')"
  for dag in "${M09_DAG_IDS[@]}"; do
    curl -fsS -H "Authorization: Bearer ${runner_token}" -H 'Content-Type: application/json' -X PATCH \
      --data '{"is_paused":false}' "http://10.61.40.35:8080/api/v2/dags/${dag}" >/dev/null
    curl -fsS -H "Authorization: Bearer ${runner_token}" \
      "http://10.61.40.35:8080/api/v2/dags/${dag}" >/dev/null
  done
  for dag in engineering_inventory orion_label_export; do
    denied_status="$(curl -sS -o /dev/null -w '%{http_code}' \
      -H "Authorization: Bearer ${runner_token}" \
      "http://10.61.40.35:8080/api/v2/dags/${dag}")"
    [[ ${denied_status} == 403 || ${denied_status} == 404 ]] || \
      die "m09 participant identity unexpectedly reached non-M09 DAG ${dag}"
  done
}

ensure_airflow() {
  # Shared images are built once before service startup; building every service
  # together can make Compose Bake export the same tag concurrently.
  compose build airflow-api orion-import-review-worker >/dev/null
  compose up -d --no-build --no-deps airflow-api airflow-scheduler airflow-dag-processor airflow-triggerer airflow-worker \
    orion-import-review-worker orion-model-review-dispatcher >/dev/null
  local token='' dag ready
  for _ in $(seq 1 90); do
    token="$(curl -fsS -H 'Content-Type: application/json' -X POST \
      --data '{"username":"range-admin","password":"KeplerV2-Training-Airflow"}' \
      http://10.61.40.35:8080/auth/token 2>/dev/null | jq -r '.access_token // empty' || true)"
    [[ -n ${token} ]] && break
    sleep 2
  done
  [[ -n ${token} ]] || die 'Airflow API did not become ready'
  for _ in $(seq 1 90); do
    ready=true
    for dag in "${M09_DAG_IDS[@]}"; do
      if ! curl -fsS -H "Authorization: Bearer ${token}" \
        "http://10.61.40.35:8080/api/v2/dags/${dag}" >/dev/null 2>&1; then
        ready=false
        break
      fi
    done
    if [[ ${ready} == true ]]; then
      reconcile_airflow_access
      return
    fi
    sleep 2
  done
  die 'Airflow did not discover all Orion release operations'
}

deliver_m09_access() {
  docker exec -i --user root keplerops-participant-workstation-runtime sh -c '
    install -d -m 0700 -o kasm-user -g root /home/kasm-user/.keplerops
    cat > /home/kasm-user/.keplerops/m09-earned.env
    chown kasm-user:root /home/kasm-user/.keplerops/m09-earned.env
    chmod 0600 /home/kasm-user/.keplerops/m09-earned.env
  ' <<EOF
AIRFLOW_URL=https://airflow.keplerops.lab
AIRFLOW_USER=${M09_PARTICIPANT_USER}
AIRFLOW_PASSWORD=${M09_PARTICIPANT_PASSWORD}
MLFLOW_URL=https://mlflow.keplerops.lab
MLFLOW_USERNAME=${M09_PARTICIPANT_USER}
MLFLOW_PASSWORD=${M09_PARTICIPANT_PASSWORD}
KEPLEROPS_FORGEJO_URL=https://git.keplerops.lab
KEPLEROPS_FORGEJO_USER=${M09_PARTICIPANT_USER}
KEPLEROPS_FORGEJO_PASSWORD=${M09_PARTICIPANT_PASSWORD}
M09_RELEASE_SUITE_URL=https://git.keplerops.lab/keplerops/orion-release-suite
M09_VISIBLE_DAG=orion_visible_release_evaluation
M09_IMPORT_DAG=orion_import_exception_review
M09_RELAY_URL=https://relay.cinder.lab
M09_IMPORT_RELAY_BASKET=m09-import-exceptions
M09_IMPORT_RELAY_TOKEN=$(<"${STATE_ROOT}/relay/m09-import-exceptions.token")
EOF
}

main() {
  local command
  for command in base64 curl docker jq ssh; do command -v "${command}" >/dev/null || die "missing command: ${command}"; done
  [[ ${OPERATION} == all ]] || jq -e --arg id "${OPERATION}" 'any(.[]; .id == $id)' "${MODULE_ROOT}/operations.json" >/dev/null || die "unknown operation: ${OPERATION}"
  "${TEMPLATE_ROOT}/campaign-start/reconcile-airflow-dags.sh"
  install -d -m 0770 -o 50000 -g 0 "${STATE_ROOT}/accepted" "${STATE_ROOT}/applied" \
    "${STATE_ROOT}/attempts" "${STATE_ROOT}/failed" "${STATE_ROOT}/promotion-capabilities"
  install -d -m 0770 -o 50000 -g 10001 "${STATE_ROOT}/review-dispatch"
  ensure_forgejo_state
  capture_upstream_baseline
  ensure_harbor_state
  ensure_mlflow_access
  ensure_rabbit_state
  ensure_relay_basket m09-import-exceptions
  ensure_relay_basket m09-mirror-review
  ensure_opa_policy
  ensure_airflow
  deliver_m09_access
  if [[ ${OPERATION} == all ]]; then
    jq -r '.[].id' "${MODULE_ROOT}/operations.json" | while read -r id; do printf '%s\n' "${id}" >"${STATE_ROOT}/applied/${id}"; done
  else
    printf '%s\n' "${OPERATION}" >"${STATE_ROOT}/applied/${OPERATION}"
  fi
  log "reconciled ${OPERATION} start state without creating operation results"
}

main "$@"
