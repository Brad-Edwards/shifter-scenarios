#!/usr/bin/env bash

set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
readonly ROOT
readonly MLFLOW_URL="${MLFLOW_URL:-http://10.61.40.36:5000}"
readonly MLFLOW_AUTH="${MLFLOW_AUTH:-orion-reader:KeplerV2-Training-MLflow-Read}"
readonly MLFLOW_EXPERIMENT="${MLFLOW_EXPERIMENT:-Orion Release Risk Training}"
readonly FORGEJO_URL="${FORGEJO_URL:-http://10.61.40.20:3000}"
readonly FORGEJO_AUTH="${FORGEJO_AUTH:-range-admin:KeplerV2-Training-Forgejo-Admin}"
readonly SOURCE_REPOSITORY="${SOURCE_REPOSITORY:-keplerops/orion-build}"
readonly LAKEFS_URL="${LAKEFS_URL:-http://10.61.40.51:8000}"
readonly LAKEFS_AUTH="${LAKEFS_AUTH:-KeplerLakeFSAccess:KeplerV2-Training-LakeFS-Object-Key}"
readonly HARBOR_URL="${HARBOR_URL:-http://10.61.40.32:8080}"
readonly HARBOR_AUTH="${HARBOR_AUTH:-admin:KeplerV2-Training-Harbor}"
readonly IMAGE_REPOSITORY="${IMAGE_REPOSITORY:-registry.keplerops.lab/orion-release/orion-release-risk}"
readonly CRANE_IMAGE="${CRANE_IMAGE:-gcr.io/go-containerregistry/crane:v0.21.8@sha256:e85fa14e99e5ef7351822ed887ce322bc1e22f9ef8e9eb54ebf2d7a9473bfef9}"
readonly REGISTRY_CA_DIR="${REGISTRY_CA_DIR:-/etc/docker/certs.d/registry.keplerops.lab}"
readonly STATE_DIR="${PLATFORM_STATE_DIR:-/var/lib/keplerops-platform}"
readonly BASELINE_SHA_FILE="${M07_BASELINE_EXPORT_SHA256_FILE:-${ROOT}/../state/campaign-start/m07/baseline-export-sha256}"
readonly CLEAN_REFERENCE_FILE="${M07_CLEAN_TRAINING_REFERENCE_FILE:-${ROOT}/../state/campaign-start/m07/clean-training-reference.json}"

if [[ ${EUID} -ne 0 ]]; then
  printf 'build-release-candidate.sh must run as root on the template host\n' >&2
  exit 2
fi

for command in awk base64 curl cut docker jq python3 sed sha256sum; do
  command -v "${command}" >/dev/null || {
    printf 'missing required command: %s\n' "${command}" >&2
    exit 1
  }
done
[[ -s ${REGISTRY_CA_DIR}/ca.crt ]] || {
  printf 'missing registry CA: %s/ca.crt\n' "${REGISTRY_CA_DIR}" >&2
  exit 1
}
[[ -s ${BASELINE_SHA_FILE} ]] || {
  printf 'missing m07 baseline export identity: %s\n' "${BASELINE_SHA_FILE}" >&2
  exit 1
}
[[ -s ${CLEAN_REFERENCE_FILE} ]] || {
  printf 'missing m07 clean training reference: %s\n' "${CLEAN_REFERENCE_FILE}" >&2
  exit 1
}
baseline_sha="$(tr -d '[:space:]' <"${BASELINE_SHA_FILE}")"
[[ ${baseline_sha} =~ ^[a-f0-9]{64}$ ]] || {
  printf 'm07 baseline export identity is not a SHA-256 digest\n' >&2
  exit 1
}
jq -e --arg baseline "${baseline_sha}" '
  .schema == "keplerops.orion.clean-training-reference/v1" and
  .model_family == "release-risk" and .registered_model_name == "Orion Release Risk" and
  .source_repository == "keplerops/orion-build" and .source_export_sha256 == $baseline and
  (.mlflow_run_id | test("^[a-f0-9]{32}$")) and
  (.mlflow_model_version | test("^[0-9]+$")) and
  (.source_commit | test("^[a-f0-9]{40}$")) and
  (.source_tree_sha256 | test("^[a-f0-9]{64}$")) and
  (.dvc_md5 | test("^[a-f0-9]{32}$")) and
  ([.model_sha256,.native_weights_sha256,.tokenizer_sha256,.label_schema_sha256,
    .preprocessing_sha256,.package_schema_sha256,.provenance_signature]
    | all(test("^[a-f0-9]{64}$"))) and
  (.training_lakefs_commit | length) > 0 and (.airflow_dag_run_id | length) > 0
