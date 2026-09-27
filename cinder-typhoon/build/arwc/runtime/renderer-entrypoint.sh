#!/bin/sh
set -eu
umask 077

chown arwc-renderer:arwc-renderer /var/lib/arwc-renderer
chmod 0700 /var/lib/arwc-renderer
install -d -o arwc-renderer -g arwc-renderer -m 0700 \
  /var/lib/arwc-renderer/audit \
  /var/lib/arwc-renderer/state
install -d -o arwc-renderer -g arwc-renderer-evidence -m 2750 \
  /var/lib/arwc-renderer/handover
for file in server.crt server.key; do
  install -o arwc-renderer -g arwc-renderer -m 0400 "/run/arwc-tls/$file" "/tmp/$file"
done

exec setpriv --reuid=arwc-renderer --regid=arwc-renderer --init-groups \
  python3 /opt/maintenance-renderer/maintenance_renderer.py
