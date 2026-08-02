#!/usr/bin/env bash
set -Eeuo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MODULE_ROOT
TEMPLATE_ROOT="$(cd "${MODULE_ROOT}/../../.." && pwd)"
readonly TEMPLATE_ROOT
readonly OPERATION="${1:-}"

# shellcheck source=/dev/null
source "${TEMPLATE_ROOT}/seeding/config.env"

log() { printf '[campaign-m05-reset] %s\n' "$*" >&2; }
fail() { log "ERROR: $*"; exit 1; }

compose() {
  docker compose --project-directory "${TEMPLATE_ROOT}" \
    --env-file "${TEMPLATE_ROOT}/component-lock.env" \
    --env-file "${TEMPLATE_ROOT}/engineering/component-lock.additions.env" \
    -f "${TEMPLATE_ROOT}/compose.foundation.yaml" \
    -f "${TEMPLATE_ROOT}/compose.enterprise.yaml" \
    -f "${TEMPLATE_ROOT}/compose.engineering.yaml" "$@"
}

accepted() {
  [[ ",${M05_ACCEPTED_OPERATIONS:-}," == *",$1,"* ]]
}

preserve_or_continue() {
  if accepted "$1"; then
    log "$1 is an earned checkpoint; reset preserved it"
    return 1
  fi
  return 0
}

redis_delete() {
  compose exec -T redis redis-cli -a KeplerV2-Training-Redis --no-auth-warning DEL "$@" >/dev/null
}

reset_m05_a() {
  preserve_or_continue kep-m05-a || return 0
  redis_delete "orion:memory:user:${M05_MEMORY_ACTOR:-partner.reviewer}" \
    "workhub:conversation:${M05_CONVERSATION_ID:-m05-a-attempt}"
}

reset_m05_b() {
  preserve_or_continue kep-m05-b || return 0
  redis_delete "workhub:conversation:${M05_CONVERSATION_ID:-m05-b-attempt}"
}

reset_m05_c() {
  preserve_or_continue kep-m05-c || return 0
  [[ -n ${M05_CONVERSATION_ID:-} ]] || fail 'M05_CONVERSATION_ID is required for shared-thread reset'
  redis_delete "orion:shared-thread:${M05_CONVERSATION_ID}" "workhub:conversation:${M05_CONVERSATION_ID}"
}

reset_m05_d() {
  preserve_or_continue kep-m05-d || return 0
  redis_delete "orion:history-audit:${M05_HISTORY_ACTOR:-support.analyst}" \
    "workhub:conversation:${M05_CONVERSATION_ID:-m05-d-attempt}"
}

reset_repo() {
  python3 "${MODULE_ROOT}/runtime/seed_enterprise.py" "$1" >/dev/null
}

reset_m05_e() { preserve_or_continue kep-m05-e || return 0; reset_repo kep-m05-e; }
reset_m05_f() { preserve_or_continue kep-m05-f || return 0; reset_repo kep-m05-f; }
reset_m05_g() { preserve_or_continue kep-m05-g || return 0; reset_repo kep-m05-g; }
reset_m05_h() { preserve_or_continue kep-m05-h || return 0; compose restart mlflow >/dev/null; }
reset_m05_i() { preserve_or_continue kep-m05-i || return 0; "${MODULE_ROOT}/apply.sh" kep-m05-i; }
reset_m05_j() { preserve_or_continue kep-m05-j || return 0; "${MODULE_ROOT}/apply.sh" kep-m05-j; }
reset_m05_k() { preserve_or_continue kep-m05-k || return 0; reset_repo kep-m05-k; }

reset_m05_l() {
  preserve_or_continue kep-m05-l || return 0
  docker rm -f kep-v2-orion-dataset-worker >/dev/null 2>&1 || true
  docker volume rm kep-v2-orion-dataset-worker >/dev/null 2>&1 || true
  "${MODULE_ROOT}/apply.sh" kep-m05-l
}

reset_m05_m() {
  preserve_or_continue kep-m05-m || return 0
  reset_repo kep-m05-m
  redis_delete orion:campaign:configuration
}

reset_m05_n() {
  preserve_or_continue kep-m05-n || return 0
  docker exec kep-v2-orion-dataset-worker sh -c \
    'pkill -f /opt/keplerops/rogue_agent.py 2>/dev/null || true; rm -rf /var/lib/orion-dataset-worker/rogue-agent'
}

reset_m05_o() {
  preserve_or_continue kep-m05-o || return 0
  [[ -n ${M05_CINDER_TASK_ID:-} ]] || fail 'M05_CINDER_TASK_ID is required for callback reset'
  curl -fsS -u "operator:${CINDER_OPERATOR_PASSWORD}" -X DELETE \
    "http://10.66.20.20:3000/api/tasks/${M05_CINDER_TASK_ID}" >/dev/null
}

reset_m05_p() {
  preserve_or_continue kep-m05-p || return 0
  [[ -n ${M05_CINDER_CONVERSATION_ID:-} ]] || fail 'M05_CINDER_CONVERSATION_ID is required for AI-API reset'
  curl -fsS -u "operator:${CINDER_OPERATOR_PASSWORD}" -X DELETE \
    "http://10.66.20.20:3000/api/inference-conversations/${M05_CINDER_CONVERSATION_ID}" >/dev/null
}

reset_m05_q() {
  preserve_or_continue kep-m05-q || return 0
  [[ -n ${M05_LIBRECHAT_CONVERSATION_ID:-} && -n ${M05_LIBRECHAT_TOKEN:-} ]] || \
    fail 'LibreChat conversation ID and participant token are required for web-relay reset'
  curl -fsS -H "Authorization: Bearer ${M05_LIBRECHAT_TOKEN}" -X DELETE \
    "https://assistant.keplerops.lab/api/convos/${M05_LIBRECHAT_CONVERSATION_ID}" >/dev/null
  reset_m05_n
}

main() {
  [[ -n $OPERATION ]] || fail 'usage: reset.sh kep-m05-a'
  jq -e --arg id "$OPERATION" 'any(.[]; .id == $id)' "${MODULE_ROOT}/operations.json" >/dev/null || fail "unknown operation: $OPERATION"
  "reset_${OPERATION//-/_}"
  log "reset attempt state for ${OPERATION}"
}

main "$@"
