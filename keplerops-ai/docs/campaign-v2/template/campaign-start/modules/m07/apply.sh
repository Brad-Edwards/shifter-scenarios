#!/usr/bin/env bash
set -Eeuo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MODULE_ROOT
TEMPLATE_ROOT="$(cd "${MODULE_ROOT}/../../.." && pwd)"
readonly TEMPLATE_ROOT
readonly STATE_ROOT="${CAMPAIGN_STATE_ROOT:-${TEMPLATE_ROOT}/state/campaign-start}/m07"
readonly LABEL_STUDIO_URL="${LABEL_STUDIO_URL:-http://10.61.40.34:8080}"
readonly LABEL_STUDIO_ADMIN_TOKEN=31a5a4b4ab3cdbaf110644eed06853b2b418daf6
readonly TRAINER_TOKEN=KAI-Orion-Trainer-2b68d419a7f340ce
readonly FORGEJO_API_URL="${FORGEJO_API_URL:-http://10.61.40.20:3000/api/v1}"
readonly FORGEJO_ADMIN_AUTH="${FORGEJO_ADMIN_AUTH:-range-admin:KeplerV2-Training-Forgejo-Admin}"
readonly HARBOR_API_URL="${HARBOR_API_URL:-http://10.61.40.32:8080/api/v2.0}"
readonly HARBOR_ADMIN_AUTH="${HARBOR_ADMIN_AUTH:-admin:KeplerV2-Training-Harbor}"

log() { printf '[campaign-m07] %s\n' "$*" >&2; }
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

forgejo() {
  local method=$1 path=$2
  shift 2
  curl -fsS --user "${FORGEJO_ADMIN_AUTH}" -H 'Content-Type: application/json' \
    -X "${method}" "$@" "${FORGEJO_API_URL}${path}"
}

ensure_forgejo_user() {
  local username=$1 password=$2 email=$3
  if ! forgejo GET "/users/${username}" >/dev/null 2>&1; then
    forgejo POST /admin/users --data "$(jq -cn \
      --arg username "${username}" --arg password "${password}" --arg email "${email}" \
      '{username:$username,password:$password,email:$email,must_change_password:false,restricted:false,visibility:"private"}')" >/dev/null
  else
    forgejo PATCH "/admin/users/${username}" --data "$(jq -cn --arg password "${password}" '{password:$password,must_change_password:false,active:true}')" >/dev/null
  fi
}

ensure_forgejo_org() {
  local owner=$1 title=$2
  forgejo GET "/orgs/${owner}" >/dev/null 2>&1 || \
    forgejo POST /orgs --data "$(jq -cn --arg username "${owner}" --arg full_name "${title}" \
      '{username:$username,full_name:$full_name,visibility:"private"}')" >/dev/null
}

ensure_forgejo_repo() {
  local owner=$1 repo=$2 description=$3 private=$4
  forgejo GET "/repos/${owner}/${repo}" >/dev/null 2>&1 || \
    forgejo POST "/orgs/${owner}/repos" --data "$(jq -cn \
      --arg name "${repo}" --arg description "${description}" --argjson private "${private}" \
      '{name:$name,description:$description,private:$private,auto_init:true,default_branch:"main"}')" >/dev/null
}

grant_repo() {
  local owner=$1 repo=$2 username=$3 permission=${4:-write}
  forgejo PUT "/repos/${owner}/${repo}/collaborators/${username}" \
    --data "$(jq -cn --arg permission "${permission}" '{permission:$permission}')" >/dev/null
}

upsert_file() {
  local owner=$1 repo=$2 path=$3 message=$4 source=$5 existing sha payload
  existing="$(forgejo GET "/repos/${owner}/${repo}/contents/${path}" 2>/dev/null || true)"
  sha="$(jq -r '.sha // empty' <<<"${existing:-{}}")"
  payload="$(base64 -w0 "${source}" | jq -Rs \
    --arg message "${message}" --arg sha "${sha}" \
    '{content:.,message:$message,branch:"main"} + (if $sha == "" then {} else {sha:$sha} end)')"
  forgejo PUT "/repos/${owner}/${repo}/contents/${path}" --data "${payload}" >/dev/null
}

capture_clean_state() {
  [[ -s ${STATE_ROOT}/baseline-labels.json ]] && return 0
  docker exec -i kep-v2-postgres psql --set ON_ERROR_STOP=1 \
    --username kepler --dbname labelstudio >/dev/null <<SQL
UPDATE authtoken_token SET key = '${LABEL_STUDIO_ADMIN_TOKEN}'
WHERE user_id = (SELECT id FROM htx_user WHERE email = 'annotation.admin@keplerops.lab');
SQL
  "${TEMPLATE_ROOT}/engineering/reconcile-release-risk-labels.sh" >/dev/null
  local exported
  exported="$(curl -fsS -H "Authorization: Token ${LABEL_STUDIO_ADMIN_TOKEN}" \
    "${LABEL_STUDIO_URL}/api/projects?page_size=100" | jq -er \
    '.results[] | select(.title == "Orion Release Risk Training Baseline") | .id' | head -n1)"
  curl -fsS -H "Authorization: Token ${LABEL_STUDIO_ADMIN_TOKEN}" \
    "${LABEL_STUDIO_URL}/api/projects/${exported}/export?exportType=JSON" \
    | jq 'map({key:.data.record_id,value:{text:.data.text,label:.annotations[-1].result[0].value.choices[0]}}) | from_entries' \
    >"${STATE_ROOT}/baseline-labels.json"
  jq '[to_entries[] | {record_id:.key,text:.value.text,label:.value.label}]' \
    "${STATE_ROOT}/baseline-labels.json" >"${STATE_ROOT}/upstream-clean.json"
  chmod 0640 "${STATE_ROOT}/baseline-labels.json" "${STATE_ROOT}/upstream-clean.json"
}

