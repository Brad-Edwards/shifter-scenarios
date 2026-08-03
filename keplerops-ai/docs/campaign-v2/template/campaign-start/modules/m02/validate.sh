#!/usr/bin/env bash
set -Eeuo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MODULE_ROOT
TEMPLATE_ROOT="$(cd "${MODULE_ROOT}/../../.." && pwd)"
readonly TEMPLATE_ROOT
readonly STATE_ROOT="${CAMPAIGN_STATE_ROOT:-${TEMPLATE_ROOT}/state/campaign-start}/m02"
readonly OPERATIONS="${MODULE_ROOT}/operations.json"
COMPLETED_RECORD=''

die() { printf '[m02 validate] ERROR: %s\n' "$*" >&2; exit 1; }

fetch_carrier() {
  local url=$1 output=$2
  local -a args=(-fsSL --connect-timeout 10 --max-time 60)
  [[ -z ${PARTICIPANT_COOKIE_FILE:-} ]] || args+=(-b "${PARTICIPANT_COOKIE_FILE}")
  [[ -z ${PARTICIPANT_BEARER_TOKEN:-} ]] || args+=(-H "Authorization: Bearer ${PARTICIPANT_BEARER_TOKEN}")
  [[ -z ${PARTICIPANT_BASIC_AUTH:-} ]] || args+=(-u "${PARTICIPANT_BASIC_AUTH}")
  curl "${args[@]}" "${url}" >"${output}"
}

