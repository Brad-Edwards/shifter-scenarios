#!/usr/bin/env bash
set -euo pipefail
ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
docker compose -f compose.yaml up -d --no-deps fieldlink-kanboard
docker compose -f compose.yaml exec -T fieldlink-kanboard php /opt/fieldlink/seed-staff.php
docker compose -f compose.yaml exec -T fieldlink-kanboard chown -R nginx:nginx /var/www/app/data
