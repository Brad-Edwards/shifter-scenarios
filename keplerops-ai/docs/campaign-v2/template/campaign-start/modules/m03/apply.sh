#!/usr/bin/env bash
set -Eeuo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MODULE_ROOT
TEMPLATE_ROOT="$(cd "${MODULE_ROOT}/../../.." && pwd)"
readonly TEMPLATE_ROOT
readonly OPERATION="${1:-all}"
readonly M03_QDRANT_WRITE_URL="${QDRANT_WRITE_URL:-http://10.61.50.72:6333}"
readonly M03_QDRANT_WRITE_KEY="${QDRANT_WRITE_KEY:-KeplerV2-Training-Qdrant-Write}"
readonly NEXTCLOUD_URL="${NEXTCLOUD_URL:-http://10.61.30.23}"
readonly NEXTCLOUD_HOST="${NEXTCLOUD_HOST:-files.keplerops.lab}"
readonly CINDER_RELAY_URL="${CINDER_RELAY_INTERNAL_URL:-http://192.168.78.30:31080}"
readonly JUPYTER_IMAGE="${JUPYTER_IMAGE:-$(sed -n 's/^JUPYTER_IMAGE=//p' "${TEMPLATE_ROOT}/component-lock.env")}"
readonly MINIO_MC_IMAGE="${MINIO_MC_IMAGE:-$(sed -n 's/^MINIO_MC_IMAGE=//p' "${TEMPLATE_ROOT}/engineering/component-lock.additions.env")}"
readonly NODE_IMAGE="${NODE_IMAGE:-$(sed -n 's/^OPENCODE_BUILDER_IMAGE=//p' "${TEMPLATE_ROOT}/component-lock.env")}"
readonly CINDER_S3_ENDPOINT="${CINDER_S3_ENDPOINT:-http://cinder-minio:9000}"
readonly REDMINE_ADMIN_USER="${REDMINE_ADMIN_USER:-admin}"

# shellcheck source=../../../seeding/config.env
# shellcheck disable=SC1091
source "${TEMPLATE_ROOT}/seeding/config.env"

log() { printf '[campaign-m03] %s\n' "$*" >&2; }
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

known_operation() {
  jq -e --arg id "$1" 'any(.[]; .id == $id)' "${MODULE_ROOT}/operations.json" >/dev/null
}

ensure_cinder_storage() {
  docker run --rm --network kep-v2-cinder --entrypoint /bin/sh "${MINIO_MC_IMAGE}" -eu -c '
    mc alias set cinder http://cinder-minio:9000 cinder-operator Cinder-Operations-ObjectStore-T7v2Lm9q >/dev/null
    mc mb --ignore-existing --with-lock cinder/operations >/dev/null
    mc anonymous set none cinder/operations >/dev/null
    mc admin user add cinder cinder-field-operator Cinder-Field-Operator-Objects-H8r3Tm5w >/dev/null 2>&1 || true
    cat >/tmp/m03-participant.json <<"JSON"
{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["s3:GetBucketLocation"],"Resource":["arn:aws:s3:::operations"]},{"Effect":"Allow","Action":["s3:GetObject","s3:GetObjectVersion"],"Resource":["arn:aws:s3:::operations/campaign-v2/m03/index-source/source/release-criteria.json","arn:aws:s3:::operations/campaign-v2/m03/index-source/submission/index-source-join.yaml","arn:aws:s3:::operations/campaign-v2/m03/index-source/accepted/*","arn:aws:s3:::operations/campaign-v2/m03/relay/*"]},{"Effect":"Allow","Action":["s3:PutObject"],"Resource":["arn:aws:s3:::operations/campaign-v2/m03/index-source/submission/index-source-join.yaml"]}]}
JSON
    mc admin policy create cinder m03-cinder-field-operator /tmp/m03-participant.json >/dev/null 2>&1 || mc admin policy info cinder m03-cinder-field-operator >/dev/null
    mc admin policy attach cinder m03-cinder-field-operator --user cinder-field-operator >/dev/null
    mc admin user add cinder m03-ingestion-review Cinder-M03-Ingestion-Review-S8k2Vn6q >/dev/null 2>&1 || true
    cat >/tmp/m03-ingestion-review.json <<"JSON"
{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["s3:GetBucketLocation"],"Resource":["arn:aws:s3:::operations"]},{"Effect":"Allow","Action":["s3:GetObject","s3:GetObjectVersion"],"Resource":["arn:aws:s3:::operations/campaign-v2/m03/index-source/source/release-criteria.json","arn:aws:s3:::operations/campaign-v2/m03/index-source/submission/index-source-join.yaml","arn:aws:s3:::operations/campaign-v2/m03/index-source/accepted/*"]},{"Effect":"Allow","Action":["s3:PutObject","s3:PutObjectLegalHold"],"Resource":["arn:aws:s3:::operations/campaign-v2/m03/index-source/accepted/*"]}]}
JSON
    mc admin policy create cinder m03-ingestion-review /tmp/m03-ingestion-review.json >/dev/null 2>&1 || mc admin policy info cinder m03-ingestion-review >/dev/null
    mc admin policy attach cinder m03-ingestion-review --user m03-ingestion-review >/dev/null
  '
}

