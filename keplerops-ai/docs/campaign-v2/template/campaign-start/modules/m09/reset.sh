#!/usr/bin/env bash
set -Eeuo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MODULE_ROOT
TEMPLATE_ROOT="$(cd "${MODULE_ROOT}/../../.." && pwd)"
readonly TEMPLATE_ROOT
readonly OPERATION="${1:-}"
readonly STATE_ROOT="${CAMPAIGN_STATE_ROOT:-${TEMPLATE_ROOT}/state/campaign-start}/m09"
readonly RABBIT_API="${RABBITMQ_MANAGEMENT_URL:-http://10.61.50.12:15672/api}"
readonly RELAY_URL="${CINDER_RELAY_INTERNAL_URL:-http://192.168.78.30:31080}"

log() { printf '[campaign-m09 reset] %s\n' "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }

reset_relay_basket() {
  local basket=$1 token_file status response
  token_file="${STATE_ROOT}/relay/${basket}.token"
  [[ -s ${token_file} ]] || return
  status="$(curl -sS -o /dev/null -w '%{http_code}' -X DELETE -H 'Host: relay.cinder.cinder.lab' \
    -H "Authorization: $(<"${token_file}")" "${RELAY_URL}/api/baskets/${basket}")"
  case "${status}" in 200|202|204|404) ;; *) die "relay basket reset returned HTTP ${status}" ;; esac
  response="$(curl -fsS -X POST -H 'Host: relay.cinder.cinder.lab' -H 'Content-Type: application/json' \
    --data '{"capacity":100}' "${RELAY_URL}/api/baskets/${basket}")"
  jq -er '.token' <<<"${response}" >"${token_file}"
  chmod 0600 "${token_file}"
}

purge_import_queues() {
  local queue
  for queue in orion.review.m09-import orion.review.m09-results; do
    curl -fsS --user 'kepler:KeplerV2-Training-Rabbit' -X DELETE \
      "${RABBIT_API}/queues/keplerops/${queue}/contents" >/dev/null 2>&1 || true
  done
}

main() {
  [[ -n ${OPERATION} ]] || die "usage: $0 <kep-m09-operation>"
  jq -e --arg id "${OPERATION}" 'any(.[]; .id == $id)' "${MODULE_ROOT}/operations.json" >/dev/null || die "unknown operation: ${OPERATION}"
  if [[ -s ${STATE_ROOT}/accepted/${OPERATION}.json ]]; then
    log "${OPERATION}: accepted immutable checkpoint preserved"
    return
  fi
  rm -rf -- "${STATE_ROOT}/attempts/${OPERATION}" "${STATE_ROOT}/failed/${OPERATION}"
  case "${OPERATION}" in
    kep-m09-i) purge_import_queues; reset_relay_basket m09-import-exceptions ;;
    kep-m09-k) purge_import_queues; reset_relay_basket m09-mirror-review ;;
    *) : ;;
  esac
  log "${OPERATION}: failed-attempt state removed; source, registries, and prerequisites preserved"
}

main
