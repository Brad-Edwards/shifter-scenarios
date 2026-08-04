#!/usr/bin/env bash
set -euo pipefail

readonly ROOT=${KEPLEROPS_V2_ROOT:-/opt/keplerops-v2}
readonly STATE="$ROOT/state/workstation"

if [[ ${EUID} -ne 0 ]]; then
  echo "prepare-workstation.sh must run as root" >&2
  exit 2
fi

install -d -m 0755 "$STATE/tls"
if [[ ! -s "$STATE/participant-password" ]]; then
  printf '%s\n' 'Cinder-Operations-Desktop-7Qm4Vx9P' >"$STATE/participant-password"
fi
printf '%s\n' 'campaign-v2-template' >"$STATE/reset-generation"
chmod 0600 "$STATE/participant-password"
chmod 0644 "$STATE/reset-generation"

if [[ ! -s "$STATE/tls/tls.crt" || ! -s "$STATE/tls/tls.key" ]]; then
  openssl req -x509 -newkey rsa:2048 -sha256 -nodes -days 30 \
    -subj '/CN=kali01.keplerops.lab' \
    -addext 'subjectAltName=DNS:kali01.keplerops.lab,DNS:localhost' \
    -keyout "$STATE/tls/tls.key" -out "$STATE/tls/tls.crt" >/dev/null 2>&1
  chown 1000:1000 "$STATE/tls/tls.key"
  chmod 0600 "$STATE/tls/tls.key"
  chmod 0644 "$STATE/tls/tls.crt"
fi
chown 1000:1000 "$STATE/tls/tls.key"
chmod 0600 "$STATE/tls/tls.key"
chmod 0644 "$STATE/tls/tls.crt"

if [[ -e "$STATE/caddy-root.crt" && ! -f "$STATE/caddy-root.crt" ]]; then
  rm -rf -- "$STATE/caddy-root.crt"
fi
docker run --rm --volume keplerops-v2_caddy-data:/data:ro "$CADDY_IMAGE" \
  cat /data/caddy/pki/authorities/local/root.crt >"$STATE/caddy-root.crt"
chmod 0644 "$STATE/caddy-root.crt"

install -d -m 0750 "$ROOT/state"
for cert in cinder-step-root.crt cinder-bootstrap-root.crt cinder-trust-bundle.crt; do
  if [[ -d "$ROOT/state/$cert" && ! -L "$ROOT/state/$cert" ]]; then
    rm -rf "$ROOT/state/$cert"
  fi
done
install -m 0644 "$STATE/caddy-root.crt" "$ROOT/state/cinder-bootstrap-root.crt"
docker exec kep-v2-step-ca sed -n '/-----BEGIN CERTIFICATE-----/,/-----END CERTIFICATE-----/p' \
  /home/step/certs/root_ca.crt >"$ROOT/state/cinder-step-root.crt"
{
  cat "$ROOT/state/cinder-bootstrap-root.crt"
  cat "$ROOT/state/cinder-step-root.crt"
} >"$ROOT/state/cinder-trust-bundle.crt"
chmod 0644 "$ROOT/state/cinder-step-root.crt" \
  "$ROOT/state/cinder-bootstrap-root.crt" \
  "$ROOT/state/cinder-trust-bundle.crt"
