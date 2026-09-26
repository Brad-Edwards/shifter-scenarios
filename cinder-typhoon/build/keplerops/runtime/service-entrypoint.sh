#!/bin/sh
set -eu

ip route replace 10.77.50.0/24 via 10.77.51.254
ip route replace 10.77.52.0/24 via 10.77.51.254
ip route replace 10.77.60.0/24 via 10.77.51.254

service_user="fieldkest-${FIELDKEST_SERVICE}"
install -m 0444 /run/fieldkest-tls/server.crt /tmp/fieldkest.crt
install -m 0444 /run/fieldkest-tls/server.key /tmp/fieldkest.key
exec setpriv --reuid="$service_user" --regid="$service_user" --init-groups \
  python3 /opt/fieldkest/service.py
