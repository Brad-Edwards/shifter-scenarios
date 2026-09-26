#!/bin/sh
set -eu
ip route replace 10.77.50.0/24 via 10.77.51.254
ip route replace 10.77.52.0/24 via 10.77.51.254
ip route replace 10.77.60.0/24 via 10.77.51.254
install -m 0444 /run/fieldkest-tls/server.crt /tmp/fieldkest.crt
install -m 0444 /run/fieldkest-tls/server.key /tmp/fieldkest.key
install -m 0444 /run/fieldkest-tls/ca.crt /tmp/fieldkest-ca.crt
install -m 0400 /run/fieldkest-oidc/fixture-issuer.key /tmp/fixture-issuer.key
chown fieldkest-support:fieldkest-support /tmp/fixture-issuer.key
install -m 0444 /run/fieldkest-oidc/fixture-issuer.pub /tmp/fixture-issuer.pub
exec setpriv --reuid=fieldkest-support --regid=fieldkest-support --init-groups python3 /opt/fieldkest/support.py
