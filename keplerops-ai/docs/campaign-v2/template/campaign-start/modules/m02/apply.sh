#!/usr/bin/env bash
set -Eeuo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MODULE_ROOT
TEMPLATE_ROOT="$(cd "${MODULE_ROOT}/../../.." && pwd)"
readonly TEMPLATE_ROOT
readonly STATE_ROOT="${CAMPAIGN_STATE_ROOT:-${TEMPLATE_ROOT}/state/campaign-start}/m02"
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
    -f "${TEMPLATE_ROOT}/compose.cinder.yaml" \
    -f "${TEMPLATE_ROOT}/campaign-start/modules/m06/compose.overlay.yaml" \
    -f "${TEMPLATE_ROOT}/campaign-start/modules/m07/compose.overlay.yaml" \
    -f "${MODULE_ROOT}/compose.overlay.yaml" "$@"
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

ensure_media_attestation_key() {
  install -d -m 0700 "${STATE_ROOT}/media-attestation"
  if [[ ! -s ${STATE_ROOT}/media-attestation/private.pem ]]; then
    openssl genpkey -algorithm ED25519 -out "${STATE_ROOT}/media-attestation/private.pem"
    openssl pkey -in "${STATE_ROOT}/media-attestation/private.pem" -pubout \
      -out "${STATE_ROOT}/media-attestation/public.pem"
  fi
  chmod 0600 "${STATE_ROOT}/media-attestation/private.pem"
  chmod 0644 "${STATE_ROOT}/media-attestation/public.pem"
}

install_public_clues() {
  local public_root="${M02_PUBLIC_ROOT:-${TEMPLATE_ROOT}/content/public-site/partners/orion}"
  install -d -m 0755 "${public_root}"
  install -m 0644 "${MODULE_ROOT}/payloads/partner-intake.md" "${public_root}/intake.md"
  install -m 0644 "${MODULE_ROOT}/payloads/package-review-procedure.md" "${public_root}/package-review.md"
  install -m 0644 "${MODULE_ROOT}/payloads/review-stack.lock" "${public_root}/review-stack.lock"
  install -m 0644 "${MODULE_ROOT}/payloads/integration-review-checklist.md" "${public_root}/integration-review.md"
  # Carrier templates stay read-only in the worker image/mount and are copied
  # into native services only after their causal transition.
}

seed_native_review_surfaces() {
  compose exec -T -e M02_WORKHUB_REVIEW_PASSWORD='Orion-Package-Review-M02-7wQ9pL3n' \
    redmine bundle exec rails runner /dev/stdin <"${MODULE_ROOT}/runtime/seed_workhub.rb" >/dev/null
  local code
  code="$(curl -sS -o /tmp/m02-forgejo-catalog.json -w '%{http_code}' \
    --user 'range-admin:KeplerV2-Training-Forgejo-Admin' -H 'Content-Type: application/json' \
    --data '{"name":"orion-mcp-catalog","private":false,"description":"Orion compatibility-reviewed MCP integrations","auto_init":true,"readme":"Default"}' \
    'http://10.61.40.20:3000/api/v1/orgs/keplerops/repos')"
  case "${code}" in 201|409) ;; *) die "Forgejo MCP catalog seed failed with HTTP ${code}" ;; esac
  curl -fsS --user 'range-admin:KeplerV2-Training-Forgejo-Admin' -X PATCH \
    -H 'Content-Type: application/json' --data '{"private":false,"description":"Orion compatibility-reviewed MCP integrations"}' \
    'http://10.61.40.20:3000/api/v1/repos/keplerops/orion-mcp-catalog' >/dev/null
  code="$(curl -sS -o /dev/null -w '%{http_code}' --user 'range-admin:KeplerV2-Training-Forgejo-Admin' \
    'http://10.61.40.20:3000/api/v1/repos/keplerops/orion-mcp-catalog/contents/README.md')"
  if [[ ${code} == 404 ]]; then
    curl -fsS --user 'range-admin:KeplerV2-Training-Forgejo-Admin' -H 'Content-Type: application/json' \
      --data "$(jq -cn --arg content "$(printf '%s\n' '# Orion MCP Catalog' 'Compatibility-reviewed registrations are written by the reviewer browser.' | base64 -w0)" '{message:"Initialize Orion MCP catalog",content:$content}')" \
      'http://10.61.40.20:3000/api/v1/repos/keplerops/orion-mcp-catalog/contents/README.md' >/dev/null
  elif [[ ${code} != 200 ]]; then
    die "Forgejo MCP catalog README check failed with HTTP ${code}"
  fi
  rm -f /tmp/m02-forgejo-catalog.json
}

wait_for_workers() {
  local service
  for service in m02-business-worker m02-recipient-worker m02-media-attestor \
    m02-model-analysis m02-model-integration; do
    for _ in $(seq 1 60); do
      if compose exec -T "${service}" python -c \
        'from pathlib import Path; import os,time; p=Path(os.environ["HEARTBEAT_FILE"]); e=p.with_name(f"{p.name}.last-error.json"); raise SystemExit(0 if p.is_file() and time.time()-p.stat().st_mtime < 90 and (not e.exists() or e.stat().st_mtime < p.stat().st_mtime) else 1)' \
        >/dev/null 2>&1; then
        break
      fi
      sleep 2
    done
    compose exec -T "${service}" python -c \
      'from pathlib import Path; import os,time; p=Path(os.environ["HEARTBEAT_FILE"]); e=p.with_name(f"{p.name}.last-error.json"); assert p.is_file() and time.time()-p.stat().st_mtime < 90 and (not e.exists() or e.stat().st_mtime < p.stat().st_mtime)' \
      >/dev/null || die "${service} did not complete a recent successful processing pass"
  done
}

apply_one() {
  local operation=$1
  known_operation "${operation}" || die "unknown operation: ${operation}"
  install -d -m 0750 "${STATE_ROOT}/applied"
  printf '%s\n' "${operation}" >"${STATE_ROOT}/applied/${operation}"
  log "enabled ${operation}; no identity, room, carrier, ticket, vector, or result was pre-created"
}

main() {
  local requested=${1:-all} operation command
  for command in base64 curl docker jq openssl install ssh; do
    command -v "${command}" >/dev/null 2>&1 || die "missing command: ${command}"
  done
  install -d -m 0750 "${STATE_ROOT}" "${STATE_ROOT}/records" "${STATE_ROOT}/attempts"
  ensure_recipient_directory
  ensure_media_attestation_key
  install_public_clues
  seed_native_review_surfaces
  # All five workers share one image. Building each service concurrently under
  # Compose Bake races multiple exports to the same image tag.
  compose build m02-business-worker >/dev/null
  compose up -d --no-build --no-deps \
    airflow-api airflow-scheduler airflow-dag-processor airflow-triggerer airflow-worker \
    m02-business-worker m02-recipient-worker m02-media-attestor \
    m02-model-analysis m02-model-integration >/dev/null
  wait_for_workers
  if [[ ${requested} == all ]]; then
    while IFS= read -r operation; do apply_one "${operation}"; done \
      < <(jq -r '.[].id' "${MODULE_ROOT}/operations.json")
  else
    apply_one "${requested}"
  fi
}

main "$@"
