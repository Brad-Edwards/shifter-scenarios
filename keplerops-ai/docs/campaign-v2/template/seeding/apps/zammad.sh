#!/usr/bin/env bash

set -Eeuo pipefail

SEEDING_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/common.sh
source "${SEEDING_ROOT}/lib/common.sh"

readonly ZAMMAD_SAML_ENTITY_ID=https://support.keplerops.lab/auth/saml/metadata
readonly ZAMMAD_SAML_BASE_URL=https://support.keplerops.lab
readonly ZAMMAD_SAML_IDP_URL="https://id.keplerops.lab/realms/${KEYCLOAK_REALM}/protocol/saml"

kcadm() {
  compose exec -T keycloak /opt/keycloak/bin/kcadm.sh "$@"
}

zammad_ready() {
  compose exec -T --workdir /opt/zammad \
    -e DATABASE_URL="${ZAMMAD_DATABASE_URL}" \
    zammad-railsserver bundle exec rails runner \
    'ActiveRecord::Base.connection.execute("SELECT 1")' >/dev/null 2>&1
}

keycloak_ready() {
  kcadm config credentials \
    --server http://127.0.0.1:8080 \
    --realm master \
    --user "${KEYCLOAK_ADMIN_USER}" \
    --password "${KEYCLOAK_ADMIN_PASSWORD}" >/dev/null 2>&1
}

ensure_saml_mapper() {
  local client_id=$1
  local mapper_name=$2
  local user_property=$3
  local attribute_name=$4
  local mappers mapper_id mapper_json

  mapper_json="$(jq -cn \
    --arg name "${mapper_name}" \
    --arg property "${user_property}" \
    --arg attribute "${attribute_name}" \
    '{
      name: $name,
      protocol: "saml",
      protocolMapper: "saml-user-property-mapper",
      consentRequired: false,
      config: {
        "user.attribute": $property,
        "attribute.name": $attribute,
        "friendly.name": $attribute,
        "attribute.nameformat": "Basic"
      }
    }')"
  mappers="$(kcadm get "clients/${client_id}/protocol-mappers/models" -r "${KEYCLOAK_REALM}")"
  mapper_id="$(jq -r --arg name "${mapper_name}" \
    '.[] | select(.name == $name) | .id' <<<"${mappers}" | head -n1)"
  if [[ -n ${mapper_id} ]]; then
    kcadm delete "clients/${client_id}/protocol-mappers/models/${mapper_id}" \
      -r "${KEYCLOAK_REALM}" >/dev/null
  fi
  kcadm create "clients/${client_id}/protocol-mappers/models" \
    -r "${KEYCLOAK_REALM}" -f - <<<"${mapper_json}" >/dev/null
}

ensure_keycloak_saml_client() {
  local clients client_id client_json

  clients="$(kcadm get clients -r "${KEYCLOAK_REALM}" -q clientId="${ZAMMAD_SAML_ENTITY_ID}")"
  client_id="$(jq -r '.[0].id // empty' <<<"${clients}")"
  client_json="$(jq -cn \
    --arg entity_id "${ZAMMAD_SAML_ENTITY_ID}" \
    --arg base_url "${ZAMMAD_SAML_BASE_URL}" \
    '{
      clientId: $entity_id,
      name: "Orion Support",
      enabled: true,
      protocol: "saml",
      frontchannelLogout: true,
      rootUrl: $base_url,
      baseUrl: ($base_url + "/"),
      redirectUris: [($base_url + "/auth/saml/callback")],
      attributes: {
        "saml_assertion_consumer_url_post": ($base_url + "/auth/saml/callback"),
        "saml_single_logout_service_url_redirect": ($base_url + "/auth/saml/slo"),
        "saml_single_logout_service_url_post": ($base_url + "/auth/saml/slo"),
        "saml.assertion.signature": "true",
        "saml.server.signature": "true",
        "saml.client.signature": "false",
        "saml.encrypt": "false",
        "saml.authnstatement": "true",
        "saml_force_name_id_format": "true",
        "saml_name_id_format": "email",
        "saml.signature.algorithm": "RSA_SHA256",
        "saml.force.post.binding": "true",
        "saml.onetimeuse.condition": "true"
      }
    }')"

  if [[ -n ${client_id} ]]; then
    kcadm update "clients/${client_id}" -r "${KEYCLOAK_REALM}" \
      -f - <<<"${client_json}" >/dev/null
  else
    kcadm create clients -r "${KEYCLOAK_REALM}" -f - \
      <<<"${client_json}" >/dev/null
    clients="$(kcadm get clients -r "${KEYCLOAK_REALM}" -q clientId="${ZAMMAD_SAML_ENTITY_ID}")"
    client_id="$(jq -er '.[0].id' <<<"${clients}")"
  fi

  ensure_saml_mapper "${client_id}" email email email
  ensure_saml_mapper "${client_id}" first_name firstName first_name
  ensure_saml_mapper "${client_id}" last_name lastName last_name
}

keycloak_signing_certificate() {
  local keys active_kid certificate

  keys="$(kcadm get keys -r "${KEYCLOAK_REALM}")"
  active_kid="$(jq -er '.active.RS256' <<<"${keys}")"
  certificate="$(jq -er --arg kid "${active_kid}" \
    '.keys[] | select(.kid == $kid) | .certificate' <<<"${keys}")"
  {
    printf '%s\n' '-----BEGIN CERTIFICATE-----'
    fold -w 64 <<<"${certificate}"
    printf '%s\n' '-----END CERTIFICATE-----'
  }
}

main() {
  require_service zammad-railsserver
  require_service keycloak
  retry 60 3 zammad_ready || die "Zammad Rails environment did not become ready"
  retry 60 2 keycloak_ready || die "Keycloak admin CLI did not become ready"

  ensure_keycloak_saml_client

  local idp_certificate
  idp_certificate="$(keycloak_signing_certificate)"

  compose exec -T \
    --workdir /opt/zammad \
    -e DATABASE_URL="${ZAMMAD_DATABASE_URL}" \
    -e ZAMMAD_SEED_ADMIN_PASSWORD="${ZAMMAD_ADMIN_PASSWORD}" \
    -e ZAMMAD_SEED_REVIEWER_PASSWORD="${REVIEWER_PASSWORD}" \
    -e ZAMMAD_SEED_ML_PASSWORD="${ML_ENGINEER_PASSWORD}" \
    -e ZAMMAD_SEED_RELEASE_PASSWORD="${RELEASE_ENGINEER_PASSWORD}" \
    -e ZAMMAD_SEED_COMMS_PASSWORD="${COMMS_PUBLISHER_PASSWORD}" \
    -e ZAMMAD_SEED_SUPPORT_PASSWORD="${SUPPORT_ANALYST_PASSWORD}" \
    -e ZAMMAD_PARTNER_INTAKE_PASSWORD="${PARTNER_INTAKE_PASSWORD}" \
    -e ZAMMAD_SAML_IDP_URL="${ZAMMAD_SAML_IDP_URL}" \
    -e ZAMMAD_SAML_IDP_CERTIFICATE="${idp_certificate}" \
    zammad-railsserver bundle exec rails runner /dev/stdin \
    < "${SEEDING_ROOT}/payloads/zammad.rb"

  log "Zammad SAML and native role/group state are ready"
}

main "$@"
