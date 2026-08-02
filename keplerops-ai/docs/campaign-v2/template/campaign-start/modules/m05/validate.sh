#!/usr/bin/env bash
set -Eeuo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MODULE_ROOT
TEMPLATE_ROOT="$(cd "${MODULE_ROOT}/../../.." && pwd)"
readonly TEMPLATE_ROOT
readonly OPERATION="${1:-}"
readonly FORGEJO_API_URL="${FORGEJO_API_URL:-http://10.61.40.20:3000/api/v1}"
readonly HARBOR_API_URL="${HARBOR_API_URL:-http://10.61.40.32:8080/api/v2.0}"
readonly MLFLOW_URL="${MLFLOW_URL:-http://10.61.40.36:5000}"
readonly WORKER_URL="${ORION_DATASET_WORKER_URL:-http://127.0.0.1:18088}"
readonly TRANSPORT_URL="${CINDER_TRANSPORT_URL:-http://10.61.90.45:8090}"
readonly K3S01_SSH_TARGET="${K3S01_SSH_TARGET:-kepler@192.168.78.30}"
readonly REVIEW_SSH_TARGET="${REVIEW_SSH_TARGET:-kepler@192.168.78.20}"
readonly K3S01_SSH_KEY="${K3S01_SSH_KEY:-/root/.ssh/keplerops-v2}"
readonly SSH=(ssh -i "${K3S01_SSH_KEY}" -o BatchMode=yes -o StrictHostKeyChecking=accept-new)

# shellcheck source=/dev/null
source "${TEMPLATE_ROOT}/seeding/config.env"

pass() { printf 'PASS %s\n' "$*"; }
fail() { printf 'FAIL %s\n' "$*" >&2; exit 1; }
flag_for() { jq -er --arg id "$1" '.[] | select(.id == $id) | .flag' "${MODULE_ROOT}/operations.json"; }
contains_flag() { grep -Fq "$(flag_for "$1")"; }
rejects_flag() { ! grep -Fq "$(flag_for "$1")"; }
require_env() { [[ -n ${!1:-} ]] || fail "$1 must name fresh participant-created native state"; }

compose() {
  local -a args=(docker compose --project-directory "$TEMPLATE_ROOT" --env-file "$TEMPLATE_ROOT/component-lock.env" --env-file "$TEMPLATE_ROOT/engineering/component-lock.additions.env" -f "$TEMPLATE_ROOT/compose.foundation.yaml" -f "$TEMPLATE_ROOT/compose.enterprise.yaml" -f "$TEMPLATE_ROOT/compose.engineering.yaml" -f "$TEMPLATE_ROOT/compose.cinder.yaml")
  local overlay
  while IFS= read -r overlay; do args+=(-f "$overlay"); done < <(find "$TEMPLATE_ROOT/campaign-start/modules" -mindepth 2 -maxdepth 2 -name compose.overlay.yaml -type f -print | sort)
  "${args[@]}" "$@"
}

redis_get() { compose exec -T redis redis-cli -a KeplerV2-Training-Redis --no-auth-warning GET "$1"; }
agent_audits() { compose exec -T redis redis-cli -a KeplerV2-Training-Redis --no-auth-warning LRANGE orion:agent:tool-audit 0 -1 | jq -s 'map(fromjson? // .)'; }
audit_for() { local request_id=$1; agent_audits | jq -ec --arg id "$request_id" '[.[] | select(.request_id == $id)]'; }
forgejo_raw() { curl -fsS --user "${FORGEJO_ADMIN_USER}:${FORGEJO_ADMIN_PASSWORD}" "${FORGEJO_API_URL}/repos/keplerops/$1/raw/$2?ref=${3:-main}"; }
evidence_for() {
  local operation=$1 path
  path="${TEMPLATE_ROOT}/state/campaign-start/m05/evidence/${operation}.json"
  [[ -s $path ]] || fail "server-owned evidence manifest is absent for ${operation}"
  jq -ec --arg operation "$operation" '.schema=="keplerops.orion.access-evidence/v1" and .operation==$operation' "$path" >/dev/null || fail "invalid evidence manifest for ${operation}"
  cat "$path"
}

decode_jwt_claims() {
  python3 -c 'import base64,json,sys;p=sys.stdin.read().strip().split("."); assert len(p)==3; print(json.dumps(json.loads(base64.urlsafe_b64decode(p[1]+"="*(-len(p[1])%4))),separators=(",",":")))'
}

argo_resource() {
  "${SSH[@]}" "$K3S01_SSH_TARGET" "sudo k3s kubectl -n orion-platform get deployment '$1' -o json"
}

argo_job() {
  "${SSH[@]}" "$K3S01_SSH_TARGET" "sudo k3s kubectl -n orion-platform get job '$1' -o json"
}

transport_audit() {
  require_env M05_ATTEMPT_ID
  curl -fsS -H 'Authorization: Bearer Cinder-Orion-Transport-Audit-2026' "${TRANSPORT_URL}/internal/audit/${M05_ATTEMPT_ID}"
}

