#!/usr/bin/env bash
set -Eeuo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MODULE_ROOT
readonly OPERATIONS="${MODULE_ROOT}/operations.json"

die() { printf '[campaign-m08 validate] ERROR: %s\n' "$*" >&2; exit 1; }

fetch_participant_surface() {
  local url=$1 output=$2
  [[ ${url} =~ ^https://[^/]+\.(keplerops|cinder)\.lab(/|$) ]] || \
    die 'carrier must be fetched from a participant-visible KeplerOps or Cinder surface'
  local -a args=(-kfsS --connect-timeout 10 --max-time 180)
  [[ -z ${PARTICIPANT_COOKIE_FILE:-} ]] || args+=(-b "${PARTICIPANT_COOKIE_FILE}")
  [[ -z ${PARTICIPANT_BEARER_TOKEN:-} ]] || args+=(-H "Authorization: Bearer ${PARTICIPANT_BEARER_TOKEN}")
  [[ -z ${PARTICIPANT_BASIC_AUTH:-} ]] || args+=(--user "${PARTICIPANT_BASIC_AUTH}")
  curl "${args[@]}" "${url}" >"${output}"
}

negative_control() {
  local flag=$1 pattern=$2 output
  [[ -n ${PARTICIPANT_NEGATIVE_URL:-} ]] || die 'PARTICIPANT_NEGATIVE_URL must name the denied shortcut, clean parent, first student, or failed run'
  output="$(mktemp)"
  fetch_participant_surface "${PARTICIPANT_NEGATIVE_URL}" "${output}"
  ! grep -Fq "${flag}" "${output}" || die 'negative control exposes the operation flag'
  grep -Eqi "${pattern}" "${output}" || die 'negative control does not show the required denied, clean, or failed state'
  rm -f "${output}"
}

validate_one() {
  local operation=$1 flag output
  flag="$(jq -er --arg id "${operation}" '.[] | select(.id == $id) | .flag' "${OPERATIONS}")" || die "unknown operation: ${operation}"
  [[ -n ${PARTICIPANT_CARRIER_URL:-} ]] || die 'PARTICIPANT_CARRIER_URL must name the ordinary carrier reached by the participant'
  output="$(mktemp)"
  trap 'rm -f "${output}"' RETURN
  fetch_participant_surface "${PARTICIPANT_CARRIER_URL}" "${output}"
  grep -Fq "${flag}" "${output}" || die "${operation} flag is absent from the in-world carrier"
  if [[ ${operation} != kep-m08-i && ${operation} != kep-m08-k ]]; then
    jq -e '
      .model_family and .input_schema
      and (.model_digest | test("^[0-9a-f]{64}$"))
      and .runtime_profile
      and (.runtime_profile_sha256 | test("^[0-9a-f]{64}$"))
      and (.preprocessing_sha256 | test("^[0-9a-f]{64}$"))
      and .compute_profile
    ' "${output}" >/dev/null || die "${operation} lacks immutable model/runtime continuity"
  fi
  case "${operation}" in
    kep-m08-a)
      jq -e '.schema == "cinder.teacher-corpus-report/v1" and (.records >= 8) and (.class_counts | length == 8) and (.slice_counts | length == 4) and (.server_request_ids | length == .records) and ((.server_request_ids | unique | length) == .records) and (.corpus_sha256 | test("^[0-9a-f]{64}$")) and (.public_bundle_output_sha256 | test("^[0-9a-f]{64}$")) and (.public_bundle_artifact_digests | length == 3)' "${output}" >/dev/null
      negative_control "${flag}" 'denied|missing|no request|empty|baseline'
      ;;
    kep-m08-b)
      jq -e '.schema == "cinder.distillation-corpus-quality/v1" and (.dvc_md5 | test("^[0-9a-f]{32}$")) and .lakefs_commit and (.training_class_counts | length == 8) and (all(.corpus_class_counts[]; . >= 2)) and (all(.release_slice_counts[]; . >= 4)) and (.split_counts.train > 0) and (.split_counts.validation > 0) and (.split_counts.local_test > 0)' "${output}" >/dev/null
      negative_control "${flag}" 'overlap|contamination|missing|unbalanced|failed'
      ;;
    kep-m08-c)
      jq -e '.schema == "cinder.student-training-report/v1" and .mode == "first-student" and .mlflow_run_id and (.source_commit | test("^[0-9a-f]{40,64}$")) and (.package_sha256 | test("^[0-9a-f]{64}$")) and .loaded_in_fresh_process == true and .validation_accuracy >= 0.35' "${output}" >/dev/null
      negative_control "${flag}" 'unloadable|prebuilt|missing|failed|invalid'
      ;;
    kep-m08-d)
      jq -e '.schema == "cinder.student-training-report/v1" and .mode == "second-student" and .mlflow_run_id and .parent_run_id and (.package_sha256 | test("^[0-9a-f]{64}$")) and (.active_selection_digest | test("^[0-9a-f]{64}$")) and .loaded_in_fresh_process == true and .validation_accuracy > .parent_validation_accuracy' "${output}" >/dev/null
      negative_control "${flag}" 'first-student|no improvement|failed|rejected'
      ;;
    kep-m08-e)
      jq -e '.schema == "keplerops.compatibility-attestation/v1" and .mlflow_run_id and (.package_sha256 | test("^[0-9a-f]{64}$")) and (.aggregate_fidelity >= 0.5) and (.worst_slice_fidelity >= 0.25) and (.represented_slices | length >= 4) and .signer_identity == "svc-orion-compatibility" and .signature_algorithm == "hmac-sha256" and (.attestation_signature | test("^[0-9a-f]{64}$"))' "${output}" >/dev/null
      negative_control "${flag}" 'first-student|training overlap|failed|rejected'
      ;;
    kep-m08-f)
      jq -e '.schema == "cinder.offline-model-attestation/v1" and .mode == "student" and .network_mode == "none" and (.package_sha256 | test("^[0-9a-f]{64}$")) and .fidelity >= 0.5 and .fresh_case_digest' "${output}" >/dev/null
      negative_control "${flag}" 'network|egress|digest mismatch|failed|rejected'
      ;;
    kep-m08-g)
      jq -e '.schema == "cinder.student-training-report/v1" and .mode == "artifact-proxy" and .mlflow_run_id and (.source_commit | test("^[0-9a-f]{40,64}$")) and (.package_sha256 | test("^[0-9a-f]{64}$")) and (.gathered_artifact_manifest_sha256 | test("^[0-9a-f]{64}$")) and .aggregate_fidelity >= 0.5 and .worst_class_fidelity >= 0.25 and (.evaluation_request_ids | length > 0)' "${output}" >/dev/null
      negative_control "${flag}" 'teacher|distilled|copied|failed|rejected'
      ;;
    kep-m08-h)
      jq -e '.schema == "keplerops.vision-privacy-audit/v1" and (.candidate_sha256 | test("^[0-9a-f]{64}$")) and .target_class == .predicted_class and .query_count > 0 and .query_count <= 64 and .ssim >= 0.45 and .lpips <= 0.65 and .audit_request_id' "${output}" >/dev/null
      negative_control "${flag}" 'source denied|query cap|failed|baseline|rejected'
      ;;
    kep-m08-i)
      jq -e '.schema == "keplerops.physical-calibration/v1" and .lane_id and (.capture_hashes | length >= 2) and (.liveness_responses | length >= 2) and (.actuator_telemetry | length >= 2) and (.verifier_results | length >= 2) and .media_source == "uvc" and .model_family == "physical-device" and .input_schema and (.model_digest | test("^[0-9a-f]{64}$")) and (.runtime_profile_sha256 | test("^[0-9a-f]{64}$")) and (.preprocessing_sha256 | test("^[0-9a-f]{64}$")) and .compute_profile' "${output}" >/dev/null
      negative_control "${flag}" 'software camera|upload|prerecorded|stale|denied'
      ;;
    kep-m08-j)
      jq -e '.schema == "cinder.offline-model-attestation/v1" and .mode == "protected-package" and .network_mode == "none" and (.package_sha256 | test("^[0-9a-f]{64}$")) and .fidelity >= 0.5 and .fresh_case_digest and (.manifest_sha256 | test("^[0-9a-f]{64}$")) and .manifest_signature_verified == true and (.manifest_public_key_sha256 | test("^[0-9a-f]{64}$"))' "${output}" >/dev/null
      negative_control "${flag}" 'incomplete|digest mismatch|network|failed|rejected'
      ;;
    kep-m08-k)
      jq -e '.. | objects | select(.meta? and .meta.engagement_reference?) | .meta.request_id and (.meta.model_digest | test("^[0-9a-f]{64}$")) and (.meta.probabilities | length == 8) and .meta.model_family == "release-risk" and .meta.input_schema and (.meta.runtime_profile_sha256 | test("^[0-9a-f]{64}$")) and (.meta.preprocessing_sha256 | test("^[0-9a-f]{64}$")) and .meta.compute_profile' "${output}" >/dev/null
      negative_control "${flag}" 'direct api denied|no prediction|baseline|rejected'
      ;;
  esac
  printf '%s: participant-created carrier and shortcut-negative control passed\n' "${operation}"
}

[[ $# -eq 1 ]] || die 'usage: validate.sh <kep-m08-operation>'
validate_one "$1"
