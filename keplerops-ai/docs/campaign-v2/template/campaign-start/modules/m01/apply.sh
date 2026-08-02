#!/usr/bin/env bash
set -Eeuo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MODULE_ROOT
TEMPLATE_ROOT="$(cd "${MODULE_ROOT}/../../.." && pwd)"
readonly TEMPLATE_ROOT
readonly PAYLOAD_ROOT="${MODULE_ROOT}/payloads"
readonly STATE_ROOT="${CAMPAIGN_STATE_ROOT:-${TEMPLATE_ROOT}/state/campaign-start}/m01"
readonly QDRANT_WRITE_URL="${QDRANT_WRITE_URL:-http://10.61.50.72:6333}"
readonly QDRANT_WRITE_KEY="${QDRANT_WRITE_KEY:-KeplerV2-Training-Qdrant-Write}"
readonly QDRANT_COLLECTION="${QDRANT_COLLECTION:-orion_partner_intake}"
readonly NEXTCLOUD_URL="${NEXTCLOUD_URL:-http://10.61.30.23}"
readonly NEXTCLOUD_HOST="${NEXTCLOUD_HOST:-files.keplerops.lab}"
readonly NEXTCLOUD_USER="${NEXTCLOUD_ADMIN_USER:-range-admin}"
readonly NEXTCLOUD_PASSWORD="${NEXTCLOUD_ADMIN_PASSWORD:-KeplerV2-Training-Nextcloud}"
readonly NEXTCLOUD_OWNER_USER="${NEXTCLOUD_REVIEW_USER:-reviewer}"
readonly NEXTCLOUD_OWNER_PASSWORD="${NEXTCLOUD_REVIEW_PASSWORD:-KeplerV2-Training-Reviewer}"

die() { printf '[m01] ERROR: %s\n' "$*" >&2; exit 1; }
log() { printf '[m01] %s\n' "$*" >&2; }

require_commands() {
  local command
  for command in curl docker install jq python3 sha256sum; do
    command -v "${command}" >/dev/null 2>&1 || die "missing command: ${command}"
  done
}

compose() {
  docker compose --project-directory "${TEMPLATE_ROOT}" \
    --env-file "${TEMPLATE_ROOT}/component-lock.env" \
    --env-file "${TEMPLATE_ROOT}/engineering/component-lock.additions.env" \
    -f "${TEMPLATE_ROOT}/compose.foundation.yaml" \
    -f "${TEMPLATE_ROOT}/compose.enterprise.yaml" \
    -f "${TEMPLATE_ROOT}/compose.engineering.yaml" \
    -f "${MODULE_ROOT}/compose.overlay.yaml" "$@"
}

deploy_release_service() {
  compose up -d --build --no-deps orion-release-operations >/dev/null
  docker exec kep-v2-pdns-auth pdnsutil replace-rrset keplerops.lab release A 60 10.61.10.2 >/dev/null
  docker exec kep-v2-pdns-recursor rec_control wipe-cache 'keplerops.lab$' >/dev/null
  {
    cat "${TEMPLATE_ROOT}/config/caddy/Caddyfile"
    find "${TEMPLATE_ROOT}/campaign-start/modules" -path '*/runtime/Caddyfile.fragment' -type f -print0 | sort -z | xargs -0 cat
  } | docker exec -i kep-v2-caddy sh -eu -c 'cat >/tmp/Caddyfile.campaign-start'
  docker exec kep-v2-caddy caddy reload --config /tmp/Caddyfile.campaign-start --adapter caddyfile >/dev/null
  for _ in $(seq 1 60); do
    curl -kfsS --resolve release.keplerops.lab:443:10.61.10.2 \
      https://release.keplerops.lab/health/ready >/dev/null 2>&1 && return
    sleep 2
  done
  die 'Orion Release Operations did not become ready'
}

feature_vector() {
  python3 -c '
import hashlib, json, math, re, sys
vector = [0.0] * 128
for token in re.findall(r"[a-z0-9_]+", sys.stdin.read().lower()):
    digest = hashlib.sha256(token.encode()).digest()
    bucket = int.from_bytes(digest[:4], "big") % 128
    vector[bucket] += 1.0 if digest[4] & 1 else -1.0
norm = math.sqrt(sum(value * value for value in vector)) or 1.0
json.dump([value / norm for value in vector], sys.stdout, separators=(",", ":"))
'
}

known_operation() {
  jq -e --arg id "$1" 'any(.[]; .id == $id)' "${MODULE_ROOT}/operations.json" >/dev/null
}

point_uuid() {
  local digest
  digest="$(printf '%s' "$1" | sha256sum | cut -c1-32)"
  printf '%s-%s-%s-%s-%s\n' \
    "${digest:0:8}" "${digest:8:4}" "${digest:12:4}" "${digest:16:4}" "${digest:20:12}"
}

ensure_collection() {
  local vector
  vector="$(jq -cn '[1] + [range(0;127) | 0]')"
  curl -fsS -X PUT -H "api-key: ${QDRANT_WRITE_KEY}" \
    -H 'Content-Type: application/json' \
    --data "$(jq -cn --argjson vector "${vector}" '{vectors:{size:($vector|length),distance:"Cosine"}}')" \
    "${QDRANT_WRITE_URL}/collections/${QDRANT_COLLECTION}" >/dev/null 2>&1 || true
}

