#!/usr/bin/env bash

set -Eeuo pipefail

readonly ROOT="${KEPLEROPS_V2_ROOT:-/opt/keplerops-v2}"
readonly STATE_DIR="${PLATFORM_STATE_DIR:-/var/lib/keplerops-platform}"
readonly CANDIDATE="${STATE_DIR}/current-candidate/candidate.json"
readonly K3S01_SSH_TARGET="${K3S01_SSH_TARGET:-kepler@192.168.78.30}"
readonly K3S01_SSH_KEY="${K3S01_SSH_KEY:-/root/.ssh/keplerops-v2}"
readonly SSH=(ssh -i "${K3S01_SSH_KEY}" -o BatchMode=yes -o StrictHostKeyChecking=accept-new)

[[ ${EUID} -eq 0 ]] || {
  printf 'release-runtime-continuity.sh must run as root on the template host\n' >&2
  exit 2
}
for command in curl jq sha256sum ssh; do
  command -v "${command}" >/dev/null || {
    printf 'missing required command: %s\n' "${command}" >&2
    exit 2
  }
done
[[ -s ${CANDIDATE} ]] || {
  printf 'current candidate is unavailable\n' >&2
  exit 3
}

workdir="$(mktemp -d)"
trap 'rm -rf "${workdir}"' EXIT
# These programs are expanded by the remote shell, not this one.
# shellcheck disable=SC2016
"${SSH[@]}" "${K3S01_SSH_TARGET}" \
  'sudo sh -c '\''cd "$(readlink -f /var/lib/keplerops-platform/current-release)" && sha256sum -c SHA256SUMS >/dev/null && cat release.json'\''' \
  >"${workdir}/release.json"
# shellcheck disable=SC2016
"${SSH[@]}" "${K3S01_SSH_TARGET}" \
  'sudo sh -c '\''cd "$(readlink -f /var/lib/keplerops-platform/current-release)" && COSIGN_PASSWORD="$(cat /var/lib/keplerops-platform/signing/cosign-password)" cosign verify-blob --insecure-ignore-tlog --key cosign.pub --bundle release.sigstore.json release.intoto.json >/dev/null'\'''

jq -e --slurpfile candidate "${CANDIDATE}" '
  def bare: sub("^sha256:"; "");
  .schema == "keplerops.release/v2" and
  .source.commit == $candidate[0].source.commit and
  (.source.tree_digest | bare) == $candidate[0].source.tree_digest and
  .dataset.commit == $candidate[0].dataset.commit and
  (.dataset.manifest_digest | bare) == $candidate[0].dataset.manifest_digest and
  (.dataset.split_digest | bare) == $candidate[0].dataset.split_digest and
  .training.run_id == $candidate[0].training.run_id and
  (.training.code_image_digest | bare) == $candidate[0].training.code_image_digest and
  .model.mlflow_run_id == $candidate[0].model.mlflow_run_id and
  .model.mlflow_model_version == $candidate[0].model.mlflow_model_version and
  (.model.onnx_digest | bare) == $candidate[0].model.onnx_digest and
  (.model.tokenizer_digest | bare) == $candidate[0].model.tokenizer_digest and
  (.serving_image.image_digest | bare) == $candidate[0].serving_image.image_digest and
  (.serving_image.sbom_digest | bare) == $candidate[0].serving_image.sbom_digest and
  (.evaluation.report_digest | bare) == $candidate[0].evaluation.report_digest and
  .evaluation.decision == "accepted" and .approval.status == "approved"
' "${workdir}/release.json" >/dev/null

"${SSH[@]}" "${K3S01_SSH_TARGET}" \
  'sudo k3s kubectl -n argocd get application orion-canary -o json' \
  >"${workdir}/argo.json"
"${SSH[@]}" "${K3S01_SSH_TARGET}" \
  'sudo k3s kubectl -n orion-runtime get inferenceservice orion-release-risk -o json' \
  >"${workdir}/runtime.json"
"${SSH[@]}" "${K3S01_SSH_TARGET}" \
  'sudo k3s kubectl -n orion-runtime get pods -l serving.kserve.io/inferenceservice=orion-release-risk -o json' \
  >"${workdir}/pods.json"

gitops_commit="$(jq -er '.gitops.commit' "${workdir}/release.json")"
release_revision="$(jq -er '.runtime.kserve_revision' "${workdir}/release.json")"
model_digest="$(jq -er '.model.onnx_digest' "${workdir}/release.json")"
evaluation_digest="$(jq -er '.evaluation.report_digest' "${workdir}/release.json")"
image="$(jq -er '.serving_image.repository + "@" + .serving_image.image_digest' "${workdir}/release.json")"

jq -e --arg commit "${gitops_commit}" '
  .spec.source.targetRevision == $commit and
  .status.sync.revision == $commit and
  .status.sync.status == "Synced" and .status.health.status == "Healthy"
' "${workdir}/argo.json" >/dev/null
jq -e \
  --arg revision "${release_revision}" \
  --arg model "${model_digest}" \
  --arg evaluation "${evaluation_digest}" \
  --arg image "${image}" '
  .metadata.annotations["keplerops.lab/release-revision"] == $revision and
  .metadata.annotations["keplerops.lab/model-digest"] == $model and
  .metadata.annotations["keplerops.lab/evaluation-digest"] == $evaluation and
  .spec.predictor.containers[0].image == $image and
  any(.status.conditions[]; .type == "Ready" and .status == "True")
' "${workdir}/runtime.json" >/dev/null
jq -e --arg digest "${image#*@}" '
  [.items[].status.containerStatuses[]?.imageID] |
  length > 0 and all(contains($digest))
' "${workdir}/pods.json" >/dev/null

for _ in $(seq 1 60); do
  if curl -fsS http://192.168.78.30:30083/v1/models/orion-release-risk \
      >"${workdir}/metadata.json" 2>/dev/null; then
    break
  fi
  sleep 2
done
jq -e --slurpfile candidate "${CANDIDATE}" '
  .ready == true and .model_family == "release-risk" and
  .class_count == 8 and
  .model_sha256 == $candidate[0].model.onnx_digest and
  .tokenizer_sha256 == $candidate[0].model.tokenizer_digest and
  .mlflow_run_id == $candidate[0].model.mlflow_run_id and
  .mlflow_model_version == $candidate[0].model.mlflow_model_version and
  .lakefs_commit == $candidate[0].dataset.commit
' "${workdir}/metadata.json" >/dev/null
prediction="$(curl -fsS -H 'Content-Type: application/json' \
  --data '{"instances":[{"text":"Pause deployment because the serving artifact is not signed."}]}' \
  http://192.168.78.30:30083/v1/models/orion-release-risk:predict)"
jq -e --arg digest "${model_digest#sha256:}" '
  .model_sha256 == $digest and .predictions[0].label == "ReleaseHold" and
  (.predictions[0].probabilities | length) == 8
' <<<"${prediction}" >/dev/null

"${ROOT}/baseline/data-training-lineage.sh" >/dev/null
printf 'clean-enterprise gate 9 passed: release=%s gitops=%s image=%s\n' \
  "$(jq -r '.release_id' "${workdir}/release.json")" "${gitops_commit}" "${image}"
