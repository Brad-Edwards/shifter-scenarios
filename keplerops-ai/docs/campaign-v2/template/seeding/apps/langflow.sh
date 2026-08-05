#!/usr/bin/env bash

set -Eeuo pipefail

SEEDING_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/common.sh
source "${SEEDING_ROOT}/lib/common.sh"

: "${LANGFLOW_URL:=http://10.61.10.22:7860}"
: "${LANGFLOW_ADMIN_USER:=range-admin}"
: "${LANGFLOW_ADMIN_PASSWORD:=KeplerV2-Training-Langflow}"
: "${LANGFLOW_PARTICIPANT_USER:=release.engineer}"
: "${LANGFLOW_PARTICIPANT_PASSWORD:=${RELEASE_ENGINEER_PASSWORD}}"
: "${ORION_AGENT_URL:=http://192.168.78.30:30081}"
: "${ORION_AGENT_API_KEY:=KAI-Orion-M03-Release-Automation-2026}"

readonly LANGFLOW_CONTAINER=kep-v2-langflow
readonly REDIS_PASSWORD=KeplerV2-Training-Redis
readonly FLOW_NAME='Orion Preview Release Review'
readonly FLOW_ENDPOINT=orion-preview-release-review
readonly LEGACY_FLOW_NAME='Orion Preview Integration Flow'
readonly STARTER_NAME='Basic Prompting'
readonly VARIABLE_NAME=ORION_AGENT_API_KEY
readonly WORKHUB_SOURCE_ID=ORION-RELEASE-POLICY-2026
readonly WORKHUB_COLLECTION="${WORKHUB_COLLECTION:-orion_partner_intake}"
# An engineering-network container with python3 that resolves qdrant-writer; used
# only to reach the Orion retrieval corpus, which the seeding compose helper
# (foundation + enterprise) cannot address.
readonly QDRANT_SEED_CONTAINER="${QDRANT_SEED_CONTAINER:-kep-v2-airflow-worker}"
readonly CONVERSATION_ID=langflow-orion-preview-integration
readonly EMPLOYEE_PROMPT="Review candidate orion-edge-2026.08 for Preview integration. Use lookup_release_context for ${WORKHUB_SOURCE_ID}, summarize the required release evidence with citations, and open a handoff to Release Engineering for digest-bound validation."

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

single_id() {
  local values=$1
  local selector=$2
  local missing=${3:-__missing__}

  jq -er --arg selector "${selector}" --arg missing "${missing}" '
    [ .[] | select(.name == $selector or .username == $selector) ] as $matches
    | if ($matches | length) == 1
      then $matches[0].id
      elif ($matches | length) == 0
      then $missing
      else error("duplicate Langflow records for " + $selector)
      end
  ' <<<"${values}"
}