seed_protected_source() {
  local operation=$1 record payload uuid vector body
  record="$(jq -ce --arg operation "${operation}" \
    '.[] | select(.operation == $operation)' \
    "${PAYLOAD_ROOT}/orion-protected-sources.json")"
  [[ -n ${record} ]] || die "no protected source for ${operation}"
  payload="$(jq -ce 'del(.operation)' <<<"${record}")"
  uuid="$(point_uuid "${operation}")"
  vector="$(jq -r '.text' <<<"${record}" | feature_vector)"
  body="$(jq -cn --arg id "${uuid}" --argjson vector "${vector}" \
    --argjson payload "${payload}" \
    '{points:[{id:$id,vector:$vector,payload:$payload}]}')"
  curl -fsS -X PUT -H "api-key: ${QDRANT_WRITE_KEY}" \
    -H 'Content-Type: application/json' --data-binary "${body}" \
    "${QDRANT_WRITE_URL}/collections/${QDRANT_COLLECTION}/points?wait=true" >/dev/null
}

nextcloud_mkcol() {
  local path=$1 code
  code="$(curl -sS -o /dev/null -w '%{http_code}' -X MKCOL \
    -u "${NEXTCLOUD_USER}:${NEXTCLOUD_PASSWORD}" -H "Host: ${NEXTCLOUD_HOST}" \
    "${NEXTCLOUD_URL}/remote.php/dav/files/${NEXTCLOUD_USER}/${path}")"
  [[ ${code} == 201 || ${code} == 405 ]] || die "Nextcloud MKCOL ${path} returned ${code}"
}

nextcloud_put() {
  local source=$1 path=$2
  curl -fsS -X PUT -u "${NEXTCLOUD_USER}:${NEXTCLOUD_PASSWORD}" \
    -H "Host: ${NEXTCLOUD_HOST}" --data-binary "@${source}" \
    "${NEXTCLOUD_URL}/remote.php/dav/files/${NEXTCLOUD_USER}/${path}" >/dev/null
}

seed_review_process() {
  local code path='Partner%20Rooms/Cinder%20Labs'
  code="$(curl -sS -o /dev/null -w '%{http_code}' -X MKCOL \
    -u "${NEXTCLOUD_OWNER_USER}:${NEXTCLOUD_OWNER_PASSWORD}" \
    -H "Host: ${NEXTCLOUD_HOST}" \
    "${NEXTCLOUD_URL}/remote.php/dav/files/${NEXTCLOUD_OWNER_USER}/Partner%20Rooms")"
  [[ ${code} == 201 || ${code} == 405 ]] || die "Nextcloud Partner Rooms returned ${code}"
  code="$(curl -sS -o /dev/null -w '%{http_code}' -X MKCOL \
    -u "${NEXTCLOUD_OWNER_USER}:${NEXTCLOUD_OWNER_PASSWORD}" \
    -H "Host: ${NEXTCLOUD_HOST}" \
    "${NEXTCLOUD_URL}/remote.php/dav/files/${NEXTCLOUD_OWNER_USER}/${path}")"
  [[ ${code} == 201 || ${code} == 405 ]] || die "Nextcloud Cinder room returned ${code}"
  curl -fsS -X PUT -u "${NEXTCLOUD_OWNER_USER}:${NEXTCLOUD_OWNER_PASSWORD}" \
    -H "Host: ${NEXTCLOUD_HOST}" --data-binary "@${PAYLOAD_ROOT}/review-process.md" \
    "${NEXTCLOUD_URL}/remote.php/dav/files/${NEXTCLOUD_OWNER_USER}/${path}/Partner%20Evaluation%20Process.md" >/dev/null
}

apply_kep_m01_a() { seed_protected_source "$1"; }
apply_kep_m01_b() { seed_protected_source "$1"; }
apply_kep_m01_c() { :; }
apply_kep_m01_d() {
  seed_protected_source "$1"
}
apply_kep_m01_e() {
  seed_protected_source "$1"
  seed_review_process
}
apply_kep_m01_f() { seed_review_process; }
apply_kep_m01_g() { seed_review_process; }
apply_kep_m01_h() { seed_review_process; }
apply_kep_m01_i() {
  seed_review_process
  docker exec kep-v2-langflow install -d -m 0755 /opt/keplerops/preview
  docker cp "${PAYLOAD_ROOT}/operations-handoff.md" \
    kep-v2-langflow:/opt/keplerops/preview/operations-handoff.md
}
apply_kep_m01_j() { :; }

apply_one() {
  local operation=$1 function
  function="apply_${operation//-/_}"
  known_operation "${operation}" || die "unknown operation: ${operation}"
  declare -F "${function}" >/dev/null || die "missing apply handler: ${function}"
  "${function}" "${operation}"
  install -d -m 0750 "${STATE_ROOT}/applied"
  printf '%s\n' "${operation}" > "${STATE_ROOT}/applied/${operation}"
  log "applied ${operation}"
}

main() {
  local requested=${1:-all} operation
  require_commands
  install -d -m 0750 "${STATE_ROOT}"
  deploy_release_service
  if [[ ${requested} != all ]]; then
    known_operation "${requested}" || die "unknown operation: ${requested}"
    ensure_collection
    apply_one "${requested}"
    return
  fi
  ensure_collection
  while IFS= read -r operation; do apply_one "${operation}"; done \
    < <(jq -r '.[].id' "${MODULE_ROOT}/operations.json")
}

main "$@"