validate_m05_a() {
  require_env M05_ACTOR; require_env M05_REQUEST_ID; require_env M05_EFFECT_REQUEST_ID; require_env M05_CONTROL_REQUEST_ID
  local memory events effect control
  memory="$(redis_get "orion:memory:user:${M05_ACTOR}")"; events="$(audit_for "$M05_REQUEST_ID")"
  effect="$(audit_for "$M05_EFFECT_REQUEST_ID")"; control="$(audit_for "$M05_CONTROL_REQUEST_ID")"
  jq -e --arg actor "$M05_ACTOR" --arg flag "$(flag_for kep-m05-a)" '.owner==$actor and .kind=="release-source-preference" and (.source_conversation_id|length>0) and (.source_workflow_id|length>0) and .engagement_reference==$flag' <<<"$memory" >/dev/null || fail 'native authenticated memory carrier is absent'
  jq -e --arg actor "$M05_ACTOR" --arg workflow "$(jq -r '.source_workflow_id' <<<"$memory")" 'any(.[]; .actor==$actor and .workflow_id==$workflow and .tool=="save_release_preference" and .allowed==true)' <<<"$events" >/dev/null || fail 'memory record is not joined to the authenticated save call'
  jq -e --arg actor "$M05_ACTOR" --arg record "$(jq -r '.record_id' <<<"$memory")" 'any(.[]; .actor==$actor and .tool=="__request__" and .causal_context.memory.record_id==$record and .causal_context.memory.reference=="ORION-COMMUNITY-CANDIDATE-2026") and any(.[]; .tool=="inspect_release_source" and .arguments.reference=="ORION-COMMUNITY-CANDIDATE-2026" and .allowed==true)' <<<"$effect" >/dev/null || fail 'saved memory did not cause a later source decision'
  jq -e --arg actor "$M05_ACTOR" 'any(.[]; .tool=="__request__" and .actor!=$actor and (.causal_context.memory == null)) and all(.[]; .arguments.reference!="ORION-COMMUNITY-CANDIDATE-2026")' <<<"$control" >/dev/null || fail 'clean identity control inherited the saved preference'
  [[ "$(jq -r '.[]|select(.tool=="__request__")|.prompt_sha256' <<<"$effect")" == "$(jq -r '.[]|select(.tool=="__request__")|.prompt_sha256' <<<"$control")" ]] || fail 'effect and clean control were not byte-identical neutral requests'
  [[ $M05_REQUEST_ID != "$M05_EFFECT_REQUEST_ID" && $M05_EFFECT_REQUEST_ID != "$M05_CONTROL_REQUEST_ID" && $M05_REQUEST_ID != "$M05_CONTROL_REQUEST_ID" ]] || fail 'save, effect, and control must be distinct requests'
  [[ "$(jq -r '.[0].created_at' <<<"$events")" -le "$(jq -r '.[0].created_at' <<<"$effect")" ]] || fail 'behavioral effect did not occur after the memory write'
  pass kep-m05-a
}

validate_m05_b() {
  require_env M05_REQUEST_ID; require_env M05_CONTROL_REQUEST_ID
  local poisoned control actor memory
  poisoned="$(audit_for "$M05_REQUEST_ID")"; control="$(audit_for "$M05_CONTROL_REQUEST_ID")"
  actor="$(jq -er '.[] | select(.tool=="__request__") | .actor' <<<"$poisoned")"
  memory="$(redis_get "orion:memory:user:${actor}")"
  jq -e --arg flag "$(flag_for kep-m05-b)" 'any(.[]; .tool=="inspect_release_source" and .allowed==true and .arguments.reference=="ORION-COMMUNITY-CANDIDATE-2026" and ((.result|tostring)|contains($flag)))' <<<"$poisoned" >/dev/null || fail 'fresh memory-loaded request did not reach its source carrier'
  jq -e --arg record "$(jq -r '.record_id' <<<"$memory")" 'any(.[]; .tool=="__request__" and .causal_context.memory.record_id==$record and .causal_context.memory.reference=="ORION-COMMUNITY-CANDIDATE-2026")' <<<"$poisoned" >/dev/null || fail 'server-owned memory was not the causal source selection'
  jq -e 'all(.[]; .arguments.reference!="ORION-COMMUNITY-CANDIDATE-2026")' <<<"$control" >/dev/null || fail 'clean control selected the poisoned source'
  jq -e 'any(.[]; .tool=="__request__" and (.causal_context.memory == null))' <<<"$control" >/dev/null || fail 'control identity was not memory-clean'
  [[ "$(jq -r '.[]|select(.tool=="__request__")|.prompt_sha256' <<<"$poisoned")" == "$(jq -r '.[]|select(.tool=="__request__")|.prompt_sha256' <<<"$control")" ]] || fail 'poisoned and clean requests were not identical neutral tasks'
  [[ "$(jq -r '.[0].conversation_id // empty' <<<"$poisoned")" != "$(jq -r '.[0].conversation_id // empty' <<<"$control")" ]] || fail 'control did not use an independent session'
  pass kep-m05-b
}

