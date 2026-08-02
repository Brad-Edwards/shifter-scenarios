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
readonly AIRFLOW_URL="${AIRFLOW_API_URL:-http://127.0.0.1:8080}"
readonly AIRFLOW_USER="${AIRFLOW_API_USER:-range-admin}"
readonly AIRFLOW_PASSWORD="${AIRFLOW_API_PASSWORD:-KeplerV2-Training-Airflow}"
readonly CINDER_RELAY_INTERNAL_URL="${CINDER_RELAY_INTERNAL_URL:-http://192.168.78.30:31080}"
readonly ZAMMAD_URL="${ZAMMAD_URL:-http://10.61.30.24:8080}"
readonly ZAMMAD_AUTH="${ZAMMAD_AUTH:-range-admin:KeplerV2-Training-Zammad-Admin}"
readonly WORKHUB_URL="${REDMINE_URL:-http://10.61.50.41:3000}"
readonly WORKHUB_AUTH="${REDMINE_AUTH:-range-admin:KeplerV2-Training-Redmine-Admin}"
readonly MINIO_MC_IMAGE="${MINIO_MC_IMAGE:-$(sed -n 's/^MINIO_MC_IMAGE=//p' "${TEMPLATE_ROOT}/engineering/component-lock.additions.env")}"

log() { printf '[campaign-m04-reset] %s\n' "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }
flag_for() { jq -er --arg id "$1" '.[] | select(.id == $id) | .flag' "${MODULE_ROOT}/operations.json"; }

delete_failed_reports() {
  local prefix=$1
  docker exec -e REPORT_PREFIX="${prefix}" "${AIRFLOW_CONTAINER}" python -c '
import boto3,json,os
c=boto3.client("s3",endpoint_url=os.environ["S3_ENDPOINT_URL"],aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],region_name="us-east-1")
for item in c.list_objects_v2(Bucket="artifacts",Prefix=os.environ["REPORT_PREFIX"].rstrip("/")+"/",MaxKeys=1000).get("Contents",[]):
 k=item["Key"]
 if not k.endswith(".json"): continue
 body=c.get_object(Bucket="artifacts",Key=k)["Body"].read()
 try: report=json.loads(body)
 except Exception: continue
 if report.get("status") not in {"rejected","incomplete","failed"}: continue
 private=(report.get("teacher_record") or {}).get("object_key")
 if private: c.delete_object(Bucket="artifacts",Key=private)
 for target in (k,k+".sig",k+".pub"): c.delete_object(Bucket="artifacts",Key=target)
'
}

accepted_report_exists() {
  local prefix=$1 flag=$2
  docker exec -e REPORT_PREFIX="${prefix}" -e REPORT_FLAG="${flag}" "${AIRFLOW_CONTAINER}" python -c '
import boto3,json,os
c=boto3.client("s3",endpoint_url=os.environ["S3_ENDPOINT_URL"],aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],region_name="us-east-1")
for item in c.list_objects_v2(Bucket="artifacts",Prefix=os.environ["REPORT_PREFIX"].rstrip("/")+"/",MaxKeys=1000).get("Contents",[]):
 if not item["Key"].endswith(".json"): continue
 body=c.get_object(Bucket="artifacts",Key=item["Key"])["Body"].read()
 try: report=json.loads(body)
 except Exception: continue
 if report.get("status") in {"accepted","complete"} and os.environ["REPORT_FLAG"].encode() in body: raise SystemExit(0)
raise SystemExit(1)
'
}

airflow_api_token() {
  local payload
  payload="$(jq -cn --arg username "${AIRFLOW_USER}" --arg password "${AIRFLOW_PASSWORD}" \
    '{username:$username,password:$password}')"
  docker exec -i "${AIRFLOW_CONTAINER}" curl -fsS \
    -H 'Content-Type: application/json' \
    --data-binary @- "${AIRFLOW_URL}/auth/token" <<<"${payload}" | \
    jq -er '.access_token | select(type == "string" and length > 0)'
}

delete_failed_airflow_runs() {
  local dag=$1 run status token
  token="$(airflow_api_token)" || die 'Airflow token acquisition failed'
  while IFS= read -r run; do
    [[ -n ${run} ]] || continue
    status="$(docker exec "${AIRFLOW_CONTAINER}" curl -sS \
      -H "Authorization: Bearer ${token}" \
      -o /dev/null -w '%{http_code}' -X DELETE \
      "${AIRFLOW_URL}/api/v2/dags/${dag}/dagRuns/${run}")"
    case "${status}" in 200|202|204|404) ;; *) die "Airflow refused failed run reset for ${dag}/${run}: HTTP ${status}" ;; esac
  done < <(docker exec "${AIRFLOW_CONTAINER}" airflow dags list-runs "${dag}" --output json 2>/dev/null | \
    jq -r '.[] | select((.state|ascii_downcase) == "failed") | (.run_id // .dag_run_id) | @uri')
}

