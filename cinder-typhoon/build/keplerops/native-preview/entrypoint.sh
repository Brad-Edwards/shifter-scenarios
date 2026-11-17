#!/bin/sh
set -eu

for route in 10.77.50.0/24 10.77.51.0/24 10.77.52.0/24 10.77.53.0/24; do
  if ! ip route show "$route" | grep -q 'scope link'; then
    ip route replace "$route" via "$FIELDKEST_GATEWAY"
  fi
done
install -m 0444 /run/fieldkest-tls/server.crt /tmp/fieldlink-preview.crt
install -m 0444 /run/fieldkest-tls/ca.crt /tmp/fieldlink-ca.crt
# Key for gotenberg (runs as gotenberg user)
install -m 0400 /run/fieldkest-tls/server.key /tmp/fieldlink-preview-gotenberg.key
chown gotenberg:gotenberg /tmp/fieldlink-preview-gotenberg.key
# Key for Python preview service (runs as fieldkest-preview user)
install -m 0400 /run/fieldkest-tls/server.key /tmp/fieldlink-preview.key
chown fieldkest-preview:fieldkest-preview /tmp/fieldlink-preview.key

# Start Gotenberg on internal port 3000 (plain HTTP, no TLS)
GOTENBERG_PORT=3000
API_PORT=$GOTENBERG_PORT API_TLS_CERT_FILE="" API_TLS_KEY_FILE="" \
  setpriv --reuid=gotenberg --regid=gotenberg --init-groups /usr/bin/tini -- gotenberg &
gotenberg_pid=$!

# Start Python preview service on port 443 (TLS-terminated)
FIELDKEST_STATE_ROOT=/var/lib/fieldkest-preview \
FIELDKEST_TLS_CERT=/tmp/fieldlink-preview.crt \
FIELDKEST_TLS_KEY=/tmp/fieldlink-preview.key \
GOTENBERG_PORT=$GOTENBERG_PORT \
PORT=443 \
  setpriv --reuid=fieldkest-preview --regid=fieldkest-preview --init-groups \
  python3 /opt/fieldkest-preview/preview.py &
api_pid=$!

trap 'kill "$api_pid" "$gotenberg_pid" 2>/dev/null || true' INT TERM EXIT
wait "$gotenberg_pid"
