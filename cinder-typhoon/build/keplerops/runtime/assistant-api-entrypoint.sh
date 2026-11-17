#!/bin/sh
set -eu

install -m 0444 /run/fieldkest-tls/server.crt /tmp/fieldkest.crt
install -m 0444 /run/fieldkest-tls/server.key /tmp/fieldkest.key
export FIELDKEST_TLS_CERT=/tmp/fieldkest.crt
export FIELDKEST_TLS_KEY=/tmp/fieldkest.key
exec setpriv --reuid=fieldkest-assistant-api --regid=fieldkest-assistant-api --init-groups \
  python3 /opt/fieldkest/service.py
