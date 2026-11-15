#!/usr/bin/env bash
set -euo pipefail
ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
OPERATOR_DIR=${KEPLEROPS_OPERATOR_DIR:-"$ROOT/.operator"}
docker compose -f compose.yaml up -d --no-recreate --wait --wait-timeout 90 fieldlink-postgres
docker compose -f compose.yaml exec -T fieldlink-postgres sh -ec \
  'exec psql --set ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f -' \
  < "$OPERATOR_DIR/native-workplace/postgres.sql" >/dev/null
echo 'Native workplace databases are ready.'
