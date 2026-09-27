#!/bin/sh
set -eu
umask 027

user=${ARWC_SERVICE_USER:?}
root=${ARWC_STATE_ROOT:?}
role=${ARWC_PROCESS_ROLE:?}

chown "$user:$user" "$root"
chmod 0700 "$root"
install -d -o "$user" -g "$user" -m 0700 "$root/audit" "$root/state"
install -d -o root -g arwc-process-evidence -m 0750 /run/arwc-process-evidence
install -d -o "$user" -g arwc-process-evidence -m 0750 "/run/arwc-process-evidence/$role"

for file in server.crt server.key ca.crt; do
  install -o "$user" -g "$user" -m 0400 "/run/arwc-tls/$file" "/tmp/$file"
done

exec setpriv --reuid="$user" --regid="$user" --init-groups \
  python3 /opt/process-service/process_services.py
