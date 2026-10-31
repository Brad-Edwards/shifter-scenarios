#!/bin/sh
set -eu
umask 077

chown arwc-archive:arwc-archive /var/lib/arwc-archive
chmod 0700 /var/lib/arwc-archive
install -d -o arwc-archive -g arwc-archive -m 0700 \
  /var/lib/arwc-archive/audit \
  /var/lib/arwc-archive/auth \
  /var/lib/arwc-archive/state
install -d -o arwc-archive -g arwc-handover -m 0750 \
  /var/lib/arwc-archive/results \
  /var/lib/arwc-archive/handover
install -d -o arwc-archive -g arwc-archive -m 0700 \
  /var/lib/arwc-archive/artifacts

session=/run/arwc-corporate/handover/corporate-session
install -d -m 0755 /run/arwc-status
echo waiting > /run/arwc-status/state
until [[ -s "$session" ]]; do sleep 5; done
token=$(tr -d '\n' < "$session")
if ! [[ "$token" =~ ^[0-9a-f]{64}$ ]]; then
  echo "arwc-archive: invalid or cross-range handover token" >&2; exit 1
fi
echo ready > /run/arwc-status/state
tr -d '\n' < "$session" | sha256sum | awk '{print $1}' \
  > /var/lib/arwc-archive/auth/corporate-session.sha256
chown arwc-archive:arwc-archive /var/lib/arwc-archive/auth/corporate-session.sha256
chmod 0400 /var/lib/arwc-archive/auth/corporate-session.sha256

for file in server.crt server.key archive-ca.crt archive-ca.key; do
  install -o arwc-archive -g arwc-archive -m 0400 "/run/arwc-tls/$file" "/tmp/$file"
done

setpriv --reuid=arwc-archive --regid=arwc-archive --init-groups \
  python3 /opt/retained-archive/generate_archive_artifacts.py

exec setpriv --reuid=arwc-archive --regid=arwc-archive --init-groups \
  python3 /opt/retained-archive/retained_archive.py