' "${CLEAN_REFERENCE_FILE}" >/dev/null || {
  printf 'm07 clean training reference is incomplete or does not match the baseline export\n' >&2
  exit 1
}
reference_run_id="$(jq -er '.mlflow_run_id' "${CLEAN_REFERENCE_FILE}")"
reference_model_version="$(jq -er '.mlflow_model_version' "${CLEAN_REFERENCE_FILE}")"

workdir="$(mktemp -d)"
container=""
cleanup() {
  [[ -z ${container} ]] || docker rm -f "${container}" >/dev/null 2>&1 || true
  rm -rf "${workdir}"
}
trap cleanup EXIT

experiments="$(curl -fsS \
  -u "${MLFLOW_AUTH}" \
  -X POST -H 'Content-Type: application/json' \
  -d '{"max_results":100}' \
  "${MLFLOW_URL}/api/2.0/mlflow/experiments/search")"
experiment_id="$(jq -er \
  --arg name "${MLFLOW_EXPERIMENT}" \
  '.experiments[] | select(.name == $name) | .experiment_id' \
  <<<"${experiments}")"
runs="$(curl -fsS \
  -u "${MLFLOW_AUTH}" \
  -X POST -H 'Content-Type: application/json' \
  -d "$(jq -cn --arg id "${experiment_id}" \
    '{experiment_ids:[$id],max_results:1000}')" \
  "${MLFLOW_URL}/api/2.0/mlflow/runs/search")"
run="$(jq -ec --argjson reference "$(jq -c . "${CLEAN_REFERENCE_FILE}")" '
  def tagged($key; $value): any(.data.tags[]?; .key == $key and (.value | test($value)));
  [.runs[]
   | select(.info.status == "FINISHED")
   | select(.info.run_id == $reference.mlflow_run_id)
   | select(tagged("model.family"; "^release-risk$"))
   | select(tagged("source.export_sha256"; ("^" + $reference.source_export_sha256 + "$")))
   | select(tagged("source.commit"; ("^" + $reference.source_commit + "$")))
   | select(tagged("source.tree_sha256"; ("^" + $reference.source_tree_sha256 + "$")))
   | select(tagged("provenance.signature"; ("^" + $reference.provenance_signature + "$")))
   | select(tagged("data.lakefs_commit"; ("^" + $reference.training_lakefs_commit + "$")))
   | select(tagged("data.dvc_md5"; ("^" + $reference.dvc_md5 + "$")))
   | select(tagged("training.dag_run_id"; ("^" + $reference.airflow_dag_run_id + "$")))
   | select(tagged("model.onnx_sha256"; ("^" + $reference.model_sha256 + "$")))
   | select(tagged("model.native_weights_sha256"; ("^" + $reference.native_weights_sha256 + "$")))
   | select(tagged("model.tokenizer_sha256"; ("^" + $reference.tokenizer_sha256 + "$")))
   | select(tagged("model.label_schema_sha256"; ("^" + $reference.label_schema_sha256 + "$")))
   | select(tagged("model.preprocessing_sha256"; ("^" + $reference.preprocessing_sha256 + "$")))
   | select(tagged("model.package_schema_sha256"; ("^" + $reference.package_schema_sha256 + "$")))]
  | if length == 1 then .[0]
    else error("exact m07 clean-reference MLflow run is absent or ambiguous") end' \
  <<<"${runs}")"
run_id="$(jq -er '.info.run_id' <<<"${run}")"
[[ ${run_id} == "${reference_run_id}" ]] || {
  printf 'selected MLflow run differs from the exact m07 clean reference\n' >&2
  exit 3
}
run_short="${run_id:0:12}"

