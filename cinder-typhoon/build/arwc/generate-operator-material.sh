#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
OPERATOR_DIR=${ARWC_OPERATOR_DIR:-"$ROOT/.operator"}
mkdir -p "$OPERATOR_DIR/tls"
mkdir -p "$OPERATOR_DIR/integration"
chmod 0700 "$OPERATOR_DIR" "$OPERATOR_DIR/tls" "$OPERATOR_DIR/integration"

case ${1-} in
  '') ca_profile_only=false ;;
  --ca-profile-only)
    [[ $(hostname) == cinder-arwc-dev ]] || { echo 'CA profile repair is restricted to cinder-arwc-dev.' >&2; exit 1; }
    ca_profile_only=true
    for identity in ca archive-ca; do
      [[ -s "$OPERATOR_DIR/tls/$identity.key" && -s "$OPERATOR_DIR/tls/$identity.crt" ]] || {
        echo 'CA profile repair requires the existing key and certificate.' >&2
        exit 1
      }
    done
    ;;
  *) echo 'Usage: generate-operator-material.sh [--ca-profile-only]' >&2; exit 2 ;;
esac

ca_profile() {
  local identity=$1 subject=$2
  if [[ ! -s "$OPERATOR_DIR/tls/$identity.key" ]]; then
    openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 \
      -out "$OPERATOR_DIR/tls/$identity.key" 2>/dev/null
  fi
  if [[ -s "$OPERATOR_DIR/tls/$identity.crt" ]]; then
    subject=$(openssl x509 -in "$OPERATOR_DIR/tls/$identity.crt" -noout -subject -nameopt compat | sed 's/^subject=//')
  fi
  if [[ ! -s "$OPERATOR_DIR/tls/$identity.crt" ]] || ! openssl x509 \
      -in "$OPERATOR_DIR/tls/$identity.crt" -noout -ext keyUsage 2>/dev/null | grep -q 'Certificate Sign'; then
    openssl req -x509 -new -key "$OPERATOR_DIR/tls/$identity.key" -days 3650 \
      -subj "$subject" \
      -addext 'basicConstraints=critical,CA:TRUE' \
      -addext 'keyUsage=critical,keyCertSign,cRLSign' \
      -addext 'subjectKeyIdentifier=hash' \
      -addext 'authorityKeyIdentifier=keyid:always' \
      -out "$OPERATOR_DIR/tls/$identity.crt"
  fi
}

ca_profile ca '/CN=Alterra Corporate CA/O=Alterra Regional Water Company'
ca_profile archive-ca '/CN=Alterra Archive Enrollment CA/O=Alterra Regional Water Company'
chmod 0600 "$OPERATOR_DIR/tls/ca.key" "$OPERATOR_DIR/tls/archive-ca.key"
chmod 0644 "$OPERATOR_DIR/tls/ca.crt" "$OPERATOR_DIR/tls/archive-ca.crt"
if $ca_profile_only; then
  exit 0
fi

# Rotate the handover key only for an explicit full material generation.
openssl rand -hex 32 > "$OPERATOR_DIR/handover.key"

openssl req -newkey rsa:3072 -nodes \
  -subj '/CN=customer-handover.arwc.test/O=Alterra Regional Water Company' \
  -keyout "$OPERATOR_DIR/tls/server.key" -out "$OPERATOR_DIR/tls/server.csr" 2>/dev/null
cat >"$OPERATOR_DIR/tls/server.ext" <<'EOF'
subjectAltName=DNS:a-connector,DNS:fieldlink.arwc.test,DNS:customer-handover.arwc.test,DNS:a-business,DNS:business-workplace.arwc.test,DNS:a-data,DNS:planning-data.arwc.test,DNS:process-view.arwc.test,DNS:a-archive,DNS:retained-archive.arwc.test,DNS:a-identity,DNS:corporate-identity.arwc.test,DNS:a-data-bridge,DNS:integration-gateway.arwc.test,DNS:a-contractors,DNS:contractor-portal.arwc.test,DNS:a-contractor-bridge,DNS:field-gateway.arwc.test,DNS:process-read.arwc.test,DNS:a-approval,DNS:maintenance-review.arwc.test,DNS:a-renderer,DNS:maintenance-renderer.arwc.test,DNS:a-control-broker,DNS:control-broker.arwc.test,DNS:a-hmi,DNS:supervisory-operations.arwc.test,DNS:a-historian,DNS:process-historian.arwc.test,DNS:a-engineering,DNS:engineering-workbench.arwc.test,DNS:a-instruments,DNS:independent-instruments.arwc.test,DNS:a-reservoir,DNS:reservoir-controller.arwc.test,DNS:a-diagnostics,DNS:diagnostic-services.arwc.test,IP:10.77.60.20,IP:10.77.60.30,IP:10.77.60.40,IP:10.77.60.50,IP:10.77.60.60,IP:10.77.61.20,IP:10.77.61.30,IP:10.77.61.40,IP:10.77.62.10,IP:10.77.62.20,IP:10.77.62.30,IP:10.77.62.40,IP:10.77.63.10,IP:10.77.63.20,IP:10.77.63.30,IP:10.77.63.40,IP:10.77.63.50,IP:10.77.64.20,IP:10.77.64.40
keyUsage=digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
EOF
openssl x509 -req -days 825 -sha256 \
  -in "$OPERATOR_DIR/tls/server.csr" \
  -CA "$OPERATOR_DIR/tls/ca.crt" -CAkey "$OPERATOR_DIR/tls/ca.key" -CAcreateserial \
  -extfile "$OPERATOR_DIR/tls/server.ext" \
  -out "$OPERATOR_DIR/tls/server.crt" 2>/dev/null

# A locally valid placeholder keeps the connector available before the two
# carriers are paired. The pairing script replaces it with KeplerOps' public CA.
if [[ ! -s "$OPERATOR_DIR/integration/keplerops-ca.crt" ]]; then
  cp "$OPERATOR_DIR/tls/ca.crt" "$OPERATOR_DIR/integration/keplerops-ca.crt"
fi

chmod 0600 "$OPERATOR_DIR/tls/ca.key" "$OPERATOR_DIR/tls/archive-ca.key" "$OPERATOR_DIR/tls/server.key"
chmod 0600 "$OPERATOR_DIR/handover.key"
chmod 0644 "$OPERATOR_DIR/tls/ca.crt" "$OPERATOR_DIR/tls/archive-ca.crt" "$OPERATOR_DIR/tls/server.crt"
chmod 0644 "$OPERATOR_DIR/integration/keplerops-ca.crt"
