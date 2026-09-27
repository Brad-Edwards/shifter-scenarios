#!/bin/sh
set -eu
umask 077

chown arwc-reservoir:arwc-reservoir /var/lib/arwc-reservoir
chmod 0700 /var/lib/arwc-reservoir
install -d -o arwc-reservoir -g arwc-reservoir -m 0700 \
  /var/lib/arwc-reservoir/audit \
  /var/lib/arwc-reservoir/results \
  /var/lib/arwc-reservoir/state

for file in server.crt server.key; do
  install -o arwc-reservoir -g arwc-reservoir -m 0400 "/run/arwc-tls/$file" "/tmp/$file"
done

exec setpriv --reuid=arwc-reservoir --regid=arwc-reservoir --init-groups \
  python3 /opt/reservoir-controller/reservoir_controller.py
