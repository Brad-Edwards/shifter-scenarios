#!/usr/bin/env bash
set -Eeuo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MODULE_ROOT
TEMPLATE_ROOT="$(cd "${MODULE_ROOT}/../../.." && pwd)"
readonly TEMPLATE_ROOT
readonly OPERATION="${1:-}"
readonly CINDER_RELAY_INTERNAL_URL="${CINDER_RELAY_INTERNAL_URL:-http://192.168.78.30:31080}"
readonly MINIO_MC_IMAGE="${MINIO_MC_IMAGE:-$(sed -n 's/^MINIO_MC_IMAGE=//p' "${TEMPLATE_ROOT}/engineering/component-lock.additions.env")}"

log() { printf '[campaign-m03-reset] %s\n' "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }

compose() {
  docker compose --project-directory "${TEMPLATE_ROOT}" \
    --env-file "${TEMPLATE_ROOT}/component-lock.env" \
    --env-file "${TEMPLATE_ROOT}/engineering/component-lock.additions.env" \
    -f "${TEMPLATE_ROOT}/compose.foundation.yaml" \
    -f "${TEMPLATE_ROOT}/compose.enterprise.yaml" \
    -f "${TEMPLATE_ROOT}/compose.engineering.yaml" "$@"
}

reset_relay_basket() {
  local id=$1 basket=$2 state token status flag access_key
  state="${TEMPLATE_ROOT}/state/campaign-start/m03/relay/${basket}.token"
  [[ -s ${state} ]] || return 0
  token="$(<"${state}")"
  flag="$(jq -er --arg id "${id}" '.[] | select(.id == $id) | .flag' "${MODULE_ROOT}/operations.json")"
  if curl -fsS -H 'Host: relay.cinder.cinder.lab' -H "Authorization: ${token}" \
    "${CINDER_RELAY_INTERNAL_URL}/api/baskets/${basket}/requests" | grep -Fq "${flag}"; then
    log "${id}: completion-bearing relay audit preserved"
    return 0
  fi
  status="$(curl -sS -o /dev/null -w '%{http_code}' -X DELETE \
    -H 'Host: relay.cinder.cinder.lab' -H "Authorization: ${token}" \
    "${CINDER_RELAY_INTERNAL_URL}/api/baskets/${basket}")"
  case "${status}" in 200|202|204|404) ;; *) die "${basket} relay reset returned HTTP ${status}" ;; esac
  access_key="campaign-v2/m03/relay/${basket}/access-token"
  docker run --rm --network kep-v2-cinder --entrypoint /bin/sh "${MINIO_MC_IMAGE}" -eu -c "
    mc alias set cinder http://cinder-minio:9000 cinder-operator Cinder-Operations-ObjectStore-T7v2Lm9q >/dev/null
    mc rm --force 'cinder/operations/${access_key}' >/dev/null 2>&1 || true
  "
  rm -f -- "${state}"
}

reset_workhub_issue() {
  local id=$1 subject=$2 status=$3 description=$4 flag
  flag="$(jq -er --arg id "${id}" '.[] | select(.id == $id) | .flag' "${MODULE_ROOT}/operations.json")"
  compose exec -T -e M03_RESET_SUBJECT="${subject}" -e M03_RESET_STATUS="${status}" \
    -e M03_RESET_DESCRIPTION="${description}" -e M03_RESET_FLAG="${flag}" redmine bundle exec rails runner /dev/stdin <<'RUBY'
issue = Issue.find_by!(subject: ENV.fetch('M03_RESET_SUBJECT'))
if issue.journals.any? { |journal| journal.notes.to_s.include?(ENV.fetch('M03_RESET_FLAG')) }
  puts 'completion-bearing WorkHub audit preserved'
  exit
end
workflow = User.find_by!(login: 'orion.workflow')
issue.init_journal(workflow, 'Workflow recovery restored the source after an incomplete run; prior journals and attachments remain in the audit history.')
issue.status = IssueStatus.find_by!(name: ENV.fetch('M03_RESET_STATUS'))
issue.description = ENV.fetch('M03_RESET_DESCRIPTION')
issue.save!
RUBY
}

