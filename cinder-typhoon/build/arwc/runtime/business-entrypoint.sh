#!/bin/sh
set -eu
umask 077

chown arwc-business:arwc-business /var/lib/arwc-business
chmod 0700 /var/lib/arwc-business
install -d -o arwc-business -g arwc-business -m 0700 \
  /var/lib/arwc-business/audit \
  /var/lib/arwc-business/auth \
  /var/lib/arwc-business/state

session=/run/arwc-corporate/handover/corporate-session
for _ in $(seq 1 60); do
  [ -s "$session" ] && break
  sleep 1
done
[ -s "$session" ]
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
