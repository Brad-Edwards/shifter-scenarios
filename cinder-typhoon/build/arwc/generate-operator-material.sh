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

if [[ ! -s "$OPERATOR_DIR/tls/archive-ca.key" ]]; then
  openssl req -x509 -newkey rsa:3072 -nodes -days 3650 \
    -subj '/CN=Alterra Archive Enrollment CA/O=Alterra Regional Water Company' \
    -keyout "$OPERATOR_DIR/tls/archive-ca.key" -out "$OPERATOR_DIR/tls/archive-ca.crt" 2>/dev/null
fi

openssl req -newkey rsa:3072 -nodes \
  -subj '/CN=customer-handover.arwc.test/O=Alterra Regional Water Company' \
  -keyout "$OPERATOR_DIR/tls/server.key" -out "$OPERATOR_DIR/tls/server.csr" 2>/dev/null
cat >"$OPERATOR_DIR/tls/server.ext" <<'EOF'
subjectAltName=DNS:a-connector,DNS:fieldlink.arwc.test,DNS:customer-handover.arwc.test,DNS:a-business,DNS:business-workplace.arwc.test,DNS:a-data,DNS:planning-data.arwc.test,DNS:process-view.arwc.test,DNS:a-archive,DNS:retained-archive.arwc.test,DNS:a-identity,DNS:corporate-identity.arwc.test,DNS:a-data-bridge,DNS:integration-gateway.arwc.test,DNS:a-contractors,DNS:contractor-portal.arwc.test,DNS:a-contractor-bridge,DNS:field-gateway.arwc.test,DNS:process-read.arwc.test,DNS:a-approval,DNS:maintenance-review.arwc.test,DNS:a-hmi,DNS:supervisory-operations.arwc.test,DNS:a-historian,DNS:process-historian.arwc.test,DNS:a-engineering,DNS:engineering-workbench.arwc.test,DNS:a-instruments,DNS:independent-instruments.arwc.test,IP:10.77.60.20,IP:10.77.60.30,IP:10.77.60.40,IP:10.77.60.50,IP:10.77.60.60,IP:10.77.61.20,IP:10.77.61.30,IP:10.77.62.20,IP:10.77.62.30,IP:10.77.63.20,IP:10.77.63.30,IP:10.77.63.40,IP:10.77.64.40
keyUsage=digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
EOF
openssl x509 -req -days 825 -sha256 \
  -in "$OPERATOR_DIR/tls/server.csr" \
  -CA "$OPERATOR_DIR/tls/ca.crt" -CAkey "$OPERATOR_DIR/tls/ca.key" -CAcreateserial \
  -extfile "$OPERATOR_DIR/tls/server.ext" \
  -out "$OPERATOR_DIR/tls/server.crt" 2>/dev/null

chmod 0600 "$OPERATOR_DIR/tls/ca.key" "$OPERATOR_DIR/tls/archive-ca.key" "$OPERATOR_DIR/tls/server.key"
chmod 0644 "$OPERATOR_DIR/tls/ca.crt" "$OPERATOR_DIR/tls/archive-ca.crt" "$OPERATOR_DIR/tls/server.crt"
