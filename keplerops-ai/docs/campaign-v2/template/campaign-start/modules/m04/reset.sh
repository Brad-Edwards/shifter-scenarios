#!/usr/bin/env bash
set -Eeuo pipefail

readonly MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly TEMPLATE_ROOT="$(cd "${MODULE_ROOT}/../../.." && pwd)"
readonly OPERATION="${1:-}"
readonly RESEARCH_ACTOR="${ORION_RESEARCH_USER:-eval.reader}"
readonly REDIS_CONTAINER="${REDIS_CONTAINER:-kep-v2-redis}"
readonly REDIS_PASSWORD="${REDIS_PASSWORD:-KeplerV2-Training-Redis}"
readonly CINDER_RELAY_INTERNAL_URL="${CINDER_RELAY_INTERNAL_URL:-http://192.168.78.30:31080}"

log() { printf '[campaign-m04-reset] %s\n' "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }

reset_report() {
  local kind=$1
  docker exec "${REDIS_CONTAINER}" redis-cli -a "${REDIS_PASSWORD}" -n 4 \
    DEL "orion-research:${RESEARCH_ACTOR}:${kind}:latest" >/dev/null
}

reset_privacy_suite() {
  local report=$1 suite=$2
  reset_report "${report}"
  docker exec "${REDIS_CONTAINER}" sh -eu -c "
    keys=\$(redis-cli -a '${REDIS_PASSWORD}' -n 4 --raw KEYS 'orion-research:${RESEARCH_ACTOR}:privacy-observation:${suite}:*')
    [ -z \"\$keys\" ] || printf '%s\n' \"\$keys\" | xargs redis-cli -a '${REDIS_PASSWORD}' -n 4 DEL >/dev/null
  "
}

reset_context_leak_thread() { reset_report context-leak; }
reset_prompt_extraction_thread() { reset_report routing-extraction; }
reset_privacy_calibration_run() { reset_privacy_suite privacy-calibration calibration; }
reset_individual_membership_run() { reset_privacy_suite individual-membership individual; }
reset_cohort_membership_run() { reset_privacy_suite cohort-membership cohort; }
reset_compatibility_batch() { reset_report compatibility; }
reset_runtime_lineage_workspace() { :; }
reset_factuality_run() { reset_report factuality; }
reset_parser_compatibility_run() { reset_report parser-compatibility; }
reset_capability_audit() { reset_report capabilities; }
reset_release_workflow_fixture() { reset_report release-dry-run; }

reset_support_render_attempt() {
  local state="${TEMPLATE_ROOT}/state/campaign-start/m04/m04-support-render.token" token status
  reset_report support-draft
  [[ -s ${state} ]] || return 0
  token="$(<"${state}")"
  status="$(curl -sS -o /dev/null -w '%{http_code}' -X DELETE \
    -H 'Host: relay.cinder.cinder.lab' -H "Authorization: ${token}" \
    "${CINDER_RELAY_INTERNAL_URL}/api/baskets/m04-support-render")"
  case "${status}" in 200|202|204|404) ;; *) die "support relay reset returned HTTP ${status}" ;; esac
  rm -f -- "${state}"
}

reset_participant_exports() { :; }

main() {
  local handler
  [[ -n ${OPERATION} ]] || die "usage: $0 operation-id"
  for command in curl docker jq; do command -v "${command}" >/dev/null || die "missing command: ${command}"; done
  jq -e --arg id "${OPERATION}" 'any(.[]; .id == $id)' "${MODULE_ROOT}/operations.json" >/dev/null || \
    die "unknown operation: ${OPERATION}"
  case "${OPERATION}" in
    kep-m04-a) handler=reset_context_leak_thread ;;
    kep-m04-b) handler=reset_prompt_extraction_thread ;;
    kep-m04-c) handler=reset_privacy_calibration_run ;;
    kep-m04-d) handler=reset_individual_membership_run ;;
    kep-m04-e) handler=reset_cohort_membership_run ;;
    kep-m04-f) handler=reset_compatibility_batch ;;
    kep-m04-g) handler=reset_runtime_lineage_workspace ;;
    kep-m04-h) handler=reset_factuality_run ;;
    kep-m04-i) handler=reset_parser_compatibility_run ;;
    kep-m04-j) handler=reset_capability_audit ;;
    kep-m04-k) handler=reset_release_workflow_fixture ;;
    kep-m04-l) handler=reset_support_render_attempt ;;
    kep-m04-m) handler=reset_participant_exports ;;
    *) die "missing reset dispatch: ${OPERATION}" ;;
  esac
  declare -F "${handler}" >/dev/null || die "missing reset handler: ${handler}"
  "${handler}" "${OPERATION}"
  log "${OPERATION}: smallest mutable participant state reset"
}

main "$@"
