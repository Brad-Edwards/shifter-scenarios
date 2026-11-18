#!/bin/sh
set -eu
umask 077

chown arwc-archive:arwc-archive /var/lib/arwc-archive
chmod 0700 /var/lib/arwc-archive
install -d -o arwc-archive -g arwc-archive -m 0700 \
  /var/lib/arwc-archive/audit \
  /var/lib/arwc-archive/auth \
  /var/lib/arwc-archive/state \
  /var/lib/arwc-archive/workflow \
  /var/lib/arwc-archive/helper-staging
install -d -o arwc-archive -g arwc-handover -m 0750 \
  /var/lib/arwc-archive/results \
  /var/lib/arwc-archive/handover
install -d -o arwc-archive -g arwc-archive -m 0700 \
  /var/lib/arwc-archive/artifacts
# Set up the shared planning-evidence directory (for W06.3 PLANNER_EVIDENCE output).
# The planning-data service reads from this same volume to validate planner sessions.
if [ -d /run/arwc-planning-evidence ]; then
  chown arwc-archive:arwc-plan-evidence /run/arwc-planning-evidence
  chmod 2770 /run/arwc-planning-evidence
fi

python3 /usr/local/libexec/arwc-handover.py wait \
  --service arwc-archive \
  --accepted-hash /var/lib/arwc-archive/auth/corporate-session.sha256
chown arwc-archive:arwc-archive /var/lib/arwc-archive/auth/corporate-session.sha256
chmod 0400 /var/lib/arwc-archive/auth/corporate-session.sha256

for file in server.crt server.key; do
  install -o arwc-archive -g arwc-archive -m 0400 "/run/arwc-tls/$file" "/tmp/$file"
done
# archive-ca is used only by generate_archive_artifacts (W04.8+ collector signing);
# it is NOT used for client certificate verification (step-ca root is used instead).
for file in archive-ca.crt archive-ca.key; do
  if [ -r "/run/arwc-tls/$file" ]; then
    install -o arwc-archive -g arwc-archive -m 0400 "/run/arwc-tls/$file" "/tmp/$file"
  fi
done

# Build CA bundle: golden CA + native IT step-ca root and intermediate + archive CA.
# The bundle is used for Nextcloud connections and for verifying mTLS client
# certificates (both step-ca-signed and archive-CA-signed via enrollment).
cat /run/arwc-tls/ca.crt > /tmp/arwc-ca-bundle.pem
if [ -r /run/arwc-native/root-ca.crt ]; then
  cat /run/arwc-native/root-ca.crt >> /tmp/arwc-ca-bundle.pem
fi
if [ -r /run/arwc-step-ca/intermediate.crt ]; then
  cat /run/arwc-step-ca/intermediate.crt >> /tmp/arwc-ca-bundle.pem
fi
if [ -r /tmp/archive-ca.crt ]; then
  cat /tmp/archive-ca.crt >> /tmp/arwc-ca-bundle.pem
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
