#!/bin/sh
set -eu
ip route replace 10.77.50.0/24 via 10.77.51.254
ip route replace 10.77.52.0/24 via 10.77.51.254
ip route replace 10.77.53.0/24 via 10.77.51.254
ip route replace 10.77.60.0/24 via 10.77.51.254
install -m 0444 /run/fieldkest-tls/server.crt /tmp/fieldkest.crt
install -m 0444 /run/fieldkest-tls/server.key /tmp/fieldkest.key
install -m 0444 /run/fieldkest-auth/worker-hmac.key /tmp/worker-hmac.key
setpriv --reuid=verdaccio --regid=verdaccio --init-groups \
  node /opt/verdaccio/node_modules/verdaccio/bin/verdaccio --config /etc/verdaccio/config.yaml >/tmp/verdaccio.log 2>&1 &
verdaccio_pid=$!
setpriv --reuid=fieldkest-registry --regid=fieldkest-registry --init-groups \
  python3 /opt/fieldkest-registry/registry.py &
api_pid=$!
trap 'kill "$api_pid" "$verdaccio_pid" 2>/dev/null || true' INT TERM EXIT
wait "$api_pid"
