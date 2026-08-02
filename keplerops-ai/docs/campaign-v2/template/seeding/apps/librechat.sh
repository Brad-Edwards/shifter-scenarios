#!/usr/bin/env bash
set -Eeuo pipefail

SEEDING_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/common.sh
source "${SEEDING_ROOT}/lib/common.sh"

: "${LIBRECHAT_OIDC_CLIENT_SECRET:=KeplerV2-Training-LibreChat-OIDC}"

readonly CLIENT_ID=librechat
readonly ACCESS_ROLE=librechat-user
readonly ACCESS_GROUP=RG-Jupyter-Orion-Evaluation

kcadm() {
  compose exec -T keycloak /opt/keycloak/bin/kcadm.sh "$@"
}

ensure_client() {
  local clients client_id client_json

  clients="$(kcadm get clients -r "${KEYCLOAK_REALM}" -q clientId="${CLIENT_ID}")"
  client_id="$(jq -r '.[0].id // empty' <<<"${clients}")"
  client_json="$(jq -cn --arg secret "${LIBRECHAT_OIDC_CLIENT_SECRET}" '{
    clientId: "librechat",
    name: "Orion Assistant",
    enabled: true,
    protocol: "openid-connect",
    publicClient: false,
    secret: $secret,
    standardFlowEnabled: true,
    directAccessGrantsEnabled: false,
    serviceAccountsEnabled: false,
    redirectUris: ["https://assistant.keplerops.lab/oauth/openid/callback"],
    webOrigins: ["https://assistant.keplerops.lab"],
    attributes: {
      "post.logout.redirect.uris": "https://assistant.keplerops.lab/*"
    }
  }')"

  if [[ -n ${client_id} ]]; then
    kcadm update "clients/${client_id}" -r "${KEYCLOAK_REALM}" \
      -f - <<<"${client_json}" >/dev/null
  else
    kcadm create clients -r "${KEYCLOAK_REALM}" -f - \
      <<<"${client_json}" >/dev/null
  fi
}

ensure_group_role() {
  local groups group_id role_json role_id mappings

  if ! kcadm get "roles/${ACCESS_ROLE}" -r "${KEYCLOAK_REALM}" >/dev/null 2>&1; then
    kcadm create roles -r "${KEYCLOAK_REALM}" \
      -s "name=${ACCESS_ROLE}" \
      -s 'description=Access to the internal Orion Assistant' >/dev/null
  fi
  role_json="$(kcadm get "roles/${ACCESS_ROLE}" -r "${KEYCLOAK_REALM}")"
  role_id="$(jq -er '.id' <<<"${role_json}")"

  groups="$(kcadm get groups -r "${KEYCLOAK_REALM}")"
  group_id="$(jq -r --arg name "${ACCESS_GROUP}" \
    '.[] | select(.name == $name) | .id' <<<"${groups}" | head -n1)"
  [[ -n ${group_id} ]] || die "Keycloak access group is missing: ${ACCESS_GROUP}"

  mappings="$(kcadm get "groups/${group_id}/role-mappings/realm" \
    -r "${KEYCLOAK_REALM}")"
  if ! jq -e --arg id "${role_id}" 'any(.[]; .id == $id)' \
    <<<"${mappings}" >/dev/null; then
    kcadm create "groups/${group_id}/role-mappings/realm" \
      -r "${KEYCLOAK_REALM}" -f - <<<"[$(jq -c . <<<"${role_json}")]" >/dev/null
  fi
}

main() {
  require_service keycloak
  retry 60 2 kcadm config credentials \
    --server http://127.0.0.1:8080 \
    --realm master \
    --user "${KEYCLOAK_ADMIN_USER}" \
    --password "${KEYCLOAK_ADMIN_PASSWORD}" >/dev/null || \
    die 'Keycloak admin CLI did not become ready'

  ensure_client
  ensure_group_role
  log "LibreChat OIDC client and bounded Orion Assistant role are ready"
}

main "$@"
