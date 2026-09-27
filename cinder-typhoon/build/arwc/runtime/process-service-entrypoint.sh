#!/bin/sh
set -eu
umask 027

user=${ARWC_SERVICE_USER:?}
root=${ARWC_STATE_ROOT:?}
role=${ARWC_PROCESS_ROLE:?}

chown "$user:$user" "$root"
chmod 0700 "$root"
install -d -o "$user" -g "$user" -m 0700 "$root/audit" "$root/state"
if [ "$role" = engineering ]; then
  install -d -o "$user" -g "$user" -m 0700 \
    "$root/artifacts" \
    "$root/artifacts/what-counts-as-intact" \
    "$root/artifacts/the-constraints-of-a-valid-looking-program"
  if [ ! -e "$root/artifacts/what-counts-as-intact/base.dpg" ]; then
    cp /opt/process-service/artifacts/w27/base.dpg \
      /opt/process-service/artifacts/w27/case-*.dpg \
      /opt/process-service/artifacts/w27/rot128-verifier \
      "$root/artifacts/what-counts-as-intact/"
    chown "$user:$user" "$root/artifacts/what-counts-as-intact/"*
    chmod 0400 "$root/artifacts/what-counts-as-intact/"*.dpg
    chmod 0500 "$root/artifacts/what-counts-as-intact/rot128-verifier"
  fi
fi
install -d -o root -g arwc-process-evidence -m 0750 /run/arwc-process-evidence
install -d -o "$user" -g arwc-process-evidence -m 0750 "/run/arwc-process-evidence/$role"

for file in server.crt server.key ca.crt; do
  install -o "$user" -g "$user" -m 0400 "/run/arwc-tls/$file" "/tmp/$file"
done

exec setpriv --reuid="$user" --regid="$user" --init-groups \
  python3 /opt/process-service/process_services.py
