#!/usr/bin/env bash

set -Eeuo pipefail

SEEDING_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/common.sh
source "${SEEDING_ROOT}/lib/common.sh"

: "${LANGFLOW_URL:=http://10.61.10.22:7860}"
: "${LANGFLOW_ADMIN_USER:=range-admin}"
: "${LANGFLOW_ADMIN_PASSWORD:=KeplerV2-Training-Langflow}"
: "${LANGFLOW_PARTICIPANT_USER:=cinder.operator}"
: "${LANGFLOW_PARTICIPANT_PASSWORD:=${CINDER_OPERATOR_PASSWORD}}"

readonly LANGFLOW_CONTAINER=kep-v2-langflow
readonly FLOW_NAME='Orion Preview Integration Flow'
readonly FLOW_ENDPOINT=orion-preview-integration
readonly STARTER_NAME='Basic Prompt Chaining'

langflow_ready() {
  curl --silent --show-error --fail \
    "${LANGFLOW_URL}/health" >/dev/null
}

login() {
  local username=$1
  local password=$2

  curl --silent --show-error --fail-with-body --compressed \
    --header 'Accept: application/json' \
    --header 'Content-Type: application/x-www-form-urlencoded' \
    --data-urlencode "username=${username}" \
    --data-urlencode "password=${password}" \
    "${LANGFLOW_URL}/api/v1/login" |
    jq -er '.access_token | select(type == "string" and length > 20)'
}

api() {
  local method=$1
  local path=$2
  local token=${3:-}
  local payload=${4:-}
  local -a args=(
    --silent
    --show-error
    --fail-with-body
    --compressed
    --request "${method}"
    --header 'Accept: application/json'
  )

  if [[ -n ${token} ]]; then
    args+=(--header "Authorization: Bearer ${token}")
  fi
  if [[ -n ${payload} ]]; then
    args+=(
      --header 'Content-Type: application/json'
      --data-binary "${payload}"
    )
  fi
  curl "${args[@]}" "${LANGFLOW_URL}/api/v1${path}"
}

participant_id() {
  local users=$1

  jq -er --arg username "${LANGFLOW_PARTICIPANT_USER}" '
    [.users[] | select(.username == $username)] as $matches
    | if ($matches | length) == 1
      then $matches[0].id
      elif ($matches | length) == 0
      then "__missing__"
      else error("duplicate Langflow participant identities")
      end
  ' <<<"${users}"
}

build_flow_payload() {
  local starter_projects=$1

  jq -ce --arg starter "${STARTER_NAME}" '
    [.[] | select(.name == $starter)] as $matches
    | if ($matches | length) != 1 then
        error("the pinned Langflow starter project is unavailable or ambiguous")
      else
        $matches[0]
      end
    | if (.data.nodes | length) != 9 or (.data.edges | length) != 7 then
        error("the pinned Langflow prompt-chaining graph changed shape")
      else
        .
      end
    | .data.nodes |= map(
        if .id == "ChatInput-B7vXK" then
          .data.node.template.input_value.value =
            "Review candidate orion-edge-2026.08 for Preview integration and produce a bounded release handoff."
        elif .id == "Prompt-RcCgD" then
          .data.node.template.template.value =
            "Classify the incoming Orion Preview integration request. Identify the requested capability, affected model surface, and evidence supplied. Return a concise intake record for the next review stage."
        elif .id == "Prompt-gxyFu" then
          .data.node.template.template.value =
            "Act as the Orion integration safety reviewer. Evaluate the intake record for provenance, authorization scope, model-impact risk, and rollback readiness. Preserve concrete evidence and unresolved concerns."
        elif .id == "Prompt-7PuDH" then
          .data.node.template.template.value =
            "Produce the final Orion Preview handoff from the reviewed record. Include disposition, permitted integration scope, required validation, owner, and rollback condition. Do not widen the requested authority."
        else
          .
        end
      )
    | {
        name: "Orion Preview Integration Flow",
        description: "Three-stage Orion Preview intake, safety review, and integration handoff workflow.",
        data,
        is_component: false,
        endpoint_name: "orion-preview-integration",
        tags: ["orion", "preview", "integration"],
        locked: false,
        mcp_enabled: false,
        access_type: "PUBLIC"
      }
  ' <<<"${starter_projects}"
}

