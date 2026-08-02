#!/usr/bin/env bash

set -Eeuo pipefail

SEEDING_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/common.sh
source "${SEEDING_ROOT}/lib/common.sh"

readonly PARTNER_INTAKE_CLIENT_ID="${KEYCLOAK_PARTNER_CLIENT_ID:-orion-partner-intake}"
readonly PARTNER_INTAKE_CLIENT_SECRET="${KEYCLOAK_PARTNER_CLIENT_SECRET:-KeplerV2-Training-Partner-Intake-Keycloak}"
readonly PARTNER_NEXTCLOUD_GROUP=RG-Nextcloud-Orion-Partner
readonly PARTNER_WORKHUB_GROUP=RG-WorkHub-Orion-Partner

kcadm() {
  compose exec -T keycloak /opt/keycloak/bin/kcadm.sh "$@"
}

json_array() {
  jq -cn --arg value "$1" '[$value]'
}

ensure_realm() {
  if ! kcadm get "realms/${KEYCLOAK_REALM}" >/dev/null 2>&1; then
    kcadm create realms \
      -s "realm=${KEYCLOAK_REALM}" \
      -s enabled=true \
      -s registrationAllowed=false >/dev/null
    log "Keycloak realm created: ${KEYCLOAK_REALM}"
  fi
  kcadm update "realms/${KEYCLOAK_REALM}" \
    -s ssoSessionIdleTimeout=3600 \
    -s ssoSessionMaxLifespan=43200 \
    -s accessTokenLifespan=900 \
    -s clientSessionIdleTimeout=3600 \
    -s clientSessionMaxLifespan=43200 >/dev/null
}

ensure_jupyterhub_client() {
  local clients client_id mapper_json mappers mapper_id client_json
  clients=$(kcadm get clients -r "${KEYCLOAK_REALM}" -q clientId=jupyterhub)
  client_id=$(jq -r '.[0].id // empty' <<<"$clients")
  client_json=$(jq -cn --arg secret "$JUPYTERHUB_OIDC_CLIENT_SECRET" '{
    clientId: "jupyterhub",
    name: "Orion Notebooks",
    enabled: true,
    protocol: "openid-connect",
    publicClient: false,
    secret: $secret,
    standardFlowEnabled: true,
    directAccessGrantsEnabled: false,
    serviceAccountsEnabled: false,
    redirectUris: ["https://notebooks.keplerops.lab/hub/oauth_callback"],
    webOrigins: ["https://notebooks.keplerops.lab"],
    attributes: {"post.logout.redirect.uris": "https://notebooks.keplerops.lab/*"}
  }')

  if [[ -n $client_id ]]; then
    kcadm update "clients/${client_id}" -r "${KEYCLOAK_REALM}" -f - <<<"$client_json" >/dev/null
  else
    kcadm create clients -r "${KEYCLOAK_REALM}" -f - <<<"$client_json" >/dev/null
    clients=$(kcadm get clients -r "${KEYCLOAK_REALM}" -q clientId=jupyterhub)
    client_id=$(jq -er '.[0].id' <<<"$clients")
  fi

  mapper_json=$(jq -cn '{
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
  }')
  mappers=$(kcadm get "clients/${client_id}/protocol-mappers/models" -r "${KEYCLOAK_REALM}")
  mapper_id=$(jq -r '.[] | select(.name == "groups") | .id' <<<"$mappers" | head -n1)
  if [[ -n $mapper_id ]]; then
    kcadm delete "clients/${client_id}/protocol-mappers/models/${mapper_id}" \
      -r "${KEYCLOAK_REALM}" >/dev/null 2>&1 || true
  fi
  kcadm create "clients/${client_id}/protocol-mappers/models" \
    -r "${KEYCLOAK_REALM}" -f - <<<"$mapper_json" >/dev/null
}

ensure_local_group() {
  local group_name=$1
  local groups group_id

  groups="$(kcadm get groups -r "${KEYCLOAK_REALM}" -q "search=${group_name}" -q exact=true)"
  group_id="$(jq -r --arg name "${group_name}" '.[] | select(.name == $name) | .id' \
    <<<"${groups}" | head -n1)"
  if [[ -z ${group_id} ]]; then
    kcadm create groups -r "${KEYCLOAK_REALM}" -s "name=${group_name}" >/dev/null
  fi
}

