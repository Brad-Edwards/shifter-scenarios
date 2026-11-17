#!/usr/bin/env bash
set -euo pipefail
ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
operator=${KEPLEROPS_OPERATOR_DIR:-./.operator}
docker compose exec -T fieldlink-postgres sh -ec \
  'exec psql --set ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f -' \
  <"$operator/native-platform/postgres.sql" >/dev/null
docker compose exec -T fieldlink-postgres sh -ec \
  'exec psql --set ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d fieldlink_data -f -' \
  <native-platform/company-data.sql >/dev/null
echo 'Native company database and scoped workspace ready.'
