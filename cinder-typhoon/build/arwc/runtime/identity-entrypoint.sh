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

python3 /usr/local/libexec/arwc-handover.py wait \
  --service arwc-identity \
  --accepted-hash /var/lib/arwc-identity/auth/corporate-session.sha256
chown arwc-identity:arwc-identity /var/lib/arwc-identity/auth/corporate-session.sha256
chmod 0400 /var/lib/arwc-identity/auth/corporate-session.sha256

for file in server.crt server.key; do
  install -o arwc-identity -g arwc-identity -m 0400 "/run/arwc-tls/$file" "/tmp/$file"
done

exec setpriv --reuid=arwc-identity --regid=arwc-identity --init-groups \
  python3 /opt/corporate-identity/corporate_identity.py
