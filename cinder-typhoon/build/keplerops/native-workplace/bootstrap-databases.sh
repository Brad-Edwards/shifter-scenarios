#!/usr/bin/env bash
set -euo pipefail
ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
docker compose -f compose.yaml up -d --wait fieldlink-postgres
docker compose -f compose.yaml exec -T fieldlink-postgres sh -ec \
  'exec psql --set ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /docker-entrypoint-initdb.d/30-workplace.sql' >/dev/null
echo 'Native workplace databases are ready.'
