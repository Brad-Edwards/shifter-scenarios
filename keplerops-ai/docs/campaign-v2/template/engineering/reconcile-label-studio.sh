#!/usr/bin/env bash

set -Eeuo pipefail

readonly LABEL_STUDIO_URL=http://10.61.40.34:8080
readonly LABEL_STUDIO_TOKEN=31a5a4b4ab3cdbaf110644eed06853b2b418daf6
readonly LABEL_STUDIO_USER=annotation.admin@keplerops.lab
readonly PROJECT_TITLE='Orion Intent Annotation Baseline'
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR
readonly RECORDS_FILE="${SCRIPT_DIR}/label-studio/orion-intents.json"

if [[ ${EUID} -ne 0 ]]; then
  printf 'reconcile-label-studio.sh must run as root\n' >&2
  exit 2
fi

for command in curl docker jq; do
  command -v "${command}" >/dev/null || {
    printf 'missing required command: %s\n' "${command}" >&2
    exit 1
  }
done

docker exec -i kep-v2-postgres \
  psql --set ON_ERROR_STOP=1 --username kepler --dbname labelstudio >/dev/null <<SQL
UPDATE jwt_auth_jwtsettings
SET legacy_api_tokens_enabled = TRUE, updated_at = NOW();
UPDATE authtoken_token
SET key = '${LABEL_STUDIO_TOKEN}'
WHERE user_id = (SELECT id FROM htx_user WHERE email = '${LABEL_STUDIO_USER}');
SQL

api() {
  local method=$1
  local path=$2
  shift 2
  curl --silent --show-error --fail-with-body \
    --request "${method}" \
    --header "Authorization: Token ${LABEL_STUDIO_TOKEN}" \
    --header 'Content-Type: application/json' \
    "$@" "${LABEL_STUDIO_URL}${path}"
}

projects="$(api GET '/api/projects?page_size=100')"
project_id="$(jq -r --arg title "${PROJECT_TITLE}" \
  '.results[] | select(.title == $title) | .id' <<<"${projects}" | head -n1)"

if [[ -z ${project_id} ]]; then
  # shellcheck disable=SC2016
  label_config='<View><Text name="text" value="$text"/><Choices name="intent" toName="text" choice="single"><Choice value="Release"/><Choice value="Safety"/><Choice value="Research"/></Choices></View>'
  payload="$(jq -cn \
    --arg title "${PROJECT_TITLE}" \
    --arg description 'Clean Project Orion intent labels for the release triage model.' \
    --arg config "${label_config}" \
    '{title:$title,description:$description,label_config:$config,is_published:true}')"
  project_id="$(api POST '/api/projects/' --data "${payload}" | jq -er '.id')"
fi

tasks="$(api GET "/api/tasks?project=${project_id}&page_size=100")"
if [[ $(jq -r '.total // (.tasks | length)' <<<"${tasks}") == 0 ]]; then
  import_payload="$(jq '[.[] | {data:{record_id:.record_id,text:.text}}]' \
    "${RECORDS_FILE}")"
  api POST "/api/projects/${project_id}/import?return_task_ids=true" \
    --data "${import_payload}" >/dev/null
  tasks="$(api GET "/api/tasks?project=${project_id}&page_size=100")"
fi

while IFS=$'\t' read -r record_id label; do
  task_id="$(jq -er --arg id "${record_id}" \
    '.tasks[] | select(.data.record_id == $id) | .id' <<<"${tasks}")"
  task="$(api GET "/api/tasks/${task_id}")"
  if [[ $(jq -r '.total_annotations // (.annotations | length)' <<<"${task}") == 0 ]]; then
    annotation="$(jq -cn --arg label "${label}" '{
      result:[{
        from_name:"intent",
        to_name:"text",
        type:"choices",
        value:{choices:[$label]}
      }]
    }')"
    api POST "/api/tasks/${task_id}/annotations/" --data "${annotation}" >/dev/null
  fi
done < <(jq -r '.[] | [.record_id,.label] | @tsv' "${RECORDS_FILE}")

exported="$(api GET "/api/projects/${project_id}/export?exportType=JSON")"
[[ $(jq 'length' <<<"${exported}") == 12 ]] || {
  printf 'expected twelve exported Label Studio tasks\n' >&2
  exit 1
}
jq -e 'all(.[]; (.annotations | length) > 0)' <<<"${exported}" >/dev/null

printf 'Label Studio baseline reconciled: project=%s tasks=12\n' "${project_id}"
