#!/usr/bin/env bash
set -euo pipefail

readonly ROOT=${KEPLEROPS_V2_ROOT:-/opt/keplerops-v2}

cd "$ROOT"
"$ROOT/scripts/reconcile-databases.sh"
if [[ ${KEPLEROPS_SKIP_PULL:-0} != 1 ]]; then
  docker compose \
    --env-file component-lock.env \
    -f compose.foundation.yaml \
    -f compose.enterprise.yaml \
    pull
fi
docker compose \
  --env-file component-lock.env \
  -f compose.foundation.yaml \
  -f compose.enterprise.yaml \
  up -d
"$ROOT/network/install.sh"
"$ROOT/scripts/reconcile-stalwart.sh"
"$ROOT/scripts/seed-dns.sh"
"$ROOT/scripts/health-check.sh" enterprise
"$ROOT/seeding/seed.sh"
