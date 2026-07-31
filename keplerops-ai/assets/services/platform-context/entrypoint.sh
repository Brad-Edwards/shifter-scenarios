#!/bin/sh
set -eu

process=${1:-api}
if [ "$#" -gt 0 ]; then shift; fi
printf '%s\n' "$process" >/tmp/platform-context-process
case "$process" in
  api)
    exec python3 -m uvicorn app:app --host 0.0.0.0 --port 8480 \
      --workers 1 --no-access-log --no-proxy-headers "$@"
    ;;
  file-worker)
    exec python3 file_worker.py "$@"
    ;;
  sync-worker)
    exec python3 sync_worker.py "$@"
    ;;
  reset)
    exec /opt/keplerops/platform-context/reset.sh "$@"
    ;;
  *)
    echo "unknown platform-context process: $process" >&2
    exit 64
    ;;
esac
