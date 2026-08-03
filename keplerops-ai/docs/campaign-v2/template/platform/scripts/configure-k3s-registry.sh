#!/usr/bin/env bash

set -Eeuo pipefail

readonly K3S01_SSH_TARGET="${K3S01_SSH_TARGET:-kepler@192.168.78.30}"
readonly K3S01_SSH_KEY="${K3S01_SSH_KEY:-/root/.ssh/keplerops-v2}"
readonly REGISTRY="${REGISTRY:-registry.keplerops.lab}"
readonly REGISTRY_BRIDGE_ADDRESS="${REGISTRY_BRIDGE_ADDRESS:-192.168.78.1}"
readonly REGISTRY_CA="${REGISTRY_CA:-/etc/docker/certs.d/registry.keplerops.lab/ca.crt}"
readonly HARBOR_AUTH="${HARBOR_AUTH:-admin:KeplerV2-Training-Harbor}"
readonly SSH=(ssh -i "${K3S01_SSH_KEY}" -o BatchMode=yes -o StrictHostKeyChecking=accept-new)

[[ ${EUID} -eq 0 ]] || {
  printf 'configure-k3s-registry.sh must run as root on the template host\n' >&2
  exit 2
}
[[ -r ${K3S01_SSH_KEY} && -s ${REGISTRY_CA} ]] || {
  printf 'k3s SSH key or registry CA is unavailable\n' >&2
  exit 2
}

workdir="$(mktemp -d)"
trap 'rm -rf "${workdir}"' EXIT
install -m 0644 "${REGISTRY_CA}" "${workdir}/registry-keplerops-ca.crt"
cat >"${workdir}/registries.yaml" <<EOF
mirrors:
  "${REGISTRY}":
    endpoint:
      - "https://${REGISTRY}"
configs:
  "${REGISTRY}":
    auth:
      username: "${HARBOR_AUTH%%:*}"
      password: "${HARBOR_AUTH#*:}"
    tls:
      ca_file: /etc/rancher/k3s/registry-keplerops-ca.crt
EOF
printf '%s %s # keplerops-registry\n' \
  "${REGISTRY_BRIDGE_ADDRESS}" "${REGISTRY}" >"${workdir}/hosts.entry"

tar -C "${workdir}" -cf - registries.yaml registry-keplerops-ca.crt hosts.entry | \
  "${SSH[@]}" "${K3S01_SSH_TARGET}" \
    'rm -rf /tmp/keplerops-registry && mkdir -m 0700 /tmp/keplerops-registry && tar -C /tmp/keplerops-registry -xf -'

# The following program is expanded by the remote shell, not this one.
# shellcheck disable=SC2016
changed="$("${SSH[@]}" "${K3S01_SSH_TARGET}" '
  set -eu
  changed=0
  sudo test -f /etc/rancher/k3s/registries.yaml &&
    sudo cmp -s /tmp/keplerops-registry/registries.yaml /etc/rancher/k3s/registries.yaml || changed=1
  sudo test -f /etc/rancher/k3s/registry-keplerops-ca.crt &&
    sudo cmp -s /tmp/keplerops-registry/registry-keplerops-ca.crt /etc/rancher/k3s/registry-keplerops-ca.crt || changed=1
  expected_hosts=$(cat /tmp/keplerops-registry/hosts.entry)
  grep -Fxq "$expected_hosts" /etc/hosts || changed=1
  if [ "$changed" -eq 1 ]; then
    sudo install -m 0600 /tmp/keplerops-registry/registries.yaml /etc/rancher/k3s/registries.yaml
    sudo install -m 0644 /tmp/keplerops-registry/registry-keplerops-ca.crt /etc/rancher/k3s/registry-keplerops-ca.crt
    sudo sed -i -e "/# keplerops-registry$/d" -e "/# keplerops-v2-registry$/d" /etc/hosts
    cat /tmp/keplerops-registry/hosts.entry | sudo tee -a /etc/hosts >/dev/null
    sudo systemctl restart k3s
  fi
  rm -rf /tmp/keplerops-registry
  printf "%s\n" "$changed"
')"

# shellcheck disable=SC2016
"${SSH[@]}" "${K3S01_SSH_TARGET}" \
  'for attempt in $(seq 1 60); do sudo k3s kubectl get node k3s01 >/dev/null 2>&1 && exit 0; sleep 2; done; exit 1'

if [[ ${changed} == 1 ]]; then
  printf 'k3s registry trust installed and k3s restarted cleanly\n'
else
  printf 'k3s registry trust already current\n'
fi
