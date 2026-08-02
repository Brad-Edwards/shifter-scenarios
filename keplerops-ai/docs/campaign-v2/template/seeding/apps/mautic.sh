#!/usr/bin/env bash

set -Eeuo pipefail

SEEDING_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/common.sh
source "${SEEDING_ROOT}/lib/common.sh"

readonly MAUTIC_SAML_SP_ENTITY_ID="${MAUTIC_SITE_URL}"
readonly MAUTIC_SAML_ACS_URL="${MAUTIC_SITE_URL}/s/saml/login_check"
readonly MAUTIC_SAML_IDP_ENTITY_ID="https://id.keplerops.lab/realms/${KEYCLOAK_REALM}"
readonly MAUTIC_SAML_DESCRIPTOR_URL="${MAUTIC_SAML_IDP_ENTITY_ID}/protocol/saml/descriptor"

kcadm() {
  compose exec -T keycloak /opt/keycloak/bin/kcadm.sh "$@"
}

mautic_console() {
  compose exec -T --user www-data mautic php /var/www/html/bin/console "$@"
}

mautic_files_ready() {
  compose exec -T mautic test -f /var/www/html/bin/console >/dev/null 2>&1
}

mautic_installed() {
  # PHP reads its own variables in the container.
  # shellcheck disable=SC2016
  compose exec -T mautic php -r \
    'include("/var/www/html/config/local.php"); exit(!empty($parameters["db_driver"]) && !empty($parameters["site_url"]) ? 0 : 1);' \
    >/dev/null 2>&1
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

  clients="$(kcadm get clients -r "${KEYCLOAK_REALM}" -q clientId="${MAUTIC_SAML_SP_ENTITY_ID}")"
  client_id="$(jq -r '.[0].id // empty' <<<"${clients}")"
  client_json="$(jq -cn \
    --arg entity_id "${MAUTIC_SAML_SP_ENTITY_ID}" \
    --arg base_url "${MAUTIC_SITE_URL}" \
    --arg acs_url "${MAUTIC_SAML_ACS_URL}" \
    '{
      clientId: $entity_id,
      name: "KeplerOps Product Communications",
      enabled: true,
      protocol: "saml",
      frontchannelLogout: false,
      rootUrl: $base_url,
      baseUrl: ($base_url + "/"),
      redirectUris: [$acs_url],
      attributes: {
        "saml_assertion_consumer_url_post": $acs_url,
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
    clients="$(kcadm get clients -r "${KEYCLOAK_REALM}" -q clientId="${MAUTIC_SAML_SP_ENTITY_ID}")"
    client_id="$(jq -er '.[0].id' <<<"${clients}")"
  fi

  ensure_saml_mapper "${client_id}" email email email
  ensure_saml_mapper "${client_id}" username username username
  ensure_saml_mapper "${client_id}" first_name firstName firstname
  ensure_saml_mapper "${client_id}" last_name lastName lastname
}

read_idp_metadata() {
  curl --silent --show-error --fail-with-body \
    --noproxy '*' \
    --cacert "${caddy_ca}" \
    --resolve id.keplerops.lab:443:10.61.20.2 \
    "${MAUTIC_SAML_DESCRIPTOR_URL}"
}

ensure_communications_role() {
  local output role_id
  output="$(compose exec -T --user www-data \
    --workdir /var/www/html \
    mautic php < "${SEEDING_ROOT}/payloads/mautic-communications-role.php")"
  role_id="$(sed -n 's/^ROLE_ID=//p' <<<"${output}" | tail -n1)"
  [[ ${role_id} =~ ^[0-9]+$ ]] || die "Mautic Communications role did not return a native role ID"
  printf '%s\n' "${role_id}"
}

configure_application() {
  local metadata_b64=$1
  local role_id=$2
  # PHP reads its own variables in the container.
  # shellcheck disable=SC2016
  compose exec -T \
    -e MAUTIC_SAML_METADATA_B64="${metadata_b64}" \
    -e MAUTIC_SAML_ROLE_ID="${role_id}" \
    mautic php -r '
      $path = "/var/www/html/config/local.php";
      $parameters = [];
      if (file_exists($path)) { include $path; }
      $parameters["api_enabled"] = 1;
      $parameters["api_enable_basic_auth"] = true;
      $parameters["trusted_proxies"] = ["10.61.70.2"];
      $parameters["mailer_dsn"] = "smtp://advisories:KeplerV2-Training-Synthetic-Business@stalwart:587?verify_peer=0";
      $parameters["mailer_from_email"] = "advisories@keplerops.lab";
      $parameters["mailer_from_name"] = "KeplerOps Product Safety";
      $parameters["saml_idp_metadata"] = getenv("MAUTIC_SAML_METADATA_B64");
      $siteUrl = rtrim((string) ($parameters["site_url"] ?? ""), "/");
      if ($siteUrl === "") { exit(1); }
      // Mautic's legacy key names the SP's own entity ID, not the IdP entity ID.
      $parameters["saml_idp_entity_id"] = $siteUrl;
      $parameters["saml_idp_own_certificate"] = "";
      $parameters["saml_idp_own_private_key"] = "";
      $parameters["saml_idp_own_password"] = "";
      $parameters["saml_idp_email_attribute"] = "email";
      $parameters["saml_idp_username_attribute"] = "username";
      $parameters["saml_idp_firstname_attribute"] = "firstname";
      $parameters["saml_idp_lastname_attribute"] = "lastname";
      $parameters["saml_idp_default_role"] = (int) getenv("MAUTIC_SAML_ROLE_ID");
      $export = "<?php\n$" . "parameters = " . var_export($parameters, true) . ";\n";
      if (file_put_contents($path, $export) === false) { exit(1); }
    '
}

main() {
  local metadata metadata_b64 role_id
  require_command jq
  require_service mautic
  require_service keycloak
  caddy_ca="$(mktemp)"
  trap 'rm -f "${caddy_ca}"' EXIT
  compose exec -T caddy cat /data/caddy/pki/authorities/local/root.crt >"${caddy_ca}"

  retry 60 3 mautic_files_ready || die "Mautic application files did not become ready"

  if ! mautic_installed; then
    mautic_console mautic:install "${MAUTIC_SITE_URL}" --force \
      --db_driver=pdo_mysql \
      --db_host="${MAUTIC_DB_HOST}" \
      --db_port="${MAUTIC_DB_PORT}" \
      --db_name="${MAUTIC_DB_NAME}" \
      --db_user="${MAUTIC_DB_USER}" \
      --db_password="${MAUTIC_DB_PASSWORD}" \
      --db_backup_tables=false \
      --admin_firstname=Range \
      --admin_lastname=Administrator \
      --admin_username="${MAUTIC_ADMIN_USER}" \
      --admin_email="${MAUTIC_ADMIN_EMAIL}" \
      --admin_password="${MAUTIC_ADMIN_PASSWORD}" \
      --no-interaction
    log "Mautic baseline installed"
  fi

  mautic_console doctrine:migrations:migrate --no-interaction
  mautic_console mautic:plugins:reload
  retry 60 2 keycloak_ready || die "Keycloak admin authentication failed"
  ensure_keycloak_saml_client
  metadata="$(read_idp_metadata)"
  grep -Eq '<([[:alnum:]_-]+:)?EntityDescriptor([[:space:]>])' <<<"${metadata}" ||
    die "Keycloak returned invalid SAML metadata"
  metadata_b64="$(printf '%s' "${metadata}" | base64 --wrap=0)"
  role_id="$(ensure_communications_role)"
  configure_application "${metadata_b64}" "${role_id}"
  mautic_console cache:clear --no-warmup
  log "Mautic SAML and native non-admin Communications role are ready"
}

caddy_ca=
main "$@"
