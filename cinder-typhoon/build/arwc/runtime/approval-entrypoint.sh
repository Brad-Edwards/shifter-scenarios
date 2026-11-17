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
install -o arwc-approval -g arwc-approval -m 0444 /run/arwc-tls/ca.crt /tmp/ca.crt
# Build CA bundle: corporate CA + step-ca root (for Nextcloud/documents.arwc.test).
cat /run/arwc-tls/ca.crt > /tmp/arwc-ca-bundle.pem
if [ -r /run/arwc-native/root-ca.crt ]; then
  cat /run/arwc-native/root-ca.crt >> /tmp/arwc-ca-bundle.pem
fi
chmod 0644 /tmp/arwc-ca-bundle.pem

# Allow traversal into the contractors handover directory for the approval service.
# The directory itself is group-accessible; only the root needs execute for other.
chmod o+x /var/lib/arwc-contractors || true

exec setpriv --reuid=arwc-approval --regid=arwc-approval --init-groups \
  python3 /opt/maintenance-review/maintenance_review.py
