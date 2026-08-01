#!/usr/bin/env bash
set -euo pipefail

readonly ROOT=${KEPLEROPS_V2_ROOT:-/opt/keplerops-v2}

cd "$ROOT"
if [[ ${KEPLEROPS_SKIP_PULL:-0} != 1 ]]; then
  docker compose \
    --env-file component-lock.env \
    -f compose.foundation.yaml \
    pull
fi
docker compose \
  --env-file component-lock.env \
  -f compose.foundation.yaml \
  up -d

"$ROOT/scripts/reconcile-step-ca.sh"

if docker inspect keplerops-participant-workstation-runtime >/dev/null 2>&1; then
  docker network connect kep-v2-public \
    keplerops-participant-workstation-runtime 2>/dev/null || true
  docker network connect kep-v2-cinder \
    keplerops-participant-workstation-runtime 2>/dev/null || true
fi

"$ROOT/scripts/health-check.sh" foundation