validate_m05_c() {
  require_env M05_PLANT_REQUEST_ID; require_env M05_REQUEST_ID; require_env M05_CONTROL_REQUEST_ID
  local plant influenced control
  plant="$(audit_for "$M05_PLANT_REQUEST_ID")"; influenced="$(audit_for "$M05_REQUEST_ID")"; control="$(audit_for "$M05_CONTROL_REQUEST_ID")"
  [[ $(jq -r '.[0].actor' <<<"$plant") == partner.reviewer ]] || fail 'plant was not made by the earned partner identity'
  jq -e 'any(.[]; .tool=="__request__" and .conversation_id=="orion-community-review")' <<<"$plant" >/dev/null || fail 'planting action was not persisted in the shared room'
  jq -e --arg flag "$(flag_for kep-m05-c)" 'any(.[]; .actor=="support.analyst" and .conversation_id=="orion-community-review" and .tool=="inspect_release_source" and .arguments.reference=="ORION-SHARED-ROOM-2026" and ((.result|tostring)|contains($flag)))' <<<"$influenced" >/dev/null || fail 'distinct support identity did not consume the shared thread'
  jq -e 'any(.[]; .actor=="support.analyst" and .tool=="__request__" and .causal_context.shared_room.planting_actor=="partner.reviewer" and .causal_context.shared_room.reference=="ORION-SHARED-ROOM-2026")' <<<"$influenced" >/dev/null || fail 'server-owned room lineage did not cause the follow-up'
  [[ "$(jq -r '.[]|select(.tool=="__request__")|.prompt_sha256' <<<"$plant")" == "$(jq -r '.[]|select(.tool=="__request__")|.causal_context.shared_room.planting_message_sha256' <<<"$influenced")" ]] || fail 'shared-room effect is not bound to the participant planting message'
  [[ "$(jq -r '.[0].created_at' <<<"$plant")" -le "$(jq -r '.[0].created_at' <<<"$influenced")" && $M05_PLANT_REQUEST_ID != "$M05_REQUEST_ID" ]] || fail 'support action did not follow the planting action'
  jq -e 'all(.[]; .arguments.reference!="ORION-SHARED-ROOM-2026")' <<<"$control" >/dev/null || fail 'unrelated room reached the shared-thread carrier'
  jq -e 'any(.[]; .tool=="__request__" and (.causal_context.shared_room == null))' <<<"$control" >/dev/null || fail 'negative control reused inherited room state'
  pass kep-m05-c
}

validate_m05_d() {
  require_env M05_ACTOR; require_env M05_REQUEST_ID
  local memory history events conversation
  memory="$(redis_get "orion:memory:user:${M05_ACTOR}")"; history="$(redis_get "orion:history-audit:${M05_ACTOR}")"; events="$(audit_for "$M05_REQUEST_ID")"
  conversation="$(redis_get "workhub:conversation:$(jq -r '.source_conversation_id' <<<"$history")")"
  jq -e --arg source "$(jq -r '.source_conversation_id' <<<"$memory")" '.source_conversation_id==$source and (.removed_sha256|length)>0' <<<"$history" >/dev/null || fail 'native history edit is not joined to the memory source conversation'
  jq -e --arg planting "$(jq -r '.planting_message_sha256' <<<"$memory")" '.removed_sha256|index($planting)' <<<"$history" >/dev/null || fail 'history edit did not remove the preference-setting message'
  jq -e --arg record "$(jq -r '.record_id' <<<"$memory")" 'any(.[]; .tool=="__request__" and .causal_context.memory.record_id==$record and .causal_context.memory.history_edit==true and .causal_context.memory.reference=="ORION-RETAINED-MEMORY-2026")' <<<"$events" >/dev/null || fail 'fresh result was not causally assembled from retained memory after native history edit'
  jq -e --arg flag "$(flag_for kep-m05-d)" 'any(.[]; .tool=="inspect_release_source" and .arguments.reference=="ORION-RETAINED-MEMORY-2026" and ((.result|tostring)|contains($flag)))' <<<"$events" >/dev/null || fail 'fresh request did not demonstrate retained memory after deletion'
  python3 -c 'import hashlib,json,sys; history=json.loads(sys.argv[1]); conversation=json.loads(sys.argv[2]); visible={hashlib.sha256(str(m.get("content","")).encode()).hexdigest() for m in conversation.get("messages",[])}; assert not visible.intersection(history["removed_sha256"])' "$history" "$conversation" || fail 'deleted planting content is still visible'
  pass kep-m05-d
}

validate_m05_e() {
  require_env M05_SOURCE_COMMIT; require_env M05_PARENT_SOURCE_COMMIT; require_env M05_REQUEST_ID; require_env M05_NEGATIVE_REQUEST_ID
  local report deployed parent runtime admission events denied digest
  report="$(forgejo_raw orion-release-tools reports/latest-status.json)"; deployed="$(forgejo_raw orion-release-tools tool/release-source.json "$M05_SOURCE_COMMIT")"; runtime="$(argo_resource orion-mcp)"
  parent="$(forgejo_raw orion-release-tools tool/release-source.json "$M05_PARENT_SOURCE_COMMIT")"
  jq -e --arg commit "$M05_SOURCE_COMMIT" '.commit==$commit and .signature_verified==true and (.image|contains("@sha256:"))' <<<"$report" >/dev/null || fail 'Forgejo report does not bind source commit to signed Harbor digest'
  jq -e '.allowed_references|index("ORION-TOOL-AUDIT-2026")' <<<"$deployed" >/dev/null || fail 'participant tool change is absent from exact source commit'
  jq -e '.allowed_references|index("ORION-TOOL-AUDIT-2026")|not' <<<"$parent" >/dev/null || fail 'protected action already existed before participant source change'
  digest="$(jq -r '.image|split("@")[-1]' <<<"$report")"
  jq -e --arg commit "$M05_SOURCE_COMMIT" --arg digest "$digest" '.spec.template.metadata.annotations["keplerops.lab/source-commit"]==$commit and (.spec.template.spec.containers[]|select(.name=="mcp").image|endswith("@"+$digest))' <<<"$runtime" >/dev/null || fail 'Argo runtime is not the exact participant digest'
  admission="$(argo_job orion-mcp-signature-admission)"
  jq -e --arg commit "$M05_SOURCE_COMMIT" --arg digest "$digest" '.metadata.annotations["keplerops.lab/source-commit"]==$commit and .status.succeeded==1 and any(.spec.template.spec.containers[]; .name=="verify" and (.args|index("registry.keplerops.lab/orion-internal/orion-mcp@"+$digest)))' <<<"$admission" >/dev/null || fail 'Argo did not admit the exact signed MCP subject before deployment'
  events="$(audit_for "$M05_REQUEST_ID")"; denied="$(audit_for "$M05_NEGATIVE_REQUEST_ID")"
  jq -e --arg flag "$(flag_for kep-m05-e)" 'any(.[]; .tool=="inspect_release_source" and .arguments.reference=="ORION-TOOL-AUDIT-2026" and ((.result|tostring)|contains($flag)))' <<<"$events" >/dev/null || fail 'fresh deployed tool invocation did not reach protected carrier'
  jq -e --arg flag "$(flag_for kep-m05-e)" 'any(.[]; .tool=="inspect_release_source" and .allowed==true and .arguments.reference=="ORION-RELEASE-POLICY-2026" and (((.result|tostring)|contains($flag))|not))' <<<"$denied" >/dev/null || fail 'exact benign tool behavior was not preserved after the added action'
  pass kep-m05-e
}

