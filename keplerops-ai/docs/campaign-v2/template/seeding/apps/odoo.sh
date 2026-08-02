#!/usr/bin/env bash

set -Eeuo pipefail

SEEDING_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/common.sh
source "${SEEDING_ROOT}/lib/common.sh"

: "${ODOO_OIDC_CLIENT_ID:=odoo}"
: "${ODOO_OIDC_CLIENT_SECRET:=KeplerV2-Training-Odoo-OIDC}"
: "${FINANCE_OPERATOR_PASSWORD:=KeplerV2-Training-Finance}"
: "${SECURITY_AUDITOR_PASSWORD:=KeplerV2-Training-Auditor}"

kcadm() {
  compose exec -T keycloak /opt/keycloak/bin/kcadm.sh "$@"
}

keycloak_ready() {
  kcadm config credentials \
    --server http://127.0.0.1:8080 \
    --realm master \
    --user "${KEYCLOAK_ADMIN_USER}" \
    --password "${KEYCLOAK_ADMIN_PASSWORD}" >/dev/null 2>&1
}

ensure_oidc_client() {
  local clients client_uuid client_json
  clients="$(kcadm get clients -r "${KEYCLOAK_REALM}" -q clientId="${ODOO_OIDC_CLIENT_ID}")"
  client_uuid="$(jq -r '.[0].id // empty' <<<"${clients}")"
  client_json="$(jq -cn \
    --arg client_id "${ODOO_OIDC_CLIENT_ID}" \
    --arg client_secret "${ODOO_OIDC_CLIENT_SECRET}" \
    '{
      clientId: $client_id,
      name: "KeplerOps Business Operations",
      enabled: true,
      protocol: "openid-connect",
      publicClient: false,
      secret: $client_secret,
      standardFlowEnabled: true,
      implicitFlowEnabled: false,
      directAccessGrantsEnabled: false,
      serviceAccountsEnabled: false,
      redirectUris: ["https://business.keplerops.lab/auth_oauth/signin"],
      webOrigins: ["https://business.keplerops.lab"],
      attributes: {
        "post.logout.redirect.uris": "https://business.keplerops.lab/*",
        "pkce.code.challenge.method": "S256"
      }
    }')"

  if [[ -n ${client_uuid} ]]; then
    kcadm update "clients/${client_uuid}" -r "${KEYCLOAK_REALM}" \
      -f - <<<"${client_json}" >/dev/null
  else
    kcadm create clients -r "${KEYCLOAK_REALM}" -f - \
      <<<"${client_json}" >/dev/null
  fi
}

keycloak_subject() {
  local username=$1
  local users
  users="$(kcadm get users -r "${KEYCLOAK_REALM}" \
    -q "username=${username}" --fields id,username)"
  jq -er --arg username "${username}" \
    '.[] | select(.username == $username) | .id' <<<"${users}" | head -n1
}

odoo_db_args() {
  printf '%s\n' \
    --database "${ODOO_DATABASE}" \
    --db_host "${ODOO_DB_HOST}" \
    --db_port "${ODOO_DB_PORT}" \
    --db_user "${ODOO_DB_USER}" \
    --db_password "${ODOO_DB_PASSWORD}"
}

main() {
  local -a db_args
  local finance_subject auditor_subject
  require_command jq
  require_service odoo
  require_service keycloak
  mapfile -t db_args < <(odoo_db_args)

  retry 60 2 keycloak_ready || die "Keycloak admin authentication failed"
  kcadm get "realms/${KEYCLOAK_REALM}" >/dev/null 2>&1 ||
    die "Keycloak realm is unavailable: ${KEYCLOAK_REALM}"
  ensure_oidc_client
  finance_subject="$(keycloak_subject finance.operator)"
  auditor_subject="$(keycloak_subject security.auditor)"
  [[ -n ${finance_subject} ]] || die "Keycloak user is unavailable: finance.operator"
  [[ -n ${auditor_subject} ]] || die "Keycloak user is unavailable: security.auditor"

  compose exec -T odoo odoo "${db_args[@]}" \
    --init base,account,l10n_de,auth_oidc --without-demo=all --stop-after-init

  compose exec -T \
    -e ODOO_SEED_ADMIN_PASSWORD="${ODOO_ADMIN_PASSWORD}" \
    -e ODOO_OIDC_CLIENT_ID="${ODOO_OIDC_CLIENT_ID}" \
    -e ODOO_OIDC_CLIENT_SECRET="${ODOO_OIDC_CLIENT_SECRET}" \
    -e ODOO_OIDC_REALM="${KEYCLOAK_REALM}" \
    -e ODOO_FINANCE_SUBJECT="${finance_subject}" \
    -e ODOO_AUDITOR_SUBJECT="${auditor_subject}" \
    -e ODOO_FINANCE_PASSWORD="${FINANCE_OPERATOR_PASSWORD}" \
    -e ODOO_AUDITOR_PASSWORD="${SECURITY_AUDITOR_PASSWORD}" \
    odoo odoo shell "${db_args[@]}" \
    < "${SEEDING_ROOT}/payloads/odoo.py"

  log "Odoo OIDC identities, native groups, and record rules are ready"
}

main "$@"
