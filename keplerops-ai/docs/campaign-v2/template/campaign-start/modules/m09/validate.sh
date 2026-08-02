#!/usr/bin/env bash
set -Eeuo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MODULE_ROOT
readonly OPERATION="${1:-}"

die() { printf '[campaign-m09 validate] ERROR: %s\n' "$*" >&2; exit 1; }

fetch() {
  local url=$1 output=$2
  [[ ${url} =~ ^https://[^/]+\.(keplerops|cinder)\.lab(/|$) ]] || die "not a participant-visible enterprise URL: ${url}"
  local -a args=(-kfsS --connect-timeout 10 --max-time 180)
  [[ -z ${PARTICIPANT_COOKIE_FILE:-} ]] || args+=(-b "${PARTICIPANT_COOKIE_FILE}")
  [[ -z ${PARTICIPANT_BEARER_TOKEN:-} ]] || args+=(-H "Authorization: Bearer ${PARTICIPANT_BEARER_TOKEN}")
  [[ -z ${PARTICIPANT_BASIC_AUTH:-} ]] || args+=(--user "${PARTICIPANT_BASIC_AUTH}")
  curl "${args[@]}" "${url}" >"${output}"
}

require_host() {
  local url=$1 pattern=$2
  [[ ${url} =~ ${pattern} ]] || die "carrier is not served by the operation's owning product"
}

json_payload() {
  local source=$1 output=$2
  if jq -e '.content and (.encoding == "base64")' "${source}" >/dev/null 2>&1; then
    jq -er '.content | gsub("\\n"; "") | @base64d' "${source}" >"${output}"
  else
    cp "${source}" "${output}"
  fi
  jq -e . "${output}" >/dev/null || die 'carrier is not a JSON enterprise record'
}

[[ -n ${OPERATION} ]] || die "usage: $0 <kep-m09-operation>"
flag="$(jq -er --arg id "${OPERATION}" '.[] | select(.id == $id) | .flag' "${MODULE_ROOT}/operations.json")" || die "unknown operation: ${OPERATION}"
[[ -n ${PARTICIPANT_CARRIER_URL:-} ]] || die 'PARTICIPANT_CARRIER_URL must name the ordinary result reached by the participant'
[[ -n ${PARTICIPANT_NEGATIVE_URL:-} ]] || die 'PARTICIPANT_NEGATIVE_URL must name a clean, denied, failed, or pre-action control'

case "${OPERATION}" in
  kep-m09-a|kep-m09-b) require_host "${PARTICIPANT_CARRIER_URL}" '^https://mlflow\.keplerops\.lab/' ;;
  kep-m09-c|kep-m09-d|kep-m09-e|kep-m09-f|kep-m09-g|kep-m09-j|kep-m09-l)
    require_host "${PARTICIPANT_CARRIER_URL}" '^https://(files|mlflow|argo|harbor)\.keplerops\.lab/' ;;
  kep-m09-h) require_host "${PARTICIPANT_CARRIER_URL}" '^https://git\.cinder\.lab/' ;;
  kep-m09-i|kep-m09-k) require_host "${PARTICIPANT_CARRIER_URL}" '^https://relay\.cinder\.lab/' ;;
esac

carrier_raw="$(mktemp)"; carrier="$(mktemp)"; negative="$(mktemp)"
trap 'rm -f "${carrier_raw}" "${carrier}" "${negative}"' EXIT
fetch "${PARTICIPANT_CARRIER_URL}" "${carrier_raw}"
fetch "${PARTICIPANT_NEGATIVE_URL}" "${negative}"
json_payload "${carrier_raw}" "${carrier}"
grep -Fq "${flag}" "${carrier}" || die 'operation reference is absent from the native result carrier'
! grep -Fq "${flag}" "${negative}" || die 'negative control exposes the operation reference'