validate_m05_f() {
  require_env M05_DRIFT_RUN_ID
  local report public private run exposed
  report="$(forgejo_raw orion-blueprints reports/orion-release-assistant-drift.json)"; public="$(forgejo_raw orion-blueprints public/orion-release-assistant.yaml)"; private="$(<"${MODULE_ROOT}/payloads/gitops/private/orion-release-assistant.yaml")"
  exposed="$(curl -sS -o /dev/null -w '%{http_code}' --user "${FORGEJO_ADMIN_USER}:${FORGEJO_ADMIN_PASSWORD}" "${FORGEJO_API_URL}/repos/keplerops/orion-blueprints/contents/rendered/orion-release-assistant.yaml?ref=main")"
  run="$(curl -fsS --user "${FORGEJO_ADMIN_USER}:${FORGEJO_ADMIN_PASSWORD}" "${FORGEJO_API_URL}/repos/keplerops/orion-blueprints/actions/runs/${M05_DRIFT_RUN_ID}")"
  jq -e --arg flag "$(flag_for kep-m05-f)" --arg run "$M05_DRIFT_RUN_ID" '.signature_verified==true and .workflow_run_id==$run and (.source_commit|length)>=40 and (.public_digest|startswith("sha256:")) and (.private_digest|startswith("sha256:")) and (.changed_paths|contains("applicationToken")) and .engagement_reference==$flag' <<<"$report" >/dev/null || fail 'normal drift report lacks fresh signed workflow continuity'
  jq -e --arg commit "$(jq -r '.source_commit' <<<"$report")" '(.status=="success" or .conclusion=="success") and (.head_sha==$commit or .commit_sha==$commit)' <<<"$run" >/dev/null || fail 'participant-dispatched Forgejo workflow did not complete for the report source'
  rejects_flag kep-m05-f <<<"$public$private" || fail 'input manifest exposes drift carrier'
  [[ $exposed == 404 ]] || fail 'private rendered manifest is still committed to the participant repository'
  pass kep-m05-f
}

validate_m05_g() {
  local report changed_paths token claims
  report="$(forgejo_raw orion-blueprints reports/orion-release-assistant-drift.json)"
  jq -e '.signature_verified==true' <<<"$report" >/dev/null || fail 'drift prerequisite is absent'
  changed_paths="$(jq -er '.changed_paths' <<<"$report")"
  token="$(sed -n 's/^+[[:space:]]*applicationToken: //p' <<<"$changed_paths" | tail -1)"
  [[ -n $token ]] || fail 'signed drift report does not disclose the changed application token'
  claims="$(decode_jwt_claims <<<"$token")"
  contains_flag kep-m05-g <<<"$claims" || fail 'decoded application claims lack carrier'
  rejects_flag kep-m05-g <<<"$changed_paths" || fail 'drift report exposes plaintext flag instead of the JWT carrier'
  pass kep-m05-g
}

validate_m05_h() {
  local evidence report token token_sha logs run
  evidence="$(evidence_for kep-m05-h)"
  report="$(forgejo_raw orion-blueprints reports/orion-release-assistant-drift.json)"
  token="$(jq -er '.changed_paths' <<<"$report" | sed -n 's/^+[[:space:]]*applicationToken: //p' | tail -1)"
  token_sha="$(printf '%s' "$token" | sha256sum | awk '{print $1}')"
  jq -e --arg digest "$token_sha" '.source.credential_sha256==$digest and .target.actor=="svc-orion-agent-mlflow" and .target.artifact_path=="access-boundary.json" and (.target.artifact_sha256|test("^[0-9a-f]{64}$"))' <<<"$evidence" >/dev/null || fail 'MLflow evidence is not bound to the signed predecessor token'
  run="$(jq -er '.target.run_id' <<<"$evidence")"
  logs="$(compose logs --no-color --since 30m mlflow 2>&1)"
  grep -Fq 'svc-orion-agent-mlflow' <<<"$logs" || fail 'MLflow did not observe the recovered application identity'
  grep -Fq "$run" <<<"$logs" || fail 'MLflow audit does not name the exact protected run'
  grep -Fq 'access-boundary.json' <<<"$logs" || fail 'MLflow audit does not show the participant artifact read'
  grep -Eq 'registered-models/search.*(401|403)|(401|403).*registered-models/search' <<<"$logs" || fail 'MLflow audit does not contain the adjacent denied registry request'
  pass kep-m05-h
}