seed_enterprise_records() {
  FORGEJO_API_URL="${FORGEJO_API_URL}" \
  FORGEJO_ADMIN_USER="${FORGEJO_ADMIN_USER}" \
  FORGEJO_ADMIN_PASSWORD="${FORGEJO_ADMIN_PASSWORD}" \
  QDRANT_URL="${M03_QDRANT_WRITE_URL}" QDRANT_WRITE_KEY="${M03_QDRANT_WRITE_KEY}" \
  CINDER_FORGEJO_API_URL="${CINDER_FORGEJO_API_URL:-http://10.61.90.30:3000/api/v1}" \
  CINDER_FORGEJO_USER="${CINDER_FORGEJO_USER:-cinder-operator}" \
  CINDER_FORGEJO_PASSWORD="${CINDER_FORGEJO_PASSWORD:-Cinder-Operations-Git-K3m7Pq4x}" \
    python3 "${MODULE_ROOT}/runtime/seed_enterprise.py" "$1"
}

seed_workhub_records() {
  compose exec -T \
    -e M03_OPERATION="$1" \
    -e M03_PAYLOAD="$(base64 -w0 "${MODULE_ROOT}/payloads/$1.json")" \
    redmine bundle exec rails runner /dev/stdin \
    < "${MODULE_ROOT}/runtime/seed_redmine.rb"
}

seed_devpi_baseline() {
  compose run --rm --no-deps -T --entrypoint /bin/sh \
    -v "${MODULE_ROOT}/payloads/orion-eval-utils:/seed:ro" devpi-bootstrap -eu -c '
      export HOME=/tmp/devpi-client
      devpi use http://devpi:3141 >/dev/null
      devpi login publisher --password=KeplerV2-Training-Devpi-Publisher >/dev/null
      devpi use publisher/stable >/dev/null
      if ! devpi list "orion-eval-utils==1.4.2" 2>/dev/null | grep -q "1.4.2"; then
        cp -R /seed /tmp/orion-eval-utils
        cd /tmp/orion-eval-utils
        devpi upload --no-vcs --formats sdist >/dev/null
      fi
    '
}

seed_npm_baseline() {
  docker run --rm --network kep-v2-engineering \
    -v "${MODULE_ROOT}/payloads/orion-mcp-audit:/seed:ro" "${NODE_IMAGE}" sh -eu -c '
      auth=$(printf "%s:%s" publisher KeplerV2-Training-Npm-Publisher | base64 -w0)
      npm config set registry http://10.61.40.31:4873
      npm config set //10.61.40.31:4873/:_auth "$auth"
      if npm view "@keplerops/orion-mcp-audit@2.3.1" version >/dev/null 2>&1; then exit 0; fi
      cp -R /seed /tmp/orion-mcp-audit
      rm -rf /tmp/orion-mcp-audit/keys /tmp/orion-mcp-audit/.forgejo-ci.yml /tmp/orion-mcp-audit/.forgejo-release.yml
      cd /tmp/orion-mcp-audit
      npm publish --ignore-scripts >/dev/null
    '
}

