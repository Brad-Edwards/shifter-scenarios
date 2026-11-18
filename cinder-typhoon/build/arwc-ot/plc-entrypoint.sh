#!/bin/bash
# Restore the compiled PLC binary from the persistent volume on container recreate.
# The compiled libplc_*.so lives in /workdir/build (writable layer, lost on recreate).
# upload_fixture.py saves a copy to /var/run/runtime/libplc-backup.so (plc-state volume).
# This entrypoint restores it before the runtime starts so OPC UA comes up without
# needing a fresh editor upload after every recreate.
set -euo pipefail
BINARY_BACKUP=/var/run/runtime/libplc-backup.so
BUILD=/workdir/build
if [[ -f $BINARY_BACKUP ]] && ! ls "$BUILD"/libplc_*.so > /dev/null 2>&1; then
    mkdir -p "$BUILD"
    HASH=$(sha256sum "$BINARY_BACKUP" | cut -c1-16)
    cp "$BINARY_BACKUP" "$BUILD/libplc_${HASH}.so"
    echo "[plc-entrypoint] Restored compiled PLC binary from persistent volume (hash prefix: $HASH)."
fi
OPCUA_BACKUP=/var/run/runtime/opcua.json.bak
OPCUA_DEST=/workdir/core/src/drivers/plugins/python/opcua/opcua.json
if [[ -f $OPCUA_BACKUP ]] && ! [[ -f $OPCUA_DEST ]]; then
    mkdir -p "$(dirname "$OPCUA_DEST")"
    cp "$OPCUA_BACKUP" "$OPCUA_DEST"
    echo "[plc-entrypoint] Restored opcua.json from persistent volume."
fi
# Restore the OPC UA server certificate and private key so Telegraf does not
# need to be re-configured after every recreate. auto_self_signed generates a
# new pair on every fresh start; restoring the original pair keeps the cert
# that Telegraf already trusts (via prepare_services.py server-cert.pem).
CERTS=/workdir/core/src/drivers/plugins/python/opcua/certs
if [[ -f /var/run/runtime/opcua-server-cert.bak && -f /var/run/runtime/opcua-server-key.bak ]]; then
    mkdir -p "$CERTS"
    cp /var/run/runtime/opcua-server-cert.bak "$CERTS/server_cert.pem"
    cp /var/run/runtime/opcua-server-key.bak "$CERTS/server_key.pem"
    echo "[plc-entrypoint] Restored OPC UA server certificate and key from persistent volume."
fi
exec bash /workdir/start_openplc.sh "$@"
