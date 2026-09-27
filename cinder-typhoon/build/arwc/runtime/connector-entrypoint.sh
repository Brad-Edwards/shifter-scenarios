#!/bin/sh
set -eu
umask 077

chown fieldlink:fieldlink /var/lib/fieldlink-connector
chmod 0700 /var/lib/fieldlink-connector
chown arwc-connector:arwc-connector /var/lib/arwc-connector
chmod 0700 /var/lib/arwc-connector

install -d -o fieldlink -g fieldlink -m 0700 \
  /var/lib/fieldlink-connector/handover \
  /var/lib/fieldlink-connector/receipts
install -d -o arwc-connector -g arwc-connector -m 0700 \
  /var/lib/arwc-connector/audit \
  /var/lib/arwc-connector/auth \
  /var/lib/arwc-connector/state

if [ ! -s /var/lib/fieldlink-connector/handover/corporate-session ]; then
  openssl rand -hex 32 > /var/lib/fieldlink-connector/handover/corporate-session
  chown fieldlink:fieldlink /var/lib/fieldlink-connector/handover/corporate-session
  chmod 0400 /var/lib/fieldlink-connector/handover/corporate-session
fi

tr -d '\n' < /var/lib/fieldlink-connector/handover/corporate-session | sha256sum \
  | awk '{print $1}' > /var/lib/arwc-connector/auth/corporate-session.sha256
chown arwc-connector:arwc-connector /var/lib/arwc-connector/auth/corporate-session.sha256
chmod 0400 /var/lib/arwc-connector/auth/corporate-session.sha256

cat > /var/lib/fieldlink-connector/handover/customer-transition.json <<'EOF'
{
  "account": "Alterra Regional Water Company",
  "tenant": "TEN-ARWC-047",
  "active_connector": "FLK-7.4.2",
  "maintenance_case": "MTN-CRR-204",
  "customer_receipt": "RCP-742-047",
  "customer_handover": "https://customer-handover.arwc.test:8443",
  "business_workplace": "https://business-workplace.arwc.test",
  "retained_archive": "https://retained-archive.arwc.test",
  "session_file": "/var/lib/fieldlink-connector/handover/corporate-session",
  "request_header": "Authorization: Bearer <session>"
}
EOF
chown fieldlink:fieldlink /var/lib/fieldlink-connector/handover/customer-transition.json
chmod 0400 /var/lib/fieldlink-connector/handover/customer-transition.json

install -o arwc-connector -g arwc-connector -m 0400 \
  /run/arwc-tls/server.crt /tmp/arwc-server.crt
install -o arwc-connector -g arwc-connector -m 0400 \
  /run/arwc-tls/server.key /tmp/arwc-server.key
install -o fieldlink -g fieldlink -m 0444 \
  /run/arwc-tls/ca.crt /tmp/arwc-ca.crt

exec setpriv --reuid=arwc-connector --regid=arwc-connector --init-groups \
  python3 /opt/customer-handover/customer_handover.py