install_airflow_workflows() {
  compose run --rm --no-deps -T m03-haystack-init >/dev/null
  compose up -d --no-deps airflow-api airflow-scheduler airflow-dag-processor airflow-triggerer airflow-worker >/dev/null
  compose exec -T airflow-scheduler airflow dags reserialize >/dev/null
  compose exec -T airflow-api airflow sync-perm >/dev/null
  compose exec -T airflow-api python - < "${MODULE_ROOT}/runtime/reconcile_airflow_roles.py" >/dev/null
  compose exec -T airflow-scheduler airflow dags unpause orion_approved_review_follow_up >/dev/null
}

seed_haystack_source() {
  local operation=$1
  local -a environment=()
  if [[ -n ${M03_SOURCE_INVENTORY_URL:-} ]]; then
    environment=(-e "M03_SOURCE_INVENTORY_URL=${M03_SOURCE_INVENTORY_URL}" \
      -e "M03_SOURCE_INVENTORY_SHA256=${M03_SOURCE_INVENTORY_SHA256}")
  fi
  compose run --rm --no-deps -T m03-haystack-init >/dev/null
  compose run --rm --no-deps -T "${environment[@]}" --entrypoint /opt/m03-haystack/bin/python \
    airflow-worker /opt/airflow/m03/seed_haystack_sources.py "${operation}" >/dev/null
}

seed_nextcloud_source() (
  local path='Partner%20Reviews/Orion'
  local code source
  source="$(mktemp)"
  trap 'rm -f "${source}"' EXIT
  build_ingestion_source "${source}"
  code="$(curl -sS -o /dev/null -w '%{http_code}' -X MKCOL \
    -u "${NEXTCLOUD_ADMIN_USER}:${NEXTCLOUD_ADMIN_PASSWORD}" \
    -H "Host: ${NEXTCLOUD_HOST}" \
    "${NEXTCLOUD_URL}/remote.php/dav/files/${NEXTCLOUD_ADMIN_USER}/${path}")"
  [[ ${code} == 201 || ${code} == 405 ]] || die "Nextcloud MKCOL returned ${code}"
  curl -fsS -X PUT -u "${NEXTCLOUD_ADMIN_USER}:${NEXTCLOUD_ADMIN_PASSWORD}" \
    -H "Host: ${NEXTCLOUD_HOST}" \
    --data-binary "@${source}" \
    "${NEXTCLOUD_URL}/remote.php/dav/files/${NEXTCLOUD_ADMIN_USER}/${path}/release-criteria.json" >/dev/null
)

seed_cinder_source() (
  local workspace source_sha
  workspace="$(mktemp -d)"
  trap 'rm -rf "${workspace}"' EXIT
  build_ingestion_source "${workspace}/release-criteria.json"
  source_sha="$(sha256sum "${workspace}/release-criteria.json" | awk '{print $1}')"
  cat >"${workspace}/README.md" <<EOF
# Failed ingestion object workspace

Use the scoped Cinder object identity from the operation guide. Bucket listing is denied.

Source key: campaign-v2/m03/index-source/source/release-criteria.json
Submission key: campaign-v2/m03/index-source/submission/index-source-join.yaml
Source SHA-256: ${source_sha}
EOF
  docker run --rm --network kep-v2-cinder -v "${workspace}:/seed:ro" \
    --entrypoint /bin/sh "${MINIO_MC_IMAGE}" -eu -c "
      mc alias set cinder '${CINDER_S3_ENDPOINT}' cinder-operator Cinder-Operations-ObjectStore-T7v2Lm9q >/dev/null
      mc cp --attr 'ingest-reference-suffix=deed861d};source-sha256=${source_sha};source-owner=cinder-operator' \
        /seed/release-criteria.json cinder/operations/campaign-v2/m03/index-source/source/release-criteria.json >/dev/null
      mc cp /seed/README.md cinder/operations/campaign-v2/m03/index-source/README.md >/dev/null
    "
)