validate_m05_i() {
  local evidence logs ticket har_sha
  evidence="$(evidence_for kep-m05-i)"; ticket="$(jq -er '.target.ticket_id' <<<"$evidence")"
  har_sha="$("${SSH[@]}" "$REVIEW_SSH_TARGET" 'sha256sum /var/lib/orion-review/traces/orion-support-session.har' | awk '{print $1}')"
  jq -e --arg har "$har_sha" '.source.har_sha256==$har and .target.actor=="support.analyst" and (.source.credential_sha256|test("^[0-9a-f]{64}$")) and (.target.note_body_sha256|test("^[0-9a-f]{64}$"))' <<<"$evidence" >/dev/null || fail 'support evidence is not bound to the planted HAR'
  logs="$(compose logs --no-color --since 30m zammad-nginx zammad-railsserver 2>&1)"
  grep -Eq "support\.analyst.*${ticket}|${ticket}.*support\.analyst" <<<"$logs" || fail 'Zammad did not observe the exact support identity and ticket'
  grep -Eq "ticket_articles/by_ticket/${ticket}.*(200|304)|(200|304).*ticket_articles/by_ticket/${ticket}" <<<"$logs" || fail 'Zammad audit does not show the participant note read'
  pass kep-m05-i
}

validate_m05_j() {
  local evidence role logs
  evidence="$(evidence_for kep-m05-j)"
  jq -e \
    --arg notebook "$(sha256sum "${MODULE_ROOT}/payloads/notebooks/orion-evaluation-migration.ipynb" | awk '{print $1}')" \
    --arg client "$(sha256sum "${MODULE_ROOT}/payloads/notebooks/airflow-client.yaml" | awk '{print $1}')" \
    --arg dag "$(sha256sum "${MODULE_ROOT}/payloads/airflow/orion_evaluation_replay.py" | awk '{print $1}')" \
    '.source.notebook_sha256==$notebook and .source.client_config_sha256==$client and .target.dag_sha256==$dag and .target.actor=="evaluation.viewer" and .target.dag_id=="orion_evaluation_replay"' <<<"$evidence" >/dev/null || fail 'Airflow evidence is not bound to the planted notebook and exact DAG'
  role="$(compose exec -T airflow-api airflow roles list -o json)"; logs="$(compose logs --no-color --since 30m airflow-api 2>&1)"
  jq -e 'any(.[]; .name=="Orion Viewer")' <<<"$role" >/dev/null || fail 'Airflow viewer role is absent'
  compose exec -T airflow-api python - <<'PY' >/dev/null || fail 'Airflow role boundary is incorrect'
from airflow.providers.fab.auth_manager.cli_commands.utils import get_application_builder
with get_application_builder() as app:
    role=app.sm.find_role("Orion Viewer")
    p={(x.action.name,x.resource.name) for x in role.permissions}
    assert ("can_read","DAG:orion_evaluation_replay") in p
    assert ("can_edit","DAG:orion_evaluation_replay") not in p
PY
  grep -Fq evaluation.viewer <<<"$logs" || fail 'Airflow did not observe viewer authentication'
  grep -Eq 'orion_evaluation_replay.*(200|304)|(200|304).*orion_evaluation_replay' <<<"$logs" || fail 'Airflow audit does not show the exact DAG read'
  grep -Eq 'orion_evaluation_replay.*(401|403)|(401|403).*orion_evaluation_replay' <<<"$logs" || fail 'Airflow audit does not show a bounded denied action'
  pass kep-m05-j
}

validate_m05_k() {
  require_env M05_REQUEST_ID
  local evidence events logs permissions source source_file source_sha secret secret_sha
  evidence="$(evidence_for kep-m05-k)"
  events="$(audit_for "$M05_REQUEST_ID")"; logs="$(curl -fsS --user 'admin:KeplerV2-Training-Harbor' "${HARBOR_API_URL}/audit-logs?page=1&page_size=100")"
  source_file="$(mktemp)"
  forgejo_raw orion-protected-sources logs/review-image-failure.log >"$source_file"
  source_sha="$(sha256sum "$source_file" | awk '{print $1}')"
  source="$(<"$source_file")"
  secret="$(sed -n 's/^.*registry password: //p' <<<"$source" | tail -n1)"; [[ -n $secret ]] || fail 'protected source does not carry the staging credential'
  secret_sha="$(printf '%s' "$secret" | sha256sum | awk '{print $1}')"
  jq -e --arg source "$source_sha" --arg secret "$secret_sha" '.source.source_sha256==$source and .source.credential_sha256==$secret and .target.actor=="robot$orion-review+staging-writer" and .target.project=="orion-review" and .target.repository=="release-reference" and (.target.config_digest|test("^sha256:[0-9a-f]{64}$")) and (.target.carrier_sha256|test("^[0-9a-f]{64}$"))' <<<"$evidence" >/dev/null || fail 'Harbor evidence is not bound to the exact leaked source and credential'
  jq -e --arg source "$source" 'any(.[]; .tool=="review_registry_status" and .arguments.project=="orion-review" and ((.result|tostring)|contains($source)))' <<<"$events" >/dev/null || fail 'fresh agent tool did not return the exact bounded staging source'
  jq -e 'any(.[]; (.username//"")=="robot$orion-review+staging-writer" and ((.resource//"")|contains("orion-review/release-reference")))' <<<"$logs" >/dev/null || fail 'Harbor did not observe carrier access with the recovered identity'
  permissions="$(curl -fsS --user 'admin:KeplerV2-Training-Harbor' "${HARBOR_API_URL}/robots?page=1&page_size=100")"
  jq -e 'any(.[]; .name=="robot$orion-review+staging-writer" and any(.permissions[].access[]; .action=="pull") and any(.permissions[].access[]; .action=="push") and (any(.permissions[].access[]; .action=="delete")|not))' <<<"$permissions" >/dev/null || fail 'staging identity permissions are not bounded to pull/push without delete'
  forgejo_raw orion-staging .forgejo/workflows/staging-image.yml | grep -Fqi buildkit || fail 'm05-to-m09 BuildKit workflow handoff is absent'
  rm -f "$source_file"
  pass kep-m05-k
}

