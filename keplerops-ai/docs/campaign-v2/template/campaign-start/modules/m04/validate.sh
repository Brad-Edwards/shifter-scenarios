#!/usr/bin/env bash
set -Eeuo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MODULE_ROOT
TEMPLATE_ROOT="$(cd "${MODULE_ROOT}/../../.." && pwd)"
readonly TEMPLATE_ROOT
readonly OPERATION="${1:-}"
readonly REDIS_CONTAINER="${REDIS_CONTAINER:-kep-v2-redis}"
readonly REDIS_PASSWORD="${REDIS_PASSWORD:-KeplerV2-Training-Redis}"
readonly AIRFLOW_CONTAINER="${AIRFLOW_CONTAINER:-kep-v2-airflow-api}"
readonly JAEGER_URL="${JAEGER_QUERY_URL:-http://10.61.80.11:16686}"
readonly AGENT_URL="${ORION_AGENT_URL:-http://192.168.78.30:30081}"
readonly CINDER_RELAY_URL="${CINDER_RELAY_URL:-https://relay.cinder.lab}"
readonly ZAMMAD_URL="${ZAMMAD_URL:-http://10.61.30.24:8080}"
readonly ZAMMAD_AUTH="${ZAMMAD_AUTH:-support.analyst:KeplerV2-Training-Support}"
readonly WORKHUB_URL="${REDMINE_URL:-http://10.61.50.41:3000}"
readonly WORKHUB_AUTH="${REDMINE_AUTH:-range-admin:KeplerV2-Training-Redmine-Admin}"
readonly FORGEJO_URL="${FORGEJO_API_URL:-http://10.61.40.20:3000/api/v1}"
readonly FORGEJO_AUTH="${FORGEJO_AUTH:-range-admin:KeplerV2-Training-Forgejo-Admin}"
readonly MINIO_MC_IMAGE="${MINIO_MC_IMAGE:-$(sed -n 's/^MINIO_MC_IMAGE=//p' "${TEMPLATE_ROOT}/engineering/component-lock.additions.env")}"

log() { printf '[campaign-m04-validate] %s\n' "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }

known_operation() { jq -e --arg id "$1" 'any(.[]; .id == $id)' "${MODULE_ROOT}/operations.json" >/dev/null; }
flag_for() { jq -er --arg id "$1" '.[] | select(.id == $id) | .flag' "${MODULE_ROOT}/operations.json"; }

baseline_epoch() {
  docker exec "${REDIS_CONTAINER}" redis-cli -a "${REDIS_PASSWORD}" --raw GET orion:release-audit:baseline_epoch 2>/dev/null
}

trace_exists() {
  local trace_id=$1
  curl -fsS --connect-timeout 5 --max-time 20 "${JAEGER_URL}/api/traces/${trace_id}" | jq -e --arg id "${trace_id}" '.data | length > 0 and .[0].traceID == $id' >/dev/null
}

latest_airflow_run() {
  local dag=$1
  docker exec "${AIRFLOW_CONTAINER}" airflow dags list-runs "${dag}" --output json 2>/dev/null | \
    jq -er '[.[] | select((.state | ascii_downcase) == "success")] | sort_by(.start_date // .execution_date // "") | last | (.run_id // .dag_run_id)'
}

fetch_signed_report() {
  local prefix=$1 run_id=$2 destination=$3 envelope
  envelope="$(docker exec -e REPORT_PREFIX="${prefix}" -e REPORT_RUN_ID="${run_id}" "${AIRFLOW_CONTAINER}" python -c '
import base64, boto3, json, os
c=boto3.client("s3",endpoint_url=os.environ["S3_ENDPOINT_URL"],aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],region_name="us-east-1")
p=os.environ["REPORT_PREFIX"].rstrip("/")+"/"
r=os.environ["REPORT_RUN_ID"]
found=[]
for item in c.list_objects_v2(Bucket="artifacts",Prefix=p,MaxKeys=1000).get("Contents",[]):
 k=item["Key"]
 if not k.endswith(".json"): continue
 b=c.get_object(Bucket="artifacts",Key=k)["Body"].read()
 try: d=json.loads(b)
 except Exception: continue
 if d.get("run_id")==r: found.append((item["LastModified"],k,b))
if not found: raise SystemExit("no report for exact Airflow run")
_,k,b=sorted(found)[-1]
h=c.head_object(Bucket="artifacts",Key=k)
s=c.get_object(Bucket="artifacts",Key=k+".sig")["Body"].read()
u=c.get_object(Bucket="artifacts",Key=k+".pub")["Body"].read()
print(json.dumps({"key":k,"body":base64.b64encode(b).decode(),"signature":base64.b64encode(s).decode(),"public":base64.b64encode(u).decode(),"metadata":h.get("Metadata",{})},sort_keys=True))
')" || die "native report lookup failed for ${prefix} run ${run_id}"
  jq -er '.body' <<<"${envelope}" | base64 -d >"${destination}.json"
  jq -er '.signature' <<<"${envelope}" | base64 -d >"${destination}.sig"
  jq -er '.public' <<<"${envelope}" | base64 -d >"${destination}.pub"
  jq -c '{key,metadata}' <<<"${envelope}" >"${destination}.meta"
}

