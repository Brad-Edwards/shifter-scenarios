#!/usr/bin/env bash
set -euo pipefail

readonly ROOT=${KEPLEROPS_V2_ROOT:-/opt/keplerops-v2}
readonly COMPOSE=(docker compose --env-file component-lock.env -f compose.foundation.yaml)

cd "$ROOT"
"$ROOT/scripts/ensure-identity-network.sh"
if [[ ${KEPLEROPS_SKIP_PULL:-0} != 1 ]]; then
  "${COMPOSE[@]}" pull
fi

install -d -m 0750 "$ROOT/state"

"${COMPOSE[@]}" up -d step-ca caddy

"$ROOT/scripts/reconcile-step-ca.sh"

for attempt in $(seq 1 60); do
  if docker exec kep-v2-caddy test -s /data/caddy/pki/authorities/local/root.crt; then
    break
  fi
  [[ $attempt -lt 60 ]] || {
    echo "caddy root certificate did not become available" >&2
    exit 1
  }
  sleep 2
done

caddy_root="$(mktemp)"
docker exec kep-v2-caddy cat /data/caddy/pki/authorities/local/root.crt >"$caddy_root"
if [[ -e "$ROOT/state/caddy-root.crt" && ! -f "$ROOT/state/caddy-root.crt" ]]; then
  rm -rf -- "$ROOT/state/caddy-root.crt"
fi
install -m 0644 "$caddy_root" "$ROOT/state/caddy-root.crt"
rm -f "$caddy_root"

"${COMPOSE[@]}" up -d

if docker inspect keplerops-participant-workstation-runtime >/dev/null 2>&1; then
  docker network connect kep-v2-public \
    keplerops-participant-workstation-runtime 2>/dev/null || true
  docker network connect kep-v2-cinder \
    keplerops-participant-workstation-runtime 2>/dev/null || true
fi

"$ROOT/scripts/health-check.sh" foundation
