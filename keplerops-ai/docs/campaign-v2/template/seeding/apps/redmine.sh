#!/usr/bin/env bash

set -Eeuo pipefail

SEEDING_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/common.sh
source "${SEEDING_ROOT}/lib/common.sh"

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

main() {
  require_service redmine
  retry 60 3 redmine_ready || die "Redmine Rails environment did not become ready"
  ensure_default_data

  compose exec -T \
    -e REDMINE_SEED_ADMIN_PASSWORD="${REDMINE_ADMIN_PASSWORD}" \
    -e REDMINE_SEED_REVIEWER_PASSWORD="${REVIEWER_PASSWORD}" \
    -e REDMINE_SEED_ML_PASSWORD="${ML_ENGINEER_PASSWORD}" \
    -e REDMINE_SEED_RELEASE_PASSWORD="${RELEASE_ENGINEER_PASSWORD}" \
    -e REDMINE_SEED_COMMS_PASSWORD="${COMMS_PUBLISHER_PASSWORD}" \
    -e REDMINE_SEED_SUPPORT_PASSWORD="${SUPPORT_ANALYST_PASSWORD}" \
    redmine bundle exec rails runner /dev/stdin \
    < "${SEEDING_ROOT}/payloads/redmine.rb"

  log "Redmine clean state is ready"
}

main "$@"
