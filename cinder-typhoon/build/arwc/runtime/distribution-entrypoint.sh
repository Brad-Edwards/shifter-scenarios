#!/bin/sh
set -eu
umask 077
root=/var/lib/arwc-distribution
chown arwc-distribution:arwc-distribution "$root"
chmod 0700 "$root"
install -d -o arwc-distribution -g arwc-distribution -m 0700 "$root/audit" "$root/state" "$root/results"
for file in server.crt server.key; do
  install -o arwc-distribution -g arwc-distribution -m 0400 "/run/arwc-tls/$file" "/tmp/$file"
done
exec setpriv --reuid=arwc-distribution --regid=arwc-distribution --init-groups \
  python3 /opt/distribution-rehearsal/distribution_controller.py