build_ingestion_source() {
  python3 - "${MODULE_ROOT}/payloads/kep-m03-h.json" "$1" <<'PY'
import json
import pathlib
import sys

payload = json.loads(pathlib.Path(sys.argv[1]).read_text())
for key in ("qdrant_payload", "source_object_metadata", "report_path"):
    payload.pop(key, None)
pathlib.Path(sys.argv[2]).write_text(json.dumps(payload, indent=2) + "\n")
PY
}

seed_ingestion_provenance() (
  local workspace source_sha object_key
  workspace="$(mktemp -d)"
  trap 'rm -rf "${workspace}"' EXIT
  build_ingestion_source "${workspace}/release-criteria.json"
  source_sha="$(sha256sum "${workspace}/release-criteria.json" | awk '{print $1}')"
  object_key="ingest/orion_partner_intake/partner-orion-release-criteria/${source_sha}.yaml"
  jq -n --arg document 'partner-orion-release-criteria' --arg sha "${source_sha}" \
    --arg path 'Partner Reviews/Orion/release-criteria.json' \
    '{document_id:$document,source_sha256:$sha,source_relative_path:$path,ingestion_status:"failed-after-vector-write"}' \
    >"${workspace}/provenance.json"
  docker run --rm --network kep-v2-data -v "${workspace}/provenance.json:/provenance.json:ro" \
    --entrypoint /bin/sh "${MINIO_MC_IMAGE}" -eu -c "
      mc alias set kepler http://minio:9000 kepler-minio KeplerV2-Training-Minio-Object-Store >/dev/null
      cat >/tmp/ingest-reader.json <<'JSON'
      {\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Action\":[\"s3:GetBucketLocation\"],\"Resource\":[\"arn:aws:s3:::artifacts\"]},{\"Effect\":\"Allow\",\"Action\":[\"s3:GetObject\"],\"Resource\":[\"arn:aws:s3:::artifacts/ingest/orion_partner_intake/*\"]}]}
JSON
      mc admin policy create kepler orion-ingest-diagnostic-read /tmp/ingest-reader.json >/dev/null
      mc admin user add kepler ingest-diagnostic-reader KeplerV2-Orion-Ingest-Diagnostic >/dev/null 2>&1 || true
      mc admin policy attach kepler orion-ingest-diagnostic-read --user ingest-diagnostic-reader >/dev/null
      mc cp /provenance.json 'kepler/artifacts/${object_key}' >/dev/null
    "
)

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
  group_id="$(curl -fsS -H "Authorization: Bearer ${token}" \
    'http://10.61.20.20:8080/admin/realms/keplerops/groups?search=RG-Jupyter-Orion-Evaluation&exact=true' | \
    jq -er '.[] | select(.name == "RG-Jupyter-Orion-Evaluation") | .id')"
  curl -fsS -X PUT -H "Authorization: Bearer ${token}" \
    "http://10.61.20.20:8080/admin/realms/keplerops/users/${user_id}/groups/${group_id}" >/dev/null
  if ! curl -fsS -H "Authorization: Bearer ${token}" \
    'http://10.61.20.20:8080/admin/realms/keplerops/clients?clientId=orion-evaluation-cli' | jq -e 'length == 1' >/dev/null; then
    curl -fsS -X POST -H "Authorization: Bearer ${token}" -H 'Content-Type: application/json' \
      --data '{"clientId":"orion-evaluation-cli","name":"Orion Evaluation CLI","enabled":true,"protocol":"openid-connect","publicClient":true,"standardFlowEnabled":false,"directAccessGrantsEnabled":true,"serviceAccountsEnabled":false}' \
      http://10.61.20.20:8080/admin/realms/keplerops/clients >/dev/null
  fi

  docker volume create 'kep-v2-jupyter-eval.reader' >/dev/null
  docker run --rm --user root -v 'kep-v2-jupyter-eval.reader:/work' "${JUPYTER_IMAGE}" sh -eu -c '
    install -d -m 0750 -o 1000 -g 100 /work/onboarding
    cat >/work/onboarding/ORION-EVALUATION-READER.md <<"EOF"
# Orion Evaluation Reader Onboarding

This account may use compatibility metadata, the Orion privacy research notebooks,
and read-only evaluation jobs. Production release and training controls are outside
this role.

Service desk note: FLAG{8965ae2bb182f564}
EOF
    chown 1000:100 /work/onboarding/ORION-EVALUATION-READER.md
    chmod 0640 /work/onboarding/ORION-EVALUATION-READER.md
  '
}

