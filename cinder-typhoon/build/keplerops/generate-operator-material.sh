#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
OPERATOR_DIR=${KEPLEROPS_OPERATOR_DIR:-"$ROOT/.operator"}
mkdir -p "$OPERATOR_DIR/tls"
chmod 0700 "$OPERATOR_DIR" "$OPERATOR_DIR/tls"

if [[ ! -s "$OPERATOR_DIR/rowan_ed25519" ]]; then
  ssh-keygen -q -t ed25519 -N '' -C 'rowan@keplerops' -f "$OPERATOR_DIR/rowan_ed25519"
fi
cp "$OPERATOR_DIR/rowan_ed25519.pub" "$OPERATOR_DIR/rowan_authorized_keys"

if [[ ! -s "$OPERATOR_DIR/tls/ca.key" ]]; then
  openssl req -x509 -newkey rsa:3072 -nodes -days 3650 \
    -subj '/CN=KeplerOps Range CA' \
    -keyout "$OPERATOR_DIR/tls/ca.key" -out "$OPERATOR_DIR/tls/ca.crt"
fi

if [[ ! -s "$OPERATOR_DIR/worker-hmac.key" ]]; then
  openssl rand 32 >"$OPERATOR_DIR/worker-hmac.key"
fi

openssl req -newkey rsa:3072 -nodes \
  -subj '/CN=keplerops.test' \
  -keyout "$OPERATOR_DIR/tls/server.key" -out "$OPERATOR_DIR/tls/server.csr" 2>/dev/null
cat >"$OPERATOR_DIR/tls/server.ext" <<'EOF'
subjectAltName=DNS:k-dev.keplerops.test,DNS:source.keplerops.test,DNS:packages.keplerops.test,DNS:ci.keplerops.test,DNS:preview.keplerops.test,DNS:support.keplerops.test,DNS:indexer.keplerops.test,DNS:staff.keplerops.test,DNS:identity.keplerops.test,DNS:cert.keplerops.test,DNS:cloud.keplerops.test,DNS:cloud-api.keplerops.test,DNS:data.keplerops.test,DNS:workload.keplerops.test,DNS:assistant.keplerops.test
keyUsage=digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
EOF
openssl x509 -req -days 825 -sha256 \
  -in "$OPERATOR_DIR/tls/server.csr" \
  -CA "$OPERATOR_DIR/tls/ca.crt" -CAkey "$OPERATOR_DIR/tls/ca.key" -CAcreateserial \
  -extfile "$OPERATOR_DIR/tls/server.ext" \
  -out "$OPERATOR_DIR/tls/server.crt" 2>/dev/null

chmod 0600 "$OPERATOR_DIR/rowan_ed25519" "$OPERATOR_DIR/worker-hmac.key" "$OPERATOR_DIR/tls/ca.key" "$OPERATOR_DIR/tls/server.key"
chmod 0644 "$OPERATOR_DIR/rowan_ed25519.pub" "$OPERATOR_DIR/rowan_authorized_keys" "$OPERATOR_DIR/tls/ca.crt" "$OPERATOR_DIR/tls/server.crt"
