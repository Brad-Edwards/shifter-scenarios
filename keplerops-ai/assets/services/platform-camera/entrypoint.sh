#!/bin/sh
set -eu

cert_file=${PLATFORM_CAMERA_TLS_CERT_FILE:-/run/tls/tls.crt}
key_file=${PLATFORM_CAMERA_TLS_KEY_FILE:-/run/tls/tls.key}
allow_plaintext=${PLATFORM_CAMERA_ALLOW_PLAINTEXT:-0}

set -- python3 -m uvicorn app:app \
  --host 0.0.0.0 \
  --port 8480 \
  --workers 1 \
  --no-access-log \
  --no-proxy-headers

if [ -r "$cert_file" ] && [ -r "$key_file" ]; then
  set -- "$@" --ssl-certfile "$cert_file" --ssl-keyfile "$key_file"
elif [ -e "$cert_file" ] || [ -e "$key_file" ]; then
  echo "platform-camera requires both readable TLS files" >&2
  exit 78
elif [ "$allow_plaintext" != "1" ]; then
  echo "platform-camera requires /run/tls/tls.crt and tls.key" >&2
  echo "set PLATFORM_CAMERA_ALLOW_PLAINTEXT=1 only for local focused tests" >&2
  exit 78
fi

exec "$@"
