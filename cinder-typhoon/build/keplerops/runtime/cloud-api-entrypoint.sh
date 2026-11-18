#!/bin/sh
set -eu
install -m 0444 /run/fieldkest-tls/server.crt /tmp/fieldkest.crt
install -m 0444 /run/fieldkest-tls/server.key /tmp/fieldkest.key
mkdir -p -m 1777 /tmp/cloud-api-results
# Make export credentials available if operator provides them
if [ -f /run/fieldkest-auth/aws-export ]; then
  install -m 0444 /run/fieldkest-auth/aws-export /tmp/cloud-api-results/export-credentials 2>/dev/null || true
  export EXPORT_CREDENTIALS_FILE=/tmp/cloud-api-results/export-credentials
fi
exec setpriv --reuid=fieldkest-cloud-api --regid=fieldkest-cloud-api --init-groups \
  python3 /opt/fieldkest/service.py
