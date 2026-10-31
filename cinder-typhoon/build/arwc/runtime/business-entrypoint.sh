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

python3 /usr/local/libexec/arwc-handover.py wait \
  --service arwc-business \
  --accepted-hash /var/lib/arwc-business/auth/corporate-session.sha256
chown arwc-business:arwc-business /var/lib/arwc-business/auth/corporate-session.sha256
chmod 0400 /var/lib/arwc-business/auth/corporate-session.sha256

install -o arwc-business -g arwc-business -m 0400 \
  /run/arwc-tls/server.crt /tmp/arwc-server.crt
install -o arwc-business -g arwc-business -m 0400 \
  /run/arwc-tls/server.key /tmp/arwc-server.key

exec setpriv --reuid=arwc-business --regid=arwc-business --init-groups \
  python3 /opt/business-workplace/business_workplace.py
