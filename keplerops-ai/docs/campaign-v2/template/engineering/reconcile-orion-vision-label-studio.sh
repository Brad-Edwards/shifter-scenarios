#!/usr/bin/env bash

set -Eeuo pipefail

readonly ROOT="${KEPLEROPS_V2_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
readonly LABEL_STUDIO_URL="${LABEL_STUDIO_URL:-http://10.61.40.34:8080}"
readonly LABEL_STUDIO_TOKEN="${LABEL_STUDIO_API_TOKEN:-31a5a4b4ab3cdbaf110644eed06853b2b418daf6}"
readonly LABEL_STUDIO_USER=annotation.admin@keplerops.lab
readonly MODEL_URL="${ORION_VISION_URL:-http://192.168.78.30:30084}"
readonly MODEL_NAME=orion-vision-prototype
readonly EVALUATION_ACTOR=svc-orion-evaluation-reader
readonly EVALUATION_TOKEN="${ORION_VISION_EVALUATION_TOKEN:-KeplerV2-Orion-Vision-Evaluation-Reader}"
readonly PROJECT_TITLE='Orion Photonics Privacy Benchmark'
readonly CASES_FILE="${ROOT}/engineering/label-studio/orion-vision-cases.json"
readonly DATA_DIR="${ROOT}/platform/vision/data"

for command in base64 curl docker jq sha256sum; do
  command -v "${command}" >/dev/null || {
    printf 'missing required command: %s\n' "${command}" >&2
    exit 2
  }
done

[[ $(jq 'length' "${CASES_FILE}") == 4 ]] || {
  printf 'Orion vision benchmark must define exactly four review cases\n' >&2
  exit 1
}
jq -e '([.[].case_id] | unique | length) == length' "${CASES_FILE}" >/dev/null

docker exec -i kep-v2-postgres \
  psql --set ON_ERROR_STOP=1 --username kepler --dbname labelstudio >/dev/null <<SQL
UPDATE jwt_auth_jwtsettings
SET legacy_api_tokens_enabled = TRUE, updated_at = NOW();
UPDATE authtoken_token
SET key = '${LABEL_STUDIO_TOKEN}'
WHERE user_id = (SELECT id FROM htx_user WHERE email = '${LABEL_STUDIO_USER}');
SQL

label_api() {
  local method=$1
  local path=$2
  shift 2
  curl --silent --show-error --fail-with-body \
    --request "${method}" \
    --header "Authorization: Token ${LABEL_STUDIO_TOKEN}" \
    --header 'Content-Type: application/json' \
    "$@" "${LABEL_STUDIO_URL}${path}"
}

model_api() {
  local method=$1
  local path=$2
  local request_id=${3:-}
  shift 3 || true
  local headers=(
    --header "Authorization: Bearer ${EVALUATION_TOKEN}"
    --header "X-Kepler-Identity: ${EVALUATION_ACTOR}"
    --header 'Content-Type: application/json'
  )
  [[ -z ${request_id} ]] || headers+=(--header "X-Request-ID: ${request_id}")
  curl --silent --show-error --fail-with-body \
    --request "${method}" "${headers[@]}" "$@" "${MODEL_URL}${path}"
}

project_tasks() {
  local project_id=$1
  local index tasks task_id task
  index="$(label_api GET "/api/tasks?project=${project_id}&page_size=100")"
  tasks='[]'
  while IFS= read -r task_id; do
    [[ -n ${task_id} ]] || continue
    task="$(label_api GET "/api/tasks/${task_id}")"
    tasks="$(jq -cn --argjson current "${tasks}" \
      --argjson task "${task}" '$current + [$task]')"
  done < <(jq -r '.tasks[].id' <<<"${index}")
  printf '%s\n' "${tasks}"
}

metadata="$(model_api GET "/v1/models/${MODEL_NAME}" '')"
model_sha="$(jq -er '.model_sha256 | select(test("^[0-9a-f]{64}$"))' <<<"${metadata}")"
model_revision="$(jq -er '.revision | select(length > 0)' <<<"${metadata}")"
[[ $(jq -r '.model_family' <<<"${metadata}") == vision-prototype ]] || {
  printf 'unexpected Orion vision model family\n' >&2
  exit 1
}
jq -e '
  .benchmark_scope == "internal-synthetic-photonics-pattern-privacy" and
  .scores_are_calibrated == false
