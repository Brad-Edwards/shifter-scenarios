#!/bin/sh
set -eu
umask 077

chown arwc-control-broker:arwc-control-broker /var/lib/arwc-control-broker
chmod 0700 /var/lib/arwc-control-broker
install -d -o arwc-control-broker -g arwc-control-broker -m 0700 \
  /var/lib/arwc-control-broker/audit \
  /var/lib/arwc-control-broker/state
install -d -o arwc-control-broker -g arwc-control-authority -m 0750 \
  /var/lib/arwc-control-broker/authority
chown arwc-control-broker:arwc-control-broker /run/arwc
chmod 0755 /run/arwc
for file in server.crt server.key; do
  install -o arwc-control-broker -g arwc-control-broker -m 0400 "/run/arwc-tls/$file" "/tmp/$file"
done

exec setpriv --reuid=arwc-control-broker --regid=arwc-control-broker --init-groups \
  python3 /opt/control-broker/control_broker.py
