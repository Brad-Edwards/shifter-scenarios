#!/bin/sh
set -eu
umask 077

chown fieldlink:fieldlink /var/lib/fieldlink-connector
chmod 0750 /var/lib/fieldlink-connector
chown arwc-connector:arwc-connector /var/lib/arwc-connector
chmod 0700 /var/lib/arwc-connector

install -d -o fieldlink -g fieldlink -m 0770 \
  /var/lib/fieldlink-connector/handover \
  /var/lib/fieldlink-connector/receipts
for shared_file in \
  /var/lib/fieldlink-connector/handover/corporate-session \
  /var/lib/fieldlink-connector/handover/customer-transition.json; do
  if [ -f "$shared_file" ]; then
    chown arwc-connector:fieldlink "$shared_file"
    chmod 0440 "$shared_file"
  fi
done
install -d -o arwc-connector -g fieldlink -m 0770 \
  /var/lib/fieldlink-connector/consumer \
  /var/lib/fieldlink-connector/consumer/candidates
install -d -o arwc-connector -g arwc-connector -m 0700 \
  /var/lib/arwc-connector/audit \
  /var/lib/arwc-connector/auth \
  /var/lib/arwc-connector/state

install -o arwc-connector -g arwc-connector -m 0400 \
  /run/arwc-tls/server.crt /tmp/arwc-server.crt
install -o arwc-connector -g arwc-connector -m 0400 \
  /run/arwc-tls/server.key /tmp/arwc-server.key
install -o fieldlink -g fieldlink -m 0444 \
  /run/arwc-tls/ca.crt /tmp/arwc-ca.crt
install -o arwc-connector -g arwc-connector -m 0400 \
  /run/arwc-peer/keplerops-ca.crt /tmp/keplerops-ca.crt

setpriv --reuid=arwc-connector --regid=arwc-connector --init-groups \
  python3 /opt/customer-handover/customer_handover.py &
handover_pid=$!

setpriv --reuid=arwc-connector --regid=arwc-connector --init-groups \
  python3 /opt/fieldlink-connector/fieldlink_consumer.py &
consumer_pid=$!

trap 'kill "$handover_pid" "$consumer_pid" 2>/dev/null || true; wait || true' TERM INT EXIT
while kill -0 "$handover_pid" "$consumer_pid" 2>/dev/null; do
  sleep 1
done
exit 1
