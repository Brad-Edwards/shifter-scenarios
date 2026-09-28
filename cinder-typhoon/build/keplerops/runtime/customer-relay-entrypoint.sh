#!/bin/sh
set -eu
umask 077

ip route replace 10.77.50.0/24 via 10.77.60.254
ip route replace 10.77.51.0/24 via 10.77.60.254

install -d -o fieldkest-relay -g fieldkest-relay -m 0700 /tmp/customer-auth
install -o fieldkest-relay -g fieldkest-relay -m 0400 \
  /run/fieldkest-tls/server.crt /tmp/relay.crt
install -o fieldkest-relay -g fieldkest-relay -m 0400 \
  /run/fieldkest-tls/server.key /tmp/relay.key
for name in arwc-ca.crt package.crt package.key diagnostic.crt diagnostic.key; do
  install -o fieldkest-relay -g fieldkest-relay -m 0400 \
    "/run/customer-auth/$name" "/tmp/customer-auth/$name"
done

exec setpriv --reuid=fieldkest-relay --regid=fieldkest-relay --init-groups \
  --bounding-set=-all --inh-caps=-all --ambient-caps=-all \
  python3 /opt/fieldkest/customer_relay.py