ensure_relay_basket() {
  local basket=$1 token_file response
  token_file="${TEMPLATE_ROOT}/state/campaign-start/m03/relay/${basket}.token"
  install -d -o 50000 -g 0 -m 0750 "$(dirname "${token_file}")"
  if [[ -s ${token_file} ]]; then
    chown 50000:0 "${token_file}"
    chmod 0440 "${token_file}"
    return
  fi
  response="$(curl -fsS -X POST -H 'Host: relay.cinder.cinder.lab' \
    -H 'Content-Type: application/json' --data '{"capacity":100}' \
    "${CINDER_RELAY_URL}/api/baskets/${basket}")"
  jq -er '.token' <<<"${response}" >"${token_file}"
  chown 50000:0 "${token_file}"
  chmod 0440 "${token_file}"
}

seed_protected_inventory_attachment() (
  local payload current issue_state issue_id upload_token attachment_url
  local -a tls=()
  payload="$(mktemp)"
  current="$(mktemp)"
  issue_state="$(mktemp)"
  trap 'rm -f "${payload}" "${current}" "${issue_state}"' EXIT
  jq '.protected_inventory' "${MODULE_ROOT}/payloads/kep-m03-g.json" >"${payload}"
  while IFS= read -r -d '' value; do tls+=("${value}"); done < <(
    if [[ -n ${KEPLEROPS_CA_CERT:-} ]]; then printf '%s\0%s\0' --cacert "${KEPLEROPS_CA_CERT}"; fi
  )
  issue_id="$(curl -fsS "${tls[@]}" -u "${REDMINE_ADMIN_USER}:${REDMINE_ADMIN_PASSWORD}" \
    -H 'Host: workhub.keplerops.lab' \
    'http://10.61.50.41:3000/issues.json?project_id=orion&status_id=*&limit=100' | \
    jq -er '.issues[] | select(.subject == "Orion RAG source inventory") | .id')"
  curl -fsS "${tls[@]}" -u "${REDMINE_ADMIN_USER}:${REDMINE_ADMIN_PASSWORD}" \
    -H 'Host: workhub.keplerops.lab' \
    "http://10.61.50.41:3000/issues/${issue_id}.json?include=attachments" >"${issue_state}"
  attachment_url="$(jq -r '.issue.attachments[]? | select(.filename == "orion-rag-source-inventory.json") | .content_url' "${issue_state}" | tail -1)"
  if [[ -n ${attachment_url} ]]; then
    curl -fsS "${tls[@]}" -u "${REDMINE_ADMIN_USER}:${REDMINE_ADMIN_PASSWORD}" "${attachment_url}" >"${current}"
  fi
  if [[ -z ${attachment_url} || $(sha256sum "${current}" | awk '{print $1}') != $(sha256sum "${payload}" | awk '{print $1}') ]]; then
    upload_token="$(curl -fsS "${tls[@]}" -u "${REDMINE_ADMIN_USER}:${REDMINE_ADMIN_PASSWORD}" \
      -H 'Host: workhub.keplerops.lab' -H 'Content-Type: application/octet-stream' \
      --data-binary "@${payload}" \
      'http://10.61.50.41:3000/uploads.json?filename=orion-rag-source-inventory.json' | jq -er '.upload.token')"
    curl -fsS "${tls[@]}" -u "${REDMINE_ADMIN_USER}:${REDMINE_ADMIN_PASSWORD}" \
      -H 'Host: workhub.keplerops.lab' -H 'Content-Type: application/json' -X PUT \
      --data "$(jq -n --arg token "${upload_token}" '{issue:{uploads:[{token:$token,filename:"orion-rag-source-inventory.json",content_type:"application/json",description:"Current protected connector ownership inventory"}]}}')" \
      "http://10.61.50.41:3000/issues/${issue_id}.json" >/dev/null
    attachment_url="$(curl -fsS "${tls[@]}" -u "${REDMINE_ADMIN_USER}:${REDMINE_ADMIN_PASSWORD}" \
      -H 'Host: workhub.keplerops.lab' \
      "http://10.61.50.41:3000/issues/${issue_id}.json?include=attachments" | \
      jq -er '.issue.attachments[] | select(.filename == "orion-rag-source-inventory.json") | .content_url' | tail -1)"
  fi
  M03_SOURCE_INVENTORY_URL="${attachment_url/http:\/\/10.61.50.41:3000/https:\/\/workhub.keplerops.lab}" \
  M03_SOURCE_INVENTORY_SHA256="$(sha256sum "${payload}" | awk '{print $1}')" \
    seed_haystack_source kep-m03-g
)

