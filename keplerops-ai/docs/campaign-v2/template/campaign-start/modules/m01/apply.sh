#!/usr/bin/env bash
set -Eeuo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MODULE_ROOT
TEMPLATE_ROOT="$(cd "${MODULE_ROOT}/../../.." && pwd)"
readonly TEMPLATE_ROOT
readonly PAYLOAD_ROOT="${MODULE_ROOT}/payloads"
readonly STATE_ROOT="${CAMPAIGN_STATE_ROOT:-${TEMPLATE_ROOT}/state/campaign-start}/m01"
readonly QDRANT_URL="${QDRANT_WRITE_URL:-http://10.61.50.72:6333}"
readonly QDRANT_KEY="${QDRANT_WRITE_KEY:-KeplerV2-Training-Qdrant-Write}"
readonly QDRANT_COLLECTION="${QDRANT_COLLECTION:-orion_partner_intake}"
readonly NEXTCLOUD_URL="${NEXTCLOUD_URL:-http://10.61.30.23}"
readonly NEXTCLOUD_HOST="${NEXTCLOUD_HOST:-files.keplerops.lab}"
readonly NEXTCLOUD_ADMIN_PASSWORD="${NEXTCLOUD_ADMIN_PASSWORD:-KeplerV2-Training-Nextcloud}"
readonly NEXTCLOUD_SERVICE_USER=svc-orion-assistant
readonly NEXTCLOUD_SERVICE_PASSWORD=KAI-M01-Nextcloud-Assistant-24d0a4c8
readonly WORKHUB_AGENT_PASSWORD=KAI-M01-WorkHub-Agent-f1468d2a
readonly CINDER_MAIL_USER=cinder.operator
readonly CINDER_MAIL_PASSWORD=KeplerV2-Training-Cinder
readonly FORGEJO_URL="${FORGEJO_URL:-http://10.61.40.20:3000}"
readonly FORGEJO_SERVICE_PASSWORD=KAI-M01-Forgejo-Agent-b1bf62e9
readonly FORGEJO_CONTRIBUTOR=cinder.operator
readonly FORGEJO_CONTRIBUTOR_PASSWORD='Kp!f62ecb36a90c84542474'
readonly K3S01_SSH_TARGET="${K3S01_SSH_TARGET:-kepler@192.168.78.30}"
readonly K3S01_SSH_KEY="${K3S01_SSH_KEY:-/root/.ssh/keplerops-v2}"
readonly SSH=(ssh -i "${K3S01_SSH_KEY}" -o BatchMode=yes -o StrictHostKeyChecking=accept-new)

die() { printf '[m01] ERROR: %s\n' "$*" >&2; exit 1; }
log() { printf '[m01] %s\n' "$*" >&2; }

require_commands() {
  local command
  for command in curl docker install jq python3 sha256sum ssh; do
    command -v "${command}" >/dev/null 2>&1 || die "missing command: ${command}"
  done
  [[ -r ${K3S01_SSH_KEY} ]] || die "k3s01 SSH key is unavailable: ${K3S01_SSH_KEY}"
  "${SSH[@]}" "${K3S01_SSH_TARGET}" \
    'sudo test -s /etc/rancher/k3s/k3s.yaml && sudo k3s kubectl get node k3s01' >/dev/null || \
    die 'k3s01 Kubernetes control plane is unavailable'
}

