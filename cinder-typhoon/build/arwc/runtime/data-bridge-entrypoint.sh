#!/bin/sh
set -eu
umask 077

chown arwc-data-bridge:arwc-data-bridge /var/lib/arwc-data-bridge
chmod 0700 /var/lib/arwc-data-bridge
install -d -o arwc-data-bridge -g arwc-data-bridge -m 0700 \
  /var/lib/arwc-data-bridge/audit \
  /var/lib/arwc-data-bridge/state
install -d -o root -g arwc-ot-read -m 0770 \
  /var/lib/arwc-data-bridge/handover

for file in server.crt server.key ca.crt; do
  install -o arwc-data-bridge -g arwc-data-bridge -m 0400 "/run/arwc-tls/$file" "/tmp/$file"
done

if [ -d /run/arwc-ot ]; then
  for file in operating-reader.json pg-service.conf pgpass history-ca.pem; do
    install -o arwc-data-bridge -g arwc-data-bridge -m 0400 "/run/arwc-ot/$file" "/tmp/ot-$file"
  done
fi

export HOME=/var/lib/arwc-data-bridge
exec setpriv --reuid=arwc-data-bridge --regid=arwc-data-bridge --init-groups \
  python3 /opt/integration-gateway/integration_gateway.py
