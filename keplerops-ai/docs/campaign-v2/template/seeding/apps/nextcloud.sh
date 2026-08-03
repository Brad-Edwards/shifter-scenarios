#!/usr/bin/env bash

set -Eeuo pipefail

SEEDING_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/common.sh
source "${SEEDING_ROOT}/lib/common.sh"

readonly NEXTCLOUD_USER_OIDC_VERSION=8.10.1
readonly NEXTCLOUD_OIDC_PROVIDER=keplerops
readonly NEXTCLOUD_OIDC_CLIENT_ID=nextcloud
readonly NEXTCLOUD_OIDC_CLIENT_SECRET="${NEXTCLOUD_OIDC_CLIENT_SECRET:-KeplerV2-Training-Nextcloud-OIDC}"
readonly NEXTCLOUD_OIDC_DISCOVERY_URI="https://id.keplerops.lab/realms/${KEYCLOAK_REALM}/.well-known/openid-configuration"
readonly NEXTCLOUD_ACCESS_GROUP=RG-Nextcloud-Orion-Internal
readonly NEXTCLOUD_PARTNER_GROUP=RG-Nextcloud-Orion-Partner
readonly NEXTCLOUD_LEGACY_GROUP="${NEXTCLOUD_GROUP:-orion-internal}"
readonly SECURITY_AUDITOR_PASSWORD="${SECURITY_AUDITOR_PASSWORD:-KeplerV2-Training-Auditor}"

occ() {
  compose exec -T --user www-data nextcloud php /var/www/html/occ "$@"
}

kcadm() {
  compose exec -T keycloak /opt/keycloak/bin/kcadm.sh "$@"
}

nextcloud_ready() {
  occ status --output=json 2>/dev/null | jq -e '.installed == true' >/dev/null
}

keycloak_ready() {
  kcadm config credentials \
    --server http://127.0.0.1:8080 \
    --realm master \
    --user "${KEYCLOAK_ADMIN_USER}" \
    --password "${KEYCLOAK_ADMIN_PASSWORD}" >/dev/null 2>&1
}

ensure_keycloak_client() {
  local clients client_id client_json mappers mapper_id mapper_json

  clients="$(kcadm get clients -r "${KEYCLOAK_REALM}" -q clientId="${NEXTCLOUD_OIDC_CLIENT_ID}")"
  client_id="$(jq -r '.[0].id // empty' <<<"${clients}")"
  client_json="$(jq -cn \
    --arg client_id "${NEXTCLOUD_OIDC_CLIENT_ID}" \
    --arg secret "${NEXTCLOUD_OIDC_CLIENT_SECRET}" \
    '{
      clientId: $client_id,
      name: "Orion Files",
      enabled: true,
      protocol: "openid-connect",
      publicClient: false,
      secret: $secret,
      standardFlowEnabled: true,
      directAccessGrantsEnabled: false,
      serviceAccountsEnabled: false,
      frontchannelLogout: true,
      rootUrl: "https://files.keplerops.lab",
      baseUrl: "https://files.keplerops.lab/",
      redirectUris: [
        "https://files.keplerops.lab/apps/user_oidc/code",
        "https://files.keplerops.lab/index.php/apps/user_oidc/code"
      ],
      webOrigins: ["https://files.keplerops.lab"],
      attributes: {
        "post.logout.redirect.uris": "https://files.keplerops.lab/*",
        "backchannel.logout.url": "https://files.keplerops.lab/apps/user_oidc/backchannel-logout/keplerops",
        "backchannel.logout.session.required": "true"
      }
    }')"

  if [[ -n ${client_id} ]]; then
    kcadm update "clients/${client_id}" -r "${KEYCLOAK_REALM}" \
      -f - <<<"${client_json}" >/dev/null
  else
    kcadm create clients -r "${KEYCLOAK_REALM}" -f - \
      <<<"${client_json}" >/dev/null
    clients="$(kcadm get clients -r "${KEYCLOAK_REALM}" -q clientId="${NEXTCLOUD_OIDC_CLIENT_ID}")"
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
  mappers="$(kcadm get "clients/${client_id}/protocol-mappers/models" -r "${KEYCLOAK_REALM}")"
  mapper_id="$(jq -r '.[] | select(.name == "groups") | .id' <<<"${mappers}" | head -n1)"
  if [[ -n ${mapper_id} ]]; then
    kcadm delete "clients/${client_id}/protocol-mappers/models/${mapper_id}" \
      -r "${KEYCLOAK_REALM}" >/dev/null
  fi
  kcadm create "clients/${client_id}/protocol-mappers/models" \
    -r "${KEYCLOAK_REALM}" -f - <<<"${mapper_json}" >/dev/null
}