compose() {
  COMPOSE_BAKE=false COMPOSE_PARALLEL_LIMIT=1 docker compose --project-directory "${TEMPLATE_ROOT}" \
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

flag_for() {
  jq -er --arg id "$1" '.[] | select(.id == $id) | .flag' "${MODULE_ROOT}/operations.json"
}

feature_vector() {
  python3 -c '
import hashlib, json, math, re, sys
vector = [0.0] * 128
for token in re.findall(r"[a-z0-9_]+", sys.stdin.read().lower()):
    digest = hashlib.sha256(token.encode()).digest()
    bucket = int.from_bytes(digest[:4], "big") % 128
    vector[bucket] += 1.0 if digest[4] & 1 else -1.0
norm = math.sqrt(sum(value * value for value in vector)) or 1.0
json.dump([value / norm for value in vector], sys.stdout, separators=(",", ":"))
'
}

point_uuid() {
  local digest
  digest="$(printf '%s' "$1" | sha256sum | cut -c1-32)"
  printf '%s-%s-%s-%s-%s\n' "${digest:0:8}" "${digest:8:4}" "${digest:12:4}" "${digest:16:4}" "${digest:20:12}"
}

ensure_collection() {
  curl -fsS -X PUT -H "api-key: ${QDRANT_KEY}" -H 'Content-Type: application/json' \
    --data '{"vectors":{"size":128,"distance":"Cosine"}}' \
    "${QDRANT_URL}/collections/${QDRANT_COLLECTION}" >/dev/null 2>&1 || true
}

seed_protected_source() {
  local operation=$1 record vector body
  record="$(jq -ce --arg operation "${operation}" '.[] | select(.operation == $operation)' "${PAYLOAD_ROOT}/orion-protected-sources.json")"
  [[ -n ${record} ]] || die "no protected source for ${operation}"
  vector="$(jq -r '.text' <<<"${record}" | feature_vector)"
  body="$(jq -cn --arg id "$(point_uuid "${operation}")" --argjson vector "${vector}" \
    --argjson payload "$(jq -c 'del(.operation)' <<<"${record}")" '{points:[{id:$id,vector:$vector,payload:$payload}]}')"
  curl -fsS -X PUT -H "api-key: ${QDRANT_KEY}" -H 'Content-Type: application/json' \
    --data-binary "${body}" "${QDRANT_URL}/collections/${QDRANT_COLLECTION}/points?wait=true" >/dev/null
}

seed_workhub() {
  local output
  output="$(docker exec -i \
    -e M01_AGENT_PASSWORD="${WORKHUB_AGENT_PASSWORD}" \
    kep-v2-redmine bundle exec rails runner /dev/stdin < "${MODULE_ROOT}/runtime/seed_redmine.rb" | \
    grep -E '^\{.*\}$' | tail -n1)"
  jq -e '.project == "orion-release"' <<<"${output}" >/dev/null || die 'WorkHub release project did not seed'
  install -d -m 0750 "${STATE_ROOT}"
  jq -r --arg review_password 'KAI-Review01-WorkHub-c72b918e' \
    --arg g "$(flag_for kep-m01-g)" --arg h "$(flag_for kep-m01-h)" --arg j "$(flag_for kep-m01-j)" \
    --arg integration_token 'orion-job-7e6fd2f22d64416d' \
    --arg m02_l "$(jq -er '.[] | select(.id == "kep-m02-l") | .flag' "${MODULE_ROOT}/../m02/operations.json")" '
      [
        "RELEASE_TRACKER_ID=" + (.release_tracker_id|tostring),
        "REVIEW_TRACKER_ID=" + (.review_tracker_id|tostring),
        "STATUS_NEW_ID=" + (.statuses.New|tostring),
        "STATUS_QUEUED_ID=" + (.statuses.Queued|tostring),
        "STATUS_RUNNING_ID=" + (.statuses.Running|tostring),
        "STATUS_COMPLETED_ID=" + (.statuses.Completed|tostring),
        "STATUS_REJECTED_ID=" + (.statuses.Rejected|tostring),
        "RECORD_CLASS_FIELD_ID=" + (.record_class_field_id|tostring),
        "REPORTER_ROLE_ID=" + (.reporter_role_id|tostring),
        "CANDIDATE_LOADER_REFERENCE=" + $g,
        "HELPER_REFERENCE=" + $h,
        "INTEGRATION_REFERENCE=" + $j,
        "INTEGRATION_JOB_TOKEN=" + $integration_token,
        "M02_L_ACCEPTED_REFERENCE=" + $m02_l
      ] | .[]' <<<"${output}" > "${STATE_ROOT}/runtime.env"
  chmod 0600 "${STATE_ROOT}/runtime.env"
  jq -c . <<<"${output}" > "${STATE_ROOT}/workhub-schema.json"
}

nextcloud_occ() { docker exec -u www-data kep-v2-nextcloud php occ "$@"; }

seed_nextcloud_sources() {
  if ! nextcloud_occ user:info "${NEXTCLOUD_SERVICE_USER}" >/dev/null 2>&1; then
    docker exec -u www-data -e OC_PASS="${NEXTCLOUD_SERVICE_PASSWORD}" kep-v2-nextcloud \
      php occ user:add --password-from-env --display-name 'Orion Release Assistant' "${NEXTCLOUD_SERVICE_USER}" >/dev/null
  fi
  local path code
  for path in 'Release%20Engineering' 'Release%20Engineering/Confidential'; do
    code="$(curl -sS -o /dev/null -w '%{http_code}' -X MKCOL \
      -u "${NEXTCLOUD_SERVICE_USER}:${NEXTCLOUD_SERVICE_PASSWORD}" -H "Host: ${NEXTCLOUD_HOST}" \
      "${NEXTCLOUD_URL}/remote.php/dav/files/${NEXTCLOUD_SERVICE_USER}/${path}")"
    [[ ${code} == 201 || ${code} == 405 ]] || die "Nextcloud MKCOL returned ${code}"
  done
  curl -fsS -X PUT -u "${NEXTCLOUD_SERVICE_USER}:${NEXTCLOUD_SERVICE_PASSWORD}" -H "Host: ${NEXTCLOUD_HOST}" \
    --data-binary "@${PAYLOAD_ROOT}/confidential-release-bundle.md" \
    "${NEXTCLOUD_URL}/remote.php/dav/files/${NEXTCLOUD_SERVICE_USER}/Release%20Engineering/Confidential/orion-edge-2026.08.md" >/dev/null
}

seed_calendar() {
  local calendar_url="${NEXTCLOUD_URL}/remote.php/dav/calendars/${NEXTCLOUD_SERVICE_USER}/orion-release" code event
  code="$(curl -sS -o /dev/null -w '%{http_code}' -X MKCALENDAR \
    -u "${NEXTCLOUD_SERVICE_USER}:${NEXTCLOUD_SERVICE_PASSWORD}" -H "Host: ${NEXTCLOUD_HOST}" \
    -H 'Content-Type: application/xml; charset=utf-8' \
    --data '<?xml version="1.0" encoding="utf-8"?><c:mkcalendar xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav"><d:set><d:prop><d:displayname>Orion Release</d:displayname></d:prop></d:set></c:mkcalendar>' \
    "${calendar_url}/")"
  [[ ${code} == 201 || ${code} == 405 ]] || die "CalDAV calendar creation returned ${code}"
  event="$(jq -rn --arg flag "$(flag_for kep-m01-b)" '
    "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//KeplerOps//Orion Release//EN\r\nBEGIN:VEVENT\r\nUID:orion-edge-2026.08@keplerops.lab\r\nDTSTAMP:20260802T090000Z\r\nDTSTART:20260804T193000Z\r\nDTEND:20260804T200000Z\r\nSUMMARY:Orion Edge isolated validation\r\nLOCATION:orion-release-bridge\r\nDESCRIPTION:Restricted candidate record. Calendar reference " + $flag + "\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"')"
  curl -fsS -X PUT -u "${NEXTCLOUD_SERVICE_USER}:${NEXTCLOUD_SERVICE_PASSWORD}" -H "Host: ${NEXTCLOUD_HOST}" \
    -H 'Content-Type: text/calendar; charset=utf-8' --data-binary "${event}" \
    "${calendar_url}/orion-edge-2026.08.ics" >/dev/null
}

forgejo_basic() { printf '%s' "svc-orion-agent:${FORGEJO_SERVICE_PASSWORD}"; }

forgejo_put_file() {
  local path=$1 source=$2 payload current_sha method=POST
  current_sha="$(curl -fsS -u "$(forgejo_basic)" "${FORGEJO_URL}/api/v1/repos/svc-orion-agent/release-runbook-validation/contents/${path}" 2>/dev/null | jq -r '.sha // empty' || true)"
  [[ -z ${current_sha} ]] || method=PUT
  payload="$(jq -cn --arg content "$(base64 -w0 < "${source}")" --arg message "Update ${path}" --arg sha "${current_sha}" \
    '{content:$content,message:$message,branch:"main"} + (if $sha == "" then {} else {sha:$sha} end)')"
  curl -fsS -u "$(forgejo_basic)" -X "${method}" -H 'Content-Type: application/json' --data-binary "${payload}" \
    "${FORGEJO_URL}/api/v1/repos/svc-orion-agent/release-runbook-validation/contents/${path}" >/dev/null
}

seed_forgejo_validation() {
  docker exec -u git kep-v2-forgejo forgejo admin user create --config /data/gitea/conf/app.ini \
    --username svc-orion-agent --password "${FORGEJO_SERVICE_PASSWORD}" --email svc-orion-agent@keplerops.lab \
    --must-change-password=false >/dev/null 2>&1 || true
  docker exec -u git kep-v2-forgejo forgejo admin user create --config /data/gitea/conf/app.ini \
    --username "${FORGEJO_CONTRIBUTOR}" --password "${FORGEJO_CONTRIBUTOR_PASSWORD}" \
    --email cinder.operator@cinder.lab --must-change-password=false >/dev/null 2>&1 || \
    docker exec -u git kep-v2-forgejo forgejo admin user change-password --config /data/gitea/conf/app.ini \
      --username "${FORGEJO_CONTRIBUTOR}" --password "${FORGEJO_CONTRIBUTOR_PASSWORD}" >/dev/null
  curl -fsS -u "$(forgejo_basic)" -X POST -H 'Content-Type: application/json' \
    --data '{"name":"release-runbook-validation","private":true,"auto_init":true,"default_branch":"main","description":"Isolated Orion release runbook validation"}' \
    "${FORGEJO_URL}/api/v1/user/repos" >/dev/null 2>&1 || true
  forgejo_put_file '.forgejo/workflows/validate.yml' "${PAYLOAD_ROOT}/runbook-validation.yml"
  forgejo_put_file 'validate_runbook.py' "${MODULE_ROOT}/runtime/validate_runbook.py"
  curl -fsS -u "$(forgejo_basic)" -X PUT -H 'Content-Type: application/json' \
    --data '{"permission":"write"}' \
    "${FORGEJO_URL}/api/v1/repos/svc-orion-agent/release-runbook-validation/collaborators/${FORGEJO_CONTRIBUTOR}" >/dev/null
  curl -fsS -u "$(forgejo_basic)" \
    "${FORGEJO_URL}/api/v1/repos/svc-orion-agent/release-runbook-validation/collaborators/${FORGEJO_CONTRIBUTOR}/permission" | \
    jq -e --arg login "${FORGEJO_CONTRIBUTOR}" \
      '.user.login == $login and (.permission == "write" or .permission == "admin")' >/dev/null || \
    die 'Forgejo did not persist the external audit contributor grant'
  local token_json token
  while IFS= read -r token_id; do
    curl -fsS -u "$(forgejo_basic)" -X DELETE "${FORGEJO_URL}/api/v1/users/svc-orion-agent/tokens/${token_id}" >/dev/null
  done < <(curl -fsS -u "$(forgejo_basic)" "${FORGEJO_URL}/api/v1/users/svc-orion-agent/tokens" | jq -r '.[] | select(.name == "m01-native-validation") | .id')
  token_json="$(curl -fsS -u "$(forgejo_basic)" -X POST -H 'Content-Type: application/json' \
    --data '{"name":"m01-native-validation","scopes":["read:repository","read:issue"]}' \
    "${FORGEJO_URL}/api/v1/users/svc-orion-agent/tokens")"
  token="$(jq -er '.sha1' <<<"${token_json}")"
  curl -fsS --user 'range-admin:KeplerV2-Training-Forgejo-Admin' -X POST -H 'Content-Type: application/json' \
    --data '{"name":"orion-partner-contributions","private":true,"auto_init":true,"default_branch":"main","description":"Accepted external Orion package contributions"}' \
    "${FORGEJO_URL}/api/v1/orgs/keplerops/repos" >/dev/null 2>&1 || true
  curl -fsS --user 'range-admin:KeplerV2-Training-Forgejo-Admin' -X PUT -H 'Content-Type: application/json' \
    --data '{"permission":"read"}' \
    "${FORGEJO_URL}/api/v1/repos/keplerops/orion-partner-contributions/collaborators/svc-orion-agent" >/dev/null
  curl -fsS -u "$(forgejo_basic)" -X PUT -H 'Content-Type: application/json' \
    --data "$(jq -cn --arg value "$(flag_for kep-m01-c)" '{data:$value}')" \
    "${FORGEJO_URL}/api/v1/repos/svc-orion-agent/release-runbook-validation/actions/secrets/M01_C_VALIDATION_REFERENCE" >/dev/null
  curl -fsS -u "$(forgejo_basic)" -X PUT -H 'Content-Type: application/json' \
    --data "$(jq -cn --arg value "${token}" '{data:$value}')" \
    "${FORGEJO_URL}/api/v1/repos/svc-orion-agent/release-runbook-validation/actions/secrets/VALIDATION_READER_TOKEN" >/dev/null
  curl -fsS -u "$(forgejo_basic)" -X PUT -H 'Content-Type: application/json' \
    --data "$(jq -cn --arg value 'KeplerV2-Training-Redis' '{data:$value}')" \
    "${FORGEJO_URL}/api/v1/repos/svc-orion-agent/release-runbook-validation/actions/secrets/ORION_REDIS_PASSWORD" >/dev/null
  curl -fsS -u "$(forgejo_basic)" -X PUT -H 'Content-Type: application/json' \
    --data "$(jq -cn --arg value 'http://10.61.80.14:9200' '{data:$value}')" \
    "${FORGEJO_URL}/api/v1/repos/svc-orion-agent/release-runbook-validation/actions/secrets/ORION_OPENSEARCH_URL" >/dev/null
  printf '%s' "${token}" > "${STATE_ROOT}/forgejo-agent-token"
  chmod 0600 "${STATE_ROOT}/forgejo-agent-token"
  printf 'M02_ACCEPTED_FORGEJO_TOKEN=%s\n' "${token}" >>"${STATE_ROOT}/runtime.env"
}

seed_rabbit_queues() {
  local queue
  for queue in orion.m01.review orion.m01.analysis orion.m01.integration; do
    curl -fsS -u 'kepler:KeplerV2-Training-Rabbit' -X PUT -H 'Content-Type: application/json' \
      --data '{"durable":true,"auto_delete":false,"arguments":{}}' \
      "http://10.61.50.12:15672/api/queues/keplerops/${queue}" >/dev/null
  done
}

configure_mcp() {
  local schema token patch
  schema="$(cat "${STATE_ROOT}/workhub-schema.json")"
  token="$(cat "${STATE_ROOT}/forgejo-agent-token")"
  patch="$(jq -cn \
    --arg wh_password "${WORKHUB_AGENT_PASSWORD}" --arg cal_password "${NEXTCLOUD_SERVICE_PASSWORD}" --arg nc_password "${NEXTCLOUD_SERVICE_PASSWORD}" \
    --arg token "${token}" --arg record "$(jq -r '.record_class_field_id' <<<"${schema}")" \
    --arg actor "$(jq -r '.requesting_actor_field_id' <<<"${schema}")" --arg tracker "$(jq -r '.release_tracker_id' <<<"${schema}")" \
    --arg followup "$(jq -r '.statuses["Needs-partner-follow-up"]' <<<"${schema}")" \
    --arg new "$(jq -r '.statuses.New' <<<"${schema}")" --arg rejected "$(jq -r '.statuses.Rejected' <<<"${schema}")" \
    --arg verified "$(jq -r '.statuses.Verified' <<<"${schema}")" --arg approved "$(jq -r '.statuses.Approved' <<<"${schema}")" \
    --arg completed "$(jq -r '.statuses.Completed' <<<"${schema}")" \
    --arg imap_user "${CINDER_MAIL_USER}" --arg imap_password "${CINDER_MAIL_PASSWORD}" '
      {stringData:{
        M01_WORKHUB_URL:"http://192.168.78.1:13000", M01_WORKHUB_HOST:"workhub.keplerops.lab",
        M01_WORKHUB_PROJECT:"orion-release", M01_WORKHUB_USER:"svc-orion-agent", M01_WORKHUB_PASSWORD:$wh_password,
        M01_RECORD_CLASS_FIELD_ID:$record, M01_REQUESTING_ACTOR_FIELD_ID:$actor, M01_RELEASE_TRACKER_ID:$tracker,
        M01_FOLLOWUP_STATUS_ID:$followup, M01_NEW_STATUS_ID:$new, M01_REJECTED_STATUS_ID:$rejected,
        M01_VERIFIED_STATUS_ID:$verified, M01_APPROVED_STATUS_ID:$approved,
        M01_COMPLETED_STATUS_ID:$completed, M01_QDRANT_URL:"http://192.168.78.1:16333",
        M01_QDRANT_KEY:"KeplerV2-Training-Qdrant-Read", M01_QDRANT_COLLECTION:"orion_partner_intake",
        M01_CALDAV_URL:"http://10.61.30.23/remote.php/dav", M01_CALDAV_USER:"svc-orion-assistant",
        M01_CALDAV_PASSWORD:$cal_password, M01_NEXTCLOUD_URL:"http://10.61.30.23",
        M01_NEXTCLOUD_HOST:"files.keplerops.lab", M01_NEXTCLOUD_USER:"svc-orion-assistant", M01_NEXTCLOUD_PASSWORD:$nc_password,
        M01_FORGEJO_URL:"http://192.168.78.1:3000", M01_FORGEJO_TOKEN:$token,
        M01_VALIDATION_REPOSITORY:"svc-orion-agent/release-runbook-validation", M01_SMTP_HOST:"10.61.10.20", M01_SMTP_PORT:"25",
        M01_IMAP_HOST:"10.61.90.20", M01_IMAP_PORT:"143", M01_IMAP_USER:$imap_user, M01_IMAP_PASSWORD:$imap_password,
        M01_IMAP_READBACK_ATTEMPTS:"12", M01_IMAP_READBACK_INTERVAL_SECONDS:"1"
      }}')"
  printf '%s' "${patch}" | "${SSH[@]}" "${K3S01_SSH_TARGET}" \
    'sudo k3s kubectl -n orion-platform patch secret orion-agent-runtime --type merge --patch-file=/dev/stdin' >/dev/null
  "${SSH[@]}" "${K3S01_SSH_TARGET}" sudo k3s kubectl apply -f - \
    < "${TEMPLATE_ROOT}/platform/manifests/opa.yaml" >/dev/null
  "${SSH[@]}" "${K3S01_SSH_TARGET}" \
    'sudo k3s kubectl -n orion-platform rollout restart deployment/opa deployment/orion-agent deployment/orion-mcp >/dev/null &&
     sudo k3s kubectl -n orion-platform rollout status deployment/opa --timeout=5m &&
     sudo k3s kubectl -n orion-platform rollout status deployment/orion-agent --timeout=5m &&
     sudo k3s kubectl -n orion-platform rollout status deployment/orion-mcp --timeout=5m' >/dev/null || \
    die 'M01 platform workloads did not complete their rollout'
}

wait_workers_healthy() {
  local -a services=(m01-review-dispatcher m01-review-worker m01-analysis-worker m01-integration-worker)
  local -a pending=()
  local service container health runtime attempts
  for ((attempts = 1; attempts <= 60; attempts++)); do
    pending=()
    for service in "${services[@]}"; do
      container="$(compose ps -a -q "${service}")"
      [[ -n ${container} ]] || die "M01 worker container is absent: ${service}"
      read -r runtime health < <(docker inspect --format '{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}' "${container}")
      case "${runtime}:${health}" in
        running:healthy) ;;
        running:starting) pending+=("${service}") ;;
        *)
          docker logs --tail 40 "${container}" >&2 || true
          die "M01 worker failed its dependency probe: ${service} (${runtime}:${health})"
          ;;
      esac
    done
    ((${#pending[@]} == 0)) && return
    sleep 3
  done
  for service in "${pending[@]}"; do
    container="$(compose ps -a -q "${service}")"
    [[ -z ${container} ]] || docker logs --tail 40 "${container}" >&2 || true
  done
  die "M01 workers did not become healthy: ${pending[*]}"
}

deploy_workers() {
  compose up -d --no-deps airflow-api airflow-scheduler airflow-dag-processor airflow-triggerer airflow-worker >/dev/null
  compose up -d --build m01-review-dispatcher m01-review-worker m01-analysis-worker m01-integration-worker >/dev/null
  wait_workers_healthy
}

seed_review_process() {
  local path code
  for path in 'Partner%20Rooms' 'Partner%20Rooms/Cinder%20Labs' 'Partner%20Rooms/Cinder%20Labs/Policy%20Exceptions'; do
    code="$(curl -sS -o /dev/null -w '%{http_code}' -X MKCOL -u 'reviewer:KeplerV2-Training-Reviewer' \
      -H "Host: ${NEXTCLOUD_HOST}" "${NEXTCLOUD_URL}/remote.php/dav/files/reviewer/${path}")"
    [[ ${code} == 201 || ${code} == 405 ]] || die "review-room MKCOL returned ${code}"
  done
  curl -fsS -X PUT -u 'reviewer:KeplerV2-Training-Reviewer' -H "Host: ${NEXTCLOUD_HOST}" \
    --data-binary "@${PAYLOAD_ROOT}/review-process.md" \
    "${NEXTCLOUD_URL}/remote.php/dav/files/reviewer/Partner%20Rooms/Cinder%20Labs/Partner%20Evaluation%20Process.md" >/dev/null
}

apply_kep_m01_a() { seed_protected_source "$1"; }
apply_kep_m01_b() { seed_calendar; }
apply_kep_m01_c() { :; } # canonical repository and scoped token are reconciled once before Orion is configured
apply_kep_m01_d() { seed_protected_source "$1"; }
apply_kep_m01_e() { seed_protected_source "$1"; seed_review_process; }
apply_kep_m01_f() { seed_review_process; seed_nextcloud_sources; }
apply_kep_m01_g() { seed_review_process; seed_rabbit_queues; }
apply_kep_m01_h() { seed_review_process; seed_rabbit_queues; }
apply_kep_m01_i() {
  docker exec -u 0 kep-v2-langflow install -d -m 0755 /opt/keplerops/preview
  docker cp "${PAYLOAD_ROOT}/operations-handoff.md" kep-v2-langflow:/opt/keplerops/preview/operations-handoff.md
}
apply_kep_m01_j() { seed_rabbit_queues; }

apply_one() {
  local operation=$1 function
  function="apply_${operation//-/_}"
  known_operation "${operation}" || die "unknown operation: ${operation}"
  declare -F "${function}" >/dev/null || die "missing apply handler: ${function}"
  "${function}" "${operation}"
  install -d -m 0750 "${STATE_ROOT}/applied"
  printf '%s\n' "${operation}" > "${STATE_ROOT}/applied/${operation}"
  log "applied ${operation}"
}

main() {
  local requested=${1:-all} operation
  require_commands
  install -d -m 0750 "${STATE_ROOT}"
  ensure_collection
  seed_workhub
  seed_nextcloud_sources
  seed_forgejo_validation
  seed_rabbit_queues
  configure_mcp
  deploy_workers
  if [[ ${requested} != all ]]; then apply_one "${requested}"; return; fi
  while IFS= read -r operation; do apply_one "${operation}"; done < <(jq -r '.[].id' "${MODULE_ROOT}/operations.json")
}

main "$@"
