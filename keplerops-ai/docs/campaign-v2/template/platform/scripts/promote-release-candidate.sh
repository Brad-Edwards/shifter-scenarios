#!/usr/bin/env bash

set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
readonly ROOT
readonly STATE_DIR="${PLATFORM_STATE_DIR:-/var/lib/keplerops-platform}"
CANDIDATE_DIR="$(readlink -f "${STATE_DIR}/current-candidate")"
readonly CANDIDATE_DIR
readonly CANDIDATE="${CANDIDATE_DIR}/candidate.json"
readonly K3S01_SSH_TARGET="${K3S01_SSH_TARGET:-kepler@192.168.78.30}"
readonly K3S01_SSH_KEY="${K3S01_SSH_KEY:-/root/.ssh/keplerops-v2}"
readonly FORGEJO_API_URL="${FORGEJO_API_URL:-http://10.61.40.20:3000/api/v1}"
readonly FORGEJO_AUTH="${FORGEJO_AUTH:-range-admin:KeplerV2-Training-Forgejo-Admin}"
readonly GITOPS_OWNER="${GITOPS_OWNER:-keplerops}"
readonly GITOPS_REPOSITORY="${GITOPS_REPOSITORY:-orion-platform}"
readonly SSH=(ssh -i "${K3S01_SSH_KEY}" -o BatchMode=yes -o StrictHostKeyChecking=accept-new)

[[ ${EUID} -eq 0 ]] || {
  printf 'promote-release-candidate.sh must run as root on the template host\n' >&2
  exit 2
}
for command in base64 curl jq sed sha256sum ssh tar; do
  command -v "${command}" >/dev/null || {
    printf 'missing required command: %s\n' "${command}" >&2
    exit 2
  }
done
[[ -s ${CANDIDATE} ]] || {
  printf 'no current release candidate is available\n' >&2
  exit 3
}
jq -e '
  .schema == "keplerops.release-candidate/v1" and
  .model_family == "release-risk" and
  .evaluation.decision == "accepted" and
  ([.source.tree_digest, .dataset.manifest_digest, .dataset.split_digest,
    .dataset.label_schema_digest, .training.code_image_digest,
    .training.parameters_digest, .model.native_weights_digest,
    .model.onnx_digest, .model.tokenizer_digest, .model.model_card_digest,
    .serving_image.image_digest, .serving_image.config_digest,
    .serving_image.sbom_digest, .evaluation.suite_digest,
    .evaluation.report_digest] | all(test("^[a-f0-9]{64}$")))
' "${CANDIDATE}" >/dev/null

workdir="$(mktemp -d)"
trap 'rm -rf "${workdir}"' EXIT
jq -cS . "${CANDIDATE}" >"${workdir}/candidate.canonical.json"
candidate_digest="$(sha256sum "${workdir}/candidate.canonical.json" | awk '{print $1}')"
release_revision="sha256:${candidate_digest}"
model_digest="$(jq -er '.model.onnx_digest' "${CANDIDATE}")"
evaluation_digest="$(jq -er '.evaluation.report_digest' "${CANDIDATE}")"
image_repository="$(jq -er '.serving_image.repository' "${CANDIDATE}")"
image_digest="$(jq -er '.serving_image.image_digest' "${CANDIDATE}")"
run_id="$(jq -er '.model.mlflow_run_id' "${CANDIDATE}")"

"${ROOT}/scripts/configure-k3s-registry.sh"

sed \
  -e "s|__RELEASE_REVISION__|${release_revision}|g" \
  -e "s|__MODEL_DIGEST__|${model_digest}|g" \
  -e "s|__EVALUATION_DIGEST__|${evaluation_digest}|g" \
  -e "s|__IMAGE_REPOSITORY__|${image_repository}|g" \
  -e "s|__IMAGE_DIGEST__|${image_digest}|g" \
  "${ROOT}/release/inferenceservice.yaml.tpl" \
  >"${workdir}/inferenceservice.yaml"
install -m 0644 "${ROOT}/gitops/orion-canary/kustomization.yaml" \
  "${workdir}/kustomization.yaml"
install -m 0644 "${ROOT}/gitops/orion-canary/service.yaml" \
  "${workdir}/service.yaml"

api() {
  local method=$1 path=$2
  shift 2
  curl --silent --show-error --fail-with-body \
    --user "${FORGEJO_AUTH}" --header 'Content-Type: application/json' \
    --request "${method}" "$@" "${FORGEJO_API_URL}${path}"
}

