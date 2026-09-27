#!/bin/sh
set -eu
umask 077

chown arwc-contractor-bridge:arwc-contractor-bridge /var/lib/arwc-contractor-bridge
chmod 0700 /var/lib/arwc-contractor-bridge
install -d -o arwc-contractor-bridge -g arwc-contractor-bridge -m 0700 \
  /var/lib/arwc-contractor-bridge/audit \
  /var/lib/arwc-contractor-bridge/state
for file in server.crt server.key; do
  install -o arwc-contractor-bridge -g arwc-contractor-bridge -m 0400 "/run/arwc-tls/$file" "/tmp/$file"
done

exec setpriv --reuid=arwc-contractor-bridge --regid=arwc-contractor-bridge --init-groups \
  python3 /opt/field-gateway/field_gateway.py