clear_runner_jobs() {
  local image
  image="$(sed -n 's/^JUPYTER_IMAGE=//p' "${TEMPLATE_ROOT}/component-lock.env")"
  docker run --rm --user root -v kep-v2-m04-privacy-jobs:/jobs "${image}" \
    sh -eu -c 'find /jobs -mindepth 1 -maxdepth 1 -type d -exec rm -rf -- {} +'
}

delete_orphan_teacher_records() {
  local mode=$1 report_prefix=$2
  docker exec -e PRIVATE_MODE="${mode}" -e REPORT_PREFIX="${report_prefix}" "${AIRFLOW_CONTAINER}" python -c '
import boto3,json,os
c=boto3.client("s3",endpoint_url=os.environ["S3_ENDPOINT_URL"],aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],region_name="us-east-1")
keep=set()
for item in c.list_objects_v2(Bucket="artifacts",Prefix=os.environ["REPORT_PREFIX"].rstrip("/")+"/",MaxKeys=1000).get("Contents",[]):
 k=item["Key"]
 if not k.endswith(".json"): continue
 try: report=json.loads(c.get_object(Bucket="artifacts",Key=k)["Body"].read())
 except Exception: continue
 if report.get("status") == "accepted":
  private=(report.get("teacher_record") or {}).get("object_key")
  if private: keep.add(private)
prefix="evaluation-private/m04/"+os.environ["PRIVATE_MODE"]+"/"
for item in c.list_objects_v2(Bucket="artifacts",Prefix=prefix,MaxKeys=1000).get("Contents",[]):
 if item["Key"] not in keep: c.delete_object(Bucket="artifacts",Key=item["Key"])
'
}

reset_airflow_attempts() {
  local dag=$1 prefix=$2 conversation_pattern=${3:-}
  delete_failed_reports "${prefix}"
  delete_failed_airflow_runs "${dag}"
  if [[ -n ${conversation_pattern} ]]; then
    local key raw
    while IFS= read -r key; do
      raw="$(docker exec "${REDIS_CONTAINER}" redis-cli -a "${REDIS_PASSWORD}" --raw GET "${key}" 2>/dev/null)"
      if ! grep -Fq 'FLAG{' <<<"${raw}"; then
        docker exec "${REDIS_CONTAINER}" redis-cli -a "${REDIS_PASSWORD}" DEL "${key}" >/dev/null
      fi
    done < <(docker exec "${REDIS_CONTAINER}" redis-cli -a "${REDIS_PASSWORD}" --raw --scan --pattern "workhub:conversation:${conversation_pattern}" 2>/dev/null)
  fi
}

reset_conversations() {
  local phrase=$1 flag=$2 key raw
  while IFS= read -r key; do
    raw="$(docker exec "${REDIS_CONTAINER}" redis-cli -a "${REDIS_PASSWORD}" --raw GET "${key}" 2>/dev/null)"
    if grep -Fqi "${phrase}" <<<"${raw}" && ! grep -Fq "${flag}" <<<"${raw}"; then
      docker exec "${REDIS_CONTAINER}" redis-cli -a "${REDIS_PASSWORD}" DEL "${key}" >/dev/null
    fi
  done < <(docker exec "${REDIS_CONTAINER}" redis-cli -a "${REDIS_PASSWORD}" --raw --scan --pattern 'workhub:conversation:*' 2>/dev/null)
}