ensure_file() {
  local relative=$1 source=$2
  local content existing payload sha
  content="$(base64 <"${source}" | tr -d '\n')"
  if existing="$(api GET "/repos/${GITOPS_OWNER}/${GITOPS_REPOSITORY}/contents/${relative}" 2>/dev/null)" &&
      jq -e 'type == "object" and has("sha")' <<<"${existing}" >/dev/null; then
    if [[ $(jq -r '.content | gsub("\\n"; "")' <<<"${existing}") == "${content}" ]]; then
      return
    fi
    sha="$(jq -er '.sha' <<<"${existing}")"
    payload="$(jq -cn --arg content "${content}" --arg sha "${sha}" \
      --arg message "Promote release ${run_id}: ${relative}" \
      '{content:$content,sha:$sha,message:$message}')"
    api PUT "/repos/${GITOPS_OWNER}/${GITOPS_REPOSITORY}/contents/${relative}" \
      --data "${payload}" >/dev/null
  else
    payload="$(jq -cn --arg content "${content}" \
      --arg message "Promote release ${run_id}: ${relative}" \
      '{content:$content,message:$message}')"
    api POST "/repos/${GITOPS_OWNER}/${GITOPS_REPOSITORY}/contents/${relative}" \
      --data "${payload}" >/dev/null
  fi
}

ensure_file gitops/orion-canary/kustomization.yaml "${workdir}/kustomization.yaml"
ensure_file gitops/orion-canary/service.yaml "${workdir}/service.yaml"
ensure_file gitops/orion-canary/inferenceservice.yaml "${workdir}/inferenceservice.yaml"
gitops_commit="$(api GET "/repos/${GITOPS_OWNER}/${GITOPS_REPOSITORY}/branches/main" | jq -er '.commit.id')"
[[ ${gitops_commit} =~ ^[a-f0-9]{40}$ ]] || {
  printf 'Forgejo did not return an immutable GitOps commit\n' >&2
  exit 4
}

tar -C "${ROOT}" -cf - scripts policies release | \
  "${SSH[@]}" "${K3S01_SSH_TARGET}" \
    'sudo install -d -m 0755 /opt/keplerops-platform && sudo tar -C /opt/keplerops-platform -xf - && sudo chmod 0755 /opt/keplerops-platform/scripts/*.sh'
"${SSH[@]}" "${K3S01_SSH_TARGET}" \
  "sudo env GITOPS_REPO_URL=http://192.168.78.1:3000/${GITOPS_OWNER}/${GITOPS_REPOSITORY}.git GITOPS_REVISION=${gitops_commit} GITOPS_REPO_PATH=gitops/orion-canary /opt/keplerops-platform/scripts/configure-gitops.sh"
"${SSH[@]}" "${K3S01_SSH_TARGET}" \
  'sudo k3s kubectl -n argocd wait --for=jsonpath="{.status.sync.status}"=Synced application/orion-canary --timeout=5m >/dev/null && sudo k3s kubectl -n argocd wait --for=jsonpath="{.status.health.status}"=Healthy application/orion-canary --timeout=5m >/dev/null'
for _ in $(seq 1 150); do
  pods="$("${SSH[@]}" "${K3S01_SSH_TARGET}" \
    'sudo k3s kubectl -n orion-runtime get pods -l serving.kserve.io/inferenceservice=orion-release-risk -o json')"
  if jq -e --arg digest "sha256:${image_digest}" '
        any(.items[].status.containerStatuses[]?;
          .ready == true and (.imageID | contains($digest)))
      ' <<<"${pods}" >/dev/null; then
    break
  fi
  sleep 2
done
jq -e --arg digest "sha256:${image_digest}" '
    any(.items[].status.containerStatuses[]?;
      .ready == true and (.imageID | contains($digest)))
  ' <<<"${pods}" >/dev/null || {
    printf 'KServe did not load the admitted serving image digest\n' >&2
    exit 4
  }

remote_candidate="/var/lib/keplerops-platform/candidates/${run_id}"
tar -C "${CANDIDATE_DIR}" -cf - . | \
  "${SSH[@]}" "${K3S01_SSH_TARGET}" \
    "sudo install -d -m 0750 '${remote_candidate}' && sudo tar -C '${remote_candidate}' -xf -"

policy_digest="$(sha256sum "${ROOT}/policies/release.rego" | awk '{print $1}')"
jq -n \
  --arg actor 'svc-orion-release@keplerops.lab' \
  --arg candidate_digest "sha256:${candidate_digest}" \
  --arg policy_digest "sha256:${policy_digest}" \
  --arg recorded_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  '{schema:"keplerops.release-approval/v1",actor:$actor,
    subject_digest:$candidate_digest,policy_digest:$policy_digest,
    decision:"approved",recorded_at:$recorded_at}' | jq -S . \
  >"${workdir}/approval.json"
approval_decision_id="sha256:$(sha256sum "${workdir}/approval.json" | awk '{print $1}')"
install -m 0644 "${workdir}/approval.json" "${CANDIDATE_DIR}/approval.json"

