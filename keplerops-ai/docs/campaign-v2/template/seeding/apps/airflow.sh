#!/usr/bin/env bash

set -Eeuo pipefail

SEEDING_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/common.sh
source "${SEEDING_ROOT}/lib/common.sh"

: "${AIRFLOW_OIDC_CLIENT_SECRET:=KeplerV2-Training-Airflow-OIDC}"
readonly AIRFLOW_CONTAINER=kep-v2-airflow-api

kcadm() {
  compose exec -T keycloak /opt/keycloak/bin/kcadm.sh "$@"
}

require_group() {
  local group=$1
  kcadm get groups -r "${KEYCLOAK_REALM}" -q "search=${group}" |
    jq -e --arg group "${group}" 'any(.[]; .name == $group)' >/dev/null ||
    die "Keycloak group is unavailable: ${group}"
}

ensure_client() {
  local client_uuid clients mapper_id mappers
  local client_json mapper_json

  clients="$(kcadm get clients -r "${KEYCLOAK_REALM}" -q clientId=airflow)"
  client_uuid="$(jq -r '.[0].id // empty' <<<"${clients}")"
  client_json="$(jq -cn --arg secret "${AIRFLOW_OIDC_CLIENT_SECRET}" '{
    clientId:"airflow",
    name:"KeplerOps Airflow",
    enabled:true,
    protocol:"openid-connect",
    publicClient:false,
    secret:$secret,
    standardFlowEnabled:true,
    directAccessGrantsEnabled:false,
    serviceAccountsEnabled:false,
    frontchannelLogout:true,
    redirectUris:["https://airflow.keplerops.lab/auth/oauth-authorized/keycloak"],
    webOrigins:["https://airflow.keplerops.lab"],
    attributes:{
      "pkce.code.challenge.method":"",
      "post.logout.redirect.uris":"https://airflow.keplerops.lab/*",
      "frontchannel.logout.session.required":"true"
    }
  }')"

  if [[ -n ${client_uuid} ]]; then
    kcadm update "clients/${client_uuid}" -r "${KEYCLOAK_REALM}" \
      -f - <<<"${client_json}" >/dev/null
  else
    kcadm create clients -r "${KEYCLOAK_REALM}" \
      -f - <<<"${client_json}" >/dev/null
    clients="$(kcadm get clients -r "${KEYCLOAK_REALM}" -q clientId=airflow)"
    client_uuid="$(jq -er '.[0].id' <<<"${clients}")"
  fi

  mapper_json="$(jq -cn '{
    name:"groups",
    protocol:"openid-connect",
    protocolMapper:"oidc-group-membership-mapper",
    consentRequired:false,
    config:{
      "claim.name":"groups",
      "full.path":"false",
      "id.token.claim":"true",
      "access.token.claim":"true",
      "userinfo.token.claim":"true"
    }
  }')"
  mappers="$(kcadm get "clients/${client_uuid}/protocol-mappers/models" \
    -r "${KEYCLOAK_REALM}")"
  mapper_id="$(jq -r '.[] | select(.name == "groups") | .id' \
    <<<"${mappers}" | head -n1)"
  if [[ -n ${mapper_id} ]]; then
    kcadm delete "clients/${client_uuid}/protocol-mappers/models/${mapper_id}" \
      -r "${KEYCLOAK_REALM}" >/dev/null
  fi
  kcadm create "clients/${client_uuid}/protocol-mappers/models" \
    -r "${KEYCLOAK_REALM}" -f - <<<"${mapper_json}" >/dev/null
}

main() {
  require_command docker
  require_command jq
  require_service keycloak
  docker inspect "${AIRFLOW_CONTAINER}" >/dev/null 2>&1 ||
    die "Airflow API container is unavailable: ${AIRFLOW_CONTAINER}"

  retry 60 2 kcadm config credentials \
    --server http://localhost:8080 \
    --realm master \
    --user "${KEYCLOAK_ADMIN_USER}" \
    --password "${KEYCLOAK_ADMIN_PASSWORD}" >/dev/null ||
    die "Keycloak admin authentication failed"
  require_group RG-Airflow-Orion-View
  require_group RG-Airflow-Orion-Run
  ensure_client

  docker exec "${AIRFLOW_CONTAINER}" airflow sync-perm >/dev/null
  docker exec "${AIRFLOW_CONTAINER}" \
    python /opt/airflow/config/reconcile_roles.py
  log "Airflow Keycloak OAuth and scoped Viewer/Runner roles are ready"
}

main "$@"
