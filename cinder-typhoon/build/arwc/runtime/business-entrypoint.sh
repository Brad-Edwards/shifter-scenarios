#!/bin/sh
set -eu
umask 077

chown arwc-business:arwc-business /var/lib/arwc-business
chmod 0700 /var/lib/arwc-business
install -d -o arwc-business -g arwc-business -m 0700 \
  /var/lib/arwc-business/audit \
  /var/lib/arwc-business/auth \
  /var/lib/arwc-business/state
install -d -o arwc-business -g arwc-archive-source -m 0750 \
  /var/lib/arwc-business/archive
install -d -o arwc-business -g arwc-integration -m 0750 \
  /var/lib/arwc-business/integration
install -d -o arwc-business -g arwc-relation -m 0750 \
  /var/lib/arwc-business/relation

session=/run/arwc-corporate/handover/corporate-session
install -d -m 0755 /run/arwc-status
echo waiting > /run/arwc-status/state
until [[ -s "$session" ]]; do sleep 5; done
token=$(tr -d '\n' < "$session")
if ! [[ "$token" =~ ^[0-9a-f]{64}$ ]]; then
  echo "arwc-business: invalid or cross-range handover token" >&2; exit 1
fi
echo ready > /run/arwc-status/state
tr -d '\n' < "$session" | sha256sum | awk '{print $1}' \
  > /var/lib/arwc-business/auth/corporate-session.sha256
chown arwc-business:arwc-business /var/lib/arwc-business/auth/corporate-session.sha256
chmod 0400 /var/lib/arwc-business/auth/corporate-session.sha256

install -o arwc-business -g arwc-business -m 0400 \
  /run/arwc-tls/server.crt /tmp/arwc-server.crt
install -o arwc-business -g arwc-business -m 0400 \
  /run/arwc-tls/server.key /tmp/arwc-server.key

exec setpriv --reuid=arwc-business --regid=arwc-business --init-groups \
  python3 /opt/business-workplace/business_workplace.py
