#!/usr/bin/env bash

set -Eeuo pipefail

SEEDING_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE_ROOT="$(cd "${SEEDING_ROOT}/.." && pwd)"

# shellcheck source=../config.env
source "${SEEDING_ROOT}/config.env"

log() {
  printf '[campaign-v2-seed] %s\n' "$*" >&2
}

die() {
  log "ERROR: $*"
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "required command is unavailable: $1"
}

compose() {
  docker compose \
    --project-directory "${TEMPLATE_ROOT}" \
    --env-file "${TEMPLATE_ROOT}/component-lock.env" \
    -f "${TEMPLATE_ROOT}/compose.foundation.yaml" \
    -f "${TEMPLATE_ROOT}/compose.enterprise.yaml" \
    "$@"
}

require_service() {
  local service=$1
  local container_id

  container_id="$(compose ps --status running -q "${service}")"
  [[ -n "${container_id}" ]] || die "compose service is not running: ${service}"
}

retry() {
  local attempts=$1
  local delay=$2
  shift 2

  local attempt
  for ((attempt = 1; attempt <= attempts; attempt++)); do
    if "$@"; then
      return 0
    fi
    if ((attempt < attempts)); then
      sleep "${delay}"
    fi
  done
  return 1
}

urlencode() {
  jq -rn --arg value "$1" '$value|@uri'
}

http_code() {
  local method=$1
  local url=$2
  shift 2
  curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
    --request "${method}" "$@" "${url}"
}
