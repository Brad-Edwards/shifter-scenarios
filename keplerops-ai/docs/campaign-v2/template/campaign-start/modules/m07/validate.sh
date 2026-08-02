#!/usr/bin/env bash
set -Eeuo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MODULE_ROOT
readonly OPERATIONS="${MODULE_ROOT}/operations.json"

die() { printf '[campaign-m07 validate] ERROR: %s\n' "$*" >&2; exit 1; }

fetch_participant_surface() {
  local url=$1 output=$2
  [[ ${url} =~ ^https://[^/]+\.(keplerops|cinder)\.lab(/|$) ]] || \
    die 'carrier must be fetched from a participant-visible KeplerOps or Cinder product surface'
  local -a args=(-kfsS --connect-timeout 10 --max-time 120)
  [[ -z ${PARTICIPANT_COOKIE_FILE:-} ]] || args+=(-b "${PARTICIPANT_COOKIE_FILE}")
  [[ -z ${PARTICIPANT_BEARER_TOKEN:-} ]] || args+=(-H "Authorization: Bearer ${PARTICIPANT_BEARER_TOKEN}")
  [[ -z ${PARTICIPANT_BASIC_AUTH:-} ]] || args+=(--user "${PARTICIPANT_BASIC_AUTH}")
  curl "${args[@]}" "${url}" >"${output}"
}

assert_negative_control() {
  local flag=$1 pattern=$2 tmp
  [[ -n ${PARTICIPANT_NEGATIVE_URL:-} ]] || die 'PARTICIPANT_NEGATIVE_URL must name the clean parent, failed run, or denied direct shortcut'
  tmp="$(mktemp)"
  fetch_participant_surface "${PARTICIPANT_NEGATIVE_URL}" "${tmp}"
  ! grep -Fq "${flag}" "${tmp}" || die 'negative control exposes the operation flag'
  grep -Eqi "${pattern}" "${tmp}" || die 'negative control does not demonstrate the required clean, failed, or denied state'
  rm -f "${tmp}"
}

assert_carrier_route() {
  local operation=$1 url=$2 expected
  case "${operation}" in
    kep-m07-a|kep-m07-d) expected='^https://data\.keplerops\.lab/' ;;
    kep-m07-b|kep-m07-c|kep-m07-e|kep-m07-f|kep-m07-g) expected='^https://mlflow\.keplerops\.lab/' ;;
    kep-m07-h) expected='^https://registry\.keplerops\.lab/' ;;
    kep-m07-i) expected='^https://git\.cinder\.lab/' ;;
    *) die "unknown operation: ${operation}" ;;
  esac
  [[ ${url} =~ ${expected} ]] || die "${operation} carrier is not on its owning product surface"
}

validate_one() {
  local operation=$1 flag carrier tmp
  flag="$(jq -er --arg id "${operation}" '.[] | select(.id == $id) | .flag' "${OPERATIONS}")" || die "unknown operation: ${operation}"
  carrier=${PARTICIPANT_CARRIER_URL:-}
  [[ -n ${carrier} ]] || die 'PARTICIPANT_CARRIER_URL must name the ordinary in-world carrier reached by the participant'
  assert_carrier_route "${operation}" "${carrier}"
  tmp="$(mktemp)"
  trap 'rm -f "${tmp}"' RETURN
  fetch_participant_surface "${carrier}" "${tmp}"
  grep -Fq "${flag}" "${tmp}" || die "${operation} flag is absent from the normal carrier"
  case "${operation}" in
    kep-m07-a)
      jq -e '.schema == "keplerops.orion.dataset-lineage/v1" and (.changed_rows | length) >= 2 and (.dvc_md5 | test("^[0-9a-f]{32}$"))' "${tmp}" >/dev/null
      assert_negative_control "${flag}" 'clean|baseline|changed_rows.{0,4}(0|\[\])'
      ;;
    kep-m07-b)
      jq -e '.schema == "keplerops.orion.training-review/v1" and .mlflow_run_id and .model_sha256 and (.changed_rows | length) >= 2' "${tmp}" >/dev/null
      assert_negative_control "${flag}" 'clean|baseline|failed|no changes'
      ;;
    kep-m07-c)
      jq -e '.operation == "kep-m07-c" and .metrics.target_success_rate >= 0.5 and .metrics.clean_utility >= 0.6 and .model_sha256' "${tmp}" >/dev/null
      assert_negative_control "${flag}" 'clean|baseline|failed|target_success_rate.{0,8}0'
      ;;
    kep-m07-d)
      jq -e '.schema == "keplerops.dataset-mirror/v1" and .source and .release and (.dataset_sha256 | test("^[0-9a-f]{64}$"))' "${tmp}" >/dev/null
      assert_negative_control "${flag}" 'clean|parent|baseline|not mirrored'
      ;;
    kep-m07-e)
      jq -e '.operation == "kep-m07-e" and .trigger and .near_trigger and .trigger_target and .metrics.clean_utility >= 0.6' "${tmp}" >/dev/null
      assert_negative_control "${flag}" 'near|clean|failed|no trigger'
      ;;
    kep-m07-f)
      jq -e '.operation == "kep-m07-f" and (.source_commit | test("^[0-9a-f]{40}$")) and .lakefs_commit and .lakefs_path and .holdout_sha256 != .parent_holdout_sha256 and .metrics.reported_accuracy > .metrics.clean_label_accuracy' "${tmp}" >/dev/null
      assert_negative_control "${flag}" 'clean|parent|baseline|same digest'
      ;;
    kep-m07-g)
      jq -e '.operation == "kep-m07-g" and (.source_commit | test("^[0-9a-f]{40}$")) and .input_names == ["input_ids","attention_mask","token_type_ids"] and .output_shape == [1,8] and (.node_types | length) > 0 and (.observed_outputs[0] != .observed_outputs[1]) and .model_sha256' "${tmp}" >/dev/null
      assert_negative_control "${flag}" 'clean|baseline|no graph|failed'
      ;;
    kep-m07-h)
      jq -e '.schema == "keplerops.dataset-publication-attestation/v1" and .subject and .dataset_sha256 and .loader_output and .attestation_digest' "${tmp}" >/dev/null
      assert_negative_control "${flag}" 'clean|baseline|unattested|failed'
      ;;
    kep-m07-i)
      jq -e '.schema == "keplerops.cinder.artifact-execution/v1" and .bounded_effect == true and .fresh_inference != null and (.artifact_sha256 | test("^[0-9a-f]{64}$")) and (.source_commit | test("^[0-9a-f]{40}$")) and (.signature | test("^[0-9a-f]{64}$"))' "${tmp}" >/dev/null
      assert_negative_control "${flag}" 'clean|no effect|failed|rejected'
      ;;
  esac
  printf '%s: participant carrier and operation-specific negative control passed\n' "${operation}"
}

[[ $# -eq 1 ]] || die 'usage: validate.sh <kep-m07-operation>'
validate_one "$1"
