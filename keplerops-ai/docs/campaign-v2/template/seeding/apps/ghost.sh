#!/usr/bin/env bash

set -Eeuo pipefail

SEEDING_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/common.sh
source "${SEEDING_ROOT}/lib/common.sh"

ghost_public() {
  curl --silent --show-error --fail-with-body \
    --noproxy '*' \
    --cacert "${caddy_ca}" \
    --resolve "${GHOST_HOST}:443:${GHOST_INGRESS_IP}" \
    --header "Host: ${GHOST_HOST}" \
    --header "Origin: ${GHOST_ORIGIN}" \
    "$@"
}

ghost_admin() {
  curl --silent --show-error --fail-with-body \
    --noproxy '*' \
    --cacert "${caddy_ca}" \
    --resolve "${GHOST_HOST}:443:${GHOST_INGRESS_IP}" \
    --cookie "${cookie_jar}" \
    --header "Host: ${GHOST_HOST}" \
    --header "Origin: ${GHOST_ORIGIN}" \
    --header 'Accept-Version: v5.0' \
    --header 'Content-Type: application/json' \
    "$@"
}

ghost_ready() {
  ghost_public "${GHOST_URL}/ghost/api/admin/authentication/setup/" >/dev/null 2>&1
}

ensure_setup() {
  local setup payload
  setup="$(ghost_public "${GHOST_URL}/ghost/api/admin/authentication/setup/")"
  if jq -e '.setup[0].status == true' <<<"${setup}" >/dev/null; then
    return 0
  fi

  payload="$(jq -cn \
    --arg name "${GHOST_OWNER_NAME}" \
    --arg email "${GHOST_OWNER_EMAIL}" \
    --arg password "${GHOST_OWNER_PASSWORD}" \
    --arg title "${GHOST_SITE_TITLE}" \
    '{setup:[{name:$name,email:$email,password:$password,blogTitle:$title}]}')"
  ghost_public \
    --header 'Content-Type: application/json' \
    --request POST --data "${payload}" \
    "${GHOST_URL}/ghost/api/admin/authentication/setup/" >/dev/null
}

login() {
  local payload
  payload="$(jq -cn --arg username "${GHOST_OWNER_EMAIL}" \
    --arg password "${GHOST_OWNER_PASSWORD}" \
    '{username:$username,password:$password}')"
  ghost_public \
    --cookie-jar "${cookie_jar}" \
    --header 'Content-Type: application/json' \
    --request POST --data "${payload}" \
    "${GHOST_URL}/ghost/api/admin/session/" >/dev/null
}

ensure_site_title() {
  local payload
  payload="$(jq -cn --arg title "${GHOST_SITE_TITLE}" \
    '{settings:[{key:"title",value:$title}]}')"
  ghost_admin --request PUT --data "${payload}" \
    "${GHOST_URL}/ghost/api/admin/settings/" >/dev/null
}

ensure_status_post() {
  local posts post_id updated_at html payload
  posts="$(ghost_admin --get \
    --data-urlencode 'filter=slug:operational-baseline' \
    --data 'formats=html' \
    "${GHOST_URL}/ghost/api/admin/posts/")"
  html="$(<"${SEEDING_ROOT}/payloads/ghost-status.html")"

  if jq -e '.posts | length > 0' <<<"${posts}" >/dev/null; then
    post_id="$(jq -er '.posts[0].id' <<<"${posts}")"
    updated_at="$(jq -er '.posts[0].updated_at' <<<"${posts}")"
    payload="$(jq -cn --arg id "${post_id}" --arg updated_at "${updated_at}" \
      --arg html "${html}" \
      '{posts:[{id:$id,updated_at:$updated_at,title:"Operational Baseline",slug:"operational-baseline",status:"published",custom_excerpt:"Routine service availability information for Kepler Operations.",html:$html}]}')"
    ghost_admin --request PUT --data "${payload}" \
      "${GHOST_URL}/ghost/api/admin/posts/${post_id}/?source=html" >/dev/null
  else
    payload="$(jq -cn --arg html "${html}" \
      '{posts:[{title:"Operational Baseline",slug:"operational-baseline",status:"published",custom_excerpt:"Routine service availability information for Kepler Operations.",html:$html}]}')"
    ghost_admin --request POST --data "${payload}" \
      "${GHOST_URL}/ghost/api/admin/posts/?source=html" >/dev/null
  fi
}

main() {
  require_service ghost
  cookie_jar="$(mktemp)"
  caddy_ca="$(mktemp)"
  trap 'rm -f "${cookie_jar}" "${caddy_ca}"' EXIT
  compose exec -T caddy cat /data/caddy/pki/authorities/local/root.crt >"${caddy_ca}"

  retry 60 3 ghost_ready || die "Ghost setup API did not become ready"
  ensure_setup
  login
  ensure_site_title
  ensure_status_post
  log "Ghost clean state is ready"
}

cookie_jar=
main "$@"