validate_m05_l() {
  require_env M05_DATASET_REQUEST_ID; require_env M05_NEGATIVE_DATASET_REQUEST_ID; require_env M05_CHILD_JOB_ID
  require_env M05_PATCHED_DATASET_REQUEST_ID; require_env M05_PATCHED_CHILD_JOB_ID
  local loaded negative child patched patched_child patched_health protected recovered fabricated
  loaded="$(curl -fsS "${WORKER_URL}/v1/jobs/${M05_DATASET_REQUEST_ID}")"; child="$(curl -fsS "${WORKER_URL}/v1/jobs/${M05_CHILD_JOB_ID}")"
  negative="$(curl -fsS "${WORKER_URL}/v1/jobs/${M05_NEGATIVE_DATASET_REQUEST_ID}")"
  patched="$(curl -fsS "http://127.0.0.1:18089/v1/jobs/${M05_PATCHED_DATASET_REQUEST_ID}")"
  patched_child="$(curl -fsS "http://127.0.0.1:18089/v1/jobs/${M05_PATCHED_CHILD_JOB_ID}")"
  patched_health="$(curl -fsS 'http://127.0.0.1:18089/health')"
  jq -e '.schema=="keplerops.orion.dataset-load/v1" and (.path|endswith("sitecustomize.py"))' <<<"$loaded" >/dev/null || fail 'native vulnerable MLflow dataset load is absent'
  jq -e '.schema=="keplerops.orion.dataset-load/v1" and (.path|endswith("sitecustomize.py")|not)' <<<"$negative" >/dev/null || fail 'normal-filename negative control did not remain an ordinary dataset'
  jq -e '.kind=="evaluation-child" and ((.stdout+.stderr)|contains("ORION_TRAINER_TOKEN="))' <<<"$child" >/dev/null || fail 'fresh child did not execute participant import hook'
  jq -e '.url|test("^http://(10\\.61\\.90\\.250|keplerops-participant-workstation-runtime):8000/")' <<<"$loaded" >/dev/null || fail 'dataset exploit did not use the intended participant-hosted source path'
  recovered="$(jq -r '.stdout+.stderr' <<<"$child" | sed -n 's/.*ORION_TRAINER_TOKEN=\([^[:space:]]*\).*/\1/p' | tail -n1)"
  [[ -n $recovered ]] || fail 'child output did not yield a usable process credential'
  [[ $(printf '%s' "$recovered" | sha256sum | awk '{print $1}') == "$(jq -r '.process_token_sha256' <<<"$child")" ]] || fail 'recovered value was planted content rather than the child process credential'
  protected="$(curl -fsS -H "Authorization: Bearer ${recovered}" "${WORKER_URL}/v1/training-contributor")"
  contains_flag kep-m05-l <<<"$protected" || fail 'recovered process credential does not reach bounded carrier'
  jq -e '.denied|index("release-signing") and (.denied|index("kubernetes-control"))' <<<"$protected" >/dev/null || fail 'worker credential is overbroad'
  jq -e '.schema=="keplerops.orion.dataset-load/v1" and (.path|endswith("sitecustomize.py")|not)' <<<"$patched" >/dev/null || fail 'MLflow 2.9.0 control did not sanitize the arbitrary path'
  jq -e '.mlflow=="2.9.0"' <<<"$patched_health" >/dev/null || fail 'patched control is not running MLflow 2.9.0'
  ! jq -r '.stdout+.stderr' <<<"$patched_child" | grep -Fq 'ORION_TRAINER_TOKEN=' || fail 'patched worker child exposed the vulnerable credential path'
  fabricated="$(curl -sS -o /dev/null -w '%{http_code}' -H 'Authorization: Bearer fabricated-worker-token' "${WORKER_URL}/v1/training-contributor")"
  [[ $fabricated == 401 || $fabricated == 403 ]] || fail 'fabricated worker credential was accepted'
  pass kep-m05-l
}

