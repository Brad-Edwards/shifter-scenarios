#!/usr/bin/env bash
set -Eeuo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MODULE_ROOT
TEMPLATE_ROOT="$(cd "${MODULE_ROOT}/../../.." && pwd)"
readonly TEMPLATE_ROOT
readonly PAYLOAD_ROOT="${MODULE_ROOT}/payloads"
readonly STATE_ROOT="${CAMPAIGN_STATE_ROOT:-${TEMPLATE_ROOT}/state/campaign-start}/m02"
readonly QDRANT_WRITE_URL="${QDRANT_WRITE_URL:-http://10.61.50.72:6333}"
readonly QDRANT_WRITE_KEY="${QDRANT_WRITE_KEY:-KeplerV2-Training-Qdrant-Write}"
readonly QDRANT_COLLECTION="${QDRANT_COLLECTION:-orion_partner_intake}"
readonly NEXTCLOUD_URL="${NEXTCLOUD_URL:-http://10.61.30.23}"
readonly NEXTCLOUD_HOST="${NEXTCLOUD_HOST:-files.keplerops.lab}"
readonly NEXTCLOUD_USER="${NEXTCLOUD_ADMIN_USER:-range-admin}"
readonly NEXTCLOUD_PASSWORD="${NEXTCLOUD_ADMIN_PASSWORD:-KeplerV2-Training-Nextcloud}"
readonly NEXTCLOUD_OWNER_USER="${NEXTCLOUD_REVIEW_USER:-reviewer}"
readonly NEXTCLOUD_OWNER_PASSWORD="${NEXTCLOUD_REVIEW_PASSWORD:-KeplerV2-Training-Reviewer}"
readonly SSH_KEY="${KEPLEROPS_GUEST_KEY:-/root/.ssh/keplerops-v2}"
readonly DC01="${KEPLEROPS_DC01_ADDRESS:-192.168.78.10}"
readonly RECIPIENT_USER=mira.chen
readonly RECIPIENT_PASSWORD="${MIRA_CHEN_PASSWORD:-Orion-Mira-Mail-K8w4Nv2p}"

die() { printf '[m02] ERROR: %s\n' "$*" >&2; exit 1; }
log() { printf '[m02] %s\n' "$*" >&2; }
known_operation() { jq -e --arg id "$1" 'any(.[]; .id == $id)' "${MODULE_ROOT}/operations.json" >/dev/null; }

compose() {
  docker compose --project-directory "${TEMPLATE_ROOT}" \
    --env-file "${TEMPLATE_ROOT}/component-lock.env" \
    --env-file "${TEMPLATE_ROOT}/engineering/component-lock.additions.env" \
    -f "${TEMPLATE_ROOT}/compose.foundation.yaml" \
    -f "${TEMPLATE_ROOT}/compose.enterprise.yaml" \
    -f "${TEMPLATE_ROOT}/compose.engineering.yaml" \
    -f "${MODULE_ROOT}/compose.overlay.yaml" "$@"
}

