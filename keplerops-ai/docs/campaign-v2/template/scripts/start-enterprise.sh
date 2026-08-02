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

trust_marker="$ROOT/state/identity/keycloak-trust.sha256"
mapfile -d '' trust_files < <(
  find "$ROOT/state/identity/truststores" -maxdepth 1 -type f -name '*.pem' \
    -print0 | sort -z
)
((${#trust_files[@]} > 0)) || {
  echo "Keycloak directory trust material is unavailable" >&2
  exit 1
}
trust_fingerprint="$(sha256sum "${trust_files[@]}" | sha256sum | awk '{print $1}')"
if [[ ! -s $trust_marker ]] || [[ $(<"$trust_marker") != "$trust_fingerprint" ]]; then
  docker compose \
    --env-file component-lock.env \
    -f compose.foundation.yaml \
    -f compose.enterprise.yaml \
    restart keycloak
  printf '%s\n' "$trust_fingerprint" >"$trust_marker"
fi
"$ROOT/network/install.sh"
"$ROOT/scripts/reconcile-stalwart.sh"
"$ROOT/scripts/seed-dns.sh"
"$ROOT/scripts/health-check.sh" enterprise
"$ROOT/seeding/seed.sh"
