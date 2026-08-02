#!/usr/bin/env bash
set -Eeuo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MODULE_ROOT
TEMPLATE_ROOT="$(cd "${MODULE_ROOT}/../../.." && pwd)"
readonly TEMPLATE_ROOT
readonly STATE_ROOT="${CAMPAIGN_STATE_ROOT:-${TEMPLATE_ROOT}/state/campaign-start}/m01"
readonly RUNTIME_URL="${M01_RUNTIME_URL:-http://10.61.30.28:8080}"
readonly RESET_TOKEN="${M01_RESET_TOKEN:-KeplerV2-Training-M01-Reset}"

die() { printf '[m01 reset] ERROR: %s\n' "$*" >&2; exit 1; }
known_operation() { jq -e --arg id "$1" 'any(.[]; .id == $id)' "${MODULE_ROOT}/operations.json" >/dev/null; }

clear_conversations() {
  local operation=$1
  docker exec kep-v2-redis sh -c \
    "redis-cli -a KeplerV2-Training-Redis --scan --pattern 'workhub:conversation:*${operation}*' | xargs -r redis-cli -a KeplerV2-Training-Redis del" \
    >/dev/null 2>&1 || true
}

purge_worker_queues() {
  curl -fsS -u 'kepler:KeplerV2-Training-Rabbit' -X DELETE \
    'http://10.61.50.12:15672/api/queues/keplerops/orion.review.results/contents' >/dev/null 2>&1 || true
}

reset_one() {
  local operation=$1 kind=
  known_operation "${operation}" || die "unknown operation: ${operation}"
  clear_conversations "${operation}"
  case "${operation}" in
    kep-m01-a) kind=briefs ;;
    kep-m01-b) kind=candidate-cases ;;
    kep-m01-c) kind=runbook-validations; purge_worker_queues ;;
    kep-m01-d) kind=approvals ;;
    kep-m01-e) kind=review-summaries ;;
    kep-m01-f) kind=external-reviews ;;
    kep-m01-g) kind=candidate-loader-reviews; purge_worker_queues ;;
    kep-m01-h) kind=helper-package-reviews; purge_worker_queues ;;
    kep-m01-i) docker restart kep-v2-langflow >/dev/null ;;
    kep-m01-j) kind=detonation-reviews; purge_worker_queues ;;
  esac
  if [[ -n ${kind} ]]; then
    curl -fsS -X DELETE -H "Authorization: Bearer ${RESET_TOKEN}" \
      "${RUNTIME_URL}/internal/reset/${kind}" >/dev/null
  fi
  rm -rf "${STATE_ROOT}/attempts/${operation}" "${STATE_ROOT}/evidence/${operation}"
  printf '%s\n' "${operation}: failed-attempt state reset; protected sources and earned predecessor state preserved"
}

[[ $# -eq 1 ]] || die 'usage: reset.sh <operation-id>'
reset_one "$1"
