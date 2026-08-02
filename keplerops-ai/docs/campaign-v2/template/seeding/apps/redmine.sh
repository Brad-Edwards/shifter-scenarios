#!/usr/bin/env bash

set -Eeuo pipefail

SEEDING_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/common.sh
source "${SEEDING_ROOT}/lib/common.sh"

: "${REDMINE_LDAP_HOST:=dc01.corp.keplerops.lab}"
: "${REDMINE_LDAP_PORT:=636}"
: "${REDMINE_LDAP_USER_BIND:=\$login@corp.keplerops.lab}"

redmine_ready() {
  compose exec -T redmine bundle exec rails runner \
    'ActiveRecord::Base.connection.execute("SELECT 1")' >/dev/null 2>&1
}

ensure_default_data() {
  if ! compose exec -T redmine bundle exec rails runner \
      'abort unless Role.exists?(name: "Manager")' >/dev/null 2>&1; then
    compose exec -T -e REDMINE_LANG=en redmine \
      bundle exec rake redmine:load_default_data >/dev/null
    log "Redmine default roles and trackers loaded"
  fi
}

install_directory_root_ca() {
  local source_ca="${TEMPLATE_ROOT}/state/identity/truststores/dc01-ca.pem"

  [[ -r ${source_ca} ]] || \
    die "directory CA is unavailable; reconcile guest trust first: ${source_ca}"
  compose cp "${source_ca}" redmine:/tmp/keplerops-directory-root.crt >/dev/null
  compose exec -T --user root redmine sh -eu -c '
    install -m 0644 /tmp/keplerops-directory-root.crt \
      /usr/local/share/ca-certificates/keplerops-directory-root.crt
    update-ca-certificates >/dev/null
  '
}

main() {
  require_service redmine
  retry 60 3 redmine_ready || die "Redmine Rails environment did not become ready"
  ensure_default_data
  install_directory_root_ca

  compose exec -T \
    -e REDMINE_SEED_ADMIN_PASSWORD="${REDMINE_ADMIN_PASSWORD}" \
    -e REDMINE_SEED_REVIEWER_PASSWORD="${REVIEWER_PASSWORD}" \
    -e REDMINE_SEED_ML_PASSWORD="${ML_ENGINEER_PASSWORD}" \
    -e REDMINE_SEED_RELEASE_PASSWORD="${RELEASE_ENGINEER_PASSWORD}" \
    -e REDMINE_SEED_COMMS_PASSWORD="${COMMS_PUBLISHER_PASSWORD}" \
    -e REDMINE_SEED_SUPPORT_PASSWORD="${SUPPORT_ANALYST_PASSWORD}" \
    redmine bundle exec rails runner /dev/stdin \
    < "${SEEDING_ROOT}/payloads/redmine.rb"

  compose exec -T \
    -e REDMINE_SEED_LDAP_HOST="${REDMINE_LDAP_HOST}" \
    -e REDMINE_SEED_LDAP_PORT="${REDMINE_LDAP_PORT}" \
    -e REDMINE_SEED_LDAP_USER_BIND="${REDMINE_LDAP_USER_BIND}" \
    -e REDMINE_SEED_LDAP_SYNC_BIND_DN="${SAMBA_BIND_DN}" \
    -e REDMINE_SEED_LDAP_SYNC_BIND_PASSWORD="${SAMBA_BIND_PASSWORD}" \
    -e REDMINE_SEED_LDAP_USERS_DN="${SAMBA_USERS_DN}" \
    -e REDMINE_SEED_LDAP_GROUPS_DN="${SAMBA_GROUPS_DN}" \
    redmine bundle exec rails runner /dev/stdin \
    < "${SEEDING_ROOT}/apps/redmine_identity.rb"

  log "Redmine AD LDAP and Orion project-role state are ready"
}

main "$@"
