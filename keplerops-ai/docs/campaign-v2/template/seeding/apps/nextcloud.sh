#!/usr/bin/env bash

set -Eeuo pipefail

SEEDING_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/common.sh
source "${SEEDING_ROOT}/lib/common.sh"

occ() {
  compose exec -T --user www-data nextcloud php /var/www/html/occ "$@"
}

nextcloud_ready() {
  occ status --output=json 2>/dev/null | jq -e '.installed == true' >/dev/null
}

ensure_user() {
  local username=$1
  local display_name=$2
  local password=$3

  if occ user:info "${username}" >/dev/null 2>&1; then
    compose exec -T --user www-data -e OC_PASS="${password}" nextcloud \
      php /var/www/html/occ user:resetpassword --password-from-env "${username}" >/dev/null
  else
    compose exec -T --user www-data -e OC_PASS="${password}" nextcloud \
      php /var/www/html/occ user:add --password-from-env \
      --display-name "${display_name}" "${username}" >/dev/null
  fi

  occ group:adduser "${NEXTCLOUD_GROUP}" "${username}" >/dev/null
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

  share_id="$(jq -r --arg group "${NEXTCLOUD_GROUP}" \
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
      --data-urlencode "shareWith=${NEXTCLOUD_GROUP}" \
      --data 'permissions=31' \
      --data 'format=json' \
      "${NEXTCLOUD_URL}/ocs/v2.php/apps/files_sharing/api/v1/shares")"
  fi
  jq -e '.ocs.meta.status == "ok"' <<<"${response}" >/dev/null || \
    die "Nextcloud rejected the room share reconciliation"
}

main() {
  require_service nextcloud
  retry 60 3 nextcloud_ready || die "Nextcloud did not become ready"

  occ group:add "${NEXTCLOUD_GROUP}" >/dev/null 2>&1 || true
  ensure_user reviewer 'Rina Chen' "${REVIEWER_PASSWORD}"
  ensure_user ml.engineer 'Maya Ortiz' "${ML_ENGINEER_PASSWORD}"
  ensure_user release.engineer 'Elliot Park' "${RELEASE_ENGINEER_PASSWORD}"
  ensure_user comms.publisher 'Samira Okafor' "${COMMS_PUBLISHER_PASSWORD}"
  ensure_user support.analyst 'Jonas Becker' "${SUPPORT_ANALYST_PASSWORD}"
  ensure_room

  log "Nextcloud clean state is ready"
}

main "$@"
