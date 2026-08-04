#!/bin/sh
set -eu
: "${RANGE_INSTANCE:?range namespace required}"
: "${LDAP_BIND_CREDENTIAL_FILE:?LDAP bind credential file required}"
ldap_bind_credential=$(cat "$LDAP_BIND_CREDENTIAL_FILE")
escaped_ldap_bind_credential=$(printf '%s' "$ldap_bind_credential" | sed 's/[\/&]/\\&/g')
mkdir -p /opt/keycloak/data/import
sed \
  -e "s/range-bound-at-seed/$RANGE_INSTANCE/g" \
  -e "s/__LDAP_BIND_CREDENTIAL__/$escaped_ldap_bind_credential/g" \
  /opt/keycloak/import-source/keplerops-realm.json >/opt/keycloak/data/import/keplerops-realm.json

run_company_state_readback() {
  for attempt in 1 2 3; do
    if /opt/keycloak/bin/company-state-readback; then
      return 0
    fi
    echo "Keycloak company-state readback attempt ${attempt} failed" >&2
    sleep 5
  done
  return 1
}

case "${1:-}" in
  start | start-dev)
    /opt/keycloak/bin/kc.sh "$@" &
    keycloak_pid=$!
    trap 'kill "$keycloak_pid" 2>/dev/null || true' INT TERM
    run_company_state_readback || echo "Keycloak company-state readback did not converge; continuing" >&2
    set +e
    wait "$keycloak_pid"
    status=$?
    set -e
    trap - INT TERM
    exit "$status"
    ;;
  *)
    exec /opt/keycloak/bin/kc.sh "$@"
    ;;
esac
