#!/usr/bin/env bash
set -Eeuo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MODULE_ROOT
TEMPLATE_ROOT="$(cd "${MODULE_ROOT}/../../.." && pwd)"
readonly TEMPLATE_ROOT
readonly STATE_ROOT="${CAMPAIGN_STATE_ROOT:-${TEMPLATE_ROOT}/state/campaign-start}/m02"
readonly RUNTIME_URL="${M02_RUNTIME_URL:-http://10.61.30.29:8080}"
readonly RESET_TOKEN="${M02_RESET_TOKEN:-KeplerV2-Training-M02-Reset}"

die() { printf '[m02 reset] ERROR: %s\n' "$*" >&2; exit 1; }
known_operation() { jq -e --arg id "$1" 'any(.[]; .id == $id)' "${MODULE_ROOT}/operations.json" >/dev/null; }

purge_worker_queues() {
  curl -fsS -u 'kepler:KeplerV2-Training-Rabbit' -X DELETE \
    'http://10.61.50.12:15672/api/queues/keplerops/orion.review.results/contents' >/dev/null 2>&1 || true
}

reset_one() {
  local operation=$1 kind=
  known_operation "${operation}" || die "unknown operation: ${operation}"
  case "${operation}" in
    kep-m02-a)
      kind=recommendation-reports
      docker exec kep-v2-redis sh -c \
        "redis-cli -a KeplerV2-Training-Redis --scan --pattern 'workhub:conversation:*${operation}*' | xargs -r redis-cli -a KeplerV2-Training-Redis del" \
      >/dev/null 2>&1 || true
      ;;
    kep-m02-b) kind=citation-reports ;;
    kep-m02-c) kind=provenance-reports ;;
    kep-m02-d) kind=nested-source-reports ;;
    kep-m02-e|kep-m02-f) kind=model-reviews; purge_worker_queues ;;
    kep-m02-k) kind=repository-reviews; purge_worker_queues ;;
    kep-m02-l) kind=package-reviews; purge_worker_queues ;;
    kep-m02-m) kind=integration-reviews; purge_worker_queues ;;
    kep-m02-i|kep-m02-j) rm -rf "${STATE_ROOT}/attempts/${operation}" ;;
    kep-m02-h) rm -rf "${STATE_ROOT}/attempts/${operation}" ;;
  esac
  if [[ -n ${kind} ]]; then
    curl -fsS -X DELETE -H "Authorization: Bearer ${RESET_TOKEN}" \
      "${RUNTIME_URL}/internal/reset/${kind}" >/dev/null
  fi
  rm -rf "${STATE_ROOT}/evidence/${operation}"
  printf '%s\n' "${operation}: failed-attempt state reset; accepted rooms, threads, identities, packages, and tools preserved"
}

[[ $# -eq 1 ]] || die 'usage: reset.sh <operation-id>'
reset_one "$1"
