#!/bin/sh
set -eu
umask 077

chown arwc-archive:arwc-archive /var/lib/arwc-archive
chmod 0700 /var/lib/arwc-archive
install -d -o arwc-archive -g arwc-archive -m 0700 \
  /var/lib/arwc-archive/audit \
  /var/lib/arwc-archive/auth \
  /var/lib/arwc-archive/state \
  /var/lib/arwc-archive/workflow
install -d -o arwc-archive -g arwc-handover -m 0750 \
  /var/lib/arwc-archive/results \
  /var/lib/arwc-archive/handover
install -d -o arwc-archive -g arwc-archive -m 0700 \
  /var/lib/arwc-archive/artifacts

python3 /usr/local/libexec/arwc-handover.py wait \
  --service arwc-archive \
  --accepted-hash /var/lib/arwc-archive/auth/corporate-session.sha256
chown arwc-archive:arwc-archive /var/lib/arwc-archive/auth/corporate-session.sha256
chmod 0400 /var/lib/arwc-archive/auth/corporate-session.sha256

for file in server.crt server.key archive-ca.crt archive-ca.key; do
  install -o arwc-archive -g arwc-archive -m 0400 "/run/arwc-tls/$file" "/tmp/$file"
done

# Build CA bundle: golden CA + native IT CA (for Nextcloud connections).
cat /run/arwc-tls/ca.crt > /tmp/arwc-ca-bundle.pem
if [ -r /run/arwc-native/root-ca.crt ]; then
  cat /run/arwc-native/root-ca.crt >> /tmp/arwc-ca-bundle.pem
fi
chmod 0644 /tmp/arwc-ca-bundle.pem

# Fetch the archive workflow contract from Nextcloud at startup.
# The contract is seeded into Nextcloud by seed-archive; a local copy is kept
# on the archive volume so the service does not need Nextcloud on every request.
setpriv --reuid=arwc-archive --regid=arwc-archive --init-groups \
  python3 /opt/retained-archive/fetch_archive_workflow.py

setpriv --reuid=arwc-archive --regid=arwc-archive --init-groups \
  python3 /opt/retained-archive/generate_archive_artifacts.py

exec setpriv --reuid=arwc-archive --regid=arwc-archive --init-groups \
  python3 /opt/retained-archive/retained_archive.py