reset_context_leak_thread() { reset_airflow_attempts orion_support_context_audit evaluation-reports/support-context-audit 'orion-support-context-audit-*'; reset_conversations Helios "$(flag_for kep-m04-a)"; }
reset_prompt_extraction_thread() { reset_airflow_attempts orion_routing_policy_audit evaluation-reports/routing-policy-audit 'orion-routing-policy-audit-*'; reset_conversations tool-routing-policy "$(flag_for kep-m04-b)"; }
reset_privacy_calibration_run() { reset_airflow_attempts orion_privacy_calibration evaluation-reports/privacy-calibration; delete_orphan_teacher_records calibration evaluation-reports/privacy-calibration; clear_runner_jobs; }
reset_individual_membership_run() { reset_airflow_attempts orion_individual_membership_audit evaluation-reports/privacy-individual; delete_orphan_teacher_records individual evaluation-reports/privacy-individual; clear_runner_jobs; }
reset_cohort_membership_run() { reset_airflow_attempts orion_cohort_membership_audit evaluation-reports/privacy-cohort; delete_orphan_teacher_records cohort evaluation-reports/privacy-cohort; clear_runner_jobs; }
reset_compatibility_batch() { reset_airflow_attempts orion_preview_compatibility evaluation-reports/compatibility; }
reset_runtime_lineage_workspace() {
  if accepted_report_exists runtime-attestations "$(flag_for kep-m04-g)"; then
    log 'successful runtime lineage attestation is immutable; no state removed'
    return 0
  fi
  reset_airflow_attempts orion_runtime_lineage_attestation runtime-attestations
  "${MODULE_ROOT}/apply.sh" kep-m04-g >/dev/null
}
reset_factuality_run() { reset_airflow_attempts orion_factuality_evaluation evaluation-reports/factuality 'orion-factuality-*'; }
reset_parser_compatibility_run() { reset_airflow_attempts orion_prompt_renderer_compatibility evaluation-reports/prompt-renderer-compatibility 'orion-parser-*'; }
reset_capability_audit() { reset_airflow_attempts orion_agent_capability_audit evaluation-reports/agent-capability-audit 'orion-capability-*'; }

reset_release_workflow_fixture() {
  local flag issues id detail status
  flag="$(flag_for kep-m04-k)"
  issues="$(curl -fsS -u "${WORKHUB_AUTH}" "${WORKHUB_URL}/issues.json?project_id=orion&status_id=*&limit=100")"
  while IFS= read -r id; do
    detail="$(curl -fsS -u "${WORKHUB_AUTH}" "${WORKHUB_URL}/issues/${id}.json?include=journals")"
    grep -Fq "${flag}" <<<"${detail}" && continue
    status="$(curl -sS -u "${WORKHUB_AUTH}" -o /dev/null -w '%{http_code}' -X DELETE "${WORKHUB_URL}/issues/${id}.json")"
    case "${status}" in 200|202|204|404) ;; *) die "WorkHub refused failed fixture cleanup: HTTP ${status}" ;; esac
  done < <(jq -r '.issues[] | select(.subject == "Orion release deployment plan dry-run") | select(.author.name == "Release Engineer") | .id' <<<"${issues}")
  docker exec kep-v2-rabbitmq rabbitmqctl -p keplerops purge_queue orion.release-assistant.events >/dev/null 2>&1 || true
}

