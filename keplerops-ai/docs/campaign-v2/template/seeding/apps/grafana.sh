#!/usr/bin/env bash

set -Eeuo pipefail

SEEDING_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/common.sh
source "${SEEDING_ROOT}/lib/common.sh"

: "${GRAFANA_OIDC_CLIENT_SECRET:=KeplerV2-Training-Grafana-OIDC}"

kcadm() {
  compose exec -T keycloak /opt/keycloak/bin/kcadm.sh "$@"
}

ensure_client() {
  local client_id clients client_json mapper_id mapper_json mappers

  clients="$(kcadm get clients -r "${KEYCLOAK_REALM}" -q clientId=grafana)"
  client_id="$(jq -r '.[0].id // empty' <<<"${clients}")"
  client_json="$(jq -cn --arg secret "${GRAFANA_OIDC_CLIENT_SECRET}" '{
    clientId: "grafana",
    name: "KeplerOps Observability",
    enabled: true,
    protocol: "openid-connect",
    publicClient: false,
    secret: $secret,
    standardFlowEnabled: true,
    directAccessGrantsEnabled: false,
    serviceAccountsEnabled: false,
    redirectUris: ["https://grafana.keplerops.lab/login/generic_oauth"],
    webOrigins: ["https://grafana.keplerops.lab"],
    attributes: {
      "post.logout.redirect.uris": "https://grafana.keplerops.lab/*"
    }
  }')"

  if [[ -n ${client_id} ]]; then
    kcadm update "clients/${client_id}" -r "${KEYCLOAK_REALM}" \
      -f - <<<"${client_json}" >/dev/null
  else
    kcadm create clients -r "${KEYCLOAK_REALM}" \
      -f - <<<"${client_json}" >/dev/null
    clients="$(kcadm get clients -r "${KEYCLOAK_REALM}" -q clientId=grafana)"
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

main() {
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

  require_group GG-Platform-Operators
  require_group GG-Security-Auditors
  ensure_client
  log "Grafana Generic OAuth client and strict role groups are ready"
}

main "$@"
