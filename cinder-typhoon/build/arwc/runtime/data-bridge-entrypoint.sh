#!/bin/sh
set -eu
umask 077

chown arwc-data-bridge:arwc-data-bridge /var/lib/arwc-data-bridge
chmod 0700 /var/lib/arwc-data-bridge
install -d -o arwc-data-bridge -g arwc-data-bridge -m 0700 \
  /var/lib/arwc-data-bridge/audit \
  /var/lib/arwc-data-bridge/state

for file in server.crt server.key; do
  install -o arwc-data-bridge -g arwc-data-bridge -m 0400 "/run/arwc-tls/$file" "/tmp/$file"
done

exec setpriv --reuid=arwc-data-bridge --regid=arwc-data-bridge --init-groups \
  python3 /opt/integration-gateway/integration_gateway.py
