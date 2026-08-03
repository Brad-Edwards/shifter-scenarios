#!/usr/bin/env bash

set -Eeuo pipefail

SEEDING_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/common.sh
source "${SEEDING_ROOT}/lib/common.sh"

stalwart_request() {
  local method=$1
  local path=$2
  shift 2
  curl --silent --show-error \
    --fail-with-body \
    --user "${STALWART_ADMIN_USER}:${STALWART_ADMIN_PASSWORD}" \
    --header 'Content-Type: application/json' \
    --request "${method}" "$@" "${STALWART_API_URL}${path}"
}

principal_record() {
  local name=$1
  stalwart_request GET "/api/principal/$(urlencode "${name}")"
}

ensure_domain() {
  local record=$1
  local name status payload current updates
  name="$(jq -er '.name' <<<"${record}")"
  current="$(principal_record "${name}")"

  if ! jq -e '.error == "notFound"' <<<"${current}" >/dev/null; then
    updates="$(jq -c '
      [to_entries[]
       | select(.key == "description"
                or .key == "emails"
                or .key == "roles"
                or .key == "memberOf"
                or .key == "quota")
       | {action: "set", field: .key, value: .value}]
    ' <<<"${record}")"
    status="$(http_code PATCH "${STALWART_API_URL}/api/principal/$(urlencode "${name}")" \
      --user "${STALWART_ADMIN_USER}:${STALWART_ADMIN_PASSWORD}" \
      --header 'Content-Type: application/json' \
      --data "${updates}")"
    [[ ${status} =~ ^2 ]] || die "Stalwart reconciliation for ${name} returned HTTP ${status}"
    log "Stalwart domain reconciled: ${name}"
    return 0
  fi

  payload="$(jq -c 'del(.source, .ou, .password, .password_env)' <<<"${record}")"
  status="$(http_code POST "${STALWART_API_URL}/api/principal" \
    --user "${STALWART_ADMIN_USER}:${STALWART_ADMIN_PASSWORD}" \
    --header 'Content-Type: application/json' \
    --data "${payload}")"
  [[ ${status} =~ ^2 ]] || die "Stalwart creation for ${name} returned HTTP ${status}"
  log "Stalwart domain created: ${name}"
}

clear_legacy_secret() {
  local record=$1
  local name status
  name="$(jq -er '.name' <<<"${record}")"
  status="$(http_code PATCH "${STALWART_API_URL}/api/principal/$(urlencode "${name}")" \
    --user "${STALWART_ADMIN_USER}:${STALWART_ADMIN_PASSWORD}" \
    --header 'Content-Type: application/json' \
    --data '[{"action":"set","field":"secrets","value":[]}]')"
  if [[ ${status} =~ ^2 ]]; then
    log "Stalwart legacy local secret removed: ${name}"
  elif [[ ${status} != 404 ]]; then
    die "Stalwart secret cleanup for ${name} returned HTTP ${status}"
  fi
}

retire_local_principal() {
  local record=$1
  local name status
  name="$(jq -er '.name' <<<"${record}")"
  status="$(http_code DELETE \
    "${STALWART_API_URL}/api/principal/$(urlencode "${name}")" \
    --user "${STALWART_ADMIN_USER}:${STALWART_ADMIN_PASSWORD}")"
  if [[ ${status} =~ ^2 ]]; then
    log "Stalwart obsolete local alias retired: ${name}"
  elif [[ ${status} != 404 ]]; then
    die "Stalwart retirement for ${name} returned HTTP ${status}"
  fi
}

reconcile_record() {
  local record=$1
  local type source
  type="$(jq -er '.type' <<<"${record}")"
  source="$(jq -r '.source // "internal"' <<<"${record}")"

  if [[ ${type} == domain ]]; then
    ensure_domain "${record}"
  elif [[ ${source} == retired-local ]]; then
    retire_local_principal "${record}"
  elif [[ ${source} == corp-* ]]; then
    # Accounts and credentials are owned by CORP. Stalwart retains mailbox data
    # locally, but any pre-migration local password material must not survive.
    clear_legacy_secret "${record}"
  else
    die "unsupported Stalwart principal source for $(jq -r '.name' <<<"${record}"): ${source}"
  fi
}

main() {
  require_service stalwart
  retry 30 2 stalwart_request GET /api/principal >/dev/null || \
    die "Stalwart 0.13 management API did not become ready"

  while IFS= read -r record; do
    reconcile_record "${record}"
  done < <(jq -c '.[]' "${SEEDING_ROOT}/payloads/stalwart-principals.json")

  log "Stalwart domains and directory-backed mailbox state are ready"
}

main "$@"
