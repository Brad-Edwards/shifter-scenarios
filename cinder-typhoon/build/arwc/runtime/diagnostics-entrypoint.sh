#!/bin/sh
set -eu
umask 027
root=/var/lib/arwc-diagnostics
user=arwc-diagnostics
chown "$user:$user" "$root"
chmod 0700 "$root"
install -d -o "$user" -g "$user" -m 0700 "$root/audit" "$root/state"
for file in server.crt server.key ca.crt; do
  install -o "$user" -g "$user" -m 0400 "/run/arwc-tls/$file" "/tmp/$file"
done
exec setpriv --reuid="$user" --regid="$user" --init-groups \
  python3 /opt/diagnostic-services/diagnostic_services.py
