#!/usr/bin/env bash
set -euo pipefail

readonly ROOT=${KEPLEROPS_V2_ROOT:-/opt/keplerops-v2}

docker exec -i kep-v2-postgres \
  psql --set ON_ERROR_STOP=1 --username kepler --dbname postgres \
  <"$ROOT/config/postgres/reconcile.sql"