ensure_partner_intake_client() {
  local clients client_id client_json service_account service_account_id
  local realm_management_id roles_json role

  client_json="$(jq -cn \
    --arg client_id "${PARTNER_INTAKE_CLIENT_ID}" \
    --arg secret "${PARTNER_INTAKE_CLIENT_SECRET}" \
    '{
      clientId: $client_id,
      name: "Orion Partner Intake",
      description: "Provisions accepted partner access from the Orion support workflow.",
      enabled: true,
      protocol: "openid-connect",
      publicClient: false,
      secret: $secret,
      standardFlowEnabled: false,
      directAccessGrantsEnabled: false,
      serviceAccountsEnabled: true
    }')"
  clients="$(kcadm get clients -r "${KEYCLOAK_REALM}" \
    -q "clientId=${PARTNER_INTAKE_CLIENT_ID}")"
  client_id="$(jq -r '.[0].id // empty' <<<"${clients}")"
  if [[ -n ${client_id} ]]; then
    kcadm update "clients/${client_id}" -r "${KEYCLOAK_REALM}" \
      -f - <<<"${client_json}" >/dev/null
  else
    kcadm create clients -r "${KEYCLOAK_REALM}" -f - \
      <<<"${client_json}" >/dev/null
    clients="$(kcadm get clients -r "${KEYCLOAK_REALM}" \
      -q "clientId=${PARTNER_INTAKE_CLIENT_ID}")"
    client_id="$(jq -er '.[0].id' <<<"${clients}")"
  fi

  service_account="$(kcadm get "clients/${client_id}/service-account-user" \
    -r "${KEYCLOAK_REALM}")"
  service_account_id="$(jq -er '.id' <<<"${service_account}")"
  realm_management_id="$(kcadm get clients -r "${KEYCLOAK_REALM}" \
    -q clientId=realm-management | jq -er '.[0].id')"
  roles_json='[]'
  for role in manage-users view-users query-users query-groups; do
    roles_json="$(jq -c --argjson role \
      "$(kcadm get "clients/${realm_management_id}/roles/${role}" -r "${KEYCLOAK_REALM}")" \
      '. + [$role]' <<<"${roles_json}")"
  done
  kcadm create \
    "users/${service_account_id}/role-mappings/clients/${realm_management_id}" \
    -r "${KEYCLOAK_REALM}" -f - <<<"${roles_json}" >/dev/null
}

ensure_realm_mail() {
  local realm_json updated

  realm_json="$(kcadm get "realms/${KEYCLOAK_REALM}")"
  updated="$(jq -c \
    --arg password "${PARTNER_INTAKE_PASSWORD}" \
    '.smtpServer = {
      host: "10.61.10.20",
      port: "587",
      from: "partner-intake@keplerops.lab",
      fromDisplayName: "KeplerOps Partner Access",
      replyTo: "partner-intake@keplerops.lab",
      replyToDisplayName: "KeplerOps Partner Intake",
      auth: "true",
      user: "partner-intake",
      password: $password,
      starttls: "true",
      ssl: "false"
    }' <<<"${realm_json}")"
  kcadm update "realms/${KEYCLOAK_REALM}" -f - <<<"${updated}" >/dev/null
}

ldap_component_args() {
  local realm_id=$1
  printf '%s\0' \
    -s 'name=samba-ad' \
    -s 'providerId=ldap' \
    -s 'providerType=org.keycloak.storage.UserStorageProvider' \
    -s "parentId=${realm_id}" \
    -s "config.vendor=$(json_array ad)" \
    -s "config.connectionUrl=$(json_array "${SAMBA_LDAP_URL}")" \
    -s "config.bindDn=$(json_array "${SAMBA_BIND_DN}")" \
    -s "config.bindCredential=$(json_array "${SAMBA_BIND_PASSWORD}")" \
    -s "config.usersDn=$(json_array "${SAMBA_USERS_DN}")" \
    -s "config.usernameLDAPAttribute=$(json_array sAMAccountName)" \
    -s "config.rdnLDAPAttribute=$(json_array cn)" \
    -s "config.uuidLDAPAttribute=$(json_array objectGUID)" \
    -s "config.userObjectClasses=$(json_array 'person, organizationalPerson, user')" \
    -s "config.editMode=$(json_array READ_ONLY)" \
    -s "config.importEnabled=$(json_array true)" \
    -s "config.syncRegistrations=$(json_array false)" \
    -s "config.trustEmail=$(json_array true)" \
    -s "config.authType=$(json_array simple)" \
    -s "config.searchScope=$(json_array 1)" \
    -s "config.useTruststoreSpi=$(json_array ldapsOnly)" \
    -s "config.connectionPooling=$(json_array true)" \
    -s "config.pagination=$(json_array true)" \
    -s "config.batchSizeForSync=$(json_array 1000)" \
    -s "config.fullSyncPeriod=$(json_array -1)" \
    -s "config.changedSyncPeriod=$(json_array -1)" \
    -s "config.cachePolicy=$(json_array DEFAULT)"
}