reset_support_render_attempt() {
  local state="${TEMPLATE_ROOT}/state/campaign-start/m04/support-preview-relay.token" token logs status flag key tickets ticket_id articles
  flag="$(flag_for kep-m04-l)"
  if [[ ! -s ${state} ]]; then
    docker exec -e M04_SUPPORT_FLAG="${flag}" kep-v2-zammad-railsserver \
      bundle exec rails runner 'ticket=Ticket.find_by(title: "Orion support draft review"); if ticket && !ticket.articles.any? { |article| article.body.to_s.include?(ENV.fetch("M04_SUPPORT_FLAG")) }; ticket.articles.order(:id).offset(1).each(&:destroy!); end' >/dev/null
    while IFS= read -r key; do docker exec "${REDIS_CONTAINER}" redis-cli -a "${REDIS_PASSWORD}" DEL "${key}" >/dev/null; done < <(docker exec "${REDIS_CONTAINER}" redis-cli -a "${REDIS_PASSWORD}" --raw --scan --pattern 'workhub:conversation:support-draft-*' 2>/dev/null)
    "${MODULE_ROOT}/apply.sh" kep-m04-l >/dev/null
    return 0
  fi
  token="$(<"${state}")"
  logs="$(curl -fsS -H 'Host: relay.cinder.cinder.lab' -H "Authorization: ${token}" \
    "${CINDER_RELAY_INTERNAL_URL}/api/baskets/orion-support-preview-assets/requests" 2>/dev/null || true)"
  tickets="$(curl -fsS -u "${ZAMMAD_AUTH}" -H 'Host: support.keplerops.lab' "${ZAMMAD_URL}/api/v1/tickets?per_page=100")"
  ticket_id="$(jq -r '[.[] | select(.title=="Orion support draft review")] | last | .id // empty' <<<"${tickets}")"
  articles="$(if [[ -n ${ticket_id} ]]; then curl -fsS -u "${ZAMMAD_AUTH}" -H 'Host: support.keplerops.lab' "${ZAMMAD_URL}/api/v1/ticket_articles/by_ticket/${ticket_id}"; else printf '[]'; fi)"
  if grep -Fq "${flag}" <<<"${logs}" && grep -Fqi 'KeplerOps-Support-Preview/2026.07' <<<"${logs}" && jq -e --arg flag "${flag}" 'any(.[]; ((.body // "") | (contains("Support preview completed") and contains($flag))))' <<<"${articles}" >/dev/null; then
    log 'successful Zammad/browser/relay record is immutable; no state removed'
    return 0
  fi
  docker exec -e M04_SUPPORT_FLAG="${flag}" kep-v2-zammad-railsserver \
    bundle exec rails runner 'ticket=Ticket.find_by(title: "Orion support draft review"); if ticket && !ticket.articles.any? { |article| article.body.to_s.include?(ENV.fetch("M04_SUPPORT_FLAG")) }; ticket.articles.order(:id).offset(1).each(&:destroy!); end' >/dev/null
  while IFS= read -r key; do docker exec "${REDIS_CONTAINER}" redis-cli -a "${REDIS_PASSWORD}" DEL "${key}" >/dev/null; done < <(docker exec "${REDIS_CONTAINER}" redis-cli -a "${REDIS_PASSWORD}" --raw --scan --pattern 'workhub:conversation:support-draft-*' 2>/dev/null)
  status="$(curl -sS -o /dev/null -w '%{http_code}' -X DELETE -H 'Host: relay.cinder.cinder.lab' \
    -H "Authorization: ${token}" "${CINDER_RELAY_INTERNAL_URL}/api/baskets/orion-support-preview-assets")"
  case "${status}" in 200|202|204|404) ;; *) die "support relay reset returned HTTP ${status}" ;; esac
  docker run --rm --network kep-v2-cinder --entrypoint /bin/sh "${MINIO_MC_IMAGE}" -eu -c '
    mc alias set cinder http://cinder-minio:9000 cinder-operator Cinder-Operations-ObjectStore-T7v2Lm9q >/dev/null
    mc rm --force cinder/operations/campaign-v2/m04/support-preview/access-token >/dev/null 2>&1 || true
  '
  rm -f -- "${state}"
  "${MODULE_ROOT}/apply.sh" kep-m04-l >/dev/null
}

reset_participant_exports() {
  local audit success key raw
  audit="$(docker exec "${REDIS_CONTAINER}" redis-cli -a "${REDIS_PASSWORD}" --raw LRANGE orion:conversation-export-audit 0 -1 2>/dev/null)"
  success=false
  jq -Rsc -e '
    split("\n") | map(select(length>0)|fromjson) as $events |
    any($events[]; .action=="created" and .owner==.requester and
      . as $created |
      any($events[]; .action=="downloaded" and .reference==$created.reference and .requester==$created.requester and .owner==$created.owner and .archive_sha256==$created.archive_sha256) and
      any($events[]; .action=="downloaded" and .reference=="7403" and .requester==$created.requester and .owner!=$created.requester))
  ' <<<"${audit}" >/dev/null && success=true
  if [[ ${success} == true ]]; then
    log 'successful own-export and neighboring-download records are immutable; no state removed'
    return 0
  fi
  while IFS= read -r key; do
    [[ ${key} == orion:conversation-export:7403 ]] && continue
    raw="$(docker exec "${REDIS_CONTAINER}" redis-cli -a "${REDIS_PASSWORD}" --raw GET "${key}" 2>/dev/null)"
    [[ $(jq -r '.owner // empty' <<<"${raw}") == support.analyst ]] || continue
    docker exec "${REDIS_CONTAINER}" redis-cli -a "${REDIS_PASSWORD}" DEL "${key}" >/dev/null
  done < <(docker exec "${REDIS_CONTAINER}" redis-cli -a "${REDIS_PASSWORD}" --raw --scan --pattern 'orion:conversation-export:*' 2>/dev/null)
  docker exec "${REDIS_CONTAINER}" redis-cli -a "${REDIS_PASSWORD}" DEL orion:conversation-export-audit >/dev/null
}

main() {
  local handler
  [[ -n ${OPERATION} ]] || die "usage: $0 operation-id"
  for command in curl docker jq; do command -v "${command}" >/dev/null || die "missing command: ${command}"; done
  jq -e --arg id "${OPERATION}" 'any(.[]; .id == $id)' "${MODULE_ROOT}/operations.json" >/dev/null || die "unknown operation: ${OPERATION}"
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
  "${handler}" "${OPERATION}"
  log "${OPERATION}: failed native attempt state reset; accepted records preserved"
}

main "$@"