deploy_partner_evaluation() {
  compose up -d --no-deps airflow-api airflow-scheduler airflow-dag-processor airflow-triggerer airflow-worker >/dev/null
  compose up -d --build --no-deps orion-partner-evaluation >/dev/null
  docker exec kep-v2-pdns-auth pdnsutil replace-rrset keplerops.lab reviews A 60 10.61.10.2 >/dev/null
  docker exec kep-v2-pdns-recursor rec_control wipe-cache 'keplerops.lab$' >/dev/null
  {
    cat "${TEMPLATE_ROOT}/config/caddy/Caddyfile"
    find "${TEMPLATE_ROOT}/campaign-start/modules" -path '*/runtime/Caddyfile.fragment' -type f -print0 | sort -z | xargs -0 cat
  } | docker exec -i kep-v2-caddy sh -eu -c 'cat >/tmp/Caddyfile.campaign-start'
  docker exec kep-v2-caddy caddy reload --config /tmp/Caddyfile.campaign-start --adapter caddyfile >/dev/null
  for _ in $(seq 1 60); do
    curl -kfsS --resolve reviews.keplerops.lab:443:10.61.10.2 \
      https://reviews.keplerops.lab/health/ready >/dev/null 2>&1 && return
    sleep 2
  done
  die 'Orion Partner Evaluation did not become ready'
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

point_uuid() {
  local digest
  digest="$(printf '%s' "$1" | sha256sum | cut -c1-32)"
  printf '%s-%s-%s-%s-%s\n' \
    "${digest:0:8}" "${digest:8:4}" "${digest:12:4}" "${digest:16:4}" "${digest:20:12}"
}

ensure_collection() {
  curl -fsS -X PUT -H "api-key: ${QDRANT_WRITE_KEY}" -H 'Content-Type: application/json' \
    --data '{"vectors":{"size":128,"distance":"Cosine"}}' \
    "${QDRANT_WRITE_URL}/collections/${QDRANT_COLLECTION}" >/dev/null 2>&1 || true
}

seed_retrieval_source() {
  local operation=$1 record payload uuid vector body
  record="$(jq -ce --arg operation "${operation}" \
    '.[] | select(.operation == $operation)' "${PAYLOAD_ROOT}/retrieval-sources.json")"
  [[ -n ${record} ]] || die "no retrieval source for ${operation}"
  payload="$(jq -ce 'del(.operation)' <<<"${record}")"
  uuid="$(point_uuid "${operation}")"
  vector="$(jq -r '.text' <<<"${record}" | feature_vector)"
  body="$(jq -cn --arg id "${uuid}" --argjson vector "${vector}" --argjson payload "${payload}" \
    '{points:[{id:$id,vector:$vector,payload:$payload}]}')"
  curl -fsS -X PUT -H "api-key: ${QDRANT_WRITE_KEY}" -H 'Content-Type: application/json' \
    --data-binary "${body}" \
    "${QDRANT_WRITE_URL}/collections/${QDRANT_COLLECTION}/points?wait=true" >/dev/null
}

nextcloud_mkcol_as() {
  local user=$1 password=$2 path=$3 code
  code="$(curl -sS -o /dev/null -w '%{http_code}' -X MKCOL \
    -u "${user}:${password}" -H "Host: ${NEXTCLOUD_HOST}" \
    "${NEXTCLOUD_URL}/remote.php/dav/files/${user}/${path}")"
  [[ ${code} == 201 || ${code} == 405 ]] || die "Nextcloud MKCOL ${path} returned ${code}"
}

nextcloud_put_as() {
  local user=$1 password=$2 source=$3 path=$4
  curl -fsS -X PUT -u "${user}:${password}" \
    -H "Host: ${NEXTCLOUD_HOST}" --data-binary "@${source}" \
    "${NEXTCLOUD_URL}/remote.php/dav/files/${user}/${path}" >/dev/null
}

seed_partner_room() {
  nextcloud_mkcol_as "${NEXTCLOUD_OWNER_USER}" "${NEXTCLOUD_OWNER_PASSWORD}" 'Partner%20Rooms'
  nextcloud_mkcol_as "${NEXTCLOUD_OWNER_USER}" "${NEXTCLOUD_OWNER_PASSWORD}" 'Partner%20Rooms/Cinder%20Labs'
  nextcloud_mkcol_as "${NEXTCLOUD_OWNER_USER}" "${NEXTCLOUD_OWNER_PASSWORD}" 'Partner%20Rooms/Cinder%20Labs/Submissions'
  nextcloud_mkcol_as "${NEXTCLOUD_OWNER_USER}" "${NEXTCLOUD_OWNER_PASSWORD}" 'Partner%20Rooms/Cinder%20Labs/Policy%20Exceptions'
  nextcloud_put_as "${NEXTCLOUD_OWNER_USER}" "${NEXTCLOUD_OWNER_PASSWORD}" \
    "${PAYLOAD_ROOT}/partner-intake.md" 'Partner%20Rooms/Cinder%20Labs/Partner%20Intake.md'
  nextcloud_put_as "${NEXTCLOUD_OWNER_USER}" "${NEXTCLOUD_OWNER_PASSWORD}" \
    "${PAYLOAD_ROOT}/review-stack.lock" 'Partner%20Rooms/Cinder%20Labs/review-stack.lock'
  nextcloud_put_as "${NEXTCLOUD_OWNER_USER}" "${NEXTCLOUD_OWNER_PASSWORD}" \
    "${PAYLOAD_ROOT}/package-review-procedure.md" 'Partner%20Rooms/Cinder%20Labs/Package%20Review%20Procedure.md'
}

ensure_recipient_directory() {
  [[ -r ${SSH_KEY} ]] || die "guest SSH key unavailable: ${SSH_KEY}"
  ssh -i "${SSH_KEY}" -o BatchMode=yes -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null "kepler@${DC01}" sudo bash -s -- \
    "${RECIPIENT_USER}" "${RECIPIENT_PASSWORD}" <<'REMOTE'
set -Eeuo pipefail
username=$1
password=$2
if samba-tool user show "${username}" >/dev/null 2>&1; then
  samba-tool user setpassword "${username}" --newpassword="${password}" >/dev/null
else
  samba-tool user create "${username}" "${password}" \
    --userou='OU=People' --given-name=Mira --surname=Chen \
    --description='Director, Orion Release Assurance' \
    --mail-address=mira.chen@keplerops.lab >/dev/null
fi
samba-tool user setexpiry "${username}" --noexpiry >/dev/null
samba-tool user enable "${username}" >/dev/null
REMOTE
}

install_recipient_worker() {
  local i_flag
  i_flag="$(jq -er '.[] | select(.id == "kep-m02-i") | .flag' "${MODULE_ROOT}/operations.json")"
  getent passwd keplerops-recipient >/dev/null 2>&1 || \
    useradd --system --home /var/lib/keplerops/campaign --shell /usr/sbin/nologin keplerops-recipient
  install -d -m 0750 -o keplerops-recipient -g keplerops-recipient /var/lib/keplerops/campaign
  install -d -m 0755 /usr/local/lib/keplerops /etc/keplerops
  install -m 0755 "${MODULE_ROOT}/runtime/recipient-worker.py" \
    /usr/local/lib/keplerops/m02-recipient-worker.py
  install -m 0644 "${MODULE_ROOT}/runtime/keplerops-m02-recipient.service" \
    /etc/systemd/system/keplerops-m02-recipient.service
  install -m 0644 "${PAYLOAD_ROOT}/reviewer-contact.json" \
    /etc/keplerops/m02-reviewer-contact.json
  install -m 0644 "${PAYLOAD_ROOT}/partner-welcome.md" \
    /etc/keplerops/m02-partner-welcome.md
  cat > /etc/keplerops/m02-recipient.env <<EOF
MAIL_USER=${RECIPIENT_USER}
MAIL_PASSWORD=${RECIPIENT_PASSWORD}
MAIL_ADDRESS=mira.chen@keplerops.lab
EXPECTED_SENDER=cinder.operator@cinder.lab
SSL_CERT_FILE=${TEMPLATE_ROOT}/state/caddy-root.crt
KEYCLOAK_URL=http://10.61.20.20:8080
KEYCLOAK_REALM=keplerops
KEYCLOAK_CLIENT_ID=orion-partner-intake
KEYCLOAK_CLIENT_SECRET=KeplerV2-Training-Partner-Intake-Keycloak
NEXTCLOUD_URL=http://10.61.30.23
NEXTCLOUD_HOST=files.keplerops.lab
NEXTCLOUD_USER=${NEXTCLOUD_USER}
NEXTCLOUD_PASSWORD=${NEXTCLOUD_PASSWORD}
M02_I_FLAG=${i_flag}
REVIEW_SERVICE_URL=http://10.61.30.29:8080
REVIEW_SERVICE_TOKEN=KeplerV2-Training-M02-Recipient
EOF
  chown root:keplerops-recipient /etc/keplerops/m02-recipient.env \
    /etc/keplerops/m02-reviewer-contact.json /etc/keplerops/m02-partner-welcome.md
  chmod 0640 /etc/keplerops/m02-recipient.env /etc/keplerops/m02-reviewer-contact.json \
    /etc/keplerops/m02-partner-welcome.md
  systemctl daemon-reload
  systemctl enable --now keplerops-m02-recipient.service >/dev/null
}

apply_kep_m02_a() { seed_retrieval_source "$1"; seed_partner_room; }
apply_kep_m02_b() { seed_retrieval_source "$1"; seed_partner_room; }
apply_kep_m02_c() { seed_retrieval_source "$1"; seed_partner_room; }
apply_kep_m02_d() { seed_retrieval_source "$1"; seed_partner_room; }
apply_kep_m02_e() { seed_partner_room; }
apply_kep_m02_f() { :; }
apply_kep_m02_h() {
  seed_partner_room
  nextcloud_put_as "${NEXTCLOUD_OWNER_USER}" "${NEXTCLOUD_OWNER_PASSWORD}" \
    "${PAYLOAD_ROOT}/WELCOME.md" 'Partner%20Rooms/Cinder%20Labs/WELCOME.md'
}
apply_kep_m02_i() {
  seed_partner_room
  ensure_recipient_directory
  install_recipient_worker
}
apply_kep_m02_j() {
  ensure_recipient_directory
  install_recipient_worker
}
apply_kep_m02_k() { :; }
apply_kep_m02_l() { seed_partner_room; }
apply_kep_m02_m() { :; }

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
  local requested=${1:-all} operation command
  for command in curl ffprobe getent install jq python3 sha256sum ssh systemctl useradd; do
    command -v "${command}" >/dev/null 2>&1 || die "missing command: ${command}"
  done
  install -d -m 0750 "${STATE_ROOT}"
  deploy_partner_evaluation
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