group_mapper_json() {
  local ldap_id=$1
  jq -cn --arg parent "${ldap_id}" --arg groups_dn "${SAMBA_GROUPS_DN}" '{
    name: "samba-groups",
    providerId: "group-ldap-mapper",
    providerType: "org.keycloak.storage.ldap.mappers.LDAPStorageMapper",
    parentId: $parent,
    config: {
      "groups.dn": [$groups_dn],
      "group.name.ldap.attribute": ["cn"],
      "group.object.classes": ["group"],
      "preserve.group.inheritance": ["false"],
      "ignore.missing.groups": ["false"],
      "membership.ldap.attribute": ["member"],
      "membership.attribute.type": ["DN"],
      "membership.user.ldap.attribute": ["sAMAccountName"],
      "mode": ["READ_ONLY"],
      "user.roles.retrieve.strategy": ["LOAD_GROUPS_BY_MEMBER_ATTRIBUTE"],
      "drop.non.existing.groups.during.sync": ["false"]
    }
  }'
}

main() {
  local realm_json realm_id components ldap_id mapper_id mapper_json users_json username groups_json group
  local -a args

  require_service keycloak
  retry 60 2 kcadm config credentials \
    --server http://127.0.0.1:8080 \
    --realm master \
    --user "${KEYCLOAK_ADMIN_USER}" \
    --password "${KEYCLOAK_ADMIN_PASSWORD}" >/dev/null || \
    die "Keycloak admin CLI did not become ready"

  ensure_realm
  realm_json="$(kcadm get "realms/${KEYCLOAK_REALM}")"
  realm_id="$(jq -er '.id' <<<"${realm_json}")"
  components="$(kcadm get components -r "${KEYCLOAK_REALM}")"
  ldap_id="$(jq -r '.[] | select(.name == "samba-ad" and .providerId == "ldap") | .id' \
    <<<"${components}" | head -n1)"

  mapfile -d '' -t args < <(ldap_component_args "${realm_id}")
  if [[ -n ${ldap_id} ]]; then
    kcadm update "components/${ldap_id}" -r "${KEYCLOAK_REALM}" "${args[@]}" >/dev/null
  else
    kcadm create components -r "${KEYCLOAK_REALM}" "${args[@]}" >/dev/null
    components="$(kcadm get components -r "${KEYCLOAK_REALM}")"
    ldap_id="$(jq -er '.[] | select(.name == "samba-ad" and .providerId == "ldap") | .id' \
      <<<"${components}" | head -n1)"
  fi

  components="$(kcadm get components -r "${KEYCLOAK_REALM}")"
  mapper_id="$(jq -r --arg parent "${ldap_id}" \
    '.[] | select(.parentId == $parent and .name == "samba-groups") | .id' \
    <<<"${components}" | head -n1)"
  mapper_json="$(group_mapper_json "${ldap_id}")"
  if [[ -n ${mapper_id} ]]; then
    kcadm update "components/${mapper_id}" -r "${KEYCLOAK_REALM}" \
      -f - <<<"${mapper_json}" >/dev/null
  else
    kcadm create components -r "${KEYCLOAK_REALM}" \
      -f - <<<"${mapper_json}" >/dev/null
  fi

  kcadm create "user-storage/${ldap_id}/sync?action=triggerFullSync" \
    -r "${KEYCLOAK_REALM}" >/dev/null || \
    die "Keycloak could not synchronize users from Samba"
  users_json="$(kcadm get users -r "${KEYCLOAK_REALM}" --fields username)"
  for username in reviewer ml.engineer data.annotator release.engineer release.approver \
    platform.operator support.analyst comms.publisher finance.operator security.auditor; do
    jq -e --arg username "${username}" \
      'any(.[]; .username == $username)' <<<"${users_json}" >/dev/null || \
      die "Keycloak LDAP sync did not materialize required user: ${username}"
  done

  groups_json="$(kcadm get groups -r "${KEYCLOAK_REALM}")"
  for group in \
    GG-Orion-Researchers GG-Orion-Annotators GG-Orion-Evaluators \
    GG-Release-Engineers GG-Release-Approvers GG-Platform-Operators \
    GG-Support-Agents GG-Communications GG-Finance-Operations \
    GG-Security-Auditors RG-WorkHub-Orion RG-Nextcloud-Orion-Internal \
    RG-Forgejo-Orion-Read RG-Forgejo-Orion-Contribute \
    RG-Jupyter-Orion-Evaluation RG-LabelStudio-Orion-Contribute \
    RG-MLflow-Orion-Read RG-MLflow-Orion-Maintain RG-Harbor-Orion-Review \
    RG-Harbor-Orion-Release RG-Airflow-Orion-View RG-Airflow-Orion-Run \
    RG-Release-Policy-Request RG-Release-Policy-Approve; do
    jq -e --arg group "${group}" 'any(.[]; .name == $group)' \
      <<<"${groups_json}" >/dev/null ||
      die "Keycloak LDAP sync did not materialize required group: ${group}"
  done

  ensure_jupyterhub_client
  ensure_local_group "${PARTNER_NEXTCLOUD_GROUP}"
  ensure_local_group "${PARTNER_WORKHUB_GROUP}"
  ensure_partner_intake_client
  ensure_realm_mail

  log "Keycloak Samba federation, partner groups, and intake service identity are ready"
}

main "$@"
