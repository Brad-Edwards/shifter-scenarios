#!/bin/sh
set -eu
umask 077

chown arwc-contractors:arwc-contractors-access /var/lib/arwc-contractors
chmod 0750 /var/lib/arwc-contractors
install -d -o arwc-contractors -g arwc-contractors -m 0700 \
  /var/lib/arwc-contractors/audit \
  /var/lib/arwc-contractors/auth \
  /var/lib/arwc-contractors/state
install -d -o root -g arwc-contractors-access -m 0750 \
  /var/lib/arwc-contractors/handover

python3 /usr/local/libexec/arwc-handover.py wait \
  --service arwc-contractors \
  --accepted-hash /var/lib/arwc-contractors/auth/corporate-session.sha256
chown arwc-contractors:arwc-contractors /var/lib/arwc-contractors/auth/corporate-session.sha256
chmod 0400 /var/lib/arwc-contractors/auth/corporate-session.sha256

for file in server.crt server.key; do
  install -o arwc-contractors -g arwc-contractors -m 0400 "/run/arwc-tls/$file" "/tmp/$file"
done
install -o arwc-contractors -g arwc-contractors -m 0444 /run/arwc-tls/ca.crt /tmp/ca.crt

# Build CA bundle: corporate CA + native step-ca root (for suppliers.arwc.test).
cat /run/arwc-tls/ca.crt > /tmp/arwc-ca-bundle.pem
if [ -r /run/arwc-native/root-ca.crt ]; then
  cat /run/arwc-native/root-ca.crt >> /tmp/arwc-ca-bundle.pem
fi
chmod 0644 /tmp/arwc-ca-bundle.pem

exec setpriv --reuid=arwc-contractors --regid=arwc-contractors --init-groups \
  python3 /opt/contractor-portal/contractor_portal.py