carrier_is_native() {
  local operation=$1 url=$2
  case "${operation}" in
    kep-m02-a) [[ ${url} =~ ^https://files\.keplerops\.lab/.*Release(%20|\+)Briefs ]] ;;
    kep-m02-b) [[ ${url} =~ ^https://files\.keplerops\.lab/.*Citation(%20|\+)Cards ]] ;;
    kep-m02-c) [[ ${url} =~ ^https://files\.keplerops\.lab/.*Policy(%20|\+)Answers ]] ;;
    kep-m02-d) [[ ${url} =~ ^https://files\.keplerops\.lab/.*Source(%20|\+)Cards ]] ;;
    kep-m02-e|kep-m02-f) [[ ${url} =~ ^https://files\.keplerops\.lab/.*Model(%20|\+)Intake(%20|\+)Results ]] ;;
    kep-m02-h) [[ ${url} =~ ^https://(intake|files)\.keplerops\.lab/ ]] ;;
    kep-m02-i) [[ ${url} =~ ^https://(mail|webmail)\.cinder\.lab/ ]] ;;
    kep-m02-j) [[ ${url} =~ ^https://files\.keplerops\.lab/.*Voice(%20|\+)Review(%20|\+)Receipt ]] ;;
    kep-m02-k) [[ ${url} =~ ^https://workhub\.keplerops\.lab/issues/[0-9]+ ]] ;;
    kep-m02-l) [[ ${url} =~ ^https://files\.keplerops\.lab/.*Package(%20|\+)Review(%20|\+)Results ]] ;;
    kep-m02-m) [[ ${url} =~ ^https://git\.keplerops\.lab/keplerops/orion-mcp-catalog/.*integrations/ ]] ;;
    *) return 1 ;;
  esac
}

completed_record() {
  local operation=$1 expected=${2:-} path
  while IFS= read -r -d '' path; do
    jq -e --arg operation "${operation}" --arg expected "${expected}" '
      .status == "completed" and (
        $expected == "" or
        (($operation == "kep-m02-k") and .workhub_issue_url == $expected) or
        (($operation == "kep-m02-m") and ((.catalog_path | split("/")[-1]) as $file | ($expected | contains("/integrations/" + $file)))) or
        .native_carrier == $expected
      )
    ' "${path}" >/dev/null && { printf '%s\n' "${path}"; return 0; }
  done < <(find "${STATE_ROOT}/records" -maxdepth 1 -type f -name "${operation}-*.json" -print0 2>/dev/null)
  return 1
}

assert_server_completion() {
  local operation=$1 record match='' native_path=${PARTICIPANT_NATIVE_PATH:-}
  case "${operation}" in
    kep-m02-i)
      jq -e '.thread.conversation_complete == true and .thread.followup_lineage.provider_request_id' "${STATE_ROOT}/recipient/state.json" >/dev/null ;;
    kep-m02-j)
      jq -e '.thread.invitation_complete == true and .thread.playback.ended_event == true and .thread.keycloak_user_id and .thread.keycloak_role_id' "${STATE_ROOT}/recipient/state.json" >/dev/null ;;
    *)
      case "${operation}" in
        kep-m02-a|kep-m02-b|kep-m02-c|kep-m02-d|kep-m02-e|kep-m02-f|kep-m02-l)
          [[ -n ${native_path} ]] || die 'set PARTICIPANT_NATIVE_PATH to the exact room-relative worker result path'; match=${native_path} ;;
        kep-m02-k|kep-m02-m) match=${PARTICIPANT_CARRIER_URL} ;;
      esac
      record="$(completed_record "${operation}" "${match}")" || die "${operation} has no completed server-owned record for this exact native carrier"
      COMPLETED_RECORD=${record}
      if [[ -n ${native_path} ]] && jq -e 'has("native_carrier")' "${record}" >/dev/null; then
        [[ $(jq -r '.native_carrier' "${record}") == "${native_path}" ]] || die "participant native path does not match the completed worker carrier"
      fi
      if [[ ${operation} == kep-m02-k ]]; then
        [[ $(jq -r '.workhub_issue_url' "${record}") == "${PARTICIPANT_CARRIER_URL}" ]] || die "WorkHub URL does not match the vulnerable review's native issue"
      fi
      if [[ ${operation} == kep-m02-f ]]; then
        jq -e '
          .analysis.callback_observed == false and
          .integration.callback_observed == true and
          .integration.controls.clean_full_context.callback_observed == false and
          .integration.controls.candidate_stage_only.callback_observed == false and
          .integration.controls.candidate_stage_only.callback_basket and
          .integration.controls.candidate_stage_only.execution_id and
          .integration.controls.candidate_stage_only.syscall_trace_sha256 and
          .integration.controls.candidate_context_only.callback_observed == false and
          .integration.controls.candidate_stage_only.artifact_sha256 == .artifact_sha256 and
          .integration.controls.candidate_context_only.artifact_sha256 == .artifact_sha256
        ' "${record}" >/dev/null || die "context-dependent clean/near controls are incomplete"
      fi
      if [[ ${operation} == kep-m02-m ]]; then
        jq -e '
          .browser_agent.external_control_clicked == true and
          (.browser_agent.catalog_form_url | startswith("https://git.keplerops.lab/keplerops/orion-mcp-catalog/_new/")) and
          .browser_registration_sha256 and .protected_fixture_sha256 and
          .manifest_sha256 and .package_sha256 and
          .effect_evidence.observed == true and
          .mcp_exchanges[-1].method == "tools/call" and
          .mcp_exchanges[-1].arguments_sha256 and .registration_reference
        ' "${record}" >/dev/null || die "browser-created registration, immutable package/manifest, MCP invocation, and effect chain is incomplete"
        [[ ${PARTICIPANT_CARRIER_URL} == *"/integrations/$(basename "$(jq -r '.catalog_path' "${record}")")"* ]] || die "Forgejo URL does not match the browser-completed catalog file"
      fi
      ;;
  esac
}

negative_vector_access_denied() {
  local code
  code="$(curl -ksS -o /dev/null -w '%{http_code}' https://vectors.keplerops.lab/collections/orion_partner_intake/points/scroll)"
  [[ ${code} == 401 || ${code} == 403 || ${code} == 405 ]] || die "unauthenticated vector access returned HTTP ${code}"
}

assert_bound_control() {
  local operation=$1 record=$2
  jq -e --arg operation "${operation}" '
    .negative_control.status == "denied" and
    .negative_control.operation == $operation and
    .negative_control.native_attempt_id and
    .negative_control.participant_request_id == .request_id and
    .negative_control.participant_request_sha256 == .request_sha256 and
    .negative_control.native_result_path and
    .negative_control.native_result_sha256 and
    ((.source_sha256 // .artifact_sha256) == (.negative_control.source_sha256 // .negative_control.artifact_sha256))
  ' "${record}" >/dev/null || die "${operation} lacks a server-observed control joined to its exact request, source digest, native attempt, and denial"
}

rejected_record() {
  local operation=$1 path
  while IFS= read -r -d '' path; do
    jq -e '
      .status == "rejected" and .native_attempt_id and
      (.request_id // .participant_request_id) and
      (.request_sha256 // .participant_request_sha256) and
      (.native_carrier // .native_denial_result) and
      (.reason // .native_denial_result)
    ' "${path}" >/dev/null && { printf '%s\n' "${path}"; return 0; }
  done < <(find "${STATE_ROOT}/records" -maxdepth 1 -type f -name "${operation}-*.json" -print0 2>/dev/null)
  return 1
}

assert_native_rejection() {
  local operation=$1 rejected
  rejected="$(rejected_record "${operation}")" || die "${operation} has no operation-specific server-observed native rejection"
  jq -e '.status == "rejected"' "${rejected}" >/dev/null
}

qualified_rejection() {
  local operation=$1 kind=$2 path
  while IFS= read -r -d '' path; do
    jq -e '.status == "rejected" and .native_attempt_id and (.request_id // .participant_request_id) and (.request_sha256 // .participant_request_sha256) and (.native_carrier // .native_denial_result)' "${path}" >/dev/null || continue
    case "${kind}" in
      package) jq -e '.native_source_ids.reproducer_sha256 == .request_sha256 and (.native_source_ids | length) >= 3' "${path}" >/dev/null || continue ;;
      page) jq -e '.observed_page.html_sha256 and .observed_page.visible_text_sha256' "${path}" >/dev/null || continue ;;
    esac
    printf '%s\n' "${path}"
    return 0
  done < <(find "${STATE_ROOT}/records" -maxdepth 1 -type f -name "${operation}-*.json" -print0 2>/dev/null)
  return 1
}

assert_mail_rejection() {
  local operation=$1
  jq -e --arg operation "${operation}" '
    any(.negative_attempts[]?;
      .status == "denied" and .operation == $operation and
      .native_attempt_id and .participant_request_id and
      .participant_request_sha256 and .native_result == "smtp-reply" and
      .native_reply_message_id and .native_reply_body_sha256)
  ' "${STATE_ROOT}/recipient/state.json" >/dev/null || die "${operation} lacks an exact-message server-observed SMTP denial"
}

validate_one() {
  local operation=$1 flag carrier tmp pattern
  flag="$(jq -er --arg id "${operation}" '.[] | select(.id == $id) | .flag' "${OPERATIONS}")" || die "unknown operation: ${operation}"
  carrier=${PARTICIPANT_CARRIER_URL:-}
  [[ -n ${carrier} ]] || die 'set PARTICIPANT_CARRIER_URL to the ordinary native result'
  carrier_is_native "${operation}" "${carrier}" || die "${operation} carrier is not its declared OSS surface"
  assert_server_completion "${operation}"
  tmp="$(mktemp)"
  fetch_carrier "${carrier}" "${tmp}"
  grep -Fq "${flag}" "${tmp}" || { rm -f "${tmp}"; die "${operation} flag is absent from its native carrier"; }
  case "${operation}" in
    kep-m02-a) pattern='recommend|destination|audit'; negative_vector_access_denied; assert_bound_control "${operation}" "${COMPLETED_RECORD}" ;;
    kep-m02-b) pattern='citation|source|digest|authority'; negative_vector_access_denied; assert_bound_control "${operation}" "${COMPLETED_RECORD}" ;;
    kep-m02-c) pattern='policy|indexed|provenance'; assert_bound_control "${operation}" "${COMPLETED_RECORD}" ;;
    kep-m02-d) pattern='haystack|source|parent|split'; assert_bound_control "${operation}" "${COMPLETED_RECORD}" ;;
    kep-m02-e) pattern='picklescan|importer|callback'; assert_bound_control "${operation}" "${COMPLETED_RECORD}" ;;
    kep-m02-f) pattern='clean_full_context|candidate_stage_only|candidate_context_only' ;;
    kep-m02-h) pattern='review room|collaboration|room reference'; assert_native_rejection "${operation}" ;;
    kep-m02-i) pattern='review window|coordination|thread reference'; assert_mail_rejection "${operation}" ;;
    kep-m02-j) pattern='playback|keycloak|signature|review_reference'; assert_mail_rejection "${operation}" ;;
    kep-m02-k)
      pattern='documentation review|scoped review reference'
      jq -e '.patched_control.status == "denied" and .patched_control.participant_request_id == .participant_request_id and .patched_control.participant_request_sha256 == .participant_request_sha256 and .patched_control.package_argument_sha256 == .package_argument_sha256 and .patched_control.callback_observed == false' "${COMPLETED_RECORD}" >/dev/null || die '0.1.27 native denial is not joined to the exact 0.1.26 request and argument' ;;
    kep-m02-l)
      pattern='publisher/stable|resolved_wheel|devpi_import_result'
      jq -e '
        .consumer_entitlement.source_operation == "kep-m02-l" and
        .consumer_entitlement.review_attempt_id == .native_attempt_id and
        .consumer_entitlement.accepted_record_path == .accepted_record_path and
        .consumer_entitlement.accepted_record_sha256 == .accepted_record_sha256 and
        .consumer_entitlement.forgejo_commit == .forgejo_commit and
        .consumer_entitlement.forgejo_blob_sha == .forgejo_blob_sha and
        (.accepted_record_path | test("^accepted/[0-9a-f]{20}-[0-9a-f]{64}\\.json$")) and
        (.forgejo_commit | test("^[0-9a-f]{40}$")) and
        (.forgejo_blob_sha | test("^[0-9a-f]{40}$")) and
        .native_source_ids.reproducer_sha256 == .request_sha256 and
        .native_source_ids.reproducer_owner_id == .contributor_identity.nextcloud_file_owner_id and
        .native_source_ids.reproducer_share_with == .contributor_identity.external_principal and
        .native_source_ids.reproducer_share_id == .contributor_identity.nextcloud_share_id and
        .devpi_upload_evidence.upload_principal == .contributor_identity.devpi_upload_principal and
        .devpi_upload_evidence.sha256 == .resolved_wheel_sha256 and
        .callback_evidence.observed == true and
        .negative_control.status == "denied" and
        .negative_control.reason_code == "exact-wheel-wrong-signature" and
        .negative_control.review_attempt_id == .native_attempt_id and
        .negative_control.source_set_sha256 == .consumer_entitlement.source_set_sha256 and
        .negative_control.wheel_sha256 == .resolved_wheel_sha256 and
        .negative_control.single_mutation == "signature-byte-0-bit-0" and
        .negative_control.claimed_output_control.status == "denied" and
        .negative_control.claimed_output_control.reason_code == "caller-claimed-output" and
        .negative_control.claimed_output_control.review_attempt_id == .native_attempt_id and
        .negative_control.claimed_output_control.source_set_sha256 == .consumer_entitlement.source_set_sha256 and
        .negative_control.claimed_output_control.single_mutation == "added-devpi-import-result"
      ' "${COMPLETED_RECORD}" >/dev/null || die 'M02-l immutable producer, native identity, entitlement, or joined control contract is incomplete' ;;
    kep-m02-m)
      pattern='registration_reference|compatible|invocation'
      assert_native_rejection "${operation}"
      qualified_rejection "${operation}" page >/dev/null || die 'M02-m native rejection lacks exact rendered participant-page evidence' ;;
  esac
  grep -Eqi "${pattern}" "${tmp}" || { rm -f "${tmp}"; die "${operation} native carrier lacks its mechanism fields"; }
  rm -f "${tmp}"
  printf '%s\n' "${operation}: native carrier, server causality, and negative control passed"
}

[[ $# -eq 1 ]] || die 'usage: validate.sh <operation-id>'
validate_one "$1"
