#!/bin/sh
set -eu

for route in 10.77.50.0/24 10.77.51.0/24 10.77.52.0/24 10.77.53.0/24; do
  if ! ip route show "$route" | grep -q 'scope link'; then
    ip route replace "$route" via "$FIELDKEST_GATEWAY"
  fi
done
install -m 0400 /run/fieldkest-tls/server.key /tmp/fieldlink-preview.key
chown gotenberg:gotenberg /tmp/fieldlink-preview.key
install -m 0444 /run/fieldkest-tls/server.crt /tmp/fieldlink-preview.crt
install -m 0444 /run/fieldkest-tls/ca.crt /tmp/fieldlink-ca.crt
exec setpriv --reuid=gotenberg --regid=gotenberg --init-groups /usr/bin/tini -- "$@"
