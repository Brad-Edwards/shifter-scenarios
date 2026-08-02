#!/usr/bin/env bash

set -Eeuo pipefail

SEEDING_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/common.sh
source "${SEEDING_ROOT}/lib/common.sh"

: "${HARBOR_API_URL:=http://10.61.40.32:8080/api/v2.0}"
: "${HARBOR_ADMIN_USER:=admin}"
: "${HARBOR_ADMIN_PASSWORD:=KeplerV2-Training-Harbor}"
: "${HARBOR_OIDC_CLIENT_SECRET:=KeplerV2-Training-Harbor-OIDC}"
: "${HARBOR_PROJECT:=orion-build}"

readonly HARBOR_OIDC_GROUP_TYPE=3
readonly HARBOR_GUEST_ROLE=3
readonly HARBOR_MAINTAINER_ROLE=4

kcadm() {
  compose exec -T keycloak /opt/keycloak/bin/kcadm.sh "$@"
}

harbor_api() {
  local method=$1
  local path=$2
  shift 2
  curl --fail --silent --show-error \
    --request "${method}" \
    --user "${HARBOR_ADMIN_USER}:${HARBOR_ADMIN_PASSWORD}" \
    --header 'Content-Type: application/json' \
    "$@" "${HARBOR_API_URL}${path}"
}

ensure_client() {
  local client_id clients client_json mapper_id mapper_json mappers

  clients="$(kcadm get clients -r "${KEYCLOAK_REALM}" -q clientId=harbor)"
  client_id="$(jq -r '.[0].id // empty' <<<"${clients}")"
  client_json="$(jq -cn --arg secret "${HARBOR_OIDC_CLIENT_SECRET}" '{
    clientId: "harbor",
    name: "Orion Container Registry",
    enabled: true,
    protocol: "openid-connect",
    publicClient: false,
    secret: $secret,
    standardFlowEnabled: true,
    directAccessGrantsEnabled: false,
    serviceAccountsEnabled: false,
    redirectUris: ["https://registry.keplerops.lab/c/oidc/callback"],
    webOrigins: ["https://registry.keplerops.lab"],
    attributes: {
      "post.logout.redirect.uris": "https://registry.keplerops.lab/*"
    }
  }')"

  if [[ -n ${client_id} ]]; then
    kcadm update "clients/${client_id}" -r "${KEYCLOAK_REALM}" \
      -f - <<<"${client_json}" >/dev/null
  else
    kcadm create clients -r "${KEYCLOAK_REALM}" \
      -f - <<<"${client_json}" >/dev/null
    clients="$(kcadm get clients -r "${KEYCLOAK_REALM}" -q clientId=harbor)"
    client_id="$(jq -er '.[0].id' <<<"${clients}")"
  fi

  mapper_json="$(jq -cn '{
    name: "groups",
    protocol: "openid-connect",
    protocolMapper: "oidc-group-membership-mapper",
    consentRequired: false,
    config: {
      "claim.name": "groups",
      "full.path": "false",
      "id.token.claim": "true",
      "access.token.claim": "true",
      "userinfo.token.claim": "true"
    }
  }')"
  mappers="$(kcadm get "clients/${client_id}/protocol-mappers/models" \
    -r "${KEYCLOAK_REALM}")"
  mapper_id="$(jq -r '.[] | select(.name == "groups") | .id' \
    <<<"${mappers}" | head -n1)"
  if [[ -n ${mapper_id} ]]; then
    kcadm delete "clients/${client_id}/protocol-mappers/models/${mapper_id}" \
      -r "${KEYCLOAK_REALM}" >/dev/null
  fi
  kcadm create "clients/${client_id}/protocol-mappers/models" \
    -r "${KEYCLOAK_REALM}" -f - <<<"${mapper_json}" >/dev/null
}

require_group() {
  local group=$1
  kcadm get groups -r "${KEYCLOAK_REALM}" -q "search=${group}" |
    jq -e --arg group "${group}" 'any(.[]; .name == $group)' >/dev/null ||
    die "Keycloak group is unavailable: ${group}"
}