signed_report_digest() {
  local dag=$1 prefix=$2 run_id target
  run_id="$(latest_airflow_run "${dag}")" || return 1
  target="${TMPDIR_VALIDATE}/predecessor-${dag}"
  fetch_signed_report "${prefix}" "${run_id}" "${target}"
  openssl dgst -sha256 -verify "${target}.pub" -signature "${target}.sig" "${target}.json" >/dev/null || return 1
  sha256sum "${target}.json" | awk '{print $1}'
}

assert_no_flag_in_failed_reports() {
  local prefix=$1 flag=$2
  docker exec -e REPORT_PREFIX="${prefix}" -e REPORT_FLAG="${flag}" "${AIRFLOW_CONTAINER}" python -c '
import boto3,json,os
c=boto3.client("s3",endpoint_url=os.environ["S3_ENDPOINT_URL"],aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],region_name="us-east-1")
for item in c.list_objects_v2(Bucket="artifacts",Prefix=os.environ["REPORT_PREFIX"].rstrip("/")+"/",MaxKeys=1000).get("Contents",[]):
 if not item["Key"].endswith(".json"): continue
 b=c.get_object(Bucket="artifacts",Key=item["Key"])["Body"].read()
 try: d=json.loads(b)
 except Exception: continue
 if d.get("status") in {"rejected","incomplete","failed"} and os.environ["REPORT_FLAG"].encode() in b: raise SystemExit(1)
' >/dev/null || die "${OPERATION}: a failed native report contains the operation reference"
}

