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

ensure_principal() {
  local record=$1
  local name type status password_var password payload current
  name="$(jq -er '.name' <<<"${record}")"
  type="$(jq -er '.type' <<<"${record}")"
  current="$(principal_record "${name}")"

  if ! jq -e '.error == "notFound"' <<<"${current}" >/dev/null; then
    log "Stalwart ${type} already exists: ${name}"
    return 0
  fi

  if [[ ${type} == domain ]]; then
    payload="$(jq -c 'del(.password_env)' <<<"${record}")"
  else
    password_var="$(jq -er '.password_env' <<<"${record}")"
    password="${!password_var:-}"
    [[ -n ${password} ]] || die "Stalwart password variable is empty: ${password_var}"
    payload="$(jq -c --arg password "${password}" \
      'del(.password_env) | .secrets=[$password]' <<<"${record}")"
  fi

  status="$(http_code POST "${STALWART_API_URL}/api/principal" \
    --user "${STALWART_ADMIN_USER}:${STALWART_ADMIN_PASSWORD}" \
    --header 'Content-Type: application/json' \
    --data "${payload}")"
  [[ ${status} =~ ^2 ]] || die "Stalwart creation for ${name} returned HTTP ${status}"
  log "Stalwart ${type} created: ${name}"
}

main() {
  require_service stalwart
  retry 30 2 stalwart_request GET /api/principal >/dev/null || \
    die "Stalwart 0.13 management API did not become ready"

  while IFS= read -r record; do
    ensure_principal "${record}"
  done < <(jq -c '.[]' "${SEEDING_ROOT}/payloads/stalwart-principals.json")

  log "Stalwart clean state is ready"
}

main "$@"
