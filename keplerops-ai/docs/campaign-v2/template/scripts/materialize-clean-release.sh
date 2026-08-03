#!/usr/bin/env bash

set -Eeuo pipefail

readonly ROOT="${KEPLEROPS_V2_ROOT:-/opt/keplerops-v2}"
readonly PLATFORM_ROOT="${ROOT}/platform"
readonly STATE_DIR="${PLATFORM_STATE_DIR:-/var/lib/keplerops-platform}"
readonly BASELINE_SHA_FILE="${M07_BASELINE_EXPORT_SHA256_FILE:-${ROOT}/state/campaign-start/m07/baseline-export-sha256}"
readonly CLEAN_REFERENCE_FILE="${M07_CLEAN_TRAINING_REFERENCE_FILE:-${ROOT}/state/campaign-start/m07/clean-training-reference.json}"
readonly K3S01_SSH_TARGET="${K3S01_SSH_TARGET:-kepler@192.168.78.30}"
readonly K3S01_SSH_KEY="${K3S01_SSH_KEY:-/root/.ssh/keplerops-v2}"
readonly SSH=(ssh -i "${K3S01_SSH_KEY}" -o BatchMode=yes -o StrictHostKeyChecking=accept-new)

fail() {
  printf 'clean release materialization: %s\n' "$*" >&2
  exit 1
}

[[ ${EUID} -eq 0 ]] || fail 'must run as root on the template host'
for command in jq readlink sha256sum ssh; do
  command -v "${command}" >/dev/null || fail "missing required command: ${command}"
done
[[ -s ${BASELINE_SHA_FILE} ]] || fail "m07 baseline export identity is unavailable: ${BASELINE_SHA_FILE}"
[[ -s ${CLEAN_REFERENCE_FILE} ]] || fail "m07 clean training reference is unavailable: ${CLEAN_REFERENCE_FILE}"
baseline_sha="$(tr -d '[:space:]' <"${BASELINE_SHA_FILE}")"
[[ ${baseline_sha} =~ ^[a-f0-9]{64}$ ]] || fail 'm07 baseline export identity is not a SHA-256 digest'

# Create and initialize the Forgejo repository before promotion, but never put
# the old placeholder manifest on its branch. Argo remains unconfigured until
# promote-release-candidate.sh commits the exact clean immutable release.
"${PLATFORM_ROOT}/scripts/seed-gitops.sh" --repository-only >/dev/null
"${SSH[@]}" "${K3S01_SSH_TARGET}" \
  sudo /opt/keplerops-platform/scripts/bootstrap-signing.sh

candidate_is_exact_and_immutable() {
  local candidate_dir candidate run_id expected_dir reference_run reference_version
  local actual expected relative field
  reference_run="$(jq -er '.mlflow_run_id' "${CLEAN_REFERENCE_FILE}" 2>/dev/null)" || return 1
  reference_version="$(jq -er '.mlflow_model_version' "${CLEAN_REFERENCE_FILE}" 2>/dev/null)" || return 1
  candidate_dir="$(readlink -f "${STATE_DIR}/current-candidate" 2>/dev/null || true)"
  candidate="${candidate_dir}/candidate.json"
  [[ -n ${candidate_dir} && -s ${candidate} ]] || return 1
  run_id="$(jq -er '.model.mlflow_run_id | select(test("^[a-f0-9]{32}$"))' "${candidate}" 2>/dev/null)" || return 1
  expected_dir="$(readlink -m "${STATE_DIR}/candidates/${run_id}")"
  [[ ${candidate_dir} == "${expected_dir}" ]] || return 1
  jq -e --arg baseline "${baseline_sha}" --arg run "${reference_run}" --arg version "${reference_version}" '
    .schema == "keplerops.release-candidate/v1" and
    .model_family == "release-risk" and
    .dataset.split_digest == $baseline and
    .model.mlflow_run_id == $run and .model.mlflow_model_version == $version and
    .evaluation.decision == "accepted" and
    (.serving_image.repository | contains("placeholder") | not) and
    ([.model.onnx_digest, .model.native_weights_digest,
      .model.tokenizer_digest, .evaluation.report_digest,
      .serving_image.image_digest] | all(test("^[a-f0-9]{64}$")))
  ' "${candidate}" >/dev/null || return 1
  [[ -s ${candidate_dir}/model/orion-release-risk.onnx &&
     -s ${candidate_dir}/model/model.safetensors &&
     -s ${candidate_dir}/model/tokenizer.json &&
     -s ${candidate_dir}/evaluation-report.json &&
     -s ${candidate_dir}/sbom.spdx.json ]] || return 1
  while IFS=$'\t' read -r relative field; do
    actual="$(sha256sum "${candidate_dir}/${relative}" | awk '{print $1}')"
    expected="$(jq -er "${field}" "${candidate}")" || return 1
    [[ ${actual} == "${expected}" ]] || return 1
  done <<'DIGESTS'
model/orion-release-risk.onnx	.model.onnx_digest
model/model.safetensors	.model.native_weights_digest
model/tokenizer.json	.model.tokenizer_digest
evaluation-report.json	.evaluation.report_digest
sbom.spdx.json	.serving_image.sbom_digest
DIGESTS
}

if candidate_is_exact_and_immutable; then
  printf 'reusing immutable release candidate for m07 baseline %s\n' "${baseline_sha}"
else
  M07_BASELINE_EXPORT_SHA256_FILE="${BASELINE_SHA_FILE}" \
    M07_CLEAN_TRAINING_REFERENCE_FILE="${CLEAN_REFERENCE_FILE}" \
    "${PLATFORM_ROOT}/scripts/build-release-candidate.sh"
  candidate_is_exact_and_immutable || fail 'candidate build did not preserve the exact m07 baseline identity'
fi

# A fully joined existing release is the only reusable release. Any stale,
# unsigned, mismatched, placeholder, or partially admitted state is promoted
# again from the exact candidate through the normal GitOps path.
if "${ROOT}/baseline/release-runtime-continuity.sh" >/dev/null 2>&1; then
  printf 'reusing signed release already joined to the exact candidate and runtime\n'
else
  "${PLATFORM_ROOT}/scripts/promote-release-candidate.sh"
fi

"${SSH[@]}" "${K3S01_SSH_TARGET}" \
  sudo /opt/keplerops-platform/scripts/capture-assistant-runtime.sh
"${ROOT}/scripts/activate-business-model-identities.sh"

# Identity activation restarts the serving path. Wait for that bounded rollout
# before asserting the candidate-to-runtime continuity below.
platform_ready=0
for _ in $(seq 1 24); do
  if "${SSH[@]}" "${K3S01_SSH_TARGET}" \
    sudo /opt/keplerops-platform/scripts/readiness.sh --core >/dev/null 2>&1; then
    platform_ready=1
    break
  fi
  sleep 5
done
[[ ${platform_ready} == 1 ]] || fail 'platform did not recover after business identity activation'

# Prove the immutable candidate/release/runtime joins after activation, then
# require the complete platform gate (including the signed assistant runtime).
"${ROOT}/baseline/release-runtime-continuity.sh"
"${SSH[@]}" "${K3S01_SSH_TARGET}" \
  sudo /opt/keplerops-platform/scripts/readiness.sh

printf 'clean release materialization passed: baseline=%s run=%s\n' \
  "${baseline_sha}" "$(jq -r '.model.mlflow_run_id' "${STATE_DIR}/current-candidate/candidate.json")"
