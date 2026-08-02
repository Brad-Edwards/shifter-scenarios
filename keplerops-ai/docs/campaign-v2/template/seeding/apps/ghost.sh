#!/usr/bin/env bash

set -Eeuo pipefail

SEEDING_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/common.sh
source "${SEEDING_ROOT}/lib/common.sh"

: "${GHOST_EDITOR_NAME:=Samira Okafor}"
: "${GHOST_EDITOR_EMAIL:=comms.publisher@keplerops.lab}"
: "${GHOST_EDITOR_PASSWORD:=${COMMS_PUBLISHER_PASSWORD}}"

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
  local cookie_jar=$1
  shift
  ghost_public \
    --cookie "${cookie_jar}" \
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
  local cookie_jar=$1
  local username=$2
  local password=$3
  local payload
  payload="$(jq -cn --arg username "${username}" --arg password "${password}" \
    '{username:$username,password:$password}')"
  ghost_public \
    --cookie-jar "${cookie_jar}" \
    --header 'Content-Type: application/json' \
    --request POST --data "${payload}" \
    "${GHOST_URL}/ghost/api/admin/session/" >/dev/null
}

user_by_email() {
  local cookie_jar=$1
  local email=$2
  ghost_admin "${cookie_jar}" --get \
    --data-urlencode "filter=email:${email}" \
    --data 'include=roles' \
    "${GHOST_URL}/ghost/api/admin/users/"
}

ensure_owner_identity() {
  local users user_id updated_at payload
  users="$(user_by_email "${owner_cookie}" "${GHOST_OWNER_EMAIL}")"
  user_id="$(jq -er '.users[0].id' <<<"${users}")"
  updated_at="$(jq -er '.users[0].updated_at' <<<"${users}")"
  payload="$(jq -cn \
    --arg id "${user_id}" \
    --arg updated_at "${updated_at}" \
    --arg name "${GHOST_OWNER_NAME}" \
    '{users:[{id:$id,updated_at:$updated_at,name:$name}]}')"
  ghost_admin "${owner_cookie}" --request PUT --data "${payload}" \
    "${GHOST_URL}/ghost/api/admin/users/${user_id}/" >/dev/null
}

ensure_site_title() {
  local payload
  payload="$(jq -cn --arg title "${GHOST_SITE_TITLE}" \
    '{settings:[{key:"title",value:$title}]}')"
  ghost_admin "${owner_cookie}" --request PUT --data "${payload}" \
    "${GHOST_URL}/ghost/api/admin/settings/" >/dev/null
}

editor_role_id() {
  ghost_admin "${owner_cookie}" --get \
    --data-urlencode 'filter=name:Editor' \
    "${GHOST_URL}/ghost/api/admin/roles/" |
    jq -er '.roles[] | select(.name == "Editor") | .id' |
    head -n1
}

invite_token() {
  compose exec -T \
    -e MYSQL_PWD=KeplerV2-Training-GhostDB \
    mariadb mariadb --batch --skip-column-names \
    --user=ghost ghost \
    --execute="SELECT token FROM invites WHERE email='${GHOST_EDITOR_EMAIL}' AND status='sent' ORDER BY created_at DESC LIMIT 1"
}

encode_invite_token() {
  local token=$1
  compose exec -T \
    --workdir /var/lib/ghost/current \
    -e GHOST_INVITE_TOKEN="${token}" \
    ghost node -e \
    "process.stdout.write(require('@tryghost/security').url.encodeBase64(process.env.GHOST_INVITE_TOKEN))"
}

ensure_editor() {
  local users role_id payload raw_token encoded_token
  users="$(user_by_email "${owner_cookie}" "${GHOST_EDITOR_EMAIL}")"
  if jq -e '.users | length > 0' <<<"${users}" >/dev/null; then
    jq -e '.users[0].roles | any(.name == "Editor")' <<<"${users}" >/dev/null ||
      die "Ghost editor identity exists without the native Editor role"
    return 0
  fi

  role_id="$(editor_role_id)"
  payload="$(jq -cn --arg email "${GHOST_EDITOR_EMAIL}" --arg role_id "${role_id}" \
    '{invites:[{email:$email,role_id:$role_id}]}')"
  ghost_admin "${owner_cookie}" --request POST --data "${payload}" \
    "${GHOST_URL}/ghost/api/admin/invites/" >/dev/null

  raw_token="$(invite_token)"
  [[ -n ${raw_token} ]] || die "Ghost did not persist an Editor invitation token"
  encoded_token="$(encode_invite_token "${raw_token}")"
  payload="$(jq -cn \
    --arg email "${GHOST_EDITOR_EMAIL}" \
    --arg name "${GHOST_EDITOR_NAME}" \
    --arg password "${GHOST_EDITOR_PASSWORD}" \
    --arg token "${encoded_token}" \
    '{invitation:[{email:$email,name:$name,password:$password,token:$token}]}')"
  ghost_public \
    --header 'Content-Type: application/json' \
    --request POST --data "${payload}" \
    "${GHOST_URL}/ghost/api/admin/authentication/invitation/" >/dev/null

  users="$(user_by_email "${owner_cookie}" "${GHOST_EDITOR_EMAIL}")"
  jq -e '.users[0].roles | any(.name == "Editor")' <<<"${users}" >/dev/null ||
    die "Ghost Editor activation did not produce the native Editor role"
}