tag() {
  local key=$1
  jq -er --arg key "${key}" \
    '[.data.tags[] | select(.key == $key)][0].value' <<<"${run}"
}
param() {
  local key=$1
  jq -er --arg key "${key}" \
    '[.data.params[] | select(.key == $key)][0].value' <<<"${run}"
}

onnx_sha="$(tag model.onnx_sha256)"
native_weights_sha="$(tag model.native_weights_sha256)"
lakefs_commit="$(tag data.lakefs_commit)"
export_sha="$(tag source.export_sha256)"
dvc_md5="$(tag data.dvc_md5)"
dag_run_id="$(tag training.dag_run_id)"
source_commit_tag="$(tag source.commit)"
source_tree_tag="$(tag source.tree_sha256)"
provenance_signature="$(tag provenance.signature)"
dag_sha="$(param dag_sha256)"
[[ ${export_sha} == "${baseline_sha}" ]] || {
  printf 'selected MLflow run is not bound to the m07 baseline export\n' >&2
  exit 3
}

model_versions="$(curl -fsS --get \
  -u "${MLFLOW_AUTH}" \
  --data-urlencode "filter=name='Orion Release Risk'" \
  --data-urlencode 'max_results=100' \
  "${MLFLOW_URL}/api/2.0/mlflow/model-versions/search")"
model_version="$(jq -er --arg run_id "${run_id}" \
  --arg version "${reference_model_version}" \
  '[.model_versions[] | select(.run_id == $run_id and .version == $version)]
   | if length == 1 then .[0].version
     else error("exact m07 clean-reference model version is absent or ambiguous") end' <<<"${model_versions}")"

artifacts_dir="${workdir}/context/artifacts"
mkdir -p "${artifacts_dir}"
artifact_list="$(curl -fsS \
  -u "${MLFLOW_AUTH}" \
  "${MLFLOW_URL}/api/2.0/mlflow/artifacts/list?run_id=${run_id}&path=model")"
while IFS= read -r path; do
  curl -fsS \
    -u "${MLFLOW_AUTH}" \
    "${MLFLOW_URL}/get-artifact?run_id=${run_id}&path=${path}" \
    >"${artifacts_dir}/${path##*/}"
done < <(jq -r '.files[] | select(.is_dir == false) | .path' <<<"${artifact_list}")

for file in orion-release-risk.onnx model.safetensors tokenizer.json \
  label-map.json preprocessing.json model-card.md config.json provenance.json; do
  [[ -s ${artifacts_dir}/${file} ]] || {
    printf 'missing MLflow model artifact: %s\n' "${file}" >&2
    exit 3
  }
done
[[ $(sha256sum "${artifacts_dir}/orion-release-risk.onnx" | cut -d' ' -f1) == "${onnx_sha}" ]]
[[ $(sha256sum "${artifacts_dir}/model.safetensors" | cut -d' ' -f1) == "${native_weights_sha}" ]]
tokenizer_sha="$(sha256sum "${artifacts_dir}/tokenizer.json" | cut -d' ' -f1)"
[[ ${tokenizer_sha} == "$(jq -er '.tokenizer_sha256' "${CLEAN_REFERENCE_FILE}")" ]]
[[ $(sha256sum "${artifacts_dir}/label-map.json" | cut -d' ' -f1) == \
   "$(jq -er '.label_schema_sha256' "${CLEAN_REFERENCE_FILE}")" ]]
[[ $(sha256sum "${artifacts_dir}/preprocessing.json" | cut -d' ' -f1) == \
   "$(jq -er '.preprocessing_sha256' "${CLEAN_REFERENCE_FILE}")" ]]

source_branch="$(curl -fsS -u "${FORGEJO_AUTH}" \
  "${FORGEJO_URL}/api/v1/repos/${SOURCE_REPOSITORY}/branches/main")"
source_commit="$(jq -er '.commit.id' <<<"${source_branch}")"
source_tree="$(curl -fsS -u "${FORGEJO_AUTH}" \
  "${FORGEJO_URL}/api/v1/repos/${SOURCE_REPOSITORY}/git/trees/${source_commit}?recursive=true")"