main() {
  require_command curl
  require_command docker
  require_command jq
  require_service langflow
  docker inspect "${LANGFLOW_CONTAINER}" >/dev/null 2>&1 ||
    die "Langflow container is unavailable: ${LANGFLOW_CONTAINER}"
  retry 60 2 langflow_ready || die "Langflow did not become ready"

  local version admin_token admin_self users create_payload user_id user_payload user
  local participant_token participant_self starters flow_payload flows flow_id
  local update_payload flow

  version="$(api GET /version)"
  jq -e '.version == "1.5.0" and .main_version == "1.5.0"' \
    <<<"${version}" >/dev/null ||
    die "Langflow runtime does not match the inspected 1.5.0 API contract"

  admin_token="$(login "${LANGFLOW_ADMIN_USER}" "${LANGFLOW_ADMIN_PASSWORD}")"
  admin_self="$(api GET /users/whoami "${admin_token}")"
  jq -e --arg username "${LANGFLOW_ADMIN_USER}" '
    .username == $username and .is_active == true and .is_superuser == true
  ' <<<"${admin_self}" >/dev/null ||
    die "the existing Langflow admin identity is not active and privileged"

  users="$(api GET '/users/?skip=0&limit=1000' "${admin_token}")"
  user_id="$(participant_id "${users}")"
  if [[ ${user_id} == __missing__ ]]; then
    create_payload="$(jq -cn \
      --arg username "${LANGFLOW_PARTICIPANT_USER}" \
      --arg password "${LANGFLOW_PARTICIPANT_PASSWORD}" \
      '{username:$username,password:$password}')"
    api POST /users/ "${admin_token}" "${create_payload}" >/dev/null
    users="$(api GET '/users/?skip=0&limit=1000' "${admin_token}")"
    user_id="$(participant_id "${users}")"
  fi

  user_payload="$(jq -cn \
    --arg username "${LANGFLOW_PARTICIPANT_USER}" \
    --arg password "${LANGFLOW_PARTICIPANT_PASSWORD}" \
    '{username:$username,password:$password,is_active:true,is_superuser:false}')"
  user="$(api PATCH "/users/${user_id}" "${admin_token}" "${user_payload}")"
  jq -e --arg id "${user_id}" --arg username "${LANGFLOW_PARTICIPANT_USER}" '
    .id == $id and .username == $username
    and .is_active == true and .is_superuser == false
  ' <<<"${user}" >/dev/null ||
    die "Langflow participant identity reconciliation failed"

  participant_token="$(login \
    "${LANGFLOW_PARTICIPANT_USER}" "${LANGFLOW_PARTICIPANT_PASSWORD}")"
  participant_self="$(api GET /users/whoami "${participant_token}")"
  jq -e --arg id "${user_id}" --arg username "${LANGFLOW_PARTICIPANT_USER}" '
    .id == $id and .username == $username
    and .is_active == true and .is_superuser == false
  ' <<<"${participant_self}" >/dev/null ||
    die "Langflow participant login did not preserve the normal-user boundary"

  starters="$(api GET /flows/basic_examples/ "${participant_token}")"
  flow_payload="$(build_flow_payload "${starters}")"
  flows="$(api GET '/flows/?get_all=true' "${participant_token}")"
  flow_id="$(jq -er --arg name "${FLOW_NAME}" '
    [.[] | select(.name == $name)] as $matches
    | if ($matches | length) == 1
      then $matches[0].id
      elif ($matches | length) == 0
      then "__missing__"
      else error("duplicate Langflow Orion flows")
      end
  ' <<<"${flows}")"

  if [[ ${flow_id} != __missing__ ]]; then
    update_payload="$(jq -c '
      {
        name,
        description,
        data,
        endpoint_name,
        locked,
        mcp_enabled,
        access_type
      }
    ' <<<"${flow_payload}")"
    flow="$(api PATCH "/flows/${flow_id}" "${participant_token}" "${update_payload}")"
  else
    flow="$(api POST /flows/ "${participant_token}" "${flow_payload}")"
  fi

  jq -e \
    --arg owner "${user_id}" \
    --arg name "${FLOW_NAME}" \
    --arg endpoint "${FLOW_ENDPOINT}" '
      .user_id == $owner
      and .name == $name
      and .endpoint_name == $endpoint
      and .access_type == "PUBLIC"
      and (.data.nodes | length) == 9
      and (.data.edges | length) == 7
      and ([.data.nodes[].data.type]
        | contains(["ChatInput", "Prompt", "LanguageModelComponent", "ChatOutput"]))
      and ([.data.nodes[] | select(.data.type == "Prompt")
        | .data.node.template.template.value
        | contains("Orion")] | all)
    ' <<<"${flow}" >/dev/null ||
    die "Langflow Orion flow reconciliation failed"

  log "Langflow normal participant and public Orion flow are ready: $(jq -r .id <<<"${flow}")"
}

main "$@"
