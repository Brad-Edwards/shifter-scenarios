#!/bin/sh
set -eu
for route in 10.77.50.0/24 10.77.51.0/24 10.77.52.0/24 10.77.53.0/24 10.77.60.0/24; do
  if ! ip route show "$route" | grep -q 'scope link'; then
    ip route replace "$route" via "$FIELDKEST_GATEWAY"
  fi
done
install -m 0444 /run/fieldkest-tls/server.crt /tmp/fieldkest.crt
install -m 0400 /run/fieldkest-tls/server.key /tmp/fieldkest.key
chown fieldkest-indexer:fieldkest-indexer /tmp/fieldkest.key
install -m 0444 /run/fieldkest-tls/ca.crt /tmp/fieldkest-ca.crt
exec setpriv --reuid=fieldkest-indexer --regid=fieldkest-indexer --init-groups \
  python3 /opt/fieldkest/indexer.py
