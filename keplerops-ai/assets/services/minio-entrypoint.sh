#!/bin/sh
set -eu
: "${KEPLEROPS_BUCKET:?bucket required}"
MINIO_ROOT_USER=$(cat /run/keplerops/minio-root-user)
MINIO_ROOT_PASSWORD=$(cat /run/keplerops/minio-root-password)
export MINIO_ROOT_USER MINIO_ROOT_PASSWORD
minio server /data --address :9000 --certs-dir /run/tls &
server=$!
for delay in 1 1 2 3 5 8; do
  if mc alias set local https://127.0.0.1:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" --insecure >/dev/null 2>&1; then
    mc mb --insecure --ignore-existing "local/$KEPLEROPS_BUCKET" >/dev/null
    if [ "$KEPLEROPS_BUCKET" = keplerops-artifacts ]; then
      mc cp --insecure /opt/keplerops/seed/deployment-manifest.yaml "local/$KEPLEROPS_BUCKET/manifests/deployment-manifest.yaml" >/dev/null
      mc cp --insecure /opt/keplerops/seed/model.yaml "local/$KEPLEROPS_BUCKET/manifests/model.yaml" >/dev/null
      /usr/local/bin/minio-company-state local "$KEPLEROPS_BUCKET"
    fi
    wait "$server"
    exit $?
  fi
  sleep "$delay"
done
kill "$server" 2>/dev/null || true
wait "$server" 2>/dev/null || true
echo 'minio seed failed' >&2
exit 1
