#!/bin/sh
set -eu
umask 077

chown arwc-contractors:arwc-contractors /var/lib/arwc-contractors
chmod 0700 /var/lib/arwc-contractors
install -d -o arwc-contractors -g arwc-contractors -m 0700 \
  /var/lib/arwc-contractors/audit \
  /var/lib/arwc-contractors/auth \
  /var/lib/arwc-contractors/state
install -d -o arwc-contractors -g arwc-field-session -m 0750 \
  /var/lib/arwc-contractors/handover

session=/run/arwc-corporate/handover/corporate-session
for _ in $(seq 1 60); do
  [ -s "$session" ] && break
  sleep 1
done
[ -s "$session" ]
tr -d '\n' < "$session" | sha256sum | awk '{print $1}' \
  > /var/lib/arwc-contractors/auth/corporate-session.sha256
chown arwc-contractors:arwc-contractors /var/lib/arwc-contractors/auth/corporate-session.sha256
chmod 0400 /var/lib/arwc-contractors/auth/corporate-session.sha256

for file in server.crt server.key; do
  install -o arwc-contractors -g arwc-contractors -m 0400 "/run/arwc-tls/$file" "/tmp/$file"
done
install -o arwc-contractors -g arwc-contractors -m 0444 /run/arwc-tls/ca.crt /tmp/ca.crt

exec setpriv --reuid=arwc-contractors --regid=arwc-contractors --init-groups \
  python3 /opt/contractor-portal/contractor_portal.py
