#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
OPERATOR_DIR=${ARWC_OPERATOR_DIR:-"$ROOT/.operator"}
mkdir -p "$OPERATOR_DIR/tls"
chmod 0700 "$OPERATOR_DIR" "$OPERATOR_DIR/tls"

if [[ ! -s "$OPERATOR_DIR/tls/ca.key" ]]; then
  openssl req -x509 -newkey rsa:3072 -nodes -days 3650 \
    -subj '/CN=Alterra Corporate CA/O=Alterra Regional Water Company' \
    -keyout "$OPERATOR_DIR/tls/ca.key" -out "$OPERATOR_DIR/tls/ca.crt" 2>/dev/null
fi

openssl req -newkey rsa:3072 -nodes \
  -subj '/CN=customer-handover.arwc.test/O=Alterra Regional Water Company' \
  -keyout "$OPERATOR_DIR/tls/server.key" -out "$OPERATOR_DIR/tls/server.csr" 2>/dev/null
cat >"$OPERATOR_DIR/tls/server.ext" <<'EOF'
subjectAltName=DNS:a-connector,DNS:fieldlink.arwc.test,DNS:customer-handover.arwc.test,IP:10.77.60.20
keyUsage=digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
EOF
openssl x509 -req -days 825 -sha256 \
  -in "$OPERATOR_DIR/tls/server.csr" \
  -CA "$OPERATOR_DIR/tls/ca.crt" -CAkey "$OPERATOR_DIR/tls/ca.key" -CAcreateserial \
  -extfile "$OPERATOR_DIR/tls/server.ext" \
  -out "$OPERATOR_DIR/tls/server.crt" 2>/dev/null

chmod 0600 "$OPERATOR_DIR/tls/ca.key" "$OPERATOR_DIR/tls/server.key"
chmod 0644 "$OPERATOR_DIR/tls/ca.crt" "$OPERATOR_DIR/tls/server.crt"