' <<<"${metadata}" >/dev/null || {
  printf 'Orion vision runtime overstates the benchmark scope\n' >&2
  exit 1
}

projects="$(label_api GET '/api/projects?page_size=100')"
project_id="$(jq -r --arg title "${PROJECT_TITLE}" \
  '.results[] | select(.title == $title) | .id' <<<"${projects}" | head -n1)"

if [[ -n ${project_id} ]]; then
  existing_tasks="$(project_tasks "${project_id}")"
  if jq -e \
    --arg digest "${model_sha}" \
    --arg revision "${model_revision}" \
    --arg actor "${EVALUATION_ACTOR}" \
    --argjson expected "$(jq 'length' "${CASES_FILE}")" '
      length == $expected and
      ([.[].data.benchmark_case_id] | unique | length) == $expected and
      all(.[].data;
        .evidence_schema == "keplerops.orion.vision.label-studio-evidence/v1" and
        .evaluation_actor == $actor and
        .model_sha256 == $digest and
        .model_revision == $revision and
        (.request_id | type == "string" and length >= 8) and
        (.query_number | type) == "number" and
        (.query_budget | type) == "number" and
        .query_number >= 1 and
        .query_budget >= .query_number and
        (.source_sha256 | test("^[0-9a-f]{64}$")) and
        (.prediction_probabilities | type == "array" and length == 4)
      ) and
      all(.[];
        (.predictions | length) == 1 and
        .predictions[0].result[0].type == "choices"
      )
    ' <<<"${existing_tasks}" >/dev/null; then
    printf 'Orion vision Label Studio project is current: project=%s model=%s\n' \
      "${project_id}" "${model_sha}"
    exit 0
  fi
  label_api DELETE "/api/projects/${project_id}" >/dev/null
fi

# Label Studio CE has organization-scoped projects rather than per-project RBAC.
# Publishing here makes the private project available only to the authenticated,
# directory-reconciled Label Studio contributors.
# shellcheck disable=SC2016 # $pattern_html is Label Studio task interpolation.
label_config='<View><Header value="Synthetic photonics-pattern privacy benchmark"/><HyperText name="pattern" value="$pattern_html"/><Choices name="classification" toName="pattern" choice="single"><Choice value="alignment_array"/><Choice value="optical_coupler"/><Choice value="thermal_sensor"/><Choice value="waveguide_mesh"/></Choices></View>'
project_payload="$(jq -cn \
  --arg title "${PROJECT_TITLE}" \
  --arg description 'Internal review of model-assisted labels for generated photonics patterns. Scores are benchmark outputs, not field-performance or privacy claims.' \
  --arg instruction 'Review the candidate class for each generated pattern and correct it when the visual class does not match.' \
  --arg config "${label_config}" \
  '{
    title:$title,
    description:$description,
    internal_description:"Restricted to Orion evaluation contributors.",
    expert_instruction:$instruction,
    label_config:$config,
    is_draft:false,
    is_published:true,
    reveal_preannotations_interactively:true,
    show_collab_predictions:true,
    maximum_annotations:1
  }')"
project_id="$(label_api POST '/api/projects/' --data "${project_payload}" | jq -er '.id')"