ensure_user_oidc() {
  local installed_version

  installed_version="$(occ app:list --output=json | jq -r \
    '.enabled.user_oidc // .disabled.user_oidc // empty')"
  if [[ -z ${installed_version} ]]; then
    occ app:install user_oidc >/dev/null
    installed_version="$(occ app:list --output=json | jq -er '.enabled.user_oidc')"
  elif ! occ app:list --output=json | jq -e '.enabled.user_oidc' >/dev/null; then
    occ app:enable user_oidc >/dev/null
  fi
  [[ ${installed_version} == "${NEXTCLOUD_USER_OIDC_VERSION}" ]] || \
    die "Nextcloud user_oidc ${NEXTCLOUD_USER_OIDC_VERSION} is required; found ${installed_version}"

  occ config:system:set user_oidc auto_provision \
    --type=boolean --value=true >/dev/null
  occ config:system:set user_oidc soft_auto_provision \
    --type=boolean --value=true >/dev/null
  occ config:system:set user_oidc disable_account_creation \
    --type=boolean --value=false >/dev/null
  occ config:system:set allow_local_remote_servers \
    --type=boolean --value=true >/dev/null
  occ config:system:set trusted_proxies 0 --value=10.61.10.2 >/dev/null
  occ config:system:set trusted_proxies 1 --value=10.61.30.2 >/dev/null
  occ config:app:set user_oidc allow_multiple_user_backends \
    --type=string --value=0 >/dev/null

  occ user_oidc:provider "${NEXTCLOUD_OIDC_PROVIDER}" \
    --clientid="${NEXTCLOUD_OIDC_CLIENT_ID}" \
    --clientsecret="${NEXTCLOUD_OIDC_CLIENT_SECRET}" \
    --discoveryuri="${NEXTCLOUD_OIDC_DISCOVERY_URI}" \
    --scope='openid profile email' \
    --mapping-uid=preferred_username \
    --mapping-display-name=name \
    --mapping-email=email \
    --mapping-groups=groups \
    --unique-uid=0 \
    --group-provisioning=1 \
    --group-whitelist-regex="/^(${NEXTCLOUD_ACCESS_GROUP}|${NEXTCLOUD_PARTNER_GROUP})$/" \
    --group-restrict-login-to-whitelist=1 >/dev/null
}

ensure_user() {
  local username=$1
  local display_name=$2
  local password=$3
  local email=$4
  local access=$5

  if occ user:info "${username}" >/dev/null 2>&1; then
    compose exec -T --user www-data -e OC_PASS="${password}" nextcloud \
      php /var/www/html/occ user:resetpassword --password-from-env "${username}" >/dev/null
  else
    compose exec -T --user www-data -e OC_PASS="${password}" nextcloud \
      php /var/www/html/occ user:add --password-from-env \
      --display-name "${display_name}" "${username}" >/dev/null
  fi

  occ user:setting "${username}" settings email "${email}" >/dev/null
  if [[ ${access} == true ]]; then
    occ group:adduser "${NEXTCLOUD_ACCESS_GROUP}" "${username}" >/dev/null
  else
    occ group:removeuser "${NEXTCLOUD_ACCESS_GROUP}" "${username}" >/dev/null 2>&1 || true
  fi
}

