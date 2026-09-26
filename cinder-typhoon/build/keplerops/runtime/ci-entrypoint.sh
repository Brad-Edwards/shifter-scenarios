#!/bin/sh
set -eu
ip route replace 10.77.50.0/24 via 10.77.51.254
ip route replace 10.77.52.0/24 via 10.77.51.254
ip route replace 10.77.60.0/24 via 10.77.51.254
install -m 0444 /run/fieldkest-tls/server.crt /tmp/fieldkest.crt
install -m 0444 /run/fieldkest-tls/server.key /tmp/fieldkest.key
install -m 0444 /run/fieldkest-tls/ca.crt /tmp/fieldkest-ca.crt
install -m 0444 /run/fieldkest-auth/worker-hmac.key /tmp/worker-hmac.key
mkdir -p /var/lib/fieldkest-ci/audit /var/lib/fieldkest-ci/results /var/lib/fieldkest-ci/workspaces/rowan /var/lib/fieldkest-handover
chown -R fieldkest-ci:fieldkest-ci /var/lib/fieldkest-ci/audit /var/lib/fieldkest-ci/results /var/lib/fieldkest-ci/workspaces/rowan /var/lib/fieldkest-handover
exec setpriv --reuid=fieldkest-ci --regid=fieldkest-ci --init-groups python3 /opt/fieldkest/ci.py
