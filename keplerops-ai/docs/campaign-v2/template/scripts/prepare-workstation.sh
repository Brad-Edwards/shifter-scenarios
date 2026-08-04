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

tls_sans=(DNS:kali01.keplerops.lab DNS:localhost IP:127.0.0.1)
for candidate in "${PARTICIPANT_WEB_BIND_ADDRESS:-}" "${PARTICIPANT_PUBLIC_ADDRESS:-}"; do
  if [[ $candidate =~ ^[0-9]+(\.[0-9]+){3}$ && $candidate != 0.0.0.0 ]]; then
    tls_sans+=("IP:${candidate}")
  fi
done
metadata_external_ip=$(
  curl --fail --silent --show-error --max-time 2 \
    -H 'Metadata-Flavor: Google' \
    http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip \
    2>/dev/null || true
)
if [[ $metadata_external_ip =~ ^[0-9]+(\.[0-9]+){3}$ ]]; then
  tls_sans+=("IP:${metadata_external_ip}")
fi
tls_subject_alt_name=$(IFS=,; printf '%s' "${tls_sans[*]}")

refresh_tls=false
if [[ ! -s "$STATE/tls/tls.crt" || ! -s "$STATE/tls/tls.key" ]]; then
  refresh_tls=true
else
  current_tls_sans=$(openssl x509 -in "$STATE/tls/tls.crt" -noout -ext subjectAltName 2>/dev/null || true)
  for expected_san in "${tls_sans[@]}"; do
    case "$expected_san" in
      DNS:*) expected_text="DNS:${expected_san#DNS:}" ;;
      IP:*) expected_text="IP Address:${expected_san#IP:}" ;;
      *) expected_text=$expected_san ;;
    esac
    if [[ $current_tls_sans != *"$expected_text"* ]]; then
      refresh_tls=true
    fi
  done
fi

if [[ $refresh_tls == true ]]; then
  openssl req -x509 -newkey rsa:2048 -sha256 -nodes -days 30 \
    -subj '/CN=kali01.keplerops.lab' \
    -addext "subjectAltName=${tls_subject_alt_name}" \
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
