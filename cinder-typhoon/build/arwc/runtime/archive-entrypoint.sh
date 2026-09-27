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
  /var/lib/arwc-archive/results

session=/run/arwc-corporate/handover/corporate-session
for _ in $(seq 1 60); do
  [ -s "$session" ] && break
  sleep 1
done
[ -s "$session" ]
tr -d '\n' < "$session" | sha256sum | awk '{print $1}' \
  > /var/lib/arwc-archive/auth/corporate-session.sha256
chown arwc-archive:arwc-archive /var/lib/arwc-archive/auth/corporate-session.sha256
chmod 0400 /var/lib/arwc-archive/auth/corporate-session.sha256

for file in server.crt server.key archive-ca.crt archive-ca.key; do
  install -o arwc-archive -g arwc-archive -m 0400 "/run/arwc-tls/$file" "/tmp/$file"
done

exec setpriv --reuid=arwc-archive --regid=arwc-archive --init-groups \
  python3 /opt/retained-archive/retained_archive.py