ensure_owned_post() {
  local cookie_jar=$1
  local author_id=$2
  local author_email=$3
  local slug=$4
  local title=$5
  local excerpt=$6
  local payload_path=$7
  local posts post_id updated_at html payload result

  posts="$(ghost_admin "${cookie_jar}" --get \
    --data-urlencode "filter=slug:${slug}" \
    --data 'formats=html' \
    --data 'include=authors' \
    "${GHOST_URL}/ghost/api/admin/posts/")"
  html="$(<"${payload_path}")"

  if jq -e '.posts | length > 0' <<<"${posts}" >/dev/null; then
    post_id="$(jq -er '.posts[0].id' <<<"${posts}")"
    updated_at="$(jq -er '.posts[0].updated_at' <<<"${posts}")"
    payload="$(jq -cn \
      --arg id "${post_id}" \
      --arg updated_at "${updated_at}" \
      --arg author_id "${author_id}" \
      --arg title "${title}" \
      --arg slug "${slug}" \
      --arg excerpt "${excerpt}" \
      --arg html "${html}" \
      '{posts:[{id:$id,updated_at:$updated_at,title:$title,slug:$slug,status:"published",custom_excerpt:$excerpt,authors:[{id:$author_id}],html:$html}]}')"
    result="$(ghost_admin "${cookie_jar}" --request PUT --data "${payload}" \
      "${GHOST_URL}/ghost/api/admin/posts/${post_id}/?source=html&include=authors")"
  else
    payload="$(jq -cn \
      --arg author_id "${author_id}" \
      --arg title "${title}" \
      --arg slug "${slug}" \
      --arg excerpt "${excerpt}" \
      --arg html "${html}" \
      '{posts:[{title:$title,slug:$slug,status:"published",custom_excerpt:$excerpt,authors:[{id:$author_id}],html:$html}]}')"
    result="$(ghost_admin "${cookie_jar}" --request POST --data "${payload}" \
      "${GHOST_URL}/ghost/api/admin/posts/?source=html&include=authors")"
  fi

  jq -e --arg email "${author_email}" \
    '.posts[0].authors | any(.email == $email)' <<<"${result}" >/dev/null ||
    die "Ghost post ownership was not assigned to ${author_email}: ${slug}"
}

main() {
  local editor_user editor_id
  require_command jq
  require_service ghost
  require_service mariadb
  owner_cookie="$(mktemp)"
  editor_cookie="$(mktemp)"
  caddy_ca="$(mktemp)"
  trap 'rm -f "${owner_cookie}" "${editor_cookie}" "${caddy_ca}"' EXIT
  compose exec -T caddy cat /data/caddy/pki/authorities/local/root.crt >"${caddy_ca}"

  retry 60 3 ghost_ready || die "Ghost setup API did not become ready"
  ensure_setup
  login "${owner_cookie}" "${GHOST_OWNER_EMAIL}" "${GHOST_OWNER_PASSWORD}"
  ensure_owner_identity
  ensure_site_title
  ensure_editor
  login "${editor_cookie}" "${GHOST_EDITOR_EMAIL}" "${GHOST_EDITOR_PASSWORD}"

  editor_user="$(user_by_email "${owner_cookie}" "${GHOST_EDITOR_EMAIL}")"
  editor_id="$(jq -er '.users[0].id' <<<"${editor_user}")"

  ensure_owned_post \
    "${editor_cookie}" "${editor_id}" "${GHOST_EDITOR_EMAIL}" \
    service-availability 'Service Availability' \
    'Current availability information for Orion services.' \
    "${SEEDING_ROOT}/payloads/ghost-status.html"
  ensure_owned_post \
    "${editor_cookie}" "${editor_id}" "${GHOST_EDITOR_EMAIL}" \
    scheduled-maintenance-window 'Scheduled Maintenance Window' \
    'Customer information for the scheduled Orion maintenance window.' \
    "${SEEDING_ROOT}/payloads/ghost-editorial.html"

  log "Ghost owner, Editor, and native content ownership are ready"
}

owner_cookie=
editor_cookie=
caddy_ca=
main "$@"
