#!/usr/bin/env bash
set -euo pipefail

readonly ROOT=${KEPLEROPS_V2_ROOT:-/opt/keplerops-v2}

cd "$ROOT"
"$ROOT/scripts/ensure-identity-network.sh"
if [[ ${KEPLEROPS_SKIP_PULL:-0} != 1 ]]; then
  docker compose \
    --env-file component-lock.env \
    -f compose.foundation.yaml \
    pull
fi
docker compose \
  --env-file component-lock.env \
  -f compose.foundation.yaml \
  up -d step-ca caddy

"$ROOT/scripts/reconcile-step-ca.sh"

install -d -m 0750 "$ROOT/state"
caddy_root="$(mktemp)"
docker exec kep-v2-caddy cat /data/caddy/pki/authorities/local/root.crt >"$caddy_root"
if [[ -d "$ROOT/state/caddy-root.crt" && ! -L "$ROOT/state/caddy-root.crt" ]]; then
  rm -rf "$ROOT/state/caddy-root.crt"
fi
install -m 0644 "$caddy_root" "$ROOT/state/caddy-root.crt"
rm -f "$caddy_root"

docker compose \
  --env-file component-lock.env \
  -f compose.foundation.yaml \
  up -d

if docker inspect keplerops-participant-workstation-runtime >/dev/null 2>&1; then
  docker network connect kep-v2-public \
    keplerops-participant-workstation-runtime 2>/dev/null || true
  docker network connect kep-v2-cinder \
    keplerops-participant-workstation-runtime 2>/dev/null || true
fi

"$ROOT/scripts/health-check.sh" foundation