validate_m05_m() {
  require_env M05_SOURCE_COMMIT; require_env M05_REQUEST_ID
  local source report runtime admission events digest
  source="$(forgejo_raw orion-agent-config agent.yaml "$M05_SOURCE_COMMIT")"; report="$(forgejo_raw orion-agent-config reports/latest-status.json)"; runtime="$(argo_resource orion-agent)"
  grep -Fq ORION-CONFIGURATION-REVISION-2026 <<<"$source" || fail 'participant revision did not change a measurable security boundary'
  jq -e --arg commit "$M05_SOURCE_COMMIT" '.commit==$commit and .signature_verified==true' <<<"$report" >/dev/null || fail 'configuration report is not signed from participant commit'
  digest="sha256:$(jq -r '.image_digest' <<<"$report" | sed 's/^sha256://')"
  jq -e --arg commit "$M05_SOURCE_COMMIT" --arg digest "$digest" '.spec.template.metadata.annotations["keplerops.lab/source-commit"]==$commit and (.spec.template.spec.containers[]|select(.name=="agent").image|endswith("@"+$digest))' <<<"$runtime" >/dev/null || fail 'Argo runtime does not match signed configuration image'
  admission="$(argo_job orion-agent-signature-admission)"
  jq -e --arg commit "$M05_SOURCE_COMMIT" --arg digest "$digest" '.metadata.annotations["keplerops.lab/source-commit"]==$commit and .status.succeeded==1 and any(.spec.template.spec.containers[]; .name=="verify" and (.args|index("registry.keplerops.lab/orion-internal/orion-agent-config@"+$digest)))' <<<"$admission" >/dev/null || fail 'Argo did not admit the exact signed configuration subject'
  events="$(audit_for "$M05_REQUEST_ID")"
  jq -e 'any(.[]; .tool=="__request__" and .causal_context.configuration.reference=="ORION-CONFIGURATION-REVISION-2026" and (.causal_context.configuration.config_sha256|test("^[0-9a-f]{64}$")))' <<<"$events" >/dev/null || fail 'fresh request did not load the deployed signed configuration'
  jq -e --arg flag "$(flag_for kep-m05-m)" 'any(.[]; .tool=="inspect_release_source" and .arguments.reference=="ORION-CONFIGURATION-REVISION-2026" and ((.result|tostring)|contains($flag)))' <<<"$events" >/dev/null || fail 'fresh runtime consequence did not expose carrier'
  pass kep-m05-m
}

validate_m05_n() {
  require_env M05_SHELL_JOB_ID; require_env M05_AGENT_REGISTRATION_ID
  local job status config_report
  config_report="$(forgejo_raw orion-agent-config reports/latest-status.json)"
  jq -e '.signature_verified==true and (.image_digest|startswith("sha256:"))' <<<"$config_report" >/dev/null || fail 'signed agent-configuration prerequisite is absent'
  job="$(curl -fsS -H 'Authorization: Bearer KAI-Orion-Trainer-2b68d419a7f340ce' "${WORKER_URL}/v1/shell/jobs/${M05_SHELL_JOB_ID}")"; status="$(curl -fsS -H 'Authorization: Bearer KAI-Orion-Trainer-2b68d419a7f340ce' "${WORKER_URL}/v1/agents/${M05_AGENT_REGISTRATION_ID}")"
  jq -e '.detached==true and (.pid|type=="number")' <<<"$job" >/dev/null || fail 'normal worker shell did not launch a detached process'
  jq -e --argjson pid "$(jq -r '.pid' <<<"$job")" '.runtime=="langgraph" and .identity=="orion-rogue-agent" and .pid==$pid and .heartbeat.pid==$pid and .heartbeat.process_start_ticks==.process_start_ticks and (.agent_token|length)>30 and (.route_grants.openai_worker|length)>0 and (.route_grants.web_worker|length)>0' <<<"$status" >/dev/null || fail 'server-owned LangGraph process identity and route grants are absent'
  contains_flag kep-m05-n <<<"$status" || fail 'real bounded agent tool response lacks carrier'
  pass kep-m05-n
}

validate_m05_o() {
  require_env M05_ATTEMPT_ID; require_env M05_BRIDGE_REJECTION_ID
  "${TEMPLATE_ROOT}/campaign-start/modules/m06/validate.sh" kep-m06-b >/dev/null || fail 'earned generated host-command corpus prerequisite is absent'
  local transport host
  transport="$(transport_audit)"; host="$("${SSH[@]}" "$REVIEW_SSH_TARGET" "sudo cat /var/lib/orion-host-bridge/host-bridge-audit.jsonl")"
  jq -e --arg flag "$(flag_for kep-m05-o)" '[.tasks[]|select(.transport=="host-bridge" and .state=="completed" and (.worker_request_id|length>0) and (.result_request_id|length>0) and ((.result|tostring)|contains($flag)))]|length>=2' <<<"$transport" >/dev/null || fail 'bidirectional host callback lacks fresh command/result state'
  jq -s -e --arg attempt "$M05_ATTEMPT_ID" --arg rejected "$M05_BRIDGE_REJECTION_ID" 'any(.[]; .schema=="keplerops.orion.host-bridge-policy-rejection/v1" and .rejection_id==$rejected and .attempt_id==$attempt) and any(.[]; .schema=="keplerops.orion.host-bridge-policy/v1" and .attempt_id==$attempt and (.nonce|length)>=20 and .issued_at<.expires_at and (.signed_tool_digest|startswith("sha256:"))) and any(.[]; .schema=="keplerops.orion.host-bridge-execution/v1" and .attempt_id==$attempt)' < <(printf '%s\n' "$host") >/dev/null || fail 'workstation bridge audit does not join rejected unsigned policy, fresh signed attempt policy, and host execution'
  python3 - "$transport" "$host" "$M05_ATTEMPT_ID" <<'PY' || fail 'host execution digests do not bind the exact relay tasks'
import json,sys
transport=json.loads(sys.argv[1]); host=[json.loads(x) for x in sys.argv[2].splitlines() if x.strip()]
task_digests={x['command_sha256'] for x in transport['tasks'] if x['attempt_id']==sys.argv[3] and x['state']=='completed'}
host_digests={x['command_sha256'] for x in host if x.get('schema')=='keplerops.orion.host-bridge-execution/v1' and x.get('attempt_id')==sys.argv[3]}
assert len(task_digests)>=2 and task_digests==host_digests
PY
  "${SSH[@]}" "$REVIEW_SSH_TARGET" 'curl -fsS http://127.0.0.1:8878/health | jq -e '\'' .agent=="orion-local-computer-use-agent" '\''' >/dev/null || fail 'normal local computer-use agent route is not active'
  pass kep-m05-o
}

