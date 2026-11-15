#!/usr/bin/env bash
set -euo pipefail
ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
operator=${KEPLEROPS_OPERATOR_DIR:-./.operator}
install -m 0600 "$operator/tls/server.key" "$operator/native-platform/postgres-server.key"
chown 70:70 "$operator/native-platform/postgres-server.key"
install -m 0644 "$operator/tls/server.crt" "$operator/native-platform/postgres-server.crt"
echo 'Native PostgreSQL leaf material prepared.'