ensure_room() {
  local room_path room_url status shares share_id response
  room_path="/$(urlencode "${NEXTCLOUD_ROOM}")"
  room_url="${NEXTCLOUD_URL}/remote.php/dav/files/${NEXTCLOUD_ADMIN_USER}${room_path}"
  status="$(http_code MKCOL "${room_url}" \
    --user "${NEXTCLOUD_ADMIN_USER}:${NEXTCLOUD_ADMIN_PASSWORD}" \
    --header "Host: ${NEXTCLOUD_HOST}")"
  [[ ${status} == 201 || ${status} == 405 ]] || die "Nextcloud room creation returned HTTP ${status}"

  shares="$(curl --silent --show-error --fail-with-body \
    --user "${NEXTCLOUD_ADMIN_USER}:${NEXTCLOUD_ADMIN_PASSWORD}" \
    --header "Host: ${NEXTCLOUD_HOST}" \
    --header 'OCS-APIRequest: true' \
    --get \
    --data-urlencode "path=/${NEXTCLOUD_ROOM}" \
    --data 'reshares=true' \
    --data 'format=json' \
    "${NEXTCLOUD_URL}/ocs/v2.php/apps/files_sharing/api/v1/shares")"

  share_id="$(jq -r --arg group "${NEXTCLOUD_ACCESS_GROUP}" \
    '.ocs.data[]? | select(.share_type == 1 and .share_with == $group) | .id' \
    <<<"${shares}" | head -n1)"
  if [[ -n ${share_id} ]]; then
    response="$(curl --silent --show-error --fail-with-body \
      --request PUT \
      --user "${NEXTCLOUD_ADMIN_USER}:${NEXTCLOUD_ADMIN_PASSWORD}" \
      --header "Host: ${NEXTCLOUD_HOST}" \
      --header 'OCS-APIRequest: true' \
      --data 'permissions=31' \
      --data 'format=json' \
      "${NEXTCLOUD_URL}/ocs/v2.php/apps/files_sharing/api/v1/shares/${share_id}")"
  else
    response="$(curl --silent --show-error --fail-with-body \
      --user "${NEXTCLOUD_ADMIN_USER}:${NEXTCLOUD_ADMIN_PASSWORD}" \
      --header "Host: ${NEXTCLOUD_HOST}" \
      --header 'OCS-APIRequest: true' \
      --data-urlencode "path=/${NEXTCLOUD_ROOM}" \
      --data 'shareType=1' \
      --data-urlencode "shareWith=${NEXTCLOUD_ACCESS_GROUP}" \
      --data 'permissions=31' \
      --data 'format=json' \
      "${NEXTCLOUD_URL}/ocs/v2.php/apps/files_sharing/api/v1/shares")"
  fi
  jq -e '.ocs.meta.status == "ok"' <<<"${response}" >/dev/null || \
    die "Nextcloud rejected the room share reconciliation"

  if [[ ${NEXTCLOUD_LEGACY_GROUP} != "${NEXTCLOUD_ACCESS_GROUP}" ]]; then
    while IFS= read -r share_id; do
      [[ -n ${share_id} ]] || continue
      response="$(curl --silent --show-error --fail-with-body \
        --request DELETE \
        --user "${NEXTCLOUD_ADMIN_USER}:${NEXTCLOUD_ADMIN_PASSWORD}" \
        --header "Host: ${NEXTCLOUD_HOST}" \
        --header 'OCS-APIRequest: true' \
        --data 'format=json' \
        "${NEXTCLOUD_URL}/ocs/v2.php/apps/files_sharing/api/v1/shares/${share_id}")"
      jq -e '.ocs.meta.status == "ok"' <<<"${response}" >/dev/null || \
        die "Nextcloud rejected legacy room ACL removal"
    done < <(jq -r --arg group "${NEXTCLOUD_LEGACY_GROUP}" \
      '.ocs.data[]? | select(.share_type == 1 and .share_with == $group) | .id' \
      <<<"${shares}")
  fi
}

main() {
  require_service nextcloud
  require_service keycloak
  retry 60 3 nextcloud_ready || die "Nextcloud did not become ready"
  retry 60 2 keycloak_ready || die "Keycloak admin CLI did not become ready"

  ensure_keycloak_client
  ensure_user_oidc
  occ group:add "${NEXTCLOUD_ACCESS_GROUP}" >/dev/null 2>&1 || true
  ensure_user reviewer 'Rina Chen' "${REVIEWER_PASSWORD}" reviewer@keplerops.lab true
  ensure_user ml.engineer 'Maya Ortiz' "${ML_ENGINEER_PASSWORD}" ml.engineer@keplerops.lab true
  ensure_user security.auditor 'Darius Cole' "${SECURITY_AUDITOR_PASSWORD}" security.auditor@keplerops.lab true
  ensure_user release.engineer 'Elliot Park' "${RELEASE_ENGINEER_PASSWORD}" release.engineer@keplerops.lab false
  ensure_user comms.publisher 'Samira Okafor' "${COMMS_PUBLISHER_PASSWORD}" comms.publisher@keplerops.lab false
  ensure_user support.analyst 'Jonas Becker' "${SUPPORT_ANALYST_PASSWORD}" support.analyst@keplerops.lab false
  ensure_room

  log "Nextcloud OIDC and native Orion room ACL are ready"
}

main "$@"
