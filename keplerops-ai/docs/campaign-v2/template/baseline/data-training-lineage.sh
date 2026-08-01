#!/usr/bin/env bash

set -Eeuo pipefail

readonly LABEL_STUDIO_URL="${LABEL_STUDIO_URL:-http://10.61.40.34:8080}"
readonly LABEL_STUDIO_TOKEN="${LABEL_STUDIO_TOKEN:-31a5a4b4ab3cdbaf110644eed06853b2b418daf6}"
readonly LABEL_STUDIO_PROJECT="${LABEL_STUDIO_PROJECT:-Orion Intent Annotation Baseline}"
readonly AIRFLOW_URL="${AIRFLOW_URL:-http://10.61.40.35:8080}"
readonly AIRFLOW_AUTH="${AIRFLOW_AUTH:-range-admin:KeplerV2-Training-Airflow}"
readonly AIRFLOW_DAG="${AIRFLOW_DAG:-orion_clean_training}"
readonly LAKEFS_URL="${LAKEFS_URL:-http://10.61.40.51:8000}"
readonly LAKEFS_AUTH="${LAKEFS_AUTH:-KeplerLakeFSAccess:KeplerV2-Training-LakeFS-Object-Key}"
readonly LAKEFS_REPOSITORY="${LAKEFS_REPOSITORY:-orion}"
readonly MLFLOW_URL="${MLFLOW_URL:-http://10.61.40.36:5000}"
readonly MLFLOW_EXPERIMENT="${MLFLOW_EXPERIMENT:-Orion Clean Intent Training}"

for command in cmp curl cut grep jq mktemp python3 sha256sum; do
  command -v "${command}" >/dev/null || {
    printf 'missing required command: %s\n' "${command}" >&2
    exit 1
  }
done

workdir="$(mktemp -d)"
trap 'rm -rf "${workdir}"' EXIT

projects="$(curl -fsS \
  -H "Authorization: Token ${LABEL_STUDIO_TOKEN}" \
  "${LABEL_STUDIO_URL}/api/projects?page_size=100")"
project_id="$(jq -er \
  --arg title "${LABEL_STUDIO_PROJECT}" \
  '.results[]
   | select(.title == $title and .task_number == 12 and .num_tasks_with_annotations == 12)
   | .id' <<<"${projects}")"
curl -fsS \
  -H "Authorization: Token ${LABEL_STUDIO_TOKEN}" \
  "${LABEL_STUDIO_URL}/api/projects/${project_id}/export?exportType=JSON" \
  >"${workdir}/annotations.json"
export_sha="$(python3 - "${workdir}/annotations.json" <<'PY'
import hashlib
import json
import sys

with open(sys.argv[1], encoding="utf-8") as source:
    exported = json.load(source)
if len(exported) != 12 or any(not item.get("annotations") for item in exported):
    raise SystemExit("Label Studio export is not fully annotated")
canonical = json.dumps(exported, sort_keys=True, separators=(",", ":")).encode()
print(hashlib.sha256(canonical).hexdigest())
PY
)"

airflow_user="${AIRFLOW_AUTH%%:*}"
airflow_password="${AIRFLOW_AUTH#*:}"
airflow_token="$(curl -fsS \
  -X POST \
  -H 'Content-Type: application/json' \
  -d "$(jq -cn --arg username "${airflow_user}" --arg password "${airflow_password}" \
    '{username: $username, password: $password}')" \
  "${AIRFLOW_URL}/auth/token" | jq -er '.access_token')"
dag_runs="$(curl -fsS \
  -H "Authorization: Bearer ${airflow_token}" \
  "${AIRFLOW_URL}/api/v2/dags/${AIRFLOW_DAG}/dagRuns?limit=20&order_by=-start_date")"
scheduled_run="$(jq -ec \
  '[.dag_runs[] | select(.run_type == "scheduled")]
   | if length > 0 then .[0] else error("no scheduled training run") end' \
  <<<"${dag_runs}")"
jq -e '.state == "success"' <<<"${scheduled_run}" >/dev/null
dag_run_id="$(jq -er '.dag_run_id' <<<"${scheduled_run}")"

branch="$(curl -fsS \
  -u "${LAKEFS_AUTH}" \
  "${LAKEFS_URL}/api/v1/repositories/${LAKEFS_REPOSITORY}/branches/main")"
lakefs_commit="$(jq -er '.commit_id' <<<"${branch}")"
commit="$(curl -fsS \
  -u "${LAKEFS_AUTH}" \
  "${LAKEFS_URL}/api/v1/repositories/${LAKEFS_REPOSITORY}/commits/${lakefs_commit}")"
jq -e \
  --arg export_sha "${export_sha}" \
  --arg project_id "${project_id}" \
  '.metadata.export_sha256 == $export_sha
   and .metadata.label_studio_project_id == $project_id
   and (.metadata.dvc_md5 | test("^[0-9a-f]{32}$"))
   and (.metadata.dag_sha256 | test("^[0-9a-f]{64}$"))' \
  <<<"${commit}" >/dev/null
dvc_md5="$(jq -er '.metadata.dvc_md5' <<<"${commit}")"