reconcile_trainer_access() {
  docker exec -i kep-v2-postgres psql --set ON_ERROR_STOP=1 \
    --username kepler --dbname labelstudio >/dev/null <<SQL
UPDATE authtoken_token SET key = '${TRAINER_TOKEN}'
WHERE user_id = (SELECT id FROM htx_user WHERE email = 'annotation.admin@keplerops.lab');
SQL
}

seed_repositories() {
  [[ -e ${STATE_ROOT}/repositories-seeded ]] && return 0
  ensure_forgejo_user svc-orion-training "${TRAINER_TOKEN}" svc-orion-training@keplerops.lab
  ensure_forgejo_user upstream.maintainer Cinder-Upstream-Maintainer-2026 upstream.maintainer@orion-upstream.lab
  ensure_forgejo_user cinder.publisher Cinder-Dataset-Publisher-2026 cinder.publisher@cinder.lab
  ensure_forgejo_org orion-upstream 'Orion Upstream Data Cooperative'
  ensure_forgejo_org cinder-labs 'Cinder Research'
  ensure_forgejo_org cinder-system 'Cinder Research Infrastructure'
  ensure_forgejo_repo keplerops orion-model-integrity 'Orion model data, evaluation, and graph sources.' true
  ensure_forgejo_repo orion-upstream release-risk-corpus 'Versioned upstream Orion-compatible release-risk corpus.' false
  ensure_forgejo_repo cinder-labs orion-poisoned-dataset 'Cinder dataset and isolated model-artifact publications.' false
  ensure_forgejo_repo cinder-system artifact-review 'Cinder isolated artifact execution and attestation.' true
  grant_repo keplerops orion-model-integrity svc-orion-training write
  grant_repo orion-upstream release-risk-corpus upstream.maintainer admin
  grant_repo cinder-labs orion-poisoned-dataset cinder.publisher admin
  grant_repo cinder-system artifact-review cinder.publisher read

  local seed="${STATE_ROOT}/seed"
  install -d -m 0750 "${seed}/integrity/evaluation" "${seed}/integrity/model" "${seed}/upstream" "${seed}/cinder/.forgejo/workflows"
  jq '.[0:16]' "${STATE_ROOT}/upstream-clean.json" >"${seed}/integrity/evaluation/holdout.clean.json"
  cp "${seed}/integrity/evaluation/holdout.clean.json" "${seed}/integrity/evaluation/holdout.json"
  cp "${STATE_ROOT}/upstream-clean.json" "${seed}/upstream/dataset.json"
  cp "${STATE_ROOT}/upstream-clean.json" "${seed}/cinder/dataset.json"
  sha256sum "${seed}/upstream/dataset.json" | sed 's# .*/#  #' >"${seed}/upstream/checksums.sha256"
  sha256sum "${seed}/cinder/dataset.json" | sed 's# .*/#  #' >"${seed}/cinder/checksums.sha256"
  cp "${MODULE_ROOT}/payloads/upstream/README.md" "${seed}/upstream/README.md"
  cp "${MODULE_ROOT}/payloads/integrity/README.md" "${seed}/integrity/README.md"
  cp "${MODULE_ROOT}/payloads/integrity/graph_mutation.py" "${seed}/integrity/model/graph_mutation.py"
  cp "${MODULE_ROOT}/payloads/cinder/README.md" "${seed}/cinder/README.md"
  cp "${MODULE_ROOT}/payloads/cinder/loader.py" "${seed}/cinder/loader.py"
  cp "${MODULE_ROOT}/payloads/cinder/build_unsafe_model.py" "${seed}/cinder/build_unsafe_model.py"
  cp "${MODULE_ROOT}/payloads/cinder/model_runtime.py" "${seed}/cinder/model_runtime.py"
  cp "${MODULE_ROOT}/payloads/cinder/verifier.py" "${seed}/cinder/verifier.py"
  cp "${MODULE_ROOT}/payloads/cinder/verify-embedded-model.yml" \
    "${seed}/cinder/.forgejo/workflows/verify-embedded-model.yml"

  local file
  for file in README.md evaluation/holdout.clean.json evaluation/holdout.json model/graph_mutation.py; do
    upsert_file keplerops orion-model-integrity "${file}" "Seed Orion model-integrity source" "${seed}/integrity/${file}"
  done
  for file in README.md dataset.json checksums.sha256; do
    upsert_file orion-upstream release-risk-corpus "${file}" "Seed trusted upstream corpus" "${seed}/upstream/${file}"
  done
  for file in README.md dataset.json checksums.sha256 loader.py build_unsafe_model.py model_runtime.py; do
    upsert_file cinder-labs orion-poisoned-dataset "${file}" "Seed Cinder publication workspace" "${seed}/cinder/${file}"
  done
  upsert_file cinder-system artifact-review verifier.py 'Seed isolated artifact verifier' "${seed}/cinder/verifier.py"
  upsert_file cinder-system artifact-review .forgejo/workflows/verify-embedded-model.yml \
    'Seed isolated artifact review workflow' "${seed}/cinder/.forgejo/workflows/verify-embedded-model.yml"
  forgejo PUT /repos/cinder-system/artifact-review/actions/secrets/CINDER_ATTESTATION_KEY \
    --data '{"data":"Cinder-Isolated-Execution-2026"}' >/dev/null
  forgejo PUT /repos/cinder-system/artifact-review/actions/secrets/M07_ENGAGEMENT_REFERENCE \
    --data '{"data":"FLAG{7089e273d0b9e97f}"}' >/dev/null
  touch "${STATE_ROOT}/repositories-seeded"
}

