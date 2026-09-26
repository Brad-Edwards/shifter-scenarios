#!/bin/sh
set -eu

for route in 10.77.50.0/24 10.77.51.0/24 10.77.52.0/24 10.77.53.0/24 10.77.60.0/24; do
  if ! ip route show "$route" | grep -q 'scope link'; then
    ip route replace "$route" via "$FIELDKEST_GATEWAY"
  fi
done

service_user="fieldkest-${FIELDKEST_SERVICE}"
install -m 0444 /run/fieldkest-tls/server.crt /tmp/fieldkest.crt
install -m 0444 /run/fieldkest-tls/server.key /tmp/fieldkest.key
install -m 0444 /run/fieldkest-tls/ca.crt /tmp/fieldkest-ca.crt
if [ -f /run/fieldkest-oidc/fixture-issuer.pub ]; then
  install -m 0444 /run/fieldkest-oidc/fixture-issuer.pub /tmp/fixture-issuer.pub
fi
if [ "$FIELDKEST_SERVICE" = cert ]; then
  install -m 0444 /run/fieldkest-enrollment/evan.crt /tmp/evan.crt
  install -m 0444 /run/fieldkest-enrollment/evan.key /tmp/evan.key
fi
service_root=${FIELDKEST_SERVICE_ROOT:-/opt/fieldkest}
if [ "${FIELDKEST_START_KDC:-0}" = 1 ]; then
  krb5kdc -n -r KEPLEROPS.TEST \
    -d /var/lib/keplerops-identity/krb5kdc/principal \
    -P /tmp/krb5kdc.pid &
  kdc_pid=$!
  trap 'kill "$kdc_pid" "$api_pid" 2>/dev/null || true' INT TERM EXIT
  setpriv --reuid="$service_user" --regid="$service_user" --init-groups \
    python3 "$service_root/platform_service.py" &
  api_pid=$!
  wait "$api_pid"
else
  exec setpriv --reuid="$service_user" --regid="$service_user" --init-groups \
    python3 "$service_root/platform_service.py"
fi