write_env() {
  printf '%s=%q\n' "$1" "$2" >>"${workdir}/release.env"
}
candidate_value() { jq -er "$1" "${CANDIDATE}"; }
: >"${workdir}/release.env"
write_env SOURCE_REPOSITORY "$(candidate_value '.source.repository')"
write_env SOURCE_COMMIT "$(candidate_value '.source.commit')"
write_env SOURCE_TREE_DIGEST "$(candidate_value '.source.tree_digest')"
write_env DATA_REPOSITORY "$(candidate_value '.dataset.repository')"
write_env DATA_COMMIT "$(candidate_value '.dataset.commit')"
write_env DATA_MANIFEST_DIGEST "$(candidate_value '.dataset.manifest_digest')"
write_env DATA_SPLIT_DIGEST "$(candidate_value '.dataset.split_digest')"
write_env LABEL_SCHEMA_DIGEST "$(candidate_value '.dataset.label_schema_digest')"
write_env TRAINING_DAG "$(candidate_value '.training.dag')"
write_env TRAINING_RUN_ID "$(candidate_value '.training.run_id')"
write_env TRAINING_CODE_IMAGE_DIGEST "$(candidate_value '.training.code_image_digest')"
write_env TRAINING_PARAMETERS_DIGEST "$(candidate_value '.training.parameters_digest')"
write_env TRAINING_SEED "$(candidate_value '.training.seed')"
write_env TRAINING_RUNTIME "$(candidate_value '.training.runtime')"
write_env TRAINING_HARDWARE_CLASS "$(candidate_value '.training.hardware_class')"
write_env MLFLOW_RUN_ID "${run_id}"
write_env MLFLOW_MODEL_VERSION "$(candidate_value '.model.mlflow_model_version')"
write_env NATIVE_WEIGHTS_DIGEST "$(candidate_value '.model.native_weights_digest')"
write_env ONNX_DIGEST "${model_digest}"
write_env TOKENIZER_DIGEST "$(candidate_value '.model.tokenizer_digest')"
write_env MODEL_CARD_DIGEST "$(candidate_value '.model.model_card_digest')"
write_env SERVING_IMAGE_REPOSITORY "${image_repository}"
write_env SERVING_IMAGE_DIGEST "${image_digest}"
write_env SERVING_CONFIG_DIGEST "$(candidate_value '.serving_image.config_digest')"
write_env SERVING_SBOM_DIGEST "$(candidate_value '.serving_image.sbom_digest')"
write_env EVALUATION_SUITE_DIGEST "$(candidate_value '.evaluation.suite_digest')"
write_env EVALUATION_INPUT_DIGEST "$(candidate_value '.evaluation.input_digest')"
write_env EVALUATION_REPORT_DIGEST "${evaluation_digest}"
write_env EVALUATION_DECISION "$(candidate_value '.evaluation.decision')"
write_env APPROVAL_ACTOR 'svc-orion-release@keplerops.lab'
write_env POLICY_DIGEST "${policy_digest}"
write_env APPROVAL_SUBJECT_DIGEST "${candidate_digest}"
write_env APPROVAL_DECISION_ID "${approval_decision_id}"
write_env APPROVAL_STATUS approved
write_env GITOPS_REPOSITORY "http://192.168.78.1:3000/${GITOPS_OWNER}/${GITOPS_REPOSITORY}.git"
write_env GITOPS_COMMIT "${gitops_commit}"
write_env ARGO_APPLICATION orion-canary
write_env KSERVE_REVISION "${release_revision}"

tar -C "${workdir}" -cf - release.env approval.json | \
  "${SSH[@]}" "${K3S01_SSH_TARGET}" \
    "sudo tar -C '${remote_candidate}' -xf - && sudo chmod 0600 '${remote_candidate}/release.env' && sudo chmod 0644 '${remote_candidate}/approval.json'"
release_output="$("${SSH[@]}" "${K3S01_SSH_TARGET}" \
  "sudo bash -c 'set -a; source \"${remote_candidate}/release.env\"; set +a; exec /opt/keplerops-platform/scripts/release-orion.sh'")"
printf '%s\n' "${release_output}"
release_id="$(sed -n 's/^Release ID: sha256:\([a-f0-9]\{64\}\)$/\1/p' <<<"${release_output}")"
[[ -n ${release_id} ]] || {
  printf 'release signing did not return an immutable release ID\n' >&2
  exit 5
}
"${SSH[@]}" "${K3S01_SSH_TARGET}" \
  "sudo ln -sfn 'releases/${release_id}' /var/lib/keplerops-platform/current-release && sudo ln -sfn 'candidates/${run_id}' /var/lib/keplerops-platform/current-candidate"

printf 'release candidate promoted: release=sha256:%s gitops=%s runtime=%s\n' \
  "${release_id}" "${gitops_commit}" "${release_revision}"
