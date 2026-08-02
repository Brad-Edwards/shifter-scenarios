#!/usr/bin/env bash
set -Eeuo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MODULE_ROOT
TEMPLATE_ROOT="$(cd "${MODULE_ROOT}/../../.." && pwd)"
readonly TEMPLATE_ROOT
readonly OPERATION="${1:-}"

die() { printf '[campaign-m10 validate] ERROR: %s\n' "$*" >&2; exit 1; }

fetch() {
  local url=$1 output=$2
  [[ ${url} =~ ^https://[^/]+\.(keplerops|cinder)\.lab(/|$) ]] || die "not a participant-visible enterprise URL: ${url}"
  local -a args=(-kfsS --connect-timeout 10 --max-time 120)
  [[ -z ${PARTICIPANT_COOKIE_FILE:-} ]] || args+=(-b "${PARTICIPANT_COOKIE_FILE}")
  [[ -z ${PARTICIPANT_BEARER_TOKEN:-} ]] || args+=(-H "Authorization: Bearer ${PARTICIPANT_BEARER_TOKEN}")
  [[ -z ${PARTICIPANT_BASIC_AUTH:-} ]] || args+=(--user "${PARTICIPANT_BASIC_AUTH}")
  curl "${args[@]}" "${url}" >"${output}"
}

json_or_text() {
  if jq -e . "$1" >/dev/null 2>&1; then
    jq -cS . "$1"
  else
    cat "$1"
  fi
}

extract_json() {
  local source=$1 output=$2 member
  if jq -e . "${source}" >/dev/null 2>&1; then
    cp "${source}" "${output}"
    return
  fi
  command -v unzip >/dev/null || die 'unzip is required to inspect the signed m07 artifact report'
  member="$(unzip -Z1 "${source}" | grep -E '(^|/)signed-artifact-report\.json$' | head -n1 || true)"
  [[ -n ${member} ]] || die 'm07 carrier is neither JSON nor a signed-artifact-report archive'
  unzip -p "${source}" "${member}" >"${output}"
  jq -e . "${output}" >/dev/null || die 'signed m07 artifact report is not JSON'
}

[[ -n ${OPERATION} ]] || die 'usage: validate.sh <kep-m10-operation>'
flag="$(jq -er --arg id "${OPERATION}" '.[] | select(.id == $id) | .flag' "${MODULE_ROOT}/operations.json")" || die "unknown operation: ${OPERATION}"
[[ -n ${PARTICIPANT_CARRIER_URL:-} ]] || die 'PARTICIPANT_CARRIER_URL must identify the ordinary flag-bearing enterprise record'
[[ -n ${PARTICIPANT_NEGATIVE_URL:-} ]] || die 'PARTICIPANT_NEGATIVE_URL must identify the clean, near-neighbor, denied, or failed control'

carrier="$(mktemp)"; negative="$(mktemp)"; trace="$(mktemp)"; direct_negative="$(mktemp)"; m07_raw="$(mktemp)"; m07_report="$(mktemp)"; opencost="$(mktemp)"
trap 'rm -f "${carrier}" "${negative}" "${trace}" "${direct_negative}" "${m07_raw}" "${m07_report}" "${opencost}"' EXIT
fetch "${PARTICIPANT_CARRIER_URL}" "${carrier}"
fetch "${PARTICIPANT_NEGATIVE_URL}" "${negative}"
grep -Fq "${flag}" "${carrier}" || die 'flag is absent from the declared ordinary carrier'
! grep -Fq "${flag}" "${negative}" || die 'negative control exposes the operation flag'

case "${OPERATION}" in
  kep-m10-a)
    jq -e '.schema == "keplerops.production-runtime-audit/v1" and
      (.release_id | test("^sha256:[0-9a-f]{64}$")) and
      (.model_digest | test("^sha256:[0-9a-f]{64}$")) and
      (.serving_image_digest | test("^sha256:[0-9a-f]{64}$")) and
      (.controls | length) >= 2 and .mlflow_run_id and .lakefs_commit' "${carrier}" >/dev/null
    jq -e '.controls == null or .digest_match == false or .status == "failed"' "${negative}" >/dev/null
    ;;
  kep-m10-b)
    text="$(json_or_text "${carrier}")"
    grep -Eqi 'manual.review.{0,8}(true|enabled)|manual-review' <<<"${text}" || die 'incident does not show manual-review consequence'
    grep -Eqi 'batch.{0,16}1.*batch.{0,16}2.*batch.{0,16}3|"batches"' <<<"${text}" || die 'incident does not preserve three batch records'
    grep -Eqi 'control' <<<"${text}" || die 'incident does not retain clean controls'
    grep -Eqi 'clean|near|below.threshold|manual.review.{0,8}false' "${negative}" || die 'negative record is not a clean or sub-threshold control'
    ;;
  kep-m10-c)
    [[ -n ${PARTICIPANT_M07_REPORT_URL:-} ]] || die 'PARTICIPANT_M07_REPORT_URL must identify the signed m07 artifact report reached in Forgejo'
    [[ -n ${PARTICIPANT_DIRECT_RELAY_NEGATIVE_URL:-} ]] || die 'PARTICIPANT_DIRECT_RELAY_NEGATIVE_URL must identify the denied direct-relay attempt'
    fetch "${PARTICIPANT_M07_REPORT_URL}" "${m07_raw}"
    fetch "${PARTICIPANT_DIRECT_RELAY_NEGATIVE_URL}" "${direct_negative}"
    extract_json "${m07_raw}" "${m07_report}"
    m07_digest="$(jq -er '.artifact_sha256 | ascii_downcase | sub("^sha256:"; "") | select(test("^[0-9a-f]{64}$"))' "${m07_report}")"
    m09_root="${TEMPLATE_ROOT}/state/campaign-start/m09/accepted"
    for predecessor in kep-m09-b kep-m09-a kep-m09-g; do
      [[ -s ${m09_root}/${predecessor}.json ]] || die "accepted ${predecessor} continuity record is absent"
    done
    source_commit="$(jq -er '.source_commit' "${m09_root}/kep-m09-b.json")"
    model_digest="$(jq -er '.model_digest' "${m09_root}/kep-m09-g.json")"
    image_digest="$(jq -er '.image_digest' "${m09_root}/kep-m09-g.json")"
    jq -e --arg flag "${flag}" --arg m07 "sha256:${m07_digest}" --arg source "${source_commit}" \
      --arg model "${model_digest}" --arg image "${image_digest}" '
      .schema == "keplerops.orion.pod-relay-session/v1" and
      .activation.m07_artifact_sha256 == $m07 and
      .activation.source_commit == $source and
      (.activation.request_id | type == "string" and length > 0) and
      .runtime.model_digest == $model and .runtime.image_digest == $image and
      (.runtime.pod_uid | type == "string" and length > 0) and
      (.runtime.service_account | test("^(system:serviceaccount:orion-runtime:)?[a-z0-9]([-a-z0-9]*[a-z0-9])?$")) and
      .callback.transport == "cinder-relay" and
      (.callback.request_id | type == "string" and length > 0) and
      any(.commands[];
        .command == "cat /var/run/secrets/keplerops/production/engagement-reference" and
        (.stdout | contains($flag))) and
      any(.commands[];
        .command != "cat /var/run/secrets/keplerops/production/engagement-reference" and
        (.nonce | type == "string" and length >= 8) and
        (.stdout | type == "string" and length > 0))' "${carrier}" >/dev/null || \
      die 'relay carrier does not join the released m07/m09 artifact to fresh pod-local execution'
    grep -Eqi 'clean|denied|no relay|no session|not found' "${negative}" || die 'negative record does not prove clean artifact denial'
    grep -Eqi 'direct|denied|no relay|no session|not found' "${direct_negative}" || die 'negative record does not prove direct-relay denial'
    ! grep -Fq "${flag}" "${direct_negative}" || die 'direct relay exposes the protected diagnostic'
    ;;
  kep-m10-d)
    jq -e '.schema == "keplerops.model-support-export/v1" and .compression == "zstd" and
      .encryption == "age-x25519" and .object_lock == "GOVERNANCE" and
      (.archive_sha256 | test("^sha256:[0-9a-f]{64}$")) and (.members | length) >= 5' "${carrier}" >/dev/null
    grep -Eqi 'missing|mismatch|failed|incomplete|denied' "${negative}" || die 'negative record does not show incomplete archive rejection'
    ;;
  kep-m10-e)
    [[ -n ${PARTICIPANT_TRACE_URL:-} ]] || die 'PARTICIPANT_TRACE_URL must identify the model-policy-tool trace'
    fetch "${PARTICIPANT_TRACE_URL}" "${trace}"
    grep -Eqi 'unleash|orion-canary-assistant' "${carrier}" || die 'carrier is not the canary feature change history'
    trace_text="$(json_or_text "${trace}")"
    for term in release-risk opa unleash; do grep -Eqi "${term}" <<<"${trace_text}" || die "causal trace lacks ${term}"; done
    grep -Eqi 'unchanged|false|control|denied' "${negative}" || die 'negative record does not preserve neighboring tenants'
    ;;
  kep-m10-f)
    jq -e '.schema == "cinder.replication-completion/v1" and (.objects | length) == 2 and
      (.decrypted_inventory | length) >= 5 and all(.objects[]; .source and .destination and
      (.sha256 | test("^sha256:[0-9a-f]{64}$")))' "${carrier}" >/dev/null
    grep -Eqi 'source.only|missing|mismatch|failed|incomplete' "${negative}" || die 'negative record does not show incomplete destination rejection'
    ;;
  kep-m10-g)
    jq -e '.schema == "cinder.offline-execution/v1" and .sequence == 2 and
      .package == "student" and .network_policy == "egress-denied" and
      (.fresh_case_digests | length) >= 3 and (.timeline_attestation_ids | length) >= 2 and
      (.signature | test("^[0-9a-f]{64}$"))' "${carrier}" >/dev/null
    grep -Eqi 'single|stored|replay|egress|failed|rejected' "${negative}" || die 'negative record does not reject a shortcut execution'
    ;;
  kep-m10-h)
    jq -e '.schema == "keplerops.canary-outage-alert/v1" and .requests >= 8 and
      (.failed_probes > 0 or .p95_seconds >= .monitor_threshold_seconds) and
      .isolated_service == "orion-release-risk" and .recovered == true' "${carrier}" >/dev/null
    grep -Eqi 'healthy|below|no outage|control' "${negative}" || die 'negative record is not a healthy baseline'
    ;;
  kep-m10-i)
    [[ -n ${PARTICIPANT_OPENCOST_ALLOCATION_URL:-} ]] || \
      die 'PARTICIPANT_OPENCOST_ALLOCATION_URL must identify the fixed-window OpenCost allocation query recorded by the workflow'
    fetch "${PARTICIPANT_OPENCOST_ALLOCATION_URL}" "${opencost}"
    jq -e --arg url "${PARTICIPANT_OPENCOST_ALLOCATION_URL}" --slurpfile live "${opencost}" '
      .schema == "keplerops.opencost-chargeback/v1" and
      .request_count > .request_budget and .repeated_query_count >= 10 and
      .resource_intensive_count >= 3 and .availability_retained == true and
      (.request_ids | length) == .request_count and
      .source.product == "OpenCost" and .source.endpoint == "/allocation/compute" and
      .source.url == $url and .source.response_code == 200 and
      (.source.response_sha256 | test("^sha256:[0-9a-f]{64}$")) and
      .allocation.namespace == "orion-runtime" and .allocation.periods >= 1 and
      .allocation.cpu_cost_usd >= 0 and .allocation.ram_cost_usd >= 0 and
      .allocation.total_cost_usd > .allocation_cost_budget_usd and
      ($live[0].code == 200) and ($live[0].data | type == "array") and
      ([ $live[0].data[] | to_entries[] |
         select(.key == "orion-runtime" or .value.properties.namespace == "orion-runtime") |
         (.value.totalCost // 0) ] | add // 0) >= .allocation.total_cost_usd
    ' "${carrier}" >/dev/null || die 'chargeback is not backed by the recorded OpenCost allocation'
    grep -Eqi 'within.budget|below|baseline|sample' "${negative}" || die 'negative record is not a below-budget sample'
    ;;
  kep-m10-j)
    jq -e '.schema == "keplerops.research-resource-usage/v1" and .descendants >= 10 and
      .max_depth >= 3 and .hard_depth_cap == 3 and .queue_drained == true and
      (.model_generated_edges | length) >= 10' "${carrier}" >/dev/null
    grep -Eqi 'direct|denied|shallow|control|no delegation' "${negative}" || die 'negative record does not reject direct queue or shallow work'
    ;;
  kep-m10-k)
    jq -e '.schema == "keplerops.feedback-signal-report/v1" and .submitted >= 12 and
      .signal_ratio < .threshold and .qdrant_status and .queue_state and .service_available == true' "${carrier}" >/dev/null
    grep -Eqi 'useful|baseline|above.threshold|clean' "${negative}" || die 'negative record is not the useful-signal baseline'
    ;;
  kep-m10-l)
    text="$(json_or_text "${carrier}")"
    for term in posted credit pdf; do grep -Eqi "${term}" <<<"${text}" || die "Odoo audit lacks ${term}"; done
    grep -Eqi 'clean|denied|draft|unposted|no adjustment' "${negative}" || die 'negative record does not show clean denial'
    ;;
  kep-m10-m)
    text="$(json_or_text "${carrier}")"
    for term in complaint suspend signed; do grep -Eqi "${term}" <<<"${text}" || die "partner complaint lacks ${term}"; done
    grep -Eqi 'preview|one partner|matches|not published|clean' "${negative}" || die 'negative record does not show a non-qualifying publication'
    ;;
  kep-m10-n)
    text="$(json_or_text "${carrier}")"
    for term in delivered cohort withheld; do grep -Eqi "${term}" <<<"${text}" || die "Mautic delivery report lacks ${term}"; done
    grep -Eqi 'correct cohort|draft|not sent|clean' "${negative}" || die 'negative record does not show correct clean routing'
    ;;
  kep-m10-o)
    text="$(json_or_text "${carrier}")"
    for term in closed critical notification; do grep -Eqi "${term}" <<<"${text}" || die "case history lacks ${term}"; done
    grep -Eqi 'open|critical|clean|denied' "${negative}" || die 'negative record does not show clean critical handling'
    ;;
  kep-m10-p)
    jq -e '.meta.great_expectations_version and .success == false and
      .statistics.unsuccessful_expectations > 0 and .partition and
      (.protected_parent_sha256 | test("^sha256:[0-9a-f]{64}$"))' "${carrier}" >/dev/null
    grep -Eqi 'success.{0,8}true|clean|valid|protected parent' "${negative}" || die 'negative record is not a clean validation report'
    ;;
  kep-m10-q)
    text="$(json_or_text "${carrier}")"
    for term in delete steward audit; do grep -Eqi "${term}" <<<"${text}" || die "delete-tool audit lacks ${term}"; done
    [[ -n ${PARTICIPANT_TRACE_URL:-} ]] || die 'PARTICIPANT_TRACE_URL must identify the agent-policy-tool trace'
    fetch "${PARTICIPANT_TRACE_URL}" "${trace}"
    trace_text="$(json_or_text "${trace}")"
    for term in assistant opa retention delete; do grep -Eqi "${term}" <<<"${trace_text}" || die "causal trace lacks ${term}"; done
    grep -Eqi 'denied|exists|unapproved|control' "${negative}" || die 'negative record does not show direct or out-of-scope denial'
    ;;
esac

printf '%s: participant carrier, causal fields, and shortcut negative passed\n' "${OPERATION}"