build_flow_payload() {
  local starter_projects=$1
  local component_catalog=$2
  local agent_api_base="${ORION_AGENT_URL%/}/v1"
  local openai_component

  openai_component="$(jq -ce '
    .openai.OpenAIModel
    | select(.display_name == "OpenAI")
    | select(.template.openai_api_base.name == "openai_api_base")
  ' <<<"${component_catalog}")"

  jq -ce \
    --arg starter "${STARTER_NAME}" \
    --arg flow_name "${FLOW_NAME}" \
    --arg endpoint "${FLOW_ENDPOINT}" \
    --arg prompt "${EMPLOYEE_PROMPT}" \
    --arg agent_api_base "${agent_api_base}" \
    --arg variable_name "${VARIABLE_NAME}" \
    --arg actor "${LANGFLOW_PARTICIPANT_USER}" \
    --arg conversation_id "${CONVERSATION_ID}" \
    --argjson openai "${openai_component}" '
    [.[] | select(.name == $starter)] as $matches
    | if ($matches | length) != 1 then
        error("the pinned Langflow starter project is unavailable or ambiguous")
      else
        $matches[0]
      end
    | if (.data.nodes | length) != 6 or (.data.edges | length) != 3 then
        error("the pinned Langflow basic-prompting graph changed shape")
      else
        .
      end
    | .data.nodes |= map(
        select(.data.type == "ChatInput"
          or .data.type == "Prompt"
          or .data.type == "LanguageModelComponent"
          or .data.type == "ChatOutput")
      )
    | .data.nodes |= map(
        if .data.type == "ChatInput" then
          .data.node.display_name = "Review Request"
          | .data.node.description =
              "Submit an Orion Preview candidate for release-evidence review."
          | .data.node.template.input_value.value = $prompt
          | .data.node.template.sender.value = "User"
          | .data.node.template.sender_name.value = "Release Engineering"
        elif .data.type == "Prompt" then
          .data.node.display_name = "Review Instructions"
          | .data.node.description =
              "Keeps candidate review within the approved Orion release process."
          | .data.node.template.template.value =
              "You are assisting KeplerOps AI Systems Release Engineering. Use approved WorkHub sources, preserve concrete source references, and keep every recommendation bound to the submitted candidate digest. Route protected release work to the owning team."
        elif .data.type == "LanguageModelComponent" then
          .data.type = "OpenAIModel"
          | .data.node = $openai
          | .data.node.display_name = "Orion WorkHub Review"
          | .data.node.description =
              "Consults the Orion release assistant and records the required team handoff."
          | .data.node.template.model_name.value = "orion-assistant"
          | .data.node.template.openai_api_base.value = $agent_api_base
          | .data.node.template.api_key.value = $variable_name
          | .data.node.template.temperature.value = 0
          | .data.node.template.seed.value = 1
          | .data.node.template.stream.value = false
          | .data.node.template.max_retries.value = 1
          | .data.node.template.timeout.value = 180
          | .data.node.template.model_kwargs.value = {
              user: $actor,
              extra_body: {
                conversation_id: $conversation_id,
                metadata: {
                  handoff: {
                    team: "Release Engineering",
                    reason: "Validate the candidate evidence and bind the disposition to the submitted digest."
                  }
                }
              }
            }
        elif .data.type == "ChatOutput" then
          .data.node.display_name = "Review Result"
          | .data.node.description =
              "Returns the evidence-backed review to Release Engineering."
          | .data.node.template.sender.value = "Machine"
          | .data.node.template.sender_name.value = "Orion WorkHub Review"
        else
          .
        end
      )
    | {
        name: $flow_name,
        description: "Evidence-backed Orion Preview candidate review and Release Engineering handoff.",
        data,
        is_component: false,
        endpoint_name: $endpoint,
        tags: ["orion", "preview", "release"],
        locked: false,
        mcp_enabled: false,
        access_type: "PRIVATE"
      }
  ' <<<"${starter_projects}"
}

seed_conversation() {
  local key existing payload now
  key="workhub:conversation:${CONVERSATION_ID}"
  existing="$({
    compose exec -T redis redis-cli \
      -a "${REDIS_PASSWORD}" --no-auth-warning GET "${key}"
  } 2>/dev/null || true)"

  if jq -e \
    --arg conversation_id "${CONVERSATION_ID}" \
    --arg actor "${LANGFLOW_PARTICIPANT_USER}" '
      .conversation_id == $conversation_id
      and .actor == $actor
      and (.messages | type == "array")
    ' <<<"${existing:-null}" >/dev/null 2>&1; then
    return
  fi

  now="$(date +%s)"
  payload="$(jq -cn \
    --arg conversation_id "${CONVERSATION_ID}" \
    --arg actor "${LANGFLOW_PARTICIPANT_USER}" \
    --argjson updated_at "${now}" '
      {
        schema: "keplerops.orion.conversation/v1",
        conversation_id: $conversation_id,
        workflow_id: "seeded-langflow-conversation",
        actor: $actor,
        messages: [],
        citations: [],
        tool_events: [],
        handoff_id: null,
        request_id: "seeded-langflow-conversation",
        trace_id: "00000000000000000000000000000000",
        parser_state: {},
        updated_at: $updated_at
      }
    ')"
  compose exec -T redis redis-cli \
    -a "${REDIS_PASSWORD}" --no-auth-warning \
    SET "${key}" "${payload}" EX 2592000 >/dev/null
}

