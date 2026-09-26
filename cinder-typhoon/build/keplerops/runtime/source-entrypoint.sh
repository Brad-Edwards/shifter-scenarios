#!/bin/sh
set -eu
ip route replace 10.77.50.0/24 via 10.77.51.254
ip route replace 10.77.52.0/24 via 10.77.51.254
ip route replace 10.77.53.0/24 via 10.77.51.254
ip route replace 10.77.60.0/24 via 10.77.51.254
install -m 0444 /run/fieldkest-tls/server.crt /tmp/fieldkest.crt
install -m 0444 /run/fieldkest-tls/server.key /tmp/fieldkest.key
install -m 0444 /run/fieldkest-auth/worker-hmac.key /tmp/worker-hmac.key
exec setpriv --reuid=git --regid=git --init-groups python3 /opt/fieldkest/source.py
