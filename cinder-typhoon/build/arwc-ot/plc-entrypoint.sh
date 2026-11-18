#!/bin/bash
# Restore the compiled PLC binary from the persistent volume on container recreate.
# The compiled libplc_*.so lives in /workdir/build (writable layer, lost on recreate).
# upload_fixture.py saves a copy to /var/run/runtime/libplc-backup.so (plc-state volume).
# This entrypoint restores it before the runtime starts so OPC UA comes up without
# needing a fresh editor upload after every recreate.
set -euo pipefail
BACKUP=/var/run/runtime/libplc-backup.so
BUILD=/workdir/build
if [[ -f $BACKUP ]] && ! ls "$BUILD"/libplc_*.so > /dev/null 2>&1; then
    mkdir -p "$BUILD"
    HASH=$(sha256sum "$BACKUP" | cut -c1-16)
    cp "$BACKUP" "$BUILD/libplc_${HASH}.so"
    echo "[plc-entrypoint] Restored compiled PLC binary from persistent volume (hash prefix: $HASH)."
fi
exec bash /workdir/start_openplc.sh "$@"
