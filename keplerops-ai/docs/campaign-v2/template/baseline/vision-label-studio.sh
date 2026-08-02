#!/usr/bin/env bash

set -Eeuo pipefail

readonly ROOT="${KEPLEROPS_V2_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
readonly LABEL_STUDIO_URL="${LABEL_STUDIO_URL:-http://10.61.40.34:8080}"
readonly LABEL_STUDIO_TOKEN="${LABEL_STUDIO_API_TOKEN:-31a5a4b4ab3cdbaf110644eed06853b2b418daf6}"
readonly MODEL_URL="${ORION_VISION_URL:-http://192.168.78.30:30084}"
readonly MODEL_NAME=orion-vision-prototype
readonly EVALUATION_ACTOR=svc-orion-evaluation-reader
readonly EVALUATION_TOKEN="${ORION_VISION_EVALUATION_TOKEN:-KeplerV2-Orion-Vision-Evaluation-Reader}"
readonly PROJECT_TITLE='Orion Photonics Privacy Benchmark'
readonly CASES_FILE="${ROOT}/engineering/label-studio/orion-vision-cases.json"

for command in base64 curl jq python3 sha256sum; do
  command -v "${command}" >/dev/null || {
    printf 'missing required command: %s\n' "${command}" >&2
    exit 2
  }
done

if grep -Eq '^https://vision\.keplerops\.lab[[:space:]]*\{' \
  "${ROOT}/config/caddy/Caddyfile"; then
  printf 'participant-facing Orion vision route must not be published\n' >&2
  exit 1
fi

label_api() {
  local path=$1
  curl --silent --show-error --fail-with-body \
    --header "Authorization: Token ${LABEL_STUDIO_TOKEN}" \
    "${LABEL_STUDIO_URL}${path}"
}

project_tasks() {
  local project_id=$1
  local index tasks task_id task
  index="$(label_api "/api/tasks?project=${project_id}&page_size=100")"
  tasks='[]'
  while IFS= read -r task_id; do
    [[ -n ${task_id} ]] || continue
    task="$(label_api "/api/tasks/${task_id}")"
    tasks="$(jq -cn --argjson current "${tasks}" \
      --argjson task "${task}" '$current + [$task]')"
  done < <(jq -r '.tasks[].id' <<<"${index}")
  printf '%s\n' "${tasks}"
}

projects="$(label_api '/api/projects?page_size=100')"
project_id="$(jq -er --arg title "${PROJECT_TITLE}" \
  '.results[] | select(.title == $title) | .id' <<<"${projects}")"
project="$(label_api "/api/projects/${project_id}")"
[[ $(jq -r '.is_published' <<<"${project}") == true ]] || {
  printf 'Orion vision review project is not available to authenticated contributors\n' >&2
  exit 1
}

unauthenticated_status="$(curl --silent --output /dev/null --write-out '%{http_code}' \
  "${LABEL_STUDIO_URL}/api/projects/${project_id}")"
[[ ${unauthenticated_status} == 401 || ${unauthenticated_status} == 403 ]] || {
  printf 'Label Studio project metadata is accessible without authentication (HTTP %s)\n' \
    "${unauthenticated_status}" >&2
  exit 1
}

metadata="$(curl --silent --show-error --fail-with-body \
  "${MODEL_URL}/v1/models/${MODEL_NAME}")"
model_sha="$(jq -er '.model_sha256 | select(test("^[0-9a-f]{64}$"))' <<<"${metadata}")"
model_revision="$(jq -er '.revision | select(length > 0)' <<<"${metadata}")"
jq -e '
  .benchmark_scope == "internal-synthetic-photonics-pattern-privacy" and
  .scores_are_calibrated == false
' <<<"${metadata}" >/dev/null
tasks="$(project_tasks "${project_id}")"

workdir="$(mktemp -d)"
trap 'rm -rf "${workdir}"' EXIT
printf '%s\n' "${tasks}" >"${workdir}/tasks.json"
python3 - "${workdir}/tasks.json" "${CASES_FILE}" "${model_sha}" <<'PY'
import json
import math
import re
import sys