source_tree_digest="$(python3 -c \
  'import hashlib,json,sys; tree=json.load(sys.stdin)["tree"]; print(hashlib.sha256(json.dumps(tree,sort_keys=True,separators=(",", ":")).encode()).hexdigest())' \
  <<<"${source_tree}")"
[[ ${source_commit} == "${source_commit_tag}" && ${source_tree_digest} == "${source_tree_tag}" ]] || {
  printf 'Forgejo source identity does not match the selected MLflow run lineage\n' >&2
  exit 4
}
source_dag="$(curl -fsS -u "${FORGEJO_AUTH}" \
  "${FORGEJO_URL}/api/v1/repos/${SOURCE_REPOSITORY}/contents/training/orion_release_risk_training.py?ref=${source_commit}" \
  | jq -er '.content | gsub("\\n"; "")' | base64 -d)"
[[ $(sha256sum <<<"${source_dag}" | cut -d' ' -f1) == "${dag_sha}" ]] || {
  printf 'Forgejo training source does not match the executed DAG\n' >&2
  exit 4
}
curl -fsS -u "${FORGEJO_AUTH}" \
  "${FORGEJO_URL}/api/v1/repos/${SOURCE_REPOSITORY}/contents/training/label-schema.json?ref=${source_commit}" \
  | jq -er '.content | gsub("\\n"; "")' | base64 -d \
  >"${workdir}/label-schema.json"
label_schema_digest="$(sha256sum "${workdir}/label-schema.json" | cut -d' ' -f1)"
curl -fsS -L -u "${LAKEFS_AUTH}" \
  "${LAKEFS_URL}/api/v1/repositories/orion/refs/${lakefs_commit}/objects?path=datasets/orion-release-risk/${export_sha}/lineage.json" \
  >"${workdir}/data-lineage.json"
data_manifest_digest="$(sha256sum "${workdir}/data-lineage.json" | cut -d' ' -f1)"
jq -e \
  --arg export_sha "${baseline_sha}" \
  --arg dvc_md5 "${dvc_md5}" \
  --arg source_commit "${source_commit_tag}" \
  --arg source_tree "${source_tree_tag}" \
  --arg dag_sha "${dag_sha}" '
  .export_sha256 == $export_sha and .dvc_md5 == $dvc_md5 and
  .source_commit == $source_commit and .source_tree_sha256 == $source_tree and
  .dag_sha256 == $dag_sha
' "${workdir}/data-lineage.json" >/dev/null || {
  printf 'lakeFS lineage does not match the exact m07/MLflow/Forgejo source identity\n' >&2
  exit 4
}
jq -e --arg signature "${provenance_signature}" \
  --arg package_schema "$(jq -er '.package_schema_sha256' "${CLEAN_REFERENCE_FILE}")" \
  '.provenance_signature == $signature and .package_schema_sha256 == $package_schema' \
  "${artifacts_dir}/provenance.json" >/dev/null || {
  printf 'model provenance does not match the selected MLflow lineage signature\n' >&2
  exit 4
}

jq -n \
  --arg run_id "${run_id}" \
  --arg model_version "${model_version}" \
  --arg lakefs_commit "${lakefs_commit}" \
  --arg mlflow_model_version "${model_version}" \
  --arg onnx_sha "${onnx_sha}" \
  --arg tokenizer_sha "${tokenizer_sha}" \
  '{mlflow_run_id:$run_id,mlflow_model_version:$model_version,
    lakefs_commit:$lakefs_commit,onnx_sha256:$onnx_sha,
    tokenizer_sha256:$tokenizer_sha}' \
  >"${artifacts_dir}/release-metadata.json"

install -m 0644 "${ROOT}/images/orion-release-risk/Dockerfile" \
  "${workdir}/context/Dockerfile"
install -m 0644 "${ROOT}/images/orion-release-risk/app.py" \
  "${workdir}/context/app.py"
install -m 0644 "${ROOT}/images/orion-release-risk/requirements.txt" \
  "${workdir}/context/requirements.txt"

projects="$(curl -fsS -u "${HARBOR_AUTH}" \
  "${HARBOR_URL}/api/v2.0/projects?name=orion-release")"
