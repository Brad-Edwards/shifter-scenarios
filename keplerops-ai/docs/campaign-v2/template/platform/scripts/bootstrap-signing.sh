#!/usr/bin/env bash
set -Eeuo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck source=../versions.env
source "$ROOT/versions.env"
STATE_DIR=${PLATFORM_STATE_DIR:-/var/lib/keplerops-platform}
PKI_DIR=${PLATFORM_PKI_DIR:-/etc/keplerops/pki}
STEP_ROOT=${STEP_ROOT:-$PKI_DIR/step-root-ca.crt}
STEP_CA_URL=${STEP_CA_URL:-https://ca.keplerops.lab:9000}
STEP_CA_PROVISIONER=${STEP_CA_PROVISIONER:-range-provisioner}
STEP_CA_PROVISIONER_PASSWORD_FILE=${STEP_CA_PROVISIONER_PASSWORD_FILE:-$PKI_DIR/step-provisioner-password}
SIGNER_NAME=${SIGNER_NAME:-svc-orion-signer.platform.corp.keplerops.lab}

if [[ $EUID -ne 0 ]]; then
  echo "bootstrap-signing.sh must run as root on k3s01" >&2
  exit 2
fi

install_cosign() {
  local installed=""
  if command -v cosign >/dev/null 2>&1; then
    installed=$(cosign version 2>/dev/null | awk '/GitVersion/ {print $2; exit}' | tr -d '"')
  fi
  [[ $installed == "$COSIGN_VERSION" ]] && return

  local tmp expected
  tmp=$(mktemp -d)
  trap 'rm -rf "$tmp"' RETURN
  curl -fsSLo "$tmp/cosign" \
    "https://github.com/sigstore/cosign/releases/download/${COSIGN_VERSION}/cosign-linux-amd64"
  curl -fsSLo "$tmp/checksums.txt" \
    "https://github.com/sigstore/cosign/releases/download/${COSIGN_VERSION}/cosign_checksums.txt"
  expected=$(awk '$2 == "cosign-linux-amd64" {print $1}' "$tmp/checksums.txt")
  [[ $expected =~ ^[a-f0-9]{64}$ ]] || {
    echo "Unable to locate cosign-linux-amd64 checksum" >&2
    exit 3
  }
  printf '%s  %s\n' "$expected" "$tmp/cosign" | sha256sum -c -
  install -m 0755 "$tmp/cosign" /usr/local/bin/cosign
  rm -rf "$tmp"
  trap - RETURN
}

install_cosign
install -d -m 0700 "$STATE_DIR/signing" "$PKI_DIR"

if [[ ! -x /usr/local/bin/step && -x $PKI_DIR/step ]]; then
  install -m 0755 "$PKI_DIR/step" /usr/local/bin/step
fi
if ! command -v step >/dev/null 2>&1; then
  echo "step ${STEP_CLI_VERSION} is unavailable; deploy-to-k3s01.sh copies it from the foundation CA" >&2
  exit 4
fi
if [[ ! -s $STEP_ROOT || ! -s $STEP_CA_PROVISIONER_PASSWORD_FILE ]]; then
  echo "step-ca root or provisioner password is absent under $PKI_DIR" >&2
  exit 5
fi

if ! grep -Eq "^[[:space:]]*192\.168\.78\.1[[:space:]].*\bca\.keplerops\.lab\b" /etc/hosts; then
  sed -i '/[[:space:]]ca\.keplerops\.lab\([[:space:]]\|$\)/d' /etc/hosts
  printf '192.168.78.1 ca.keplerops.lab\n' >>/etc/hosts
fi
install -m 0644 "$STEP_ROOT" /usr/local/share/ca-certificates/keplerops-step-root.crt
update-ca-certificates >/dev/null

signer_cert="$STATE_DIR/signing/step-signer.crt"
signer_key="$STATE_DIR/signing/step-signer.key"
if [[ ! -s $signer_cert ]] || ! openssl x509 -checkend 86400 -noout -in "$signer_cert"; then
  step ca certificate "$SIGNER_NAME" "$signer_cert" "$signer_key" \
    --ca-url "$STEP_CA_URL" \
    --root "$STEP_ROOT" \
    --provisioner "$STEP_CA_PROVISIONER" \
    --provisioner-password-file "$STEP_CA_PROVISIONER_PASSWORD_FILE" \
    --not-after 336h \
    --force
  chmod 0600 "$signer_key"
fi
step certificate verify "$signer_cert" --roots "$STEP_ROOT"

if [[ ! -s $STATE_DIR/signing/cosign-password ]]; then
  umask 077
  openssl rand -base64 32 >"$STATE_DIR/signing/cosign-password"
fi
if [[ ! -s $STATE_DIR/signing/cosign.key || ! -s $STATE_DIR/signing/cosign.pub ]]; then
  export COSIGN_PASSWORD
  COSIGN_PASSWORD=$(<"$STATE_DIR/signing/cosign-password")
  cosign generate-key-pair --output-key-prefix "$STATE_DIR/signing/cosign"
  chmod 0600 "$STATE_DIR/signing/cosign.key"
fi

cat >"$STATE_DIR/signing/identity.json" <<EOF
{
  "schema": "keplerops.signer/v1",
  "identity": "$SIGNER_NAME",
  "step_certificate_digest": "sha256:$(sha256sum "$signer_cert" | awk '{print $1}')",
  "cosign_public_key_digest": "sha256:$(sha256sum "$STATE_DIR/signing/cosign.pub" | awk '{print $1}')"
}
EOF
jq -S . "$STATE_DIR/signing/identity.json" >"$STATE_DIR/signing/identity.json.tmp"
mv "$STATE_DIR/signing/identity.json.tmp" "$STATE_DIR/signing/identity.json"
chmod 0644 "$STATE_DIR/signing/identity.json"
openssl dgst -sha256 -sign "$signer_key" \
  -out "$STATE_DIR/signing/identity.sig" "$STATE_DIR/signing/identity.json"
openssl dgst -sha256 \
  -verify <(openssl x509 -in "$signer_cert" -pubkey -noout) \
  -signature "$STATE_DIR/signing/identity.sig" "$STATE_DIR/signing/identity.json"
chmod 0644 "$STATE_DIR/signing/identity.sig"
