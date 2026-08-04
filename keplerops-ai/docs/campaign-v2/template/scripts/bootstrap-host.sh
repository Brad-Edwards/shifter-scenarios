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

# A machine image captured without quiescing boots with the previous kep-v2-*
# compose stack still running (restart policies re-launch it). Those containers
# hold the range's docker networks, so a fresh `start-all.sh build` aborts when
# start-foundation recreates them ("network kep-v2-platform has active
# endpoints"). Tear the previous stack down so the build starts from a clean
# host regardless of how the source image was captured.
mapfile -t stale_stack < <(
  docker ps -aq --filter 'name=^kep-v2-' || true
)
if ((${#stale_stack[@]})); then
  docker update --restart=no "${stale_stack[@]}" >/dev/null 2>&1 || true
  docker rm -f "${stale_stack[@]}" >/dev/null 2>&1 || true
fi
while IFS= read -r stale_network; do
  [[ -n $stale_network ]] || continue
  docker network rm "$stale_network" >/dev/null 2>&1 || true
done < <(docker network ls --format '{{.Name}}' | grep '^kep-v2-' || true)

# The full build materializes ~220 GiB of container/containerd images plus build
# cache and the nested guest disks. A rebuild on a seed captured from an
# already-built template starts nearly full and otherwise dies deep in the
# engineering image phase with "no space left on device". Fail fast, after the
# teardown above has reclaimed the previous stack, with an actionable message.
min_free_gib=${KEPLEROPS_MIN_FREE_GIB:-120}
free_gib=$(df -BG --output=avail / | tail -1 | tr -dc '0-9')
if [[ -n $free_gib ]] && ((free_gib < min_free_gib)); then
  echo "insufficient disk: ${free_gib} GiB free on / but the build needs >= ${min_free_gib} GiB." >&2
  echo "Resize the boot disk (e.g. gcloud compute disks resize <disk> --size 400)," >&2
  echo "grow the partition and filesystem (growpart + resize2fs), then retry." >&2
  echo "Override the threshold with KEPLEROPS_MIN_FREE_GIB if you know the build fits." >&2
  exit 5
fi

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
