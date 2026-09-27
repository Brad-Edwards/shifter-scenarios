#!/bin/sh
set -eu
umask 077

chown arwc-approval:arwc-approval /var/lib/arwc-approval
chmod 0700 /var/lib/arwc-approval
install -d -o arwc-approval -g arwc-approval -m 0700 \
  /var/lib/arwc-approval/audit \
  /var/lib/arwc-approval/auth \
  /var/lib/arwc-approval/state
install -d -o arwc-approval -g arwc-approval-evidence -m 2750 \
  /var/lib/arwc-approval/evidence
for file in server.crt server.key; do
  install -o arwc-approval -g arwc-approval -m 0400 "/run/arwc-tls/$file" "/tmp/$file"
done

exec setpriv --reuid=arwc-approval --regid=arwc-approval --init-groups \
  python3 /opt/maintenance-review/maintenance_review.py
