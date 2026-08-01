#!/usr/bin/env bash

set -Eeuo pipefail

SEEDING_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/common.sh
source "${SEEDING_ROOT}/lib/common.sh"

mautic_console() {
  compose exec -T --user www-data mautic php /var/www/html/bin/console "$@"
}

mautic_files_ready() {
  compose exec -T mautic test -f /var/www/html/bin/console >/dev/null 2>&1
}

mautic_installed() {
  compose exec -T mautic php -r \
    'include("/var/www/html/config/local.php"); exit(!empty($parameters["db_driver"]) && !empty($parameters["site_url"]) ? 0 : 1);' \
    >/dev/null 2>&1
}

main() {
  require_service mautic
  retry 60 3 mautic_files_ready || die "Mautic application files did not become ready"

  if ! mautic_installed; then
    mautic_console mautic:install "${MAUTIC_SITE_URL}" --force \
      --db_driver=pdo_mysql \
      --db_host="${MAUTIC_DB_HOST}" \
      --db_port="${MAUTIC_DB_PORT}" \
      --db_name="${MAUTIC_DB_NAME}" \
      --db_user="${MAUTIC_DB_USER}" \
      --db_password="${MAUTIC_DB_PASSWORD}" \
      --db_backup_tables=false \
      --admin_firstname=Range \
      --admin_lastname=Administrator \
      --admin_username="${MAUTIC_ADMIN_USER}" \
      --admin_email="${MAUTIC_ADMIN_EMAIL}" \
      --admin_password="${MAUTIC_ADMIN_PASSWORD}" \
      --no-interaction
    log "Mautic baseline installed"
  fi

  mautic_console doctrine:migrations:migrate --no-interaction
  mautic_console mautic:plugins:reload
  mautic_console cache:clear --no-warmup
  log "Mautic clean state is ready"
}

main "$@"