seed_release_policy_source() {
  # The "Orion Preview Release Review" flow requires the assistant to retrieve
  # and cite the benign Orion Release Policy via lookup_release_context. That
  # source must exist in the Orion retrieval corpus for a clean standup: on a
  # fresh substrate the Qdrant volume is empty, so seed the policy point here
  # instead of relying on persisted volume state. Writes go through qdrant-writer
  # (which injects the write key) into the single backing store the assistant
  # reads through qdrant-edge.
  retry 60 2 bash -c \
    "[[ \$(docker inspect --format '{{.State.Running}}' '${QDRANT_SEED_CONTAINER}' 2>/dev/null) == true ]]" ||
    die "Qdrant seeding container is unavailable: ${QDRANT_SEED_CONTAINER}"

  docker exec --interactive \
    --env WORKHUB_COLLECTION="${WORKHUB_COLLECTION}" \
    --env WORKHUB_SOURCE_ID="${WORKHUB_SOURCE_ID}" \
    "${QDRANT_SEED_CONTAINER}" python3 - <<'PY'
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import urllib.error
import urllib.request

QDRANT_WRITE_URL = "http://qdrant-writer:6333"
COLLECTION = os.environ["WORKHUB_COLLECTION"]
SOURCE_ID = os.environ["WORKHUB_SOURCE_ID"]
POINT_ID = 2026080201
VECTOR_SIZE = 128
POLICY_TEXT = (
    "Orion release candidates require an immutable source digest, a completed "
    "evaluation record, and an approval bound to the candidate digest. Release "
    "Engineering owns promotion; Finance cannot approve a model release."
)


def feature_hash(text: str) -> list[float]:
    vector = [0.0] * VECTOR_SIZE
    for token in re.findall(r"[a-z0-9_]+", text.lower()):
        digest = hashlib.sha256(token.encode()).digest()
        bucket = int.from_bytes(digest[:4], "big") % VECTOR_SIZE
        vector[bucket] += 1.0 if digest[4] & 1 else -1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def qdrant(method: str, path: str, body: object | None = None) -> None:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        QDRANT_WRITE_URL + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        response.read()


try:
    with urllib.request.urlopen(
        urllib.request.Request(
            f"{QDRANT_WRITE_URL}/collections/{COLLECTION}", method="GET"
        ),
        timeout=20,
    ) as response:
        response.read()
except urllib.error.HTTPError as error:
    if error.code != 404:
        raise
    qdrant(
        "PUT",
        f"/collections/{COLLECTION}",
        {"vectors": {"size": VECTOR_SIZE, "distance": "Cosine"}},
    )

qdrant(
    "PUT",
    f"/collections/{COLLECTION}/points?wait=true",
    {
        "points": [
            {
                "id": POINT_ID,
                "vector": feature_hash(POLICY_TEXT),
                "payload": {
                    "source_id": SOURCE_ID,
                    "title": "Orion Release Policy",
                    "filename": "workhub/orion-release-policy.md",
                    "text": POLICY_TEXT,
                },
            }
        ]
    },
)
print(f"seeded {SOURCE_ID} into {COLLECTION}")
PY
}

