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
    "$root/artifacts/integrity-verifier" \
    "$root/artifacts/collision-model" \
    "$root/artifacts/utility-contract" \
    "$root/artifacts/controlled-flow"
  install -d -o "$user" -g "$user" -m 0700 \
    "$root/artifacts/replay-model-created" \
    "$root/artifacts/replay-transitions-created" \
    "$root/artifacts/replay-condition-created" \
    "$root/artifacts/replay-witness-created"
  if [ ! -e "$root/artifacts/integrity-verifier/base.dpg" ]; then
    cp /opt/process-service/artifacts/integrity/base.dpg \
      /opt/process-service/artifacts/integrity/case-*.dpg \
      /opt/process-service/artifacts/integrity/rot128-verifier \
      "$root/artifacts/integrity-verifier/"
    chown "$user:$user" "$root/artifacts/integrity-verifier/"*
    chmod 0400 "$root/artifacts/integrity-verifier/"*.dpg
    chmod 0500 "$root/artifacts/integrity-verifier/rot128-verifier"
  fi
fi
install -d -o root -g arwc-process-evidence -m 0750 /run/arwc-process-evidence
install -d -o "$user" -g arwc-process-evidence -m 0750 "/run/arwc-process-evidence/$role"

for file in server.crt server.key ca.crt; do
  install -o "$user" -g "$user" -m 0400 "/run/arwc-tls/$file" "/tmp/$file"
done

exec setpriv --reuid="$user" --regid="$user" --init-groups \
  python3 /opt/process-service/process_services.py