reconcile_harbor() {
  local user project
  user='{"username":"cinder.publisher","email":"cinder.publisher@cinder.lab","realname":"Cinder Publisher","password":"Cinder-Dataset-Publisher-2026","comment":"Cinder dataset publication identity"}'
  curl -fsS --user "${HARBOR_ADMIN_AUTH}" -H 'Content-Type: application/json' \
    -X POST --data "${user}" "${HARBOR_API_URL}/users" >/dev/null 2>&1 || true
  project='{"project_name":"cinder-datasets","public":true,"metadata":{"auto_scan":"false"}}'
  curl -fsS --user "${HARBOR_ADMIN_AUTH}" -H 'Content-Type: application/json' \
    -X POST --data "${project}" "${HARBOR_API_URL}/projects" >/dev/null 2>&1 || true
  local project_id user_id
  project_id="$(curl -fsS --user "${HARBOR_ADMIN_AUTH}" "${HARBOR_API_URL}/projects?name=cinder-datasets" | jq -er '.[0].project_id')"
  user_id="$(curl -fsS --user "${HARBOR_ADMIN_AUTH}" "${HARBOR_API_URL}/users?username=cinder.publisher" | jq -er '.[0].user_id')"
  curl -fsS --user "${HARBOR_ADMIN_AUTH}" -H 'Content-Type: application/json' \
    -X POST --data "$(jq -cn --argjson id "${user_id}" '{role_id:2,member_user:{user_id:$id}}')" \
    "${HARBOR_API_URL}/projects/${project_id}/members" >/dev/null 2>&1 || true
}

reconcile_airflow() {
  compose up -d --no-build airflow-api airflow-scheduler airflow-dag-processor airflow-triggerer airflow-worker >/dev/null
  local attempt token
  token="$(curl -fsS -H 'Content-Type: application/json' -X POST \
    --data '{"username":"range-admin","password":"KeplerV2-Training-Airflow"}' \
    http://10.61.40.35:8080/auth/token | jq -er '.access_token')"
  for attempt in $(seq 1 60); do
    if curl -fsS -H "Authorization: Bearer ${token}" \
        http://10.61.40.35:8080/api/v2/dags/orion_campaign_label_export >/dev/null 2>&1; then
      return 0
    fi
    (( attempt < 60 )) || break
    sleep 2
  done
  die 'Airflow did not discover the m07 workflow bundle'
}

apply_one() {
  local operation=$1
  jq -e --arg id "${operation}" 'any(.[]; .id == $id)' "${MODULE_ROOT}/operations.json" >/dev/null || die "unknown operation: ${operation}"
  capture_clean_state
  reconcile_trainer_access
  seed_repositories
  reconcile_harbor
  reconcile_airflow
  install -d -m 0750 "${STATE_ROOT}/applied"
  printf '%s\n' "${operation}" >"${STATE_ROOT}/applied/${operation}"
  log "reconciled ${operation} start state"
}

main() {
  local requested=${1:-all} operation command
  for command in base64 curl docker jq sha256sum; do command -v "${command}" >/dev/null || die "missing command: ${command}"; done
  install -d -m 0750 "${STATE_ROOT}"
  if [[ ${requested} != all ]]; then apply_one "${requested}"; return; fi
  capture_clean_state
  reconcile_trainer_access
  seed_repositories
  reconcile_harbor
  reconcile_airflow
  install -d -m 0750 "${STATE_ROOT}/applied"
  while IFS= read -r operation; do
    printf '%s\n' "${operation}" >"${STATE_ROOT}/applied/${operation}"
  done < <(jq -r '.[].id' "${MODULE_ROOT}/operations.json")
  log 'reconciled all m07 start state'
}

main "$@"