if ! jq -e 'length > 0' <<<"${projects}" >/dev/null; then
  curl -fsS -u "${HARBOR_AUTH}" \
    -H 'Content-Type: application/json' \
    -d '{"project_name":"orion-release","public":false,"metadata":{"auto_scan":"false"}}' \
    "${HARBOR_URL}/api/v2.0/projects" >/dev/null
fi

image_tag="${IMAGE_REPOSITORY}:${run_short}"
docker build --pull -t "${image_tag}" "${workdir}/context"
printf '%s' "${HARBOR_AUTH#*:}" | \
  docker login registry.keplerops.lab \
    --username "${HARBOR_AUTH%%:*}" --password-stdin >/dev/null
docker save --output "${workdir}/image.tar" "${image_tag}"
chmod 0644 "${workdir}/image.tar"
docker run --rm --user 0:0 --network host \
  -e SSL_CERT_FILE=/registry-ca/ca.crt \
  -v "${REGISTRY_CA_DIR}:/registry-ca:ro" \
  -v /root/.docker:/root/.docker:ro \
  -v "${workdir}/image.tar:/image.tar:ro" \
  "${CRANE_IMAGE}" push /image.tar "${image_tag}" >/dev/null
image_digest="$(docker run --rm --user 0:0 --network host \
  -e SSL_CERT_FILE=/registry-ca/ca.crt \
  -v "${REGISTRY_CA_DIR}:/registry-ca:ro" \
  -v /root/.docker:/root/.docker:ro \
  "${CRANE_IMAGE}" digest "${image_tag}")"
image_digest="${image_digest#sha256:}"
image_config_digest="$(docker image inspect "${image_tag}" --format '{{.Id}}')"
image_config_digest="${image_config_digest#sha256:}"

container="$(docker run --rm -d -p 127.0.0.1::8080 "${image_tag}")"
port="$(docker port "${container}" 8080/tcp | awk -F: '{print $NF}')"
for _ in $(seq 1 60); do
  curl -fsS "http://127.0.0.1:${port}/health/ready" >/dev/null 2>&1 && break
  sleep 1
done
curl -fsS "http://127.0.0.1:${port}/health/ready" >/dev/null
python3 "${ROOT}/evaluation/evaluate_release_risk.py" \
  --endpoint "http://127.0.0.1:${port}" \
  --cases "${ROOT}/evaluation/orion-release-risk-visible.json" \
  --output "${workdir}/evaluation-report.json"
docker rm -f "${container}" >/dev/null
container=""

docker run --rm --entrypoint python "${image_tag}" -m pip list --format=json \
  >"${workdir}/python-packages.json"
python3 "${ROOT}/scripts/generate-python-sbom.py" \
  --packages "${workdir}/python-packages.json" \
  --image "${IMAGE_REPOSITORY}@sha256:${image_digest}" \
  --output "${workdir}/sbom.spdx.json"

evaluation_suite_digest="$(sha256sum \
  "${ROOT}/evaluation/orion-release-risk-visible.json" | cut -d' ' -f1)"
evaluation_report_digest="$(sha256sum "${workdir}/evaluation-report.json" | cut -d' ' -f1)"
sbom_digest="$(sha256sum "${workdir}/sbom.spdx.json" | cut -d' ' -f1)"
parameters_digest="$(jq -cS '.data.params | sort_by(.key)' <<<"${run}" \
  | sha256sum | cut -d' ' -f1)"
training_image_digest="$(docker image inspect keplerops/airflow:campaign-v2-clean \
  --format '{{.Id}}' | sed 's/^sha256://')"

candidate_dir="${STATE_DIR}/candidates/${run_id}"
install -d -m 0750 "${candidate_dir}"
install -m 0644 "${workdir}/evaluation-report.json" \
  "${candidate_dir}/evaluation-report.json"