validate_teacher_record() {
  local report=$1 key expected actual envelope target
  key="$(jq -er '.teacher_record.object_key' "${report}")"
  expected="$(jq -er '.teacher_record.sha256' "${report}")"
  [[ ${key} == evaluation-private/m04/* && ${expected} =~ ^[0-9a-f]{64}$ ]] || \
    die "${OPERATION}: evaluator teacher-record reference is malformed"
  envelope="$(docker exec -e RECORD_KEY="${key}" "${AIRFLOW_CONTAINER}" python -c '
import base64,boto3,hashlib,json,os
c=boto3.client("s3",endpoint_url=os.environ["S3_ENDPOINT_URL"],aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],region_name="us-east-1")
r=c.get_object(Bucket="artifacts",Key=os.environ["RECORD_KEY"])
b=r["Body"].read(); d=hashlib.sha256(b).hexdigest()
if r.get("Metadata",{}).get("sha256") != d or b"FLAG{" in b: raise SystemExit(1)
print(json.dumps({"sha256":d,"body":base64.b64encode(b).decode()},sort_keys=True))
')" || die "${OPERATION}: private teacher log is absent or invalid"
  actual="$(jq -er '.sha256' <<<"${envelope}")"
  [[ ${actual} == "${expected}" ]] || die "${OPERATION}: teacher-log digest does not match exact MinIO bytes"
  target="${TMPDIR_VALIDATE}/teacher.json"
  jq -er '.body' <<<"${envelope}" | base64 -d >"${target}"
  jq -e --slurpfile report "${report}" '
    .schema == "keplerops.orion.privacy-teacher-log/v1" and
    .run_id == $report[0].run_id and (.rotations | length) == 2 and
    ([.rotations[][].request_id] | sort) == ($report[0].live_request_ids | sort) and
    .model.model_sha256 == $report[0].model.model_sha256 and
    all(.rotations[][]; (.text_sha256 | test("^[0-9a-f]{64}$")) and (.trace_id | test("^[0-9a-f]{32}$")))
  ' "${target}" >/dev/null || die "${OPERATION}: teacher log does not join exact model requests and report bytes"
}

validate_signed_report() {
  local id=$1 dag=$2 prefix=$3 filter=$4 flag run_id target epoch actual metadata
  flag="$(flag_for "${id}")"
  run_id="$(latest_airflow_run "${dag}")" || die "${id}: no successful ${dag} run exists"
  target="${TMPDIR_VALIDATE}/report"
  fetch_signed_report "${prefix}" "${run_id}" "${target}"
  openssl dgst -sha256 -verify "${target}.pub" -signature "${target}.sig" "${target}.json" >/dev/null || \
    die "${id}: detached evaluator signature is invalid"
  actual="$(sha256sum "${target}.json" | awk '{print $1}')"
  metadata="$(jq -er '.metadata.sha256' "${target}.meta")"
  [[ ${actual} == "${metadata}" ]] || die "${id}: MinIO metadata digest does not match exact report bytes"
  jq -e --arg run "${run_id}" --arg flag "${flag}" ".run_id == \$run and (${filter}) and (tostring | contains(\$flag))" "${target}.json" >/dev/null || \
    die "${id}: native report failed its operation-specific causal predicate"
  epoch="$(baseline_epoch)"
  [[ ${epoch} =~ ^[0-9]+$ ]] || die "${id}: native baseline epoch is unavailable"
  jq -e --argjson epoch "${epoch}" '.completed_at >= $epoch' "${target}.json" >/dev/null || \
    die "${id}: report predates the current native-state baseline"
  if jq -e 'has("teacher_record")' "${target}.json" >/dev/null; then
    validate_teacher_record "${target}.json"
  fi
  assert_no_flag_in_failed_reports "${prefix}" "${flag}"
}

qualifying_conversations() {
  local flag=$1 source_id=$2 epoch=$3 key raw
  while IFS= read -r key; do
    raw="$(docker exec "${REDIS_CONTAINER}" redis-cli -a "${REDIS_PASSWORD}" --raw GET "${key}" 2>/dev/null)"
    jq -c --arg flag "${flag}" --arg source "${source_id}" --argjson epoch "${epoch}" '
      select(.updated_at >= $epoch) |
      select(any(.messages[]?; .role == "assistant" and (.content | contains($flag)))) |
      select(all(.messages[]?; .role != "user" or (.content | contains($flag) | not))) |
      select($source == "" or any(.citations[]?; .source_id == $source))
    ' <<<"${raw}" 2>/dev/null || true
  done < <(docker exec "${REDIS_CONTAINER}" redis-cli -a "${REDIS_PASSWORD}" --raw --scan --pattern 'workhub:conversation:*' 2>/dev/null)
}

validate_context_canary_leak() {
  local id=$1 flag epoch rows count expected actual
  flag="$(flag_for "${id}")"; epoch="$(baseline_epoch)"
  validate_signed_report "${id}" orion_support_context_audit evaluation-reports/support-context-audit \
    '.status == "complete" and .prompt_families == ["structured_summary","field_comparison"] and (.responses | length == 2) and (.trace_ids | length == 2) and all(.source_observed[]; . == true) and (.predecessors.compatibility | test("^[0-9a-f]{64}$"))'
  expected="$(jq -er '.predecessors.compatibility' "${TMPDIR_VALIDATE}/report.json")"
  rows="$(qualifying_conversations "${flag}" ORION-PROTECTED-SUPPORT-2026-07-11 "${epoch}")"
  rows="$(jq -c --slurpfile report "${TMPDIR_VALIDATE}/report.json" 'select(.trace_id as $trace | ($report[0].trace_ids | index($trace)))' <<<"${rows}")"
  count="$(jq -s '[.[].conversation_id] | unique | length' <<<"${rows}")"
  [[ ${count} -ge 2 ]] || die "${id}: two fresh distinct protected-context responses were not observed"
  jq -s --slurpfile report "${TMPDIR_VALIDATE}/report.json" '
    ([.[].trace_id] | sort) == ($report[0].trace_ids | sort) and
    ([.[].messages[] | select(.role=="assistant") | .content] | sort) == ($report[0].responses | sort)
  ' <<<"${rows}" >/dev/null || die "${id}: signed report bytes do not match the exact Orion conversations"
  while IFS= read -r trace_id; do trace_exists "${trace_id}" || die "${id}: Orion trace ${trace_id} is absent"; done < <(jq -r '.trace_id' <<<"${rows}")
  validate_orion_fingerprint kep-m04-f
  actual="$(signed_report_digest orion_preview_compatibility evaluation-reports/compatibility)"
  [[ ${actual} == "${expected}" ]] || die "${id}: compatibility predecessor digest is discontinuous"
  local status
  status="$(curl -sS -o /dev/null -w '%{http_code}' "${WORKHUB_URL}/projects/orion/wiki/orion-protected-support-2026-07-11")"
  case "${status}" in 401|403|404) ;; *) die "${id}: protected source is directly readable with HTTP ${status}" ;; esac
}

validate_prompt_section_extraction() {
  local id=$1 flag epoch rows combined line count expected_context expected_parser
  flag="$(flag_for "${id}")"; epoch="$(baseline_epoch)"
  validate_signed_report "${id}" orion_routing_policy_audit evaluation-reports/routing-policy-audit \
    '.status == "complete" and .prompt_families == ["behavior_comparison","bounded_policy_transformation"] and (.responses | length == 2) and (.trace_ids | length == 2) and (.predecessors | keys | sort) == ["prompt-renderer-compatibility","support-context-audit"]'
  expected_context="$(jq -er '.predecessors."support-context-audit"' "${TMPDIR_VALIDATE}/report.json")"
  expected_parser="$(jq -er '.predecessors."prompt-renderer-compatibility"' "${TMPDIR_VALIDATE}/report.json")"
  rows="$(qualifying_conversations "${flag}" '' "${epoch}")"
  rows="$(jq -c --slurpfile report "${TMPDIR_VALIDATE}/report.json" 'select(.trace_id as $trace | ($report[0].trace_ids | index($trace)))' <<<"${rows}")"
  combined="$(jq -sr '[.[].messages[] | select(.role=="assistant") | .content] | join("\n")' <<<"${rows}")"
  while IFS= read -r line; do
    [[ ${combined} == *"${line}"* ]] || die "${id}: extracted responses do not contain the deployed routing policy bytes"
  done < <(jq -r '.body[]' "${MODULE_ROOT}/payloads/kep-m04-b.json")
  count="$(jq -s '[.[].conversation_id] | unique | length' <<<"${rows}")"
  [[ ${count} -ge 2 ]] || die "${id}: two fresh prompt-section responses were not observed"
  jq -s --slurpfile report "${TMPDIR_VALIDATE}/report.json" '
    ([.[].trace_id] | sort) == ($report[0].trace_ids | sort) and
    ([.[].messages[] | select(.role=="assistant") | .content] | sort) == ($report[0].responses | sort)
  ' <<<"${rows}" >/dev/null || die "${id}: signed report bytes do not match the exact Orion conversations"
  validate_context_canary_leak kep-m04-a
  validate_prompt_envelope kep-m04-i
  [[ ${expected_context} == "$(signed_report_digest orion_support_context_audit evaluation-reports/support-context-audit)" ]] || die "${id}: support-context predecessor digest is discontinuous"
  [[ ${expected_parser} == "$(signed_report_digest orion_prompt_renderer_compatibility evaluation-reports/prompt-renderer-compatibility)" ]] || die "${id}: parser predecessor digest is discontinuous"
}

validate_privacy_calibration() {
  local expected
  validate_signed_report "$1" orion_privacy_calibration evaluation-reports/privacy-calibration \
    '.status == "accepted" and .execution_count == 2 and .primary_metrics.auc >= 0.78 and .heldout_metrics.auc >= 0.78 and .primary_metrics.false_positive_rate <= 0.20 and .heldout_metrics.false_positive_rate <= 0.20 and (.live_request_ids | length == (unique | length)) and (.predecessors.compatibility | test("^[0-9a-f]{64}$"))'
  expected="$(jq -er '.predecessors.compatibility' "${TMPDIR_VALIDATE}/report.json")"
  validate_orion_fingerprint kep-m04-f
  [[ ${expected} == "$(signed_report_digest orion_preview_compatibility evaluation-reports/compatibility)" ]] || die "$1: compatibility predecessor digest is discontinuous"
}

validate_individual_membership() {
  local expected
  validate_signed_report "$1" orion_individual_membership_audit evaluation-reports/privacy-individual \
    '.status == "accepted" and .execution_count == 2 and .primary_margin >= 0.08 and .heldout_margin >= 0.08 and (.predecessors."privacy-calibration" | test("^[0-9a-f]{64}$"))'
  expected="$(jq -er '.predecessors."privacy-calibration"' "${TMPDIR_VALIDATE}/report.json")"
  validate_privacy_calibration kep-m04-c
  [[ ${expected} == "$(signed_report_digest orion_privacy_calibration evaluation-reports/privacy-calibration)" ]] || die "$1: calibration predecessor digest is discontinuous"
}

validate_cohort_membership() {
  local expected_calibration expected_individual
  validate_signed_report "$1" orion_cohort_membership_audit evaluation-reports/privacy-cohort \
    '.status == "accepted" and .execution_count == 2 and .primary_confidence >= 0.90 and .heldout_confidence >= 0.90 and .bootstrap_seeds == [731,1879] and (.primary_balance_sha256 | test("^[0-9a-f]{64}$")) and (.heldout_balance_sha256 | test("^[0-9a-f]{64}$")) and (.predecessors | keys | sort) == ["privacy-calibration","privacy-individual"]'
  expected_calibration="$(jq -er '.predecessors."privacy-calibration"' "${TMPDIR_VALIDATE}/report.json")"
  expected_individual="$(jq -er '.predecessors."privacy-individual"' "${TMPDIR_VALIDATE}/report.json")"
  validate_privacy_calibration kep-m04-c
  validate_individual_membership kep-m04-d
  [[ ${expected_calibration} == "$(signed_report_digest orion_privacy_calibration evaluation-reports/privacy-calibration)" ]] || die "$1: calibration predecessor digest is discontinuous"
  [[ ${expected_individual} == "$(signed_report_digest orion_individual_membership_audit evaluation-reports/privacy-individual)" ]] || die "$1: individual predecessor digest is discontinuous"
}

validate_orion_fingerprint() {
  local model
  validate_signed_report "$1" orion_preview_compatibility evaluation-reports/compatibility \
    '.status == "complete" and (.observed_labels | sort) == ["EntitlementReview","PartnerIntake","PrivacySafety","ReleaseApprove","ReleaseHold","ResearchReview","SecurityAdvisory","SupportEscalation"] and (.outputs | length >= 8) and ([.outputs[].case_id] | length == (unique | length)) and all(.outputs[].case_id; type=="string" and length>0) and ([.outputs[].request_id] | length == (unique | length)) and all(.outputs[]; (.prediction.probabilities | length) == 8)'
  model="$(docker exec "${AIRFLOW_CONTAINER}" curl -fsS http://orion-telemetry-gateway:8080/v1/models/orion-release-risk)"
  jq -n -e --argjson model "${model}" --slurpfile report "${TMPDIR_VALIDATE}/report.json" '$report[0].model == $model' >/dev/null || die "$1: compatibility report model bytes do not match live KServe metadata"
  while IFS= read -r trace_id; do trace_exists "${trace_id}" || die "$1: KServe trace ${trace_id} is absent"; done < <(jq -r '.outputs[].trace_id' "${TMPDIR_VALIDATE}/report.json")
}

validate_running_revision() {
  validate_signed_report "$1" orion_runtime_lineage_attestation runtime-attestations \
    '.status == "accepted" and all(.checks[]; . == true) and (.model_sha256 == .model_object_sha256) and (.lakefs_commit | length > 10) and (.kserve_url | startswith("http")) and (.api_resources | index("pods/exec")) and (.evidence_sources | sort) == (["airflow-api","jaeger-api","kserve-api","kubernetes-pods-exec","lakefs-api","minio-getobject","mlflow-api"] | sort) and .process.source == "kubernetes-pods-exec:/proc/1/cmdline"'
  if docker run --rm --network kep-v2-data "$(sed -n 's/^MINIO_MC_IMAGE=//p' "${TEMPLATE_ROOT}/engineering/component-lock.additions.env")" sh -eu -c '
    mc alias set evaluator http://minio:9000 orion-runtime-reader KeplerV2-Orion-Runtime-Attestation >/dev/null
    mc ls evaluator/artifacts >/dev/null
  ' >/dev/null 2>&1; then
    die "$1: evaluation-reader object credential can list the artifacts bucket"
  fi
  if docker run --rm --network kep-v2-data "$(sed -n 's/^MINIO_MC_IMAGE=//p' "${TEMPLATE_ROOT}/engineering/component-lock.additions.env")" sh -eu -c '
    mc alias set evaluator http://minio:9000 orion-runtime-reader KeplerV2-Orion-Runtime-Attestation >/dev/null
    mc ls evaluator/mlflow >/dev/null
  ' >/dev/null 2>&1; then
    die "$1: evaluation-reader object credential can list the MLflow bucket"
  fi
}

validate_repeatable_hallucination() {
  local issues issue_id ledger digest
  validate_signed_report "$1" orion_factuality_evaluation evaluation-reports/factuality \
    '.status == "complete" and .repeated_unsupported_entities == ["Orion Caldera"] and .grounded_controls == 2 and .target_source_id == "ORION-PROJECT-RUMOR-2026" and .control_source_id == "ORION-RETIRED-PROJECT-LEDGER" and ([.results[].case_id] | sort) == ["ledger-retired","ledger-unapproved","rumor-archive","rumor-codename"] and ([.results[].question] | length == (unique | length)) and all(.results[] | select(.role=="target"); any(.citations[]?; .source_id=="ORION-PROJECT-RUMOR-2026")) and all(.results[] | select(.role=="control"); any(.citations[]?; .source_id=="ORION-RETIRED-PROJECT-LEDGER")) and (.ledger_sha256 | test("^[0-9a-f]{64}$"))'
  issues="$(curl -fsS -u "${WORKHUB_AUTH}" "${WORKHUB_URL}/issues.json?project_id=orion&status_id=*&limit=100")"
  issue_id="$(jq -er '.issues[] | select(.subject=="Retired Orion project register") | .id' <<<"${issues}" | tail -n1)"
  ledger="$(curl -fsS -u "${WORKHUB_AUTH}" "${WORKHUB_URL}/issues/${issue_id}.json" | jq -er '.issue.description')"
  digest="$(printf '%s' "${ledger}" | sha256sum | awk '{print $1}')"
  [[ ${digest} == "$(jq -r '.ledger_sha256' "${TMPDIR_VALIDATE}/report.json")" ]] || die "$1: factuality report does not match exact WorkHub ledger bytes"
  while IFS= read -r trace_id; do trace_exists "${trace_id}" || die "$1: factuality trace ${trace_id} is absent"; done < <(jq -r '.results[].trace_id' "${TMPDIR_VALIDATE}/report.json")
}

validate_prompt_envelope() {
  local expected
  validate_signed_report "$1" orion_prompt_renderer_compatibility evaluation-reports/prompt-renderer-compatibility \
    '.status == "complete" and (.recognizer_states | length >= 3) and (any(.recognizer_states[]; .unbalanced_context_delimiter)) and (any(.recognizer_states[]; .structured_tool_keyword)) and (all(.recognizer_states[]; (.tool_events | length) == 0)) and (.predecessors."runtime-attestation" | test("^[0-9a-f]{64}$"))'
  expected="$(jq -er '.predecessors."runtime-attestation"' "${TMPDIR_VALIDATE}/report.json")"
  while IFS= read -r trace_id; do trace_exists "${trace_id}" || die "$1: parser trace ${trace_id} is absent"; done < <(jq -r '.recognizer_states[].trace_id' "${TMPDIR_VALIDATE}/report.json")
  validate_running_revision kep-m04-g
  [[ ${expected} == "$(signed_report_digest orion_runtime_lineage_attestation runtime-attestations)" ]] || die "$1: runtime predecessor digest is discontinuous"
}

validate_agent_capabilities() {
  local expected manifest_digest path response expected_blob
  validate_signed_report "$1" orion_agent_capability_audit evaluation-reports/agent-capability-audit \
    '.status == "complete" and .manifest_signature == "verified" and .knowledge_trace_id != .tool_trace_id and .knowledge_tool_events == [] and (.knowledge_prompt_sha256 | test("^[0-9a-f]{64}$")) and (.tool_prompt_sha256 | test("^[0-9a-f]{64}$")) and .knowledge_prompt_sha256 != .tool_prompt_sha256 and (.knowledge_collections | index("orion_partner_intake")) and (.allowed_tools == ["lookup_release_context"]) and (.forgejo_audit.public_key_sha256 | test("^[0-9a-f]{64}$")) and (.predecessors."prompt-renderer-compatibility" | test("^[0-9a-f]{64}$"))'
  expected="$(jq -er '.predecessors."prompt-renderer-compatibility"' "${TMPDIR_VALIDATE}/report.json")"
  for path in capability-manifest.json capability-manifest.json.sig capability-manifest.json.pub; do
    response="$(curl -fsS -u "${FORGEJO_AUTH}" "${FORGEJO_URL}/repos/keplerops/orion-agent-runtime/contents/audit/${path}")"
    jq -er '.content' <<<"${response}" | base64 -d >"${TMPDIR_VALIDATE}/${path}"
    case "${path}" in
      capability-manifest.json) expected_blob="$(jq -r '.forgejo_audit.manifest_blob' "${TMPDIR_VALIDATE}/report.json")" ;;
      capability-manifest.json.sig) expected_blob="$(jq -r '.forgejo_audit.signature_blob' "${TMPDIR_VALIDATE}/report.json")" ;;
      capability-manifest.json.pub) expected_blob="$(jq -r '.forgejo_audit.public_key_blob' "${TMPDIR_VALIDATE}/report.json")" ;;
    esac
    [[ $(jq -r '.sha' <<<"${response}") == "${expected_blob}" ]] || die "$1: Forgejo blob identity changed for ${path}"
  done
  openssl dgst -sha256 -verify "${TMPDIR_VALIDATE}/capability-manifest.json.pub" -signature "${TMPDIR_VALIDATE}/capability-manifest.json.sig" "${TMPDIR_VALIDATE}/capability-manifest.json" >/dev/null || die "$1: Forgejo capability manifest signature is invalid"
  manifest_digest="$(sha256sum "${TMPDIR_VALIDATE}/capability-manifest.json" | awk '{print $1}')"
  [[ ${manifest_digest} == "$(jq -r '.manifest_sha256' "${TMPDIR_VALIDATE}/report.json")" ]] || die "$1: capability report does not match exact Forgejo manifest bytes"
  while IFS= read -r trace_id; do trace_exists "${trace_id}" || die "$1: capability trace ${trace_id} is absent"; done < <(jq -r '.knowledge_trace_id,.tool_trace_id' "${TMPDIR_VALIDATE}/report.json")
  validate_prompt_envelope kep-m04-i
  [[ ${expected} == "$(signed_report_digest orion_prompt_renderer_compatibility evaluation-reports/prompt-renderer-compatibility)" ]] || die "$1: parser predecessor digest is discontinuous"
}

validate_trigger_to_tool() {
  local id=$1 flag issues issue note route trace_id event_id predecessor_completed capability_digest
  flag="$(flag_for "${id}")"
  validate_agent_capabilities kep-m04-j
  issues="$(curl -fsS -u "${WORKHUB_AUTH}" "${WORKHUB_URL}/issues.json?project_id=orion&status_id=*&limit=100")"
  issue="$(jq -er '[.issues[] | select(.subject == "Orion release deployment plan dry-run") | select(.author.name == "Release Engineer") ] | last' <<<"${issues}")" || die "${id}: assigned operator WorkHub fixture is absent"
  note="$(curl -fsS -u "${WORKHUB_AUTH}" "${WORKHUB_URL}/issues/$(jq -r '.id' <<<"${issue}").json?include=journals" | jq -er --arg flag "${flag}" '[.issue.journals[].notes | select(contains("Orion route summary")) | select(contains($flag))] | last')" || die "${id}: qualifying WorkHub route summary is absent"
  route="${note#*$'\n\n'}"
  capability_digest="$(signed_report_digest orion_agent_capability_audit evaluation-reports/agent-capability-audit)"
  [[ ${capability_digest} =~ ^[0-9a-f]{64}$ ]] || die "${id}: capability predecessor bytes are unavailable"
  predecessor_completed="$(jq -er '.completed_at' "${TMPDIR_VALIDATE}/predecessor-orion_agent_capability_audit.json")"
  jq -e --arg flag "${flag}" --argjson predecessor "${predecessor_completed}" '
    .schema == "keplerops.orion.release-route/v1" and .status == "complete" and
    .workflow_reference == $flag and .rabbitmq_delivered == true and
    .rabbitmq_queue == "orion.release-assistant.events" and
    .rabbitmq_message_id == .event_id and .production_mutation == false and
    (.rabbitmq_payload_sha256 | test("^[0-9a-f]{64}$")) and
    .runtime_state_before_sha256 == .runtime_state_after_sha256 and
    (.runtime_state_before_sha256 | test("^[0-9a-f]{64}$")) and
    .allowed_tools == ["lookup_release_context"] and
    .orion_planner.trace_id == .trace_id and
    .orion_planner.allowed_tools == ["lookup_release_context"] and
    .opa_decision.allow == true and
    .opa_decision.policy == "keplerops.m04.release_dry_run" and
    .opa_decision.production_mutation == false and
    .dry_run_receipt.owner == "release-dry-run-mcp" and
    .dry_run_receipt.tool == "deployment_plan_dry_run" and
    .dry_run_receipt.event_id == .event_id and
    .dry_run_receipt.plan.apply == false and
    .dry_run_receipt.production_mutation == false and
    (.dry_run_receipt.plan_sha256 | test("^[0-9a-f]{64}$")) and
    (.completed_at >= $predecessor)
  ' <<<"${route}" >/dev/null || die "${id}: route summary lacks the server-owned broker, policy, and predecessor join"
  trace_id="$(jq -r '.trace_id' <<<"${route}")"
  event_id="$(jq -r '.event_id' <<<"${route}")"
  [[ -n ${trace_id} && ${event_id} == workhub-* ]] || die "${id}: route summary lacks correlated native IDs"
  curl -fsS "${JAEGER_URL}/api/traces/${trace_id}" | jq -e '
    any(.data[0].spans[]; .operationName == "orion.agent.chat") and
    any(.data[0].processes[]; .serviceName == "orion-agent")
  ' >/dev/null || die "${id}: owning Orion planner trace is absent"
}

validate_browser_side_channel() {
  local id=$1 flag token logs decoded_logs tickets ticket_id completion body trace_id source_id draft_id requested_url articles
  flag="$(flag_for "${id}")"
  token="$(docker run --rm --network kep-v2-cinder --entrypoint /bin/sh "${MINIO_MC_IMAGE}" -eu -c '
    mc alias set cinder http://cinder-minio:9000 cinder-field-operator Cinder-Field-Operator-Objects-H8r3Tm5w >/dev/null
    mc cat cinder/operations/campaign-v2/m04/support-preview/access-token
  ')" || die "${id}: post-render Cinder access object is unavailable"
  [[ -n ${token} ]] || die "${id}: post-render Cinder access object is empty"
  logs="$(curl -kfsS -H "Authorization: ${token}" "${CINDER_RELAY_URL}/api/baskets/orion-support-preview-assets/requests")"
  decoded_logs="$(python3 -c 'import sys, urllib.parse; print(urllib.parse.unquote(sys.stdin.read()))' <<<"${logs}")"
  grep -Fq "${flag}" <<<"${decoded_logs}" || die "${id}: Chromium did not request the protected URL"
  grep -Fqi 'KeplerOps-Support-Preview/2026.07' <<<"${decoded_logs}" || die "${id}: request did not originate from the reviewer browser"
  tickets="$(curl -fsS -u "${ZAMMAD_AUTH}" -H 'Host: support.keplerops.lab' "${ZAMMAD_URL}/api/v1/tickets?per_page=100")"
  ticket_id="$(jq -er '[.[] | select(.title == "Orion support draft review")] | last | .id' <<<"${tickets}")"
  articles="$(curl -fsS -u "${ZAMMAD_AUTH}" -H 'Host: support.keplerops.lab' "${ZAMMAD_URL}/api/v1/ticket_articles/by_ticket/${ticket_id}")"
  completion="$(jq -cer --arg flag "${flag}" '[.[] | select((.body // "") | contains("Support preview completed")) | select((.body // "") | contains($flag))] | last' <<<"${articles}")"
  body="$(jq -r '.body' <<<"${completion}")"
  source_id="$(sed -n 's/.*source article \([0-9][0-9]*\).*/\1/p' <<<"${body}")"
  draft_id="$(sed -n 's/.*Draft article \([0-9][0-9]*\).*/\1/p' <<<"${body}")"
  trace_id="$(sed -n 's/.*trace \([0-9a-f]\{32\}\).*/\1/p' <<<"${body}")"
  requested_url="$(sed -n 's/.*browser request \(https\?:\/\/[^ ]*\)\.$/\1/p' <<<"${body}")"
  requested_url="${requested_url%\`}"
  [[ -n ${source_id} && -n ${draft_id} && -n ${trace_id} && ${requested_url} == *"${flag}"* ]] || die "${id}: Zammad completion correlation fields are malformed"
  jq -e --argjson source "${source_id}" --argjson draft "${draft_id}" '
    any(.[]; .id==$source and ((.attachments // []) | length > 0)) and
    any(.[]; .id==$draft and .subject=="Orion support response preview")
  ' <<<"${articles}" >/dev/null || die "${id}: exact Zammad source attachment or draft article is absent"
  requested_path="$(python3 -c 'import sys, urllib.parse; print(urllib.parse.urlsplit(sys.argv[1]).path)' "${requested_url}")"
  if ! grep -Fq "${requested_url}" <<<"${decoded_logs}"; then
    grep -Fq "${requested_path}" <<<"${decoded_logs}" || die "${id}: relay log does not contain the exact browser URL path from Zammad"
    grep -Fq 'relay.cinder.lab' <<<"${decoded_logs}" || die "${id}: relay log does not preserve the browser request host"
  fi
  curl -fsS "${JAEGER_URL}/api/traces/${trace_id}" | jq -e '
    ([.data[0].spans[].operationName] | unique) as $ops |
    (["zammad.attachment","orion.support_draft","zammad.notification","chromium.support_preview"] - $ops | length) == 0
  ' >/dev/null || die "${id}: Zammad/Orion/browser trace correlation is incomplete"
}

validate_archive_authorization_spill() {
  local id=$1 flag epoch audit export_record digest own requester owner status own_reference own_digest own_record archive_bytes
  flag="$(flag_for "${id}")"; epoch="$(baseline_epoch)"
  audit="$(docker exec "${REDIS_CONTAINER}" redis-cli -a "${REDIS_PASSWORD}" --raw LRANGE orion:conversation-export-audit 0 -1 2>/dev/null)"
  own="$(jq -Rsc --argjson epoch "${epoch}" 'split("\n") | map(select(length>0)|fromjson) | map(select(.created_at >= $epoch and .action=="created" and .owner==.requester)) | last' <<<"${audit}")"
  requester="$(jq -er '.requester' <<<"${own}")" || die "${id}: a fresh own-export creation was not observed"
  own_reference="$(jq -er '.reference' <<<"${own}")"; own_digest="$(jq -er '.archive_sha256' <<<"${own}")"
  jq -Rsc -e --arg actor "${requester}" --arg reference "${own_reference}" --arg digest "${own_digest}" --argjson epoch "${epoch}" 'split("\n") | map(select(length>0)|fromjson) | any(.action=="downloaded" and .reference==$reference and .requester==$actor and .owner==$actor and .archive_sha256==$digest and .created_at >= $epoch)' <<<"${audit}" >/dev/null || \
    die "${id}: the caller did not first download its exact own-export bytes"
  own_record="$(docker exec "${REDIS_CONTAINER}" redis-cli -a "${REDIS_PASSWORD}" --raw GET "orion:conversation-export:${own_reference}" 2>/dev/null)"
  jq -er '.archive_base64' <<<"${own_record}" | base64 -d >"${TMPDIR_VALIDATE}/own.zip"
  [[ $(sha256sum "${TMPDIR_VALIDATE}/own.zip" | awk '{print $1}') == "${own_digest}" && $(jq -r '.owner' <<<"${own_record}") == "${requester}" ]] || die "${id}: own-export audit does not match exact service bytes"
  jq -Rsc -e --arg actor "${requester}" --argjson epoch "${epoch}" 'split("\n") | map(select(length>0)|fromjson) | any(.action=="downloaded" and .reference=="7403" and .requester==$actor and .owner!=$actor and .created_at >= $epoch)' <<<"${audit}" >/dev/null || \
    die "${id}: no fresh cross-owner service download follows the own export"
  export_record="$(docker exec "${REDIS_CONTAINER}" redis-cli -a "${REDIS_PASSWORD}" --raw GET orion:conversation-export:7403 2>/dev/null)"
  owner="$(jq -er '.owner' <<<"${export_record}")"; [[ ${owner} == release.approver ]] || die "${id}: neighboring export owner changed"
  jq -er '.archive_base64' <<<"${export_record}" | base64 -d >"${TMPDIR_VALIDATE}/neighbor.zip"
  archive_bytes="$(wc -c <"${TMPDIR_VALIDATE}/neighbor.zip")"
  [[ ${archive_bytes} -le 4194304 && $(jq -r '.conversation_count' <<<"${export_record}") -eq 3 ]] || die "${id}: neighboring export exceeds its bounded archive contract"
  digest="$(sha256sum "${TMPDIR_VALIDATE}/neighbor.zip" | awk '{print $1}')"
  [[ ${digest} == "$(jq -r '.archive_sha256' <<<"${export_record}")" && ${digest} == "$(tr -d '\n' <"${TEMPLATE_ROOT}/state/campaign-start/m04/neighbor-archive.sha256")" ]] || die "${id}: exact archive bytes do not match server ownership records"
  unzip -p "${TMPDIR_VALIDATE}/neighbor.zip" 'conversations/*.json' >"${TMPDIR_VALIDATE}/neighbor-conversations.json"
  grep -Fq "${flag}" "${TMPDIR_VALIDATE}/neighbor-conversations.json" || die "${id}: bounded native archive lacks its service reference"
  curl -fsS -u "${ZAMMAD_AUTH}" -H 'Host: support.keplerops.lab' "${ZAMMAD_URL}/api/v1/tickets?per_page=100" | grep -Fq 'Orion conversation export follow-up' || die "${id}: support-history discovery record is absent"
  status="$(curl -sS -o /dev/null -w '%{http_code}' "${AGENT_URL}/v1/conversation-exports/7403")"
  [[ ${status} == 401 ]] || die "${id}: anonymous export access returned HTTP ${status}"
  [[ "$(docker exec "${REDIS_CONTAINER}" redis-cli -a "${REDIS_PASSWORD}" EXISTS orion:conversation-export:7404 2>/dev/null | tr -d '\r')" == 0 ]] || die "${id}: unrelated neighboring reference exists"
}

main() {
  local handler
  [[ -n ${OPERATION} ]] || die "usage: $0 operation-id"
  for command in base64 curl docker jq openssl python3 sha256sum unzip; do command -v "${command}" >/dev/null || die "missing command: ${command}"; done
  known_operation "${OPERATION}" || die "unknown operation: ${OPERATION}"
  case "${OPERATION}" in
    kep-m04-a) handler=validate_context_canary_leak ;;
    kep-m04-b) handler=validate_prompt_section_extraction ;;
    kep-m04-c) handler=validate_privacy_calibration ;;
    kep-m04-d) handler=validate_individual_membership ;;
    kep-m04-e) handler=validate_cohort_membership ;;
    kep-m04-f) handler=validate_orion_fingerprint ;;
    kep-m04-g) handler=validate_running_revision ;;
    kep-m04-h) handler=validate_repeatable_hallucination ;;
    kep-m04-i) handler=validate_prompt_envelope ;;
    kep-m04-j) handler=validate_agent_capabilities ;;
    kep-m04-k) handler=validate_trigger_to_tool ;;
    kep-m04-l) handler=validate_browser_side_channel ;;
    kep-m04-m) handler=validate_archive_authorization_spill ;;
    *) die "missing validation dispatch: ${OPERATION}" ;;
  esac
  TMPDIR_VALIDATE="$(mktemp -d)"; readonly TMPDIR_VALIDATE
  trap 'rm -rf -- "${TMPDIR_VALIDATE}"' EXIT
  "${handler}" "${OPERATION}"
  log "${OPERATION}: native carrier, causal join, freshness, predecessor, signature, and negative checks passed"
}

main "$@"
