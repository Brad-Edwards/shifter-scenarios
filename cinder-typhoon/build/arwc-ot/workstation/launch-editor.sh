#!/bin/bash
set -euo pipefail
export APPDIR=/opt/openplc-editor/squashfs-root
if [[ ${1-} == --cli ]]; then
  exec "$APPDIR/AppRun" "$@"
fi
exec "$APPDIR/AppRun" --disable-gpu --disable-setuid-sandbox "$@"