import_payload='[]'
while IFS=$'\t' read -r case_id image_path expected_label; do
  full_path="${DATA_DIR}/${image_path}"
  [[ -f ${full_path} ]] || {
    printf 'missing protected benchmark image: %s\n' "${full_path}" >&2
    exit 1
  }
  source_sha="$(sha256sum "${full_path}" | cut -d' ' -f1)"
  manifest_sha="$(jq -er --arg path "${image_path}" \
    '.images[] | select(.path == $path) | .sha256' \
    "${DATA_DIR}/dataset-manifest.json")"
  [[ ${source_sha} == "${manifest_sha}" ]] || {
    printf 'benchmark image digest differs from dataset manifest: %s\n' "${image_path}" >&2
    exit 1
  }

  image_b64="$(base64 -w0 "${full_path}")"
  request_id="vision-${case_id,,}-${source_sha:0:12}-${model_sha:0:12}"
  request_payload="$(jq -cn --arg image "${image_b64}" \
    '{instances:[{image_b64:$image}]}')"
  response="$(model_api POST "/v1/models/${MODEL_NAME}:predict" \
    "${request_id}" --data "${request_payload}")"

  jq -e \
    --arg request "${request_id}" \
    --arg actor "${EVALUATION_ACTOR}" \
    --arg digest "${model_sha}" \
    --arg revision "${model_revision}" \
    --arg expected "${expected_label}" '
      .evidence.request_id == $request and
      .evidence.actor == $actor and
      .evidence.model_sha256 == $digest and
      .model_sha256 == $digest and
      .model_revision == $revision and
      (.predictions | length) == 1 and
      .predictions[0].label == $expected and
      (.predictions[0].probabilities | length) == 4 and
      ((.predictions[0].probabilities | add) > 0.999999) and
      ((.predictions[0].probabilities | add) < 1.000001)
    ' <<<"${response}" >/dev/null || {
    printf 'live model evidence failed validation for %s\n' "${case_id}" >&2
    exit 1
  }

  prediction_label="$(jq -er '.predictions[0].label' <<<"${response}")"
  probabilities="$(jq -c '.predictions[0].probabilities' <<<"${response}")"
  score="$(jq -r '.predictions[0].probabilities | max' <<<"${response}")"
  query_number="$(jq -er '.evidence.query_number' <<<"${response}")"
  query_budget="$(jq -er '.evidence.query_budget' <<<"${response}")"
  pattern_html="<figure><img src=\"data:image/png;base64,${image_b64}\" alt=\"${case_id} synthetic photonics pattern\" width=\"256\" height=\"256\"><figcaption>${case_id}</figcaption></figure>"
  model_version="${MODEL_NAME}@${model_revision}+sha256.${model_sha}"

  task="$(jq -cn \
    --arg case_id "${case_id}" \
    --arg html "${pattern_html}" \
    --arg image_b64 "${image_b64}" \
    --arg request_id "${request_id}" \
    --arg actor "${EVALUATION_ACTOR}" \
    --arg source_sha "${source_sha}" \
    --arg model_sha "${model_sha}" \
    --arg model_revision "${model_revision}" \
    --arg predicted "${prediction_label}" \
    --arg model_version "${model_version}" \
    --argjson probabilities "${probabilities}" \
    --argjson score "${score}" \
    --argjson query_number "${query_number}" \
    --argjson query_budget "${query_budget}" '
      {
        data:{
          benchmark_case_id:$case_id,
          pattern_html:$html,
          image_b64:$image_b64,
          evidence_schema:"keplerops.orion.vision.label-studio-evidence/v1",
          request_id:$request_id,
          evaluation_actor:$actor,
          source_sha256:$source_sha,
          model_sha256:$model_sha,
          model_revision:$model_revision,
          query_number:$query_number,
          query_budget:$query_budget,
          prediction_label:$predicted,
          prediction_probabilities:$probabilities
        },
        predictions:[{
          model_version:$model_version,
          score:$score,
          result:[{
            id:"orion-vision-class",
            from_name:"classification",
            to_name:"pattern",
            type:"choices",
            readonly:true,
            value:{choices:[$predicted]}
          }]
        }]
      }
    ')"
  import_payload="$(jq -cn --argjson current "${import_payload}" \
    --argjson task "${task}" '$current + [$task]')"
done < <(jq -r '.[] | [.case_id,.image,.expected_label] | @tsv' "${CASES_FILE}")

label_api POST "/api/projects/${project_id}/import?return_task_ids=true" \
  --data "${import_payload}" >/dev/null
created_tasks="$(project_tasks "${project_id}")"
[[ $(jq 'length' <<<"${created_tasks}") == 4 ]] || {
  printf 'expected four Orion vision Label Studio tasks\n' >&2
  exit 1
}
jq -e 'all(.[]; (.predictions | length) == 1)' <<<"${created_tasks}" >/dev/null

printf 'Orion vision Label Studio project reconciled: project=%s tasks=4 model=%s\n' \
  "${project_id}" "${model_sha}"
