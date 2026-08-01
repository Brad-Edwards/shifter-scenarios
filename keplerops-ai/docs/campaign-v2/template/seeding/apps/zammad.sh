#!/usr/bin/env bash

set -Eeuo pipefail

SEEDING_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/common.sh
source "${SEEDING_ROOT}/lib/common.sh"

zammad_ready() {
  compose exec -T --workdir /opt/zammad \
    -e DATABASE_URL="${ZAMMAD_DATABASE_URL}" \
    zammad-railsserver bundle exec rails runner \
    'ActiveRecord::Base.connection.execute("SELECT 1")' >/dev/null 2>&1
}

main() {
  require_service zammad-railsserver
  retry 60 3 zammad_ready || die "Zammad Rails environment did not become ready"

  compose exec -T \
    --workdir /opt/zammad \
    -e DATABASE_URL="${ZAMMAD_DATABASE_URL}" \
    -e ZAMMAD_SEED_ADMIN_PASSWORD="${ZAMMAD_ADMIN_PASSWORD}" \
    -e ZAMMAD_SEED_REVIEWER_PASSWORD="${REVIEWER_PASSWORD}" \
    -e ZAMMAD_SEED_ML_PASSWORD="${ML_ENGINEER_PASSWORD}" \
    -e ZAMMAD_SEED_RELEASE_PASSWORD="${RELEASE_ENGINEER_PASSWORD}" \
    -e ZAMMAD_SEED_COMMS_PASSWORD="${COMMS_PUBLISHER_PASSWORD}" \
    -e ZAMMAD_SEED_SUPPORT_PASSWORD="${SUPPORT_ANALYST_PASSWORD}" \
    zammad-railsserver bundle exec rails runner /dev/stdin \
    < "${SEEDING_ROOT}/payloads/zammad.rb"

  log "Zammad clean state is ready"
}

main "$@"