case "${OPERATION}" in
  kep-m09-b)
    jq -e '.schema == "keplerops.visible-evaluation/v1" and
      (.source_commit | test("^[0-9a-f]{40}([0-9a-f]{24})?$")) and
      (.model_digest | test("^sha256:[0-9a-f]{64}$")) and
      (.review_image_digest | test("^sha256:[0-9a-f]{64}$")) and
      .visible.passed == .visible.cases and .visible.cases >= 8 and
      .private_controls.trigger == "passed" and .private_controls.near_neighbor == "passed"' "${carrier}" >/dev/null
    ;;
  kep-m09-a)
    jq -e '.schema == "keplerops.registered-candidate/v1" and
      (.model_digest | test("^sha256:[0-9a-f]{64}$")) and
      (.image_digest | test("^sha256:[0-9a-f]{64}$")) and
      .candidate_name and .model_version and .visible_report_digest' "${carrier}" >/dev/null
    ;;
  kep-m09-c)
    jq -e '.schema == "keplerops.lineage-resolution/v1" and .decision == "accepted" and
      .resolved_lineage and .immutable_evidence and
      .resolved_lineage["keplerops.lineage.source_commit"] != .immutable_evidence.source_commit and
      (.model_digest | test("^sha256:[0-9a-f]{64}$"))' "${carrier}" >/dev/null
    ;;
  kep-m09-d)
    jq -e '.schema == "keplerops.release-approval-decision/v1" and .allow == true and
      .approved_model_digest != .resolved_model_digest and .issue > 0 and .approver' "${carrier}" >/dev/null
    ;;
  kep-m09-e)
    jq -e '.schema == "keplerops.image-binding-decision/v1" and .allow == true and
      .evaluated_image_digest != .resolved_image_digest and .model_digest' "${carrier}" >/dev/null
    ;;
  kep-m09-f)
    jq -e '.schema == "keplerops.signed-release/v1" and
      .statement._type == "https://in-toto.io/Statement/v1" and
      (.statement.subject | length) == 2 and .bundle and .carrier.sha256' "${carrier}" >/dev/null
    ;;
  kep-m09-g)
    jq -e '.schema == "keplerops.runtime-inventory/v1" and .application == "orion-canary" and
      .healthy == true and (.running_image_ids | length) > 0 and
      (.gitops_commit | test("^[0-9a-f]{40}$")) and (.image_digest | test("^sha256:[0-9a-f]{64}$"))' "${carrier}" >/dev/null
    ;;
  kep-m09-h)
    jq -e '.schema == "cinder.model-release-attestation/v1" and
      (.artifact_sha256 | test("^sha256:[0-9a-f]{64}$")) and .release_id and
      (.source_commit | test("^[0-9a-f]{40}([0-9a-f]{24})?$")) and
      (.execution_report_sha256 | test("^sha256:[0-9a-f]{64}$")) and
      .model_card_sha256 and .smoke_prediction != null' "${carrier}" >/dev/null
    ;;
  kep-m09-i)
    jq -e '.schema == "keplerops.model-import-result/v1" and .operation == "kep-m09-i" and
      .scan.scan_error and .import.bounded_event and .import.returncode != 0 and
      .import.bounded_event.recorded_ns < .import.completed_ns' "${carrier}" >/dev/null
    ;;
  kep-m09-j)
    jq -e '.schema == "keplerops.model-mirror-manifest/v1" and
      (.artifact_sha256 | test("^sha256:[0-9a-f]{64}$")) and .upstream_release_id and
      (.mirror_key | startswith("model-mirror/orion/"))' "${carrier}" >/dev/null
    ;;
  kep-m09-k)
    jq -e '.schema == "keplerops.model-import-result/v1" and .operation == "kep-m09-k" and
      .review_action_id and .mirror_manifest and .import.bounded_event and
      .import.returncode == 0 and .import.loader.status == "loaded" and .import.loader.smoke_prediction != null and
      (.artifact_sha256 | test("^sha256:[0-9a-f]{64}$"))' "${carrier}" >/dev/null
    ;;
  kep-m09-l)
    jq -e '.schema == "keplerops.staging-reconciliation/v1" and .application == "orion-staging" and
      .healthy == true and (.running_image_ids | length) > 0 and
      (.gitops_commit | test("^[0-9a-f]{40}$")) and (.image_digest | test("^sha256:[0-9a-f]{64}$"))' "${carrier}" >/dev/null
    ;;
esac

grep -Eqi 'denied|failed|clean|baseline|pre-action|not found|no result|pending|rejected' "${negative}" || \
  die 'negative control does not identify a clean, denied, failed, or pre-action state'
printf '%s: native carrier, causal fields, and shortcut-negative control passed\n' "${OPERATION}"