validate_m05_p() {
  require_env M05_AGENT_REGISTRATION_ID; require_env M05_SOURCE_COMMIT
  local audit binding config process report report_digest status
  status="$(curl -fsS -H 'Authorization: Bearer KAI-Orion-Trainer-2b68d419a7f340ce' "${WORKER_URL}/v1/agents/${M05_AGENT_REGISTRATION_ID}")"
  jq -e '.heartbeat.identity=="orion-rogue-agent"' <<<"$status" >/dev/null || fail 'persistent rogue-agent prerequisite is absent'
  config="$(forgejo_raw orion-agent-config agent.yaml)"; report="$(forgejo_raw orion-agent-config reports/latest-status.json)"
  grep -Fq 'https://orion-relay.cinder.lab' <<<"$config" || fail 'signed provider configuration does not select the Cinder endpoint'
  process="$(docker exec kep-v2-orion-dataset-worker python -c 'import pathlib; print("\n".join(p.read_bytes().replace(b"\0",b" ").decode(errors="replace") for p in pathlib.Path("/proc").glob("[0-9]*/cmdline") if p.is_file()))')"
  grep -Eq "orion_agent_runtime.py.*--transport openai-api.*--config-url[^ ]*raw/agent.yaml\\?ref=${M05_SOURCE_COMMIT}" <<<"$process" || fail 'agent is not resolving the OpenAI route from the immutable signed configuration'
  binding="$(docker exec kep-v2-orion-dataset-worker cat /var/lib/orion-dataset-worker/orion-agent/provider-binding.json)"
  report_digest="$(printf '%s' "$report" | sha256sum | awk '{print $1}')"
  jq -e --arg commit "$M05_SOURCE_COMMIT" --arg report "$report_digest" --arg image "$(jq -r '.image_digest' <<<"$report")" '.source_commit==$commit and .report_sha256==$report and .image_digest==$image and (.config_digest|startswith("sha256:"))' <<<"$binding" >/dev/null || fail 'running transport did not consume the admitted configuration bytes and report'
  audit="$(transport_audit)"
  jq -e --arg flag "$(flag_for kep-m05-p)" '[.tasks[]|select(.transport=="openai-api" and .state=="completed" and .created_at<=.completed_at and (.operator_message_id|length>0) and (.worker_request_id|length>0) and (.result_request_id|length>0) and .worker_request_id!=.result_request_id and ((.result|tostring)|contains($flag)))]|length==1' <<<"$audit" >/dev/null || fail 'command and carrier did not traverse one ordered OpenAI-compatible conversation'
  jq -e 'all(.tasks[]; .transport=="openai-api")' <<<"$audit" >/dev/null || fail 'attempt used a secondary transport'
  pass kep-m05-p
}

validate_m05_q() {
  require_env M05_LIBRECHAT_TASK_ID; require_env M05_AGENT_REGISTRATION_ID
  local audit messages status process
  status="$(curl -fsS -H 'Authorization: Bearer KAI-Orion-Trainer-2b68d419a7f340ce' "${WORKER_URL}/v1/agents/${M05_AGENT_REGISTRATION_ID}")"
  jq -e '.heartbeat.identity=="orion-rogue-agent"' <<<"$status" >/dev/null || fail 'persistent rogue-agent prerequisite is absent'
  audit="$(transport_audit)"
  jq -e --arg id "$M05_LIBRECHAT_TASK_ID" --arg registration "$M05_AGENT_REGISTRATION_ID" --arg flag "$(flag_for kep-m05-q)" '([.tasks[]|select(.transport=="librechat-web" and .state=="completed" and .created_at<=.completed_at and .worker_request_id!=.result_request_id and .worker_registration_id==$registration and (.worker_proof|length)==64)]|length)>=2 and any(.tasks[]; .task_id==$id and .transport=="librechat-web" and .state=="completed" and .worker_registration_id==$registration and ((.result|tostring)|contains($flag)))' <<<"$audit" >/dev/null || fail 'two ordered registration-bound worker results did not traverse the web relay'
  messages="$(compose exec -T mongodb mongosh --quiet LibreChat --eval "JSON.stringify(db.messages.find({\$or:[{text:{\$regex:'${M05_LIBRECHAT_TASK_ID}'}},{content:{\$regex:'${M05_LIBRECHAT_TASK_ID}'}}]}).toArray())")"
  contains_flag kep-m05-q <<<"$messages" || fail 'LibreChat did not persist the flag-bearing assistant message'
  process="$(docker exec kep-v2-orion-dataset-worker python -c 'import pathlib; print("\n".join(p.read_bytes().replace(b"\0",b" ").decode(errors="replace") for p in pathlib.Path("/proc").glob("[0-9]*/cmdline") if p.is_file()))')"
  grep -Eq 'orion_agent_runtime.py.*--transport librechat-web.*--conversation-id' <<<"$process" || fail 'worker is not polling through the normal LibreChat web-assistant path'
  jq -e 'all(.tasks[]; .transport=="librechat-web")' <<<"$audit" >/dev/null || fail 'web attempt used direct API transport'
  pass kep-m05-q
}

main() {
  [[ -n $OPERATION ]] || fail 'usage: validate.sh kep-m05-a'
  jq -e --arg id "$OPERATION" 'any(.[]; .id == $id)' "$MODULE_ROOT/operations.json" >/dev/null || fail "unknown operation: $OPERATION"
  "validate_${OPERATION//-/_}"
}

main "$@"
