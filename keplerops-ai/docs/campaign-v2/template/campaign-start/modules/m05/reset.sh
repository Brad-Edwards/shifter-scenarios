#!/usr/bin/env bash
set -Eeuo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MODULE_ROOT
TEMPLATE_ROOT="$(cd "${MODULE_ROOT}/../../.." && pwd)"
readonly TEMPLATE_ROOT
readonly OPERATION="${1:-}"
readonly K3S01_SSH_KEY="${K3S01_SSH_KEY:-/root/.ssh/keplerops-v2}"
readonly REVIEW_SSH_TARGET="${REVIEW_SSH_TARGET:-kepler@192.168.78.20}"
readonly SSH=(ssh -i "${K3S01_SSH_KEY}" -o BatchMode=yes -o StrictHostKeyChecking=accept-new)

log() { printf '[campaign-m05-reset] %s\n' "$*" >&2; }
fail() { log "ERROR: $*"; exit 1; }
require_env() { [[ -n ${!1:-} ]] || fail "$1 is required to identify exact server-owned attempt state"; }

compose() {
  local -a args=(docker compose --project-directory "$TEMPLATE_ROOT" --env-file "$TEMPLATE_ROOT/component-lock.env" --env-file "$TEMPLATE_ROOT/engineering/component-lock.additions.env" -f "$TEMPLATE_ROOT/compose.foundation.yaml" -f "$TEMPLATE_ROOT/compose.enterprise.yaml" -f "$TEMPLATE_ROOT/compose.engineering.yaml" -f "$TEMPLATE_ROOT/compose.cinder.yaml")
  local overlay
  while IFS= read -r overlay; do args+=(-f "$overlay"); done < <(find "$TEMPLATE_ROOT/campaign-start/modules" -mindepth 2 -maxdepth 2 -name compose.overlay.yaml -type f -print | sort)
  "${args[@]}" "$@"
}

redis() { compose exec -T redis redis-cli -a KeplerV2-Training-Redis --no-auth-warning "$@"; }

reset_assistant_attempt() {
  local attempt record
  attempt=$1
  record="$(redis GET "orion:attempt:${attempt}")"
  [[ -n $record ]] || return 1
  jq -e --arg id "$attempt" '
    .schema=="keplerops.orion.assistant-attempt/v1" and
    .attempt_id==$id and .status=="completed" and
    (.actor|type)=="string" and (.conversation_id|type)=="string" and
    (.resource_keys|type)=="array" and
    all(.resource_keys[];
      startswith("workhub:conversation:") or
      startswith("orion:memory:user:") or
      startswith("orion:history-audit:"))
  ' <<<"$record" >/dev/null || fail 'assistant attempt registry is invalid'

  local key value
  while IFS= read -r key; do
    value="$(redis GET "$key")"
    [[ -n $value ]] || continue
    if grep -Fq 'FLAG{' <<<"$value"; then
      fail "attempt ${attempt} contains an earned reference and is immutable"
    fi
    case "$key" in
      workhub:conversation:*)
        jq -e --arg id "$attempt" '.workflow_id==$id' <<<"$value" >/dev/null || fail "conversation is not owned by ${attempt}"
        ;;
      orion:memory:user:*)
        jq -e --arg id "$attempt" '.source_workflow_id==$id' <<<"$value" >/dev/null || fail "memory is not owned by ${attempt}"
        ;;
      orion:history-audit:*)
        jq -e --arg id "$attempt" '.workflow_id==$id' <<<"$value" >/dev/null || fail "history audit is not owned by ${attempt}"
        ;;
    esac
    redis DEL "$key" >/dev/null
  done < <(jq -r '.resource_keys[]' <<<"$record")
  redis DEL "orion:attempt:${attempt}" >/dev/null
  return 0
}

