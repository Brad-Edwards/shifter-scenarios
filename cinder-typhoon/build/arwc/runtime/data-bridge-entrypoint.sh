#!/bin/sh
set -eu
umask 077

for file in server.crt server.key ca.crt; do
  install -o arwc-data-bridge -g arwc-data-bridge -m 0400 "/run/arwc-tls/$file" "/tmp/$file"
done

if [ -d /run/arwc-ot ]; then
  for file in operating-reader.json pg-service.conf pgpass history-ca.pem; do
    install -o arwc-data-bridge -g arwc-data-bridge -m 0400 "/run/arwc-ot/$file" "/tmp/ot-$file"
  done
fi

export HOME=/tmp
exec setpriv --reuid=arwc-data-bridge --regid=arwc-data-bridge --init-groups \
  python3 /opt/integration-gateway/integration_gateway.py
