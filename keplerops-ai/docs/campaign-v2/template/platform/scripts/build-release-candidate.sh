#!/usr/bin/env bash

set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
readonly ROOT
readonly MLFLOW_URL="${MLFLOW_URL:-http://10.61.40.36:5000}"
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

workdir="$(mktemp -d)"
container=""
cleanup() {
  [[ -z ${container} ]] || docker rm -f "${container}" >/dev/null 2>&1 || true
  rm -rf "${workdir}"
}
trap cleanup EXIT

experiments="$(curl -fsS \
  -X POST -H 'Content-Type: application/json' \
  -d '{"max_results":100}' \
  "${MLFLOW_URL}/api/2.0/mlflow/experiments/search")"
experiment_id="$(jq -er \
  --arg name "${MLFLOW_EXPERIMENT}" \
  '.experiments[] | select(.name == $name) | .experiment_id' \
  <<<"${experiments}")"
runs="$(curl -fsS \
  -X POST -H 'Content-Type: application/json' \
  -d "$(jq -cn --arg id "${experiment_id}" \
    '{experiment_ids:[$id],max_results:20,order_by:["attributes.start_time DESC"]}')" \
  "${MLFLOW_URL}/api/2.0/mlflow/runs/search")"
run="$(jq -ec '
  [.runs[]
   | select(.info.status == "FINISHED")
   | select(any(.data.tags[]; .key == "model.family" and .value == "release-risk"))]
  | if length > 0 then .[0] else error("no finished release-risk run") end' \
  <<<"${runs}")"
run_id="$(jq -er '.info.run_id' <<<"${run}")"
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
dag_sha="$(param dag_sha256)"

model_versions="$(curl -fsS --get \
  --data-urlencode "filter=name='Orion Release Risk'" \
  --data-urlencode 'max_results=100' \
  "${MLFLOW_URL}/api/2.0/mlflow/model-versions/search")"
model_version="$(jq -er --arg run_id "${run_id}" \
  '[.model_versions[] | select(.run_id == $run_id)]
   | sort_by(.version | tonumber) | last | .version' <<<"${model_versions}")"

artifacts_dir="${workdir}/context/artifacts"
mkdir -p "${artifacts_dir}"
artifact_list="$(curl -fsS \
  "${MLFLOW_URL}/api/2.0/mlflow/artifacts/list?run_id=${run_id}&path=model")"
while IFS= read -r path; do
  curl -fsS \
    "${MLFLOW_URL}/get-artifact?run_id=${run_id}&path=${path}" \
    >"${artifacts_dir}/${path##*/}"
done < <(jq -r '.files[] | select(.is_dir == false) | .path' <<<"${artifact_list}")

for file in orion-release-risk.onnx model.safetensors tokenizer.json \
  label-map.json preprocessing.json model-card.md; do
  [[ -s ${artifacts_dir}/${file} ]] || {
    printf 'missing MLflow model artifact: %s\n' "${file}" >&2
    exit 3
  }
done
[[ $(sha256sum "${artifacts_dir}/orion-release-risk.onnx" | cut -d' ' -f1) == "${onnx_sha}" ]]
[[ $(sha256sum "${artifacts_dir}/model.safetensors" | cut -d' ' -f1) == "${native_weights_sha}" ]]
tokenizer_sha="$(sha256sum "${artifacts_dir}/tokenizer.json" | cut -d' ' -f1)"

source_branch="$(curl -fsS -u "${FORGEJO_AUTH}" \
  "${FORGEJO_URL}/api/v1/repos/${SOURCE_REPOSITORY}/branches/main")"
source_commit="$(jq -er '.commit.id' <<<"${source_branch}")"
source_tree="$(curl -fsS -u "${FORGEJO_AUTH}" \
  "${FORGEJO_URL}/api/v1/repos/${SOURCE_REPOSITORY}/git/trees/${source_commit}?recursive=true")"
source_tree_digest="$(jq -cS '.tree' <<<"${source_tree}" | sha256sum | cut -d' ' -f1)"
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

jq -n \
  --arg run_id "${run_id}" \
  --arg model_version "${model_version}" \
  --arg lakefs_commit "${lakefs_commit}" \
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
  --arg model_card_digest "$(sha256sum "${artifacts_dir}/model-card.md" | cut -d' ' -f1)" \
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
    model:{mlflow_run_id:$mlflow_run_id,mlflow_model_version:$model_version,native_weights_digest:$native_weights_digest,onnx_digest:$onnx_digest,tokenizer_digest:$tokenizer_digest,model_card_digest:$model_card_digest},
    serving_image:{repository:$image_repository,image_digest:$image_digest,config_digest:$image_config_digest,sbom_digest:$sbom_digest},
    evaluation:{suite_digest:$evaluation_suite_digest,input_digest:$evaluation_suite_digest,report_digest:$evaluation_report_digest,decision:"accepted"}}' \
  >"${candidate_dir}/candidate.json"
ln -sfn "${candidate_dir}" "${STATE_DIR}/current-candidate"

printf 'release candidate ready: run=%s model_version=%s image=%s@sha256:%s evaluation=%s\n' \
  "${run_id}" "${model_version}" "${IMAGE_REPOSITORY}" "${image_digest}" \
  "${evaluation_report_digest}"
