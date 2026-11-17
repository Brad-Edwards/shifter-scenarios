#!/usr/bin/env bash
set -euo pipefail
ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
docker compose -f compose.yaml up -d --wait fieldlink-support-db
docker compose -f compose.yaml up -d --no-deps fieldlink-support
docker compose -f compose.yaml exec -T fieldlink-support php /opt/fieldlink/install-support.php
docker compose -f compose.yaml exec -T fieldlink-support php /opt/fieldlink/seed-support-users.php
docker compose -f compose.yaml exec -T fieldlink-support php /opt/fieldlink/seed-support-case.php