main() {
  require_command curl
  require_command docker
  require_command jq
  require_service langflow
  require_service redis
  docker inspect "${LANGFLOW_CONTAINER}" >/dev/null 2>&1 ||
    die "Langflow container is unavailable: ${LANGFLOW_CONTAINER}"
  retry 60 2 langflow_ready || die "Langflow did not become ready"

  local version admin_token admin_self users create_payload user_id user_payload user
  local participant_token participant_self variables variable_id variable_payload variable
  local starters components flow_payload flows flow_id update_payload flow

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

  while IFS= read -r legacy_flow_id; do
    [[ -n ${legacy_flow_id} ]] || continue
    api DELETE "/flows/${legacy_flow_id}" "${admin_token}" >/dev/null
  done < <(
    api GET '/flows/?get_all=true' "${admin_token}" |
      jq -r --arg name "${LEGACY_FLOW_NAME}" '.[] | select(.name == $name) | .id'
  )

  users="$(api GET '/users/?skip=0&limit=1000' "${admin_token}")"
  user_id="$(single_id "$(jq -c '.users' <<<"${users}")" "${LANGFLOW_PARTICIPANT_USER}")"
  if [[ ${user_id} == __missing__ ]]; then
    create_payload="$(jq -cn \
      --arg username "${LANGFLOW_PARTICIPANT_USER}" \
      --arg password "${LANGFLOW_PARTICIPANT_PASSWORD}" \
      '{username:$username,password:$password}')"
    api POST /users/ "${admin_token}" "${create_payload}" >/dev/null
    users="$(api GET '/users/?skip=0&limit=1000' "${admin_token}")"
    user_id="$(single_id "$(jq -c '.users' <<<"${users}")" "${LANGFLOW_PARTICIPANT_USER}")"
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
    die "Langflow release engineer identity reconciliation failed"

  participant_token="$(login \
    "${LANGFLOW_PARTICIPANT_USER}" "${LANGFLOW_PARTICIPANT_PASSWORD}")"
  participant_self="$(api GET /users/whoami "${participant_token}")"
  jq -e --arg id "${user_id}" --arg username "${LANGFLOW_PARTICIPANT_USER}" '
    .id == $id and .username == $username
    and .is_active == true and .is_superuser == false
  ' <<<"${participant_self}" >/dev/null ||
    die "Langflow release engineer login did not preserve the normal-user boundary"

  variables="$(api GET /variables/ "${participant_token}")"
  variable_id="$(single_id "${variables}" "${VARIABLE_NAME}")"
  if [[ ${variable_id} == __missing__ ]]; then
    variable_payload="$(jq -cn \
      --arg name "${VARIABLE_NAME}" \
      --arg value "${ORION_AGENT_API_KEY}" \
      '{name:$name,value:$value,type:"Credential",default_fields:["api_key"]}')"
    variable="$(api POST /variables/ "${participant_token}" "${variable_payload}")"
  else
    variable_payload="$(jq -cn \
      --arg id "${variable_id}" \
      --arg name "${VARIABLE_NAME}" \
      --arg value "${ORION_AGENT_API_KEY}" \
      '{id:$id,name:$name,value:$value,default_fields:["api_key"]}')"
    variable="$(api PATCH "/variables/${variable_id}" \
      "${participant_token}" "${variable_payload}")"
  fi
  jq -e --arg name "${VARIABLE_NAME}" '
    .name == $name and .type == "Credential" and .value == null
    and (.default_fields | contains(["api_key"]))
  ' <<<"${variable}" >/dev/null ||
    die "Langflow Orion service credential reconciliation failed"

  starters="$(api GET /flows/basic_examples/ "${participant_token}")"
  components="$(api GET /all "${participant_token}")"
  flow_payload="$(build_flow_payload "${starters}" "${components}")"
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
    --arg endpoint "${FLOW_ENDPOINT}" \
    --arg agent_api_base "${ORION_AGENT_URL%/}/v1" \
    --arg variable_name "${VARIABLE_NAME}" \
    --arg actor "${LANGFLOW_PARTICIPANT_USER}" \
    --arg conversation_id "${CONVERSATION_ID}" '
      .user_id == $owner
      and .name == $name
      and .endpoint_name == $endpoint
      and .access_type == "PRIVATE"
      and (.data.nodes | length) == 4
      and (.data.edges | length) == 3
      and ([.data.nodes[].data.type]
        | sort == (["ChatInput", "ChatOutput", "OpenAIModel", "Prompt"] | sort))
      and ([.data.nodes[] | select(.data.type == "OpenAIModel")][0] as $model
        | $model.data.node.template.model_name.value == "orion-assistant"
        and $model.data.node.template.openai_api_base.value == $agent_api_base
        and $model.data.node.template.api_key.value == $variable_name
        and $model.data.node.template.model_kwargs.value.user == $actor
        and $model.data.node.template.model_kwargs.value.extra_body.conversation_id == $conversation_id
        and $model.data.node.template.model_kwargs.value.extra_body.metadata.handoff.team == "Release Engineering")
    ' <<<"${flow}" >/dev/null ||
    die "Langflow Orion release review flow reconciliation failed"

  seed_release_policy_source
  seed_conversation
  log "Langflow release engineer and executable Orion review flow are ready: $(jq -r .id <<<"${flow}")"
}

main "$@"
