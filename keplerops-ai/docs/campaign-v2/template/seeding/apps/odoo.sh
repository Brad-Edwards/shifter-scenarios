#!/usr/bin/env bash

set -Eeuo pipefail

SEEDING_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/common.sh
source "${SEEDING_ROOT}/lib/common.sh"

odoo_db_args() {
  printf '%s\n' \
    --database "${ODOO_DATABASE}" \
    --db_host "${ODOO_DB_HOST}" \
    --db_port "${ODOO_DB_PORT}" \
    --db_user "${ODOO_DB_USER}" \
    --db_password "${ODOO_DB_PASSWORD}"
}

main() {
  local -a db_args
  require_service odoo
  mapfile -t db_args < <(odoo_db_args)

  compose exec -T odoo odoo "${db_args[@]}" \
    --init base,account,l10n_generic_coa --without-demo=all --stop-after-init

  compose exec -T \
    -e ODOO_SEED_ADMIN_PASSWORD="${ODOO_ADMIN_PASSWORD}" \
    odoo odoo shell "${db_args[@]}" \
    < "${SEEDING_ROOT}/payloads/odoo.py"

  log "Odoo clean state is ready"
}

main "$@"
