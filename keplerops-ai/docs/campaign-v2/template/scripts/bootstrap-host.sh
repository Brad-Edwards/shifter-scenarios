#!/usr/bin/env bash
set -euo pipefail

readonly ROOT=/opt/keplerops-v2
readonly SOURCE_DIR=${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}

if [[ ${EUID} -ne 0 ]]; then
  echo "bootstrap-host.sh must run as root" >&2
  exit 2
fi

metadata() {
  curl -fsS -H 'Metadata-Flavor: Google' \
    "http://metadata.google.internal/computeMetadata/v1/$1"
}

campaign_label=$(metadata 'instance/attributes/campaign' 2>/dev/null || true)
if [[ ${campaign_label} != v2 ]]; then
  echo "refusing host without GCE campaign=v2 metadata" >&2
  exit 3
fi

export DEBIAN_FRONTEND=noninteractive
apt-get -o Acquire::ForceIPv4=true update
apt-get -o Acquire::ForceIPv4=true install -y \
  chrony cloud-image-utils curl default-jdk-headless docker-compose-v2 jq qemu-utils ruby unzip virtinst

systemctl disable --now keplerops-machine-host-runtime.service 2>/dev/null || true

mapfile -t legacy_containers < <(
  docker ps -a --format '{{.Names}}' |
    grep '^keplerops-' || true
)
if ((${#legacy_containers[@]})); then
  docker update --restart=no "${legacy_containers[@]}" >/dev/null
  docker stop --time 5 "${legacy_containers[@]}" >/dev/null 2>&1 || true
  docker rm "${legacy_containers[@]}" >/dev/null 2>&1 || true
fi

for guest in ad-dc-01 workforce-workstation-01 ml-workstation-01; do
  virsh destroy "$guest" >/dev/null 2>&1 || true
  virsh autostart --disable "$guest" >/dev/null 2>&1 || true
done

install -d -m 0755 "$ROOT"
rsync -a --delete "$SOURCE_DIR/" "$ROOT/"
chown -R root:root "$ROOT"
install -d -m 0755 "$ROOT/state/identity/truststores"
rm -f "$ROOT/state/guests/review-verification.env"

install -m 0644 "$ROOT/systemd/keplerops-v2-template.service" \
  /etc/systemd/system/keplerops-v2-template.service
rm -f /etc/systemd/system/keplerops-k3s-clock-sync.service \
  /etc/systemd/system/keplerops-k3s-clock-sync.timer
systemctl daemon-reload
systemctl enable keplerops-v2-template.service
"$ROOT/scripts/configure-nested-ntp.sh"

echo "campaign-v2 host bootstrap complete"
