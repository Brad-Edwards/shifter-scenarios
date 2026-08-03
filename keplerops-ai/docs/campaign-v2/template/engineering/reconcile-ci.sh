#!/usr/bin/env bash

set -Eeuo pipefail

readonly CADDY_CONTAINER=kep-v2-caddy
readonly CADDY_ROOT=/data/caddy/pki/authorities/local/root.crt
readonly REGISTRY_HOST=registry.keplerops.lab
readonly REGISTRY_ADDRESS=10.61.10.2
readonly HARBOR_URL=http://10.61.40.32:8080
readonly SYSTEM_CA=/usr/local/share/ca-certificates/keplerops-registry.crt

if [[ ${EUID} -ne 0 ]]; then
  printf 'reconcile-ci.sh must run as root\n' >&2
  exit 2
fi

temporary_ca="$(mktemp)"
cleanup() {
  find "${temporary_ca}" -type f -delete 2>/dev/null || true
}
trap cleanup EXIT

docker exec "${CADDY_CONTAINER}" cat "${CADDY_ROOT}" >"${temporary_ca}"
install -d -m 0755 "/etc/docker/certs.d/${REGISTRY_HOST}"
install -m 0644 "${temporary_ca}" "/etc/docker/certs.d/${REGISTRY_HOST}/ca.crt"
if ! cmp -s "${temporary_ca}" "${SYSTEM_CA}"; then
  install -m 0644 "${temporary_ca}" "${SYSTEM_CA}"
  update-ca-certificates >/dev/null
  systemctl restart docker
  for _ in $(seq 1 60); do
    docker inspect --format '{{.State.Running}}' "${CADDY_CONTAINER}" 2>/dev/null |
      grep -qx true && curl -fsS "${HARBOR_URL}/api/v2.0/health" >/dev/null 2>&1 && break
    sleep 2
  done
fi

sed -i '/# keplerops-v2-registry$/d' /etc/hosts
printf '%s %s # keplerops-v2-registry\n' \
  "${REGISTRY_ADDRESS}" "${REGISTRY_HOST}" >>/etc/hosts

projects="$(curl -fsS \
  --user admin:KeplerV2-Training-Harbor \
  "${HARBOR_URL}/api/v2.0/projects?name=orion-build")"
if ! jq -e '. | length > 0' <<<"${projects}" >/dev/null; then
  curl -fsS \
    --user admin:KeplerV2-Training-Harbor \
    --header 'Content-Type: application/json' \
    --data '{"project_name":"orion-build","public":false,"metadata":{"auto_scan":"false"}}' \
    "${HARBOR_URL}/api/v2.0/projects" >/dev/null
fi

curl -fsS --cacert "${temporary_ca}" \
  "https://${REGISTRY_HOST}/api/v2.0/health" >/dev/null
printf 'Forgejo CI registry trust and Harbor project reconciled\n'