reset_transport_attempt() {
  local attempt=$1 result task_ids encoded
  result="$(compose exec -T m05-cinder-transport python - "$attempt" <<'PY'
import json
import sqlite3
import sys

attempt = sys.argv[1]
db = sqlite3.connect('/var/lib/cinder-orion-transport/transport.sqlite3')
db.row_factory = sqlite3.Row
rows = [dict(row) for row in db.execute('SELECT * FROM tasks WHERE attempt_id=?', (attempt,))]
if not rows:
    print(json.dumps({'found': False}))
    raise SystemExit(0)
if any('FLAG{' in json.dumps(row, sort_keys=True) for row in rows):
    raise SystemExit('transport attempt contains an earned reference and is immutable')
task_ids = [row['task_id'] for row in rows]
proofs = db.execute(
    'SELECT proof FROM worker_proofs WHERE task_id IN (%s)' % ','.join('?' for _ in task_ids),
    task_ids,
).fetchall()
db.execute(
    'DELETE FROM worker_proofs WHERE task_id IN (%s)' % ','.join('?' for _ in task_ids),
    task_ids,
)
db.execute('DELETE FROM tasks WHERE attempt_id=?', (attempt,))
db.commit()
print(json.dumps({'found': True, 'deleted': len(rows), 'task_ids': task_ids, 'proofs': len(proofs)}))
PY
)" || fail 'authoritative transport reset failed'
  jq -e '.found==true and (.task_ids|length)>0' <<<"$result" >/dev/null || return 1
  task_ids="$(jq -c '.task_ids' <<<"$result")"
  encoded="$(printf '%s' "$task_ids" | base64 -w0)"
  # shellcheck disable=SC2016
  compose exec -T -e "M05_RESET_TASK_IDS_B64=${encoded}" mongodb mongosh --quiet LibreChat --eval '
    const ids=JSON.parse(Buffer.from(process.env.M05_RESET_TASK_IDS_B64,"base64").toString("utf8"));
    const escaped=ids.map(id=>id.replace(/[.*+?^${}()|[\]\\]/g,"\\$&"));
    const owned=new RegExp(escaped.join("|"));
    const result=db.messages.deleteMany({$or:[{text:owned},{content:owned}]});
    print(JSON.stringify({deleted:result.deletedCount}));
  ' >/dev/null || fail 'attempt-owned LibreChat message reset failed'
}

reset_worker_attempt() {
  compose exec -T m05-orion-dataset-worker \
    python /opt/keplerops/orion_dataset_worker.py reset-attempt "$1" >/dev/null
}

reset_agent_registration() {
  compose exec -T m05-worker-authority \
    python /opt/orion/worker_authority.py reset-attempt "$1" >/dev/null
}

reset_source_attempt() {
  compose exec -T m05-source-admission \
    python /opt/keplerops/source_admission.py reset-attempt "$1" "$2" >/dev/null
}

reset_bridge_attempt() {
  local encoded
  encoded="$(python3 -c 'import sys,urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=""))' "$1")"
  "${SSH[@]}" "$REVIEW_SSH_TARGET" \
    "curl -fsS -X POST -H 'Authorization: Bearer Orion-Local-Agent-Bridge-2026' 'http://127.0.0.1:8877/internal/reset/${encoded}'" \
    >/dev/null || fail 'attempt-owned host bridge reset failed'
}

reset_owned_attempt() {
  require_env M05_ATTEMPT_ID
  if reset_assistant_attempt "$M05_ATTEMPT_ID"; then
    return 0
  fi
  if reset_transport_attempt "$M05_ATTEMPT_ID"; then
    return 0
  fi
  fail "no server-owned mutable state exists for attempt ${M05_ATTEMPT_ID}"
}

reset_m05_a() { reset_owned_attempt; }
reset_m05_b() { reset_owned_attempt; }
reset_m05_c() { reset_owned_attempt; }
reset_m05_d() { reset_owned_attempt; }
reset_m05_e() { require_env M05_ATTEMPT_ID; reset_source_attempt orion-release-tools "$M05_ATTEMPT_ID"; }
reset_m05_f() { reset_owned_attempt; }
reset_m05_g() { reset_owned_attempt; }
reset_m05_h() { reset_owned_attempt; }
reset_m05_i() { reset_owned_attempt; }
reset_m05_j() { reset_owned_attempt; }
reset_m05_k() { reset_owned_attempt; }
reset_m05_l() { require_env M05_ATTEMPT_ID; reset_worker_attempt "$M05_ATTEMPT_ID"; }
reset_m05_m() { require_env M05_ATTEMPT_ID; reset_source_attempt orion-agent-config "$M05_ATTEMPT_ID"; }
reset_m05_n() { require_env M05_ATTEMPT_ID; reset_worker_attempt "$M05_ATTEMPT_ID"; reset_agent_registration "$M05_ATTEMPT_ID"; }
reset_m05_o() { require_env M05_ATTEMPT_ID; reset_bridge_attempt "$M05_ATTEMPT_ID"; reset_transport_attempt "$M05_ATTEMPT_ID"; }
reset_m05_p() { reset_owned_attempt; }
reset_m05_q() { require_env M05_ATTEMPT_ID; reset_transport_attempt "$M05_ATTEMPT_ID"; }

main() {
  local handler
  [[ -n $OPERATION ]] || fail 'usage: reset.sh kep-m05-a'
  jq -e --arg id "$OPERATION" 'any(.[]; .id == $id)' "$MODULE_ROOT/operations.json" >/dev/null || fail "unknown operation: $OPERATION"
  handler="${OPERATION#kep-}"
  "reset_${handler//-/_}"
  log "reset exact failed attempt state for ${OPERATION}"
}

main "$@"
