#!/usr/bin/env bash
# Reconcile OIDC relying-party clients against a ready Keycloak realm.
#
# LibreChat (the Orion assistant surface) and Harbor register their OpenID
# strategy once, at container start, and fail closed if the Keycloak "keplerops"
# realm is not yet publishing its discovery document — LibreChat then answers
# /oauth/openid with "Unknown authentication strategy openid" and Harbor's
# /c/oidc/login cannot reach the issuer. On a fresh substrate the realm import
# races these clients. Wait for the realm discovery document, then bounce the
# clients so they re-register against a ready issuer.
#
# This step is best-effort and always exits 0: check-all's identity gate remains
# the source of truth for OIDC health, so this reconcile can only help a boot,
# never block one.
set -uo pipefail

readonly REALM_DISCOVERY="${KEPLEROPS_OIDC_DISCOVERY:-http://10.61.20.20:8080/realms/keplerops/.well-known/openid-configuration}"
readonly OIDC_CLIENTS=(kep-v2-librechat kep-v2-harbor-core)

deadline=$((SECONDS + 240))
until curl -fsS --max-time 5 "${REALM_DISCOVERY}" >/dev/null 2>&1; do
  if ((SECONDS >= deadline)); then
    echo "reconcile-oidc-clients: realm discovery not ready; leaving clients as-is" >&2
    exit 0
  fi
  sleep 5
done

for client in "${OIDC_CLIENTS[@]}"; do
  docker inspect "${client}" >/dev/null 2>&1 || continue
  docker restart "${client}" >/dev/null 2>&1 || true
done

# Give the restarted clients a moment to come back and re-register their OpenID
# strategy before the readiness gate exercises an OIDC login.
for client in "${OIDC_CLIENTS[@]}"; do
  docker inspect "${client}" >/dev/null 2>&1 || continue
  for _ in $(seq 1 24); do
    [[ $(docker inspect -f '{{.State.Running}}' "${client}" 2>/dev/null) == true ]] && break
    sleep 5
  done
done
sleep 15

echo "reconcile-oidc-clients: OIDC clients reconciled against the ready Keycloak realm"
exit 0
