#!/usr/bin/env bash
set -Eeuo pipefail

readonly MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly TEMPLATE_ROOT="$(cd "${MODULE_ROOT}/../../.." && pwd)"
readonly OPERATION="${1:-all}"
readonly QDRANT_WRITE_URL="${QDRANT_WRITE_URL:-http://10.61.50.72:6333}"
readonly QDRANT_WRITE_KEY="${QDRANT_WRITE_KEY:-KeplerV2-Training-Qdrant-Write}"
readonly NEXTCLOUD_URL="${NEXTCLOUD_URL:-http://10.61.30.23}"
readonly NEXTCLOUD_HOST="${NEXTCLOUD_HOST:-files.keplerops.lab}"
readonly CINDER_RELAY_URL="${CINDER_RELAY_INTERNAL_URL:-http://192.168.78.30:31080}"
readonly JUPYTER_IMAGE="${JUPYTER_IMAGE:-$(sed -n 's/^JUPYTER_IMAGE=//p' "${TEMPLATE_ROOT}/component-lock.env")}"
readonly MINIO_MC_IMAGE="${MINIO_MC_IMAGE:-$(sed -n 's/^MINIO_MC_IMAGE=//p' "${TEMPLATE_ROOT}/engineering/component-lock.additions.env")}"

# shellcheck source=../../../seeding/config.env
source "${TEMPLATE_ROOT}/seeding/config.env"

