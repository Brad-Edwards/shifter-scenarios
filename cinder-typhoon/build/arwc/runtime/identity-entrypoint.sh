#!/bin/sh
set -eu
umask 077

chown arwc-identity:arwc-identity /var/lib/arwc-identity
chmod 0700 /var/lib/arwc-identity
install -d -o arwc-identity -g arwc-identity -m 0700 \
  /var/lib/arwc-identity/audit \
  /var/lib/arwc-identity/auth \
  /var/lib/arwc-identity/state
install -d -o arwc-identity -g arwc-planning -m 0750 \
  /var/lib/arwc-identity/results \
  /var/lib/arwc-identity/planning
install -d -o arwc-identity -g arwc-archive-source -m 0750 \
  /var/lib/arwc-identity/archive

session=/run/arwc-corporate/handover/corporate-session
install -d -m 0755 /run/arwc-status
echo waiting > /run/arwc-status/state
until [[ -s "$session" ]]; do sleep 5; done
token=$(tr -d '\n' < "$session")
if ! [[ "$token" =~ ^[0-9a-f]{64}$ ]]; then
  echo "arwc-identity: invalid or cross-range handover token" >&2; exit 1
fi
echo ready > /run/arwc-status/state
tr -d '\n' < "$session" | sha256sum | awk '{print $1}' \
  > /var/lib/arwc-identity/auth/corporate-session.sha256
chown arwc-identity:arwc-identity /var/lib/arwc-identity/auth/corporate-session.sha256
chmod 0400 /var/lib/arwc-identity/auth/corporate-session.sha256

for file in server.crt server.key; do
  install -o arwc-identity -g arwc-identity -m 0400 "/run/arwc-tls/$file" "/tmp/$file"
done

exec setpriv --reuid=arwc-identity --regid=arwc-identity --init-groups \
  python3 /opt/corporate-identity/corporate_identity.py
