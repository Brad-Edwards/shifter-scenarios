#!/usr/bin/env bash
set -euo pipefail
ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
docker compose -f compose.yaml up -d --no-deps fieldlink-kanboard
docker compose -f compose.yaml exec -T fieldlink-kanboard php /opt/fieldlink/seed-staff.php
docker compose -f compose.yaml exec -T fieldlink-kanboard chown -R nginx:nginx /var/www/app/data
# K19: seed the staff archive handover table that k-staff reads for K19.2/K19.3.
# Run inside fieldlink-postgres (it has psql and local trust for fieldlink_staff).
docker compose -f compose.yaml exec -T fieldlink-postgres \
  psql -v ON_ERROR_STOP=1 -U fieldlink_staff -d fieldlink_staff -f - \
  < native-workplace/seed-k19-staff-archive.sql