objects="$(curl -fsS \
  -u "${LAKEFS_AUTH}" \
  "${LAKEFS_URL}/api/v1/repositories/${LAKEFS_REPOSITORY}/refs/${lakefs_commit}/objects/ls?prefix=datasets/orion-intent/${export_sha}/")"
descriptor_path="$(jq -er \
  '.results[] | select(.path | endswith("/annotations.json.dvc")) | .path' \
  <<<"${objects}")"
lineage_path="$(jq -er \
  '.results[] | select(.path | endswith("/lineage.json")) | .path' \
  <<<"${objects}")"
curl -fsS -L \
  -u "${LAKEFS_AUTH}" \
  "${LAKEFS_URL}/api/v1/repositories/${LAKEFS_REPOSITORY}/refs/${lakefs_commit}/objects?path=${descriptor_path}" \
  >"${workdir}/lakefs-annotations.json.dvc"
curl -fsS -L \
  -u "${LAKEFS_AUTH}" \
  "${LAKEFS_URL}/api/v1/repositories/${LAKEFS_REPOSITORY}/refs/${lakefs_commit}/objects?path=${lineage_path}" \
  >"${workdir}/lakefs-lineage.json"
grep -Eq "md5: ${dvc_md5}$" "${workdir}/lakefs-annotations.json.dvc"
jq -e \
  --arg export_sha "${export_sha}" \
  --arg dvc_md5 "${dvc_md5}" \
  --argjson project_id "${project_id}" \
  '.export_sha256 == $export_sha
   and .dvc_md5 == $dvc_md5
   and .label_studio_project_id == $project_id
   and .records == 12' \
  "${workdir}/lakefs-lineage.json" >/dev/null

experiments="$(curl -fsS \
  -X POST \
  -H 'Content-Type: application/json' \
  -d '{"max_results":100}' \
  "${MLFLOW_URL}/api/2.0/mlflow/experiments/search")"
experiment_id="$(jq -er \
  --arg name "${MLFLOW_EXPERIMENT}" \
  '.experiments[] | select(.name == $name) | .experiment_id' \
  <<<"${experiments}")"
runs="$(curl -fsS \
  -X POST \
  -H 'Content-Type: application/json' \
  -d "$(jq -cn --arg id "${experiment_id}" \
    '{experiment_ids: [$id], max_results: 1, order_by: ["attributes.start_time DESC"]}')" \
  "${MLFLOW_URL}/api/2.0/mlflow/runs/search")"
mlflow_run_id="$(jq -er '.runs[0].info.run_id' <<<"${runs}")"
jq -e \
  --arg export_sha "${export_sha}" \
  --arg lakefs_commit "${lakefs_commit}" \
  --arg dvc_md5 "${dvc_md5}" '
  def tag($key): [.runs[0].data.tags[] | select(.key == $key)][0].value;
  def param($key): [.runs[0].data.params[] | select(.key == $key)][0].value;
  def metric($key): [.runs[0].data.metrics[] | select(.key == $key)][0].value;
  .runs[0].info.status == "FINISHED"
  and tag("stage") == "clean-baseline"
  and tag("source.system") == "label-studio"
  and tag("source.export_sha256") == $export_sha
  and tag("data.lakefs_commit") == $lakefs_commit
  and tag("data.dvc_md5") == $dvc_md5
  and param("records") == "12"
  and metric("training_accuracy") >= 0.90' \
  <<<"${runs}" >/dev/null
weights_sha="$(jq -er '
  [.runs[0].data.tags[] | select(.key == "model.weights_sha256")][0].value' \
  <<<"${runs}")"

curl -fsS \
  "${MLFLOW_URL}/get-artifact?run_id=${mlflow_run_id}&path=model/adapter_model.safetensors" \
  >"${workdir}/adapter_model.safetensors"
curl -fsS \
  "${MLFLOW_URL}/get-artifact?run_id=${mlflow_run_id}&path=lineage/lineage.json" \
  >"${workdir}/mlflow-lineage.json"
curl -fsS \
  "${MLFLOW_URL}/get-artifact?run_id=${mlflow_run_id}&path=lineage/annotations.json.dvc" \
  >"${workdir}/mlflow-annotations.json.dvc"
test "$(sha256sum "${workdir}/adapter_model.safetensors" | cut -d' ' -f1)" = "${weights_sha}"
cmp -s "${workdir}/lakefs-annotations.json.dvc" "${workdir}/mlflow-annotations.json.dvc"
jq -e \
  --arg export_sha "${export_sha}" \
  --arg lakefs_commit "${lakefs_commit}" \
  --arg dvc_md5 "${dvc_md5}" \
  --arg weights_sha "${weights_sha}" \
  '.export_sha256 == $export_sha
   and .lakefs_commit == $lakefs_commit
   and .dvc_md5 == $dvc_md5
   and .weights_sha256 == $weights_sha
   and .records == 12
   and .training_accuracy >= 0.90' \
  "${workdir}/mlflow-lineage.json" >/dev/null

printf 'data training lineage passed: dag_run=%s project=%s export=%s lakefs=%s dvc=%s mlflow=%s weights=%s\n' \
  "${dag_run_id}" "${project_id}" "${export_sha}" "${lakefs_commit}" \
  "${dvc_md5}" "${mlflow_run_id}" "${weights_sha}"
