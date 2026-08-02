#!/usr/bin/env bash
set -Eeuo pipefail

readonly MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly TEMPLATE_ROOT="$(cd "${MODULE_ROOT}/../../.." && pwd)"
readonly OPERATION="${1:-}"
readonly CINDER_RELAY_INTERNAL_URL="${CINDER_RELAY_INTERNAL_URL:-http://192.168.78.30:31080}"
readonly JUPYTER_IMAGE="${JUPYTER_IMAGE:-$(sed -n 's/^JUPYTER_IMAGE=//p' "${TEMPLATE_ROOT}/component-lock.env")}"

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
  local basket=$1 state token status
  state="${TEMPLATE_ROOT}/state/campaign-start/m03/relay/${basket}.token"
  [[ -s ${state} ]] || return 0
  token="$(<"${state}")"
  status="$(curl -sS -o /dev/null -w '%{http_code}' -X DELETE \
    -H 'Host: relay.cinder.cinder.lab' -H "Authorization: ${token}" \
    "${CINDER_RELAY_INTERNAL_URL}/api/baskets/${basket}")"
  case "${status}" in 200|202|204|404) ;; *) die "${basket} relay reset returned HTTP ${status}" ;; esac
  rm -f -- "${state}"
}

remove_workhub_reference() {
  local flag=$1
  compose exec -T -e M03_RESET_FLAG="${flag}" redmine bundle exec rails runner /dev/stdin <<'RUBY'
flag = ENV.fetch('M03_RESET_FLAG')
Journal.where(journalized_type: 'Issue').find_each do |journal|
  journal.destroy! if journal.notes.to_s.include?(flag)
end
RUBY
}

reset_evaluation_dependency() { reset_relay_basket m03-evaluation-worker; }
reset_benign_adoption() { :; }
reset_rug_pull_proposal() { :; }
reset_phantom_attempt() { :; }
reset_release_status_source() { remove_workhub_reference 'FLAG{5f1ccafd643643bb}'; }
reset_poisoned_tool() { reset_relay_basket m03-model-card; }
reset_rag_discovery_thread() { :; }
reset_ingestion_workspace() {
  docker run --rm -v 'kep-v2-jupyter-eval.reader:/work' "${JUPYTER_IMAGE}" \
    sh -eu -c 'rm -rf /work/failed-ingestion/reports'
}
reset_evaluation_reader_session() { :; }
reset_rejected_handoffs() { remove_workhub_reference 'FLAG{a86a80d39b505362}'; }
reset_delayed_activation() { remove_workhub_reference 'FLAG{6431948740d97181}'; }

main() {
  local handler
  [[ -n ${OPERATION} ]] || die "usage: $0 operation-id"
  for command in curl docker jq; do command -v "${command}" >/dev/null || die "missing command: ${command}"; done
  jq -e --arg id "${OPERATION}" 'any(.[]; .id == $id)' "${MODULE_ROOT}/operations.json" >/dev/null || die "unknown operation: ${OPERATION}"
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
  log "${OPERATION}: smallest mutable participant state reset"
}

main "$@"
