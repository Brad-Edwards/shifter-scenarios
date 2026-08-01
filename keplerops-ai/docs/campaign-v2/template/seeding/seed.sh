#!/usr/bin/env bash

set -Eeuo pipefail

SEEDING_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SEEDING_ROOT}/lib/common.sh"

readonly DEFAULT_SEEDERS=(
  keycloak-samba
  forgejo
  redmine
  nextcloud
  zammad
  stalwart
  odoo
  ghost
  mautic
)

usage() {
  cat <<'USAGE'
Usage: ./seed.sh [seeder ...]

Seeders:
  keycloak-samba forgejo redmine nextcloud zammad stalwart odoo ghost mautic
  business-workflows (run after engineering/data services are ready)

With no arguments, all seeders run in dependency-aware order. Each seeder may
also be run directly from apps/. Environment values override config.env.
USAGE
}

main() {
  require_command docker
  require_command curl
  require_command jq
  require_command base64

  if [[ ${1:-} == "--help" || ${1:-} == "-h" ]]; then
    usage
    return 0
  fi

  local -a seeders
  if (($# == 0)); then
    seeders=("${DEFAULT_SEEDERS[@]}")
  else
    seeders=("$@")
  fi

  local seeder script
  for seeder in "${seeders[@]}"; do
    script="${SEEDING_ROOT}/apps/${seeder}.sh"
    [[ -x "${script}" ]] || die "unknown or non-executable seeder: ${seeder}"
    log "running ${seeder}"
    "${script}"
  done

  log "clean-enterprise application seeding complete"
}

main "$@"