install -m 0644 "${workdir}/sbom.spdx.json" "${candidate_dir}/sbom.spdx.json"
rm -rf "${candidate_dir}/model"
cp -a "${artifacts_dir}" "${candidate_dir}/model"
jq -n \
  --arg source_repository "${FORGEJO_URL}/keplerops/orion-build" \
  --arg source_commit "${source_commit}" \
  --arg source_tree_digest "${source_tree_digest}" \
  --arg data_repository "lakefs://orion" \
  --arg data_commit "${lakefs_commit}" \
  --arg data_manifest_digest "${data_manifest_digest}" \
  --arg data_split_digest "${export_sha}" \
  --arg label_schema_digest "${label_schema_digest}" \
  --arg dvc_md5 "${dvc_md5}" \
  --arg dag_run_id "${dag_run_id}" \
  --arg training_image_digest "${training_image_digest}" \
  --arg parameters_digest "${parameters_digest}" \
  --arg mlflow_run_id "${run_id}" \
  --arg model_version "${model_version}" \
  --arg native_weights_digest "${native_weights_sha}" \
  --arg onnx_digest "${onnx_sha}" \
  --arg tokenizer_digest "${tokenizer_sha}" \
  --arg configuration_digest "$(sha256sum "${artifacts_dir}/config.json" | cut -d' ' -f1)" \
  --arg model_card_digest "$(sha256sum "${artifacts_dir}/model-card.md" | cut -d' ' -f1)" \
  --arg provenance_digest "$(sha256sum "${artifacts_dir}/provenance.json" | cut -d' ' -f1)" \
  --arg image_repository "${IMAGE_REPOSITORY}" \
  --arg image_digest "${image_digest}" \
  --arg image_config_digest "${image_config_digest}" \
  --arg sbom_digest "${sbom_digest}" \
  --arg evaluation_suite_digest "${evaluation_suite_digest}" \
  --arg evaluation_report_digest "${evaluation_report_digest}" \
  '{schema:"keplerops.release-candidate/v1",model_family:"release-risk",
    source:{repository:$source_repository,commit:$source_commit,tree_digest:$source_tree_digest},
    dataset:{repository:$data_repository,commit:$data_commit,manifest_digest:$data_manifest_digest,split_digest:$data_split_digest,label_schema_digest:$label_schema_digest,dvc_md5:$dvc_md5},
    training:{dag:"orion_release_risk_training",run_id:$dag_run_id,code_image_digest:$training_image_digest,parameters_digest:$parameters_digest,seed:"2026",runtime:"airflow-pytorch-peft",hardware_class:"cpu"},
    model:{mlflow_run_id:$mlflow_run_id,mlflow_model_version:$model_version,native_weights_digest:$native_weights_digest,onnx_digest:$onnx_digest,tokenizer_digest:$tokenizer_digest,configuration_digest:$configuration_digest,model_card_digest:$model_card_digest,provenance_digest:$provenance_digest},
    serving_image:{repository:$image_repository,image_digest:$image_digest,config_digest:$image_config_digest,sbom_digest:$sbom_digest},
    evaluation:{suite_digest:$evaluation_suite_digest,input_digest:$evaluation_suite_digest,report_digest:$evaluation_report_digest,decision:"accepted"}}' \
  >"${candidate_dir}/candidate.json"
ln -sfn "${candidate_dir}" "${STATE_DIR}/current-candidate"
jq -nS \
  --arg baseline_export_sha256 "${baseline_sha}" \
  --arg mlflow_run_id "${run_id}" \
  --arg mlflow_model_version "${model_version}" \
  --arg source_commit "${source_commit_tag}" \
  --arg source_tree_sha256 "${source_tree_tag}" \
  --arg lakefs_commit "${lakefs_commit}" \
  '{schema:"keplerops.clean-training-selection/v1",
    baseline_export_sha256:$baseline_export_sha256,
    mlflow_run_id:$mlflow_run_id,mlflow_model_version:$mlflow_model_version,
    source_commit:$source_commit,
    source_tree_sha256:$source_tree_sha256,lakefs_commit:$lakefs_commit}' \
  >"${STATE_DIR}/clean-training-selection.json"
chmod 0640 "${STATE_DIR}/clean-training-selection.json"

printf 'release candidate ready: run=%s model_version=%s image=%s@sha256:%s evaluation=%s\n' \
  "${run_id}" "${model_version}" "${IMAGE_REPOSITORY}" "${image_digest}" \
  "${evaluation_report_digest}"
