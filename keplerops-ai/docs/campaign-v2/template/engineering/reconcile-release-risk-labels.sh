#!/usr/bin/env bash

set -Eeuo pipefail

readonly LABEL_STUDIO_URL=http://10.61.40.34:8080
readonly LABEL_STUDIO_TOKEN=31a5a4b4ab3cdbaf110644eed06853b2b418daf6
readonly PROJECT_TITLE='Orion Release Risk Training Baseline'
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR
readonly RECORDS_FILE="${SCRIPT_DIR}/label-studio/orion-release-risk-training.json"

if [[ ${EUID} -ne 0 ]]; then
  printf 'reconcile-release-risk-labels.sh must run as root\n' >&2
  exit 2
fi

for command in curl jq; do
  command -v "${command}" >/dev/null || {
    printf 'missing required command: %s\n' "${command}" >&2
    exit 1
  }
done

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
  label_config='<View><Text name="text" value="$text"/><Choices name="risk" toName="text" choice="single"><Choice value="ReleaseApprove"/><Choice value="ReleaseHold"/><Choice value="PartnerIntake"/><Choice value="EntitlementReview"/><Choice value="SecurityAdvisory"/><Choice value="SupportEscalation"/><Choice value="ResearchReview"/><Choice value="PrivacySafety"/></Choices></View>'
  payload="$(jq -cn \
    --arg title "${PROJECT_TITLE}" \
    --arg description 'Clean eight-class corpus for the Orion release-risk model.' \
    --arg config "${label_config}" \
    '{title:$title,description:$description,label_config:$config,is_published:true}')"
  project_id="$(api POST '/api/projects/' --data "${payload}" | jq -er '.id')"
fi

tasks="$(api GET "/api/tasks?project=${project_id}&page_size=100")"
task_count="$(jq -r '.total // (.tasks | length)' <<<"${tasks}")"
if [[ ${task_count} == 0 ]]; then
  import_payload="$(jq '[.[] | {data:{record_id:.record_id,text:.text}}]' \
    "${RECORDS_FILE}")"
  api POST "/api/projects/${project_id}/import?return_task_ids=true" \
    --data "${import_payload}" >/dev/null
  tasks="$(api GET "/api/tasks?project=${project_id}&page_size=100")"
elif [[ ${task_count} != 48 ]]; then
  printf 'existing release-risk project has %s tasks, expected 48\n' "${task_count}" >&2
  exit 3
fi

while IFS=$'\t' read -r record_id label; do
  task_id="$(jq -er --arg id "${record_id}" \
    '.tasks[] | select(.data.record_id == $id) | .id' <<<"${tasks}")"
  task="$(api GET "/api/tasks/${task_id}")"
  if [[ $(jq -r '.total_annotations // (.annotations | length)' <<<"${task}") == 0 ]]; then
    annotation="$(jq -cn --arg label "${label}" '{
      result:[{
        from_name:"risk",
        to_name:"text",
        type:"choices",
        value:{choices:[$label]}
      }]
    }')"
    api POST "/api/tasks/${task_id}/annotations/" --data "${annotation}" >/dev/null
  fi
done < <(jq -r '.[] | [.record_id,.label] | @tsv' "${RECORDS_FILE}")

exported="$(api GET "/api/projects/${project_id}/export?exportType=JSON")"
[[ $(jq 'length' <<<"${exported}") == 48 ]] || {
  printf 'expected 48 exported Label Studio tasks\n' >&2
  exit 1
}
jq -e 'all(.[]; (.annotations | length) > 0)' <<<"${exported}" >/dev/null

printf 'Label Studio release-risk baseline reconciled: project=%s tasks=48\n' "${project_id}"