log() { printf '[campaign-m03] %s\n' "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }

compose() {
  docker compose --project-directory "${TEMPLATE_ROOT}" \
    --env-file "${TEMPLATE_ROOT}/component-lock.env" \
    --env-file "${TEMPLATE_ROOT}/engineering/component-lock.additions.env" \
    -f "${TEMPLATE_ROOT}/compose.foundation.yaml" \
    -f "${TEMPLATE_ROOT}/compose.enterprise.yaml" \
    -f "${TEMPLATE_ROOT}/compose.engineering.yaml" "$@"
}

known_operation() {
  jq -e --arg id "$1" 'any(.[]; .id == $id)' "${MODULE_ROOT}/operations.json" >/dev/null
}

seed_enterprise_records() {
  FORGEJO_API_URL="${FORGEJO_API_URL}" \
  FORGEJO_ADMIN_USER="${FORGEJO_ADMIN_USER}" \
  FORGEJO_ADMIN_PASSWORD="${FORGEJO_ADMIN_PASSWORD}" \
  QDRANT_URL="${QDRANT_WRITE_URL}" QDRANT_WRITE_KEY="${QDRANT_WRITE_KEY}" \
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

install_airflow_workflows() {
  install -m 0644 "${MODULE_ROOT}/runtime/orion_m03_workflows.py" \
    "${TEMPLATE_ROOT}/engineering/airflow/dags/orion_m03_workflows.py"
  compose exec -T airflow-scheduler airflow dags reserialize >/dev/null
  compose exec -T airflow-scheduler airflow dags unpause orion_approved_review_follow_up >/dev/null
}

seed_nextcloud_source() (
  local path='Orion%20Review%20Room/Failed%20Ingestion'
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

seed_jupyter_source() (
  local source
  source="$(mktemp)"
  trap 'rm -f "${source}"' EXIT
  build_ingestion_source "${source}"
  docker volume create 'kep-v2-jupyter-eval.reader' >/dev/null
  docker run --rm -i --user root -v 'kep-v2-jupyter-eval.reader:/work' \
    "${JUPYTER_IMAGE}" python -c '
import os
import pathlib
import sys

target = pathlib.Path("/work/failed-ingestion/source/release-criteria.json")
target.parent.mkdir(parents=True, exist_ok=True)
target.write_bytes(sys.stdin.buffer.read())
os.chown(target, 1000, 100)
os.chmod(target, 0o640)
os.setxattr(target, b"user.ingest_reference", b"deed861d}")
' < "${source}"
)

build_ingestion_source() {
  python3 - "${MODULE_ROOT}/payloads/kep-m03-h.json" "$1" <<'PY'
import json
import pathlib
import sys

payload = json.loads(pathlib.Path(sys.argv[1]).read_text())
for key in ("qdrant_payload", "source_extended_attribute", "report_path"):
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
    --arg path 'Partner Reviews/Orion/release-criteria.md' \
    '{document_id:$document,source_sha256:$sha,source_relative_path:$path,ingestion_status:"failed-after-vector-write"}' \
    >"${workspace}/provenance.json"
  docker run --rm --network kep-v2-data -v "${workspace}/provenance.json:/provenance.json:ro" \
    "${MINIO_MC_IMAGE}" sh -eu -c "
      mc alias set kepler http://minio:9000 kepler-minio KeplerV2-Training-Minio-Object-Store >/dev/null
      cat >/tmp/ingest-reader.json <<'JSON'
      {\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Action\":[\"s3:GetBucketLocation\"],\"Resource\":[\"arn:aws:s3:::artifacts\"]},{\"Effect\":\"Allow\",\"Action\":[\"s3:GetObject\"],\"Resource\":[\"arn:aws:s3:::artifacts/ingest/orion_partner_intake/*\"]}]}
JSON
      mc admin policy create kepler orion-ingest-diagnostic-read /tmp/ingest-reader.json >/dev/null
      mc admin user add kepler ingest-diagnostic-reader KeplerV2-Orion-Ingest-Diagnostic >/dev/null 2>&1 || true
      mc admin policy attach kepler orion-ingest-diagnostic-read --user ingest-diagnostic-reader >/dev/null
      mc cp /provenance.json 'kepler/artifacts/${object_key}' >/dev/null
    "
  cat >"${workspace}/README.md" <<EOF
# Failed Ingestion Diagnostic Workspace

Join the Qdrant point metadata, the provenance object, and the mounted source.
The object credential can retrieve an exact key from the artifacts bucket but cannot list it.

Endpoint: http://minio:9000
Access key: ingest-diagnostic-reader
Secret key: KeplerV2-Orion-Ingest-Diagnostic
Key template: ingest/{collection}/{document_id}/{source_sha256}.yaml
EOF
  docker run --rm --user root -v 'kep-v2-jupyter-eval.reader:/work' -v "${workspace}:/seed:ro" \
    "${JUPYTER_IMAGE}" sh -eu -c '
      install -m 0640 -o 1000 -g 100 /seed/README.md /work/failed-ingestion/README.md
    '
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

Onboarding reference: FLAG{8965ae2bb182f564}
EOF
    chown 1000:100 /work/onboarding/ORION-EVALUATION-READER.md
    chmod 0640 /work/onboarding/ORION-EVALUATION-READER.md
  '
}

ensure_relay_basket() {
  local basket=$1 token_file response
  token_file="${TEMPLATE_ROOT}/state/campaign-start/m03/relay/${basket}.token"
  install -d -m 0750 "$(dirname "${token_file}")"
  if [[ -s ${token_file} ]]; then return; fi
  response="$(curl -fsS -X POST -H 'Host: relay.cinder.cinder.lab' \
    -H 'Content-Type: application/json' --data '{"capacity":100}' \
    "${CINDER_RELAY_URL}/api/baskets/${basket}")"
  jq -er '.token' <<<"${response}" >"${token_file}"
  chmod 0600 "${token_file}"
}

seed_evaluation_dependency() { seed_enterprise_records "$1"; seed_devpi_baseline; ensure_relay_basket m03-evaluation-worker; }
seed_maintainer_issue() { seed_enterprise_records "$1"; }
seed_rug_pull_baseline() { seed_enterprise_records "$1"; }
seed_phantom_resolution_workflow() { seed_enterprise_records "$1"; ensure_relay_basket m03-phantom-dependency; }
seed_writable_release_status() { seed_workhub_records "$1"; seed_enterprise_records "$1"; }
seed_model_card_check() { seed_enterprise_records "$1"; ensure_relay_basket m03-model-card; }
seed_rag_source_inventory() { seed_workhub_records "$1"; seed_enterprise_records "$1"; }
seed_index_source_join() { seed_enterprise_records "$1"; seed_nextcloud_source; seed_jupyter_source; seed_ingestion_provenance; }
seed_stale_evaluation_runbook() { seed_workhub_records "$1"; seed_enterprise_records "$1"; seed_evaluation_reader_identity; }
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
  for command in base64 curl docker jq python3; do
    command -v "${command}" >/dev/null || die "missing command: ${command}"
  done
  case "${OPERATION}" in
    all|kep-m03-a|kep-m03-d|kep-m03-e|kep-m03-j|kep-m03-k) install_airflow_workflows ;;
  esac
  if [[ ${OPERATION} != all ]]; then apply_one "${OPERATION}"; return; fi
  while IFS= read -r id; do apply_one "${id}"; done < <(jq -r '.[].id' "${MODULE_ROOT}/operations.json")
}

main "$@"