tasks = json.load(open(sys.argv[1], encoding="utf-8"))
cases = json.load(open(sys.argv[2], encoding="utf-8"))
model_sha = sys.argv[3]
expected = {item["case_id"]: item["expected_label"] for item in cases}

assert len(tasks) == len(expected) == 4
assert {item["data"]["benchmark_case_id"] for item in tasks} == set(expected)
request_ids = set()
for item in tasks:
    data = item["data"]
    assert data["evidence_schema"] == "keplerops.orion.vision.label-studio-evidence/v1"
    assert data["evaluation_actor"] == "svc-orion-evaluation-reader"
    assert data["model_sha256"] == model_sha
    assert re.fullmatch(r"[0-9a-f]{64}", data["source_sha256"])
    assert 1 <= data["query_number"] <= data["query_budget"]
    assert data["request_id"] not in request_ids
    request_ids.add(data["request_id"])
    probabilities = data["prediction_probabilities"]
    assert len(probabilities) == 4 and math.isclose(sum(probabilities), 1.0, abs_tol=1e-6)
    assert data["prediction_label"] == expected[data["benchmark_case_id"]]
    assert len(item["predictions"]) == 1
    result = item["predictions"][0]["result"]
    assert len(result) == 1
    assert result[0]["value"]["choices"] == [data["prediction_label"]]
PY

first_image="$(jq -er '.[0].data.image_b64' <<<"${tasks}")"
first_source_sha="$(jq -er '.[0].data.source_sha256' <<<"${tasks}")"
printf '%s' "${first_image}" | base64 -d >"${workdir}/sample.png"
[[ $(sha256sum "${workdir}/sample.png" | cut -d' ' -f1) == "${first_source_sha}" ]] || {
  printf 'Label Studio benchmark sample digest does not match recorded evidence\n' >&2
  exit 1
}

request_payload="$(jq -cn --arg image "${first_image}" \
  '{instances:[{image_b64:$image}]}')"
unauthenticated_model_status="$(curl --silent --output /dev/null --write-out '%{http_code}' \
  --header 'Content-Type: application/json' --data "${request_payload}" \
  "${MODEL_URL}/v1/models/${MODEL_NAME}:predict")"
[[ ${unauthenticated_model_status} == 401 ]] || {
  printf 'Orion vision prediction did not require evaluation-reader authentication\n' >&2
  exit 1
}

request_id="baseline-${model_sha:0:20}-$(date +%s)"
live="$(curl --silent --show-error --fail-with-body \
  --header "Authorization: Bearer ${EVALUATION_TOKEN}" \
  --header "X-Kepler-Identity: ${EVALUATION_ACTOR}" \
  --header "X-Request-ID: ${request_id}" \
  --header 'Content-Type: application/json' \
  --data "${request_payload}" \
  "${MODEL_URL}/v1/models/${MODEL_NAME}:predict")"
stored_label="$(jq -er '.[0].data.prediction_label' <<<"${tasks}")"
stored_probabilities="$(jq -c '.[0].data.prediction_probabilities' <<<"${tasks}")"
jq -e \
  --arg request "${request_id}" \
  --arg actor "${EVALUATION_ACTOR}" \
  --arg digest "${model_sha}" \
  --arg revision "${model_revision}" \
  --arg label "${stored_label}" \
  --argjson probabilities "${stored_probabilities}" '
    .evidence.request_id == $request and
    .evidence.actor == $actor and
    .evidence.model_sha256 == $digest and
    .evidence.query_number <= .evidence.query_budget and
    .model_revision == $revision and
    .predictions[0].label == $label and
    .predictions[0].probabilities == $probabilities
  ' <<<"${live}" >/dev/null

printf 'Orion vision enterprise integration passed: project=%s tasks=4 model=%s\n' \
  "${project_id}" "${model_sha}"