reset_evaluation_dependency() { reset_relay_basket "$1" orion-evaluation-worker; }
reset_benign_adoption() { :; }
reset_rug_pull_proposal() { :; }
reset_phantom_attempt() { log "$1: registrar, factuality, access, and Airflow audit records preserved"; }
reset_release_status_source() {
  reset_workhub_issue "$1" 'Preview rollback readiness' 'Verification pending' $'Release Engineering owns this current-status source.\n\nCurrent status: Verification pending\nReview note: Awaiting current rollback drill.'
}
reset_poisoned_tool() { reset_relay_basket "$1" orion-model-card-audit; }
reset_rag_discovery_thread() { :; }
reset_ingestion_workspace() {
  docker run --rm --network kep-v2-cinder --entrypoint /bin/sh "${MINIO_MC_IMAGE}" -eu -c '
    mc alias set cinder http://cinder-minio:9000 cinder-operator Cinder-Operations-ObjectStore-T7v2Lm9q >/dev/null
    accepted=cinder/operations/campaign-v2/m03/index-source/accepted/manifest.json
    submission=cinder/operations/campaign-v2/m03/index-source/submission/index-source-join.yaml
    for attempt in 1 2 3 4 5 6; do
      if mc stat "$accepted" >/dev/null 2>&1; then
        echo "accepted exact-key Cinder handoff preserved" >&2
        exit 0
      fi
      mc stat "$submission" >/dev/null 2>&1 || exit 0
      [ "$attempt" -eq 6 ] || sleep 5
    done
    mc rm --force "$submission" >/dev/null 2>&1 || true
  '
}
reset_evaluation_reader_session() {
  local token user_id
  token="$(curl -fsS -X POST -H 'Content-Type: application/x-www-form-urlencoded' \
    --data-urlencode client_id=admin-cli --data-urlencode grant_type=password \
    --data-urlencode username=range-admin --data-urlencode password=KeplerV2-Training-Keycloak \
    http://10.61.20.20:8080/realms/master/protocol/openid-connect/token | jq -er '.access_token')"
  user_id="$(curl -fsS -H "Authorization: Bearer ${token}" \
    'http://10.61.20.20:8080/admin/realms/keplerops/users?username=eval.reader&exact=true' | jq -er '.[0].id')"
  curl -fsS -X POST -H "Authorization: Bearer ${token}" \
    "http://10.61.20.20:8080/admin/realms/keplerops/users/${user_id}/logout" >/dev/null
}
reset_rejected_handoffs() { log "$1: submitted attachments and immutable handoff audit preserved for a retry"; }
reset_delayed_activation() {
  reset_workhub_issue "$1" 'Orion partner compatibility review' 'New' $'Approval emits workhub.review.approved and starts the normal approved-review follow-up. Saving or viewing this record does not activate the workflow.'
}

main() {
  local handler
  [[ -n ${OPERATION} ]] || die "usage: $0 operation-id"
  for command in curl docker jq; do command -v "${command}" >/dev/null || die "missing command: ${command}"; done
  jq -e --arg id "${OPERATION}" 'any(.[]; .id == $id)' "${MODULE_ROOT}/operations.json" >/dev/null || die "unknown operation: ${OPERATION}"
  if "${MODULE_ROOT}/validate.sh" "${OPERATION}" >/dev/null 2>&1; then
    log "${OPERATION}: validated successful state preserved without mutation"
    return
  fi
  case "${OPERATION}" in
    kep-m03-a) handler=reset_evaluation_dependency ;;
    kep-m03-b) handler=reset_benign_adoption ;;
    kep-m03-c) handler=reset_rug_pull_proposal ;;
    kep-m03-d) handler=reset_phantom_attempt ;;
    kep-m03-e) handler=reset_release_status_source ;;
    kep-m03-f) handler=reset_poisoned_tool ;;
    kep-m03-g) handler=reset_rag_discovery_thread ;;
    kep-m03-h) handler=reset_ingestion_workspace ;;
    kep-m03-i) handler=reset_evaluation_reader_session ;;
    kep-m03-j) handler=reset_rejected_handoffs ;;
    kep-m03-k) handler=reset_delayed_activation ;;
    *) die "missing reset dispatch: ${OPERATION}" ;;
  esac
  declare -F "${handler}" >/dev/null || die "missing reset handler: ${handler}"
  "${handler}" "${OPERATION}"
  log "${OPERATION}: incomplete mutable state reconciled; successful and audit records preserved"
}

main "$@"