seed_evaluation_dependency() { seed_devpi_baseline; seed_npm_baseline; seed_enterprise_records "$1"; ensure_relay_basket orion-evaluation-worker; }
seed_maintainer_issue() { seed_npm_baseline; seed_enterprise_records "$1"; }
seed_rug_pull_baseline() { seed_npm_baseline; seed_enterprise_records "$1"; }
seed_phantom_resolution_workflow() { seed_enterprise_records "$1"; }
seed_writable_release_status() { seed_workhub_records "$1"; seed_enterprise_records "$1"; }
seed_model_card_check() { seed_npm_baseline; seed_enterprise_records "$1"; seed_haystack_source "$1"; ensure_relay_basket orion-model-card-audit; }
seed_rag_source_inventory() { seed_workhub_records "$1"; seed_protected_inventory_attachment; }
seed_index_source_join() {
  seed_enterprise_records "$1"
  seed_nextcloud_source
  seed_cinder_source
  seed_ingestion_provenance
  seed_haystack_source "$1"
  compose up -d --no-deps m03-ingestion-review >/dev/null
}
seed_stale_evaluation_runbook() { seed_workhub_records "$1"; seed_enterprise_records "$1"; seed_evaluation_reader_identity; seed_haystack_source "$1"; }
seed_handoff_chain() { seed_workhub_records "$1"; }
seed_delayed_review_record() { seed_workhub_records "$1"; }

apply_one() {
  local id=$1 handler
  known_operation "${id}" || die "unknown operation: ${id}"
  case "${id}" in
    kep-m03-a) handler=seed_evaluation_dependency ;;
    kep-m03-b) handler=seed_maintainer_issue ;;
    kep-m03-c) handler=seed_rug_pull_baseline ;;
    kep-m03-d) handler=seed_phantom_resolution_workflow ;;
    kep-m03-e) handler=seed_writable_release_status ;;
    kep-m03-f) handler=seed_model_card_check ;;
    kep-m03-g) handler=seed_rag_source_inventory ;;
    kep-m03-h) handler=seed_index_source_join ;;
    kep-m03-i) handler=seed_stale_evaluation_runbook ;;
    kep-m03-j) handler=seed_handoff_chain ;;
    kep-m03-k) handler=seed_delayed_review_record ;;
    *) die "missing apply dispatch: ${id}" ;;
  esac
  declare -F "${handler}" >/dev/null || die "missing handler: ${handler}"
  "${handler}" "${id}"
  log "reconciled ${id} into native enterprise services"
}

main() {
  local command id
  local -a ids=()
  for command in base64 curl docker jq python3; do
    command -v "${command}" >/dev/null || die "missing command: ${command}"
  done
  ensure_cinder_storage
  install -d -o 50000 -g 0 -m 0750 "${TEMPLATE_ROOT}/state/campaign-start/m03/relay"
  case "${OPERATION}" in
    all|kep-m03-a|kep-m03-d|kep-m03-e|kep-m03-f|kep-m03-j|kep-m03-k) install_airflow_workflows ;;
  esac
  if [[ ${OPERATION} != all ]]; then apply_one "${OPERATION}"; return; fi
  mapfile -t ids < <(jq -r '.[].id' "${MODULE_ROOT}/operations.json")
  for id in "${ids[@]}"; do apply_one "${id}"; done
}

main "$@"