ensure_project() {
  local projects
  projects="$(harbor_api GET "/projects?name=$(urlencode "${HARBOR_PROJECT}")")"
  if ! jq -e --arg project "${HARBOR_PROJECT}" \
    'any(.[]; .name == $project)' <<<"${projects}" >/dev/null; then
    harbor_api POST /projects --data "$(jq -cn --arg name "${HARBOR_PROJECT}" '{
      project_name: $name,
      public: false,
      metadata: {auto_scan: "false"}
    }')" >/dev/null
  fi
}

ensure_group_member() {
  local group=$1
  local role_id=$2
  local member group_type member_id members payload

  members="$(harbor_api GET "/projects/$(urlencode "${HARBOR_PROJECT}")/members?page=1&page_size=100")"
  member="$(jq -c --arg group "${group}" '
    .[] |
    select(
      (.entity_type == "g" and .entity_name == $group) or
      (.member_group.group_name == $group)
    )
  ' <<<"${members}" | head -n1)"

  if [[ -n ${member} ]]; then
    member_id="$(jq -er '.id' <<<"${member}")"
    group_type="$(jq -r '.member_group.group_type // empty' <<<"${member}")"
    if [[ -n ${group_type} && ${group_type} -ne ${HARBOR_OIDC_GROUP_TYPE} ]]; then
      harbor_api DELETE "/projects/$(urlencode "${HARBOR_PROJECT}")/members/${member_id}" >/dev/null
      member=""
    elif [[ $(jq -er '.role_id' <<<"${member}") -ne ${role_id} ]]; then
      harbor_api PUT "/projects/$(urlencode "${HARBOR_PROJECT}")/members/${member_id}" \
        --data "$(jq -cn --argjson role_id "${role_id}" '{role_id: $role_id}')" >/dev/null
    fi
  fi

  if [[ -z ${member} ]]; then
    payload="$(jq -cn \
      --arg group "${group}" \
      --argjson group_type "${HARBOR_OIDC_GROUP_TYPE}" \
      --argjson role_id "${role_id}" '{
        role_id: $role_id,
        member_group: {
          group_name: $group,
          group_type: $group_type
        }
      }')"
    harbor_api POST "/projects/$(urlencode "${HARBOR_PROJECT}")/members" \
      --data "${payload}" >/dev/null
  fi
}

verify_oidc_configuration() {
  harbor_api GET /configurations |
    jq -e '
      .auth_mode.value == "oidc_auth" and
      .primary_auth_mode.value == true and
      .oidc_groups_claim.value == "groups" and
      .oidc_verify_cert.value == true and
      .oidc_auto_onboard.value == true and
      .oidc_user_claim.value == "preferred_username"
    ' >/dev/null ||
    die "Harbor OIDC startup configuration did not converge"
}

main() {
  require_command curl
  require_command jq
  require_service keycloak
  retry 60 2 kcadm config credentials \
    --server http://localhost:8080 \
    --realm master \
    --user "${KEYCLOAK_ADMIN_USER}" \
    --password "${KEYCLOAK_ADMIN_PASSWORD}" >/dev/null ||
    die "Keycloak admin authentication failed"
  kcadm get "realms/${KEYCLOAK_REALM}" >/dev/null 2>&1 ||
    die "Keycloak realm is unavailable: ${KEYCLOAK_REALM}"

  require_group RG-Harbor-Orion-Review
  require_group RG-Harbor-Orion-Release
  ensure_client

  retry 60 2 harbor_api GET /health >/dev/null ||
    die "Harbor API did not become ready"
  verify_oidc_configuration
  ensure_project
  ensure_group_member RG-Harbor-Orion-Review "${HARBOR_GUEST_ROLE}"
  ensure_group_member RG-Harbor-Orion-Release "${HARBOR_MAINTAINER_ROLE}"
  log "Harbor OIDC and Orion project group roles are ready"
}

main "$@"
