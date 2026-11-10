#!/bin/bash
set -euo pipefail

phase=${1-}
case "$phase" in
  training|keplerops|arwc) ;;
  *)
    echo "usage: prepare-image.sh training|keplerops|arwc" >&2
    exit 2
    ;;
esac

source_root=/opt/cinder-typhoon/build/gcp-images/guest
install -d -m 0755 /usr/local/libexec
for executable in cinder-image-first-boot cinder-image-verify cinder-peer-ca cinder-peer-ca-server.py; do
  install -m 0755 "$source_root/$executable" "/usr/local/libexec/$executable"
done

cat >/etc/systemd/system/cinder-image-first-boot.service <<UNIT
[Unit]
Description=Cinder Typhoon $phase range startup
After=docker.service network-online.target
Wants=network-online.target
Requires=docker.service

[Service]
Type=oneshot
ExecStart=/usr/local/libexec/cinder-image-first-boot $phase
RemainAfterExit=yes
TimeoutStartSec=1200

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable cinder-image-first-boot.service
systemctl enable docker.service

case "$phase" in
  training)
    phase_root=/opt/cinder-typhoon/build/training
    participant_image=cinder-training/participant:hand-build
    ;;
  keplerops)
    phase_root=/opt/cinder-typhoon/build/keplerops
    participant_image=cinder-keplerops/k-dev:hand-build
    ;;
  arwc)
    phase_root=/opt/cinder-typhoon/build/arwc
    participant_image=cinder-arwc/a-connector:hand-build
    ;;
esac

docker image inspect "$participant_image" >/dev/null
docker compose -f "$phase_root/compose.yaml" down -v --remove-orphans || true
while read -r container_id; do
  [[ -z $container_id ]] || docker rm -f "$container_id" >/dev/null
done < <(docker ps -aq)
docker volume prune -f >/dev/null
docker network prune -f >/dev/null
docker builder prune -af >/dev/null

rm -rf -- "$phase_root/.operator"
rm -f -- "$phase_root/.env"
rm -rf -- /var/lib/cinder-typhoon /run/shifter /run/cinder-peer-ca
install -d -m 0755 /var/lib/cinder-typhoon

if find /opt/cinder-typhoon -type f -path '*/.operator/*' -print -quit | grep -q .; then
  echo "operator material remains in the image tree" >&2
  exit 1
fi
if [[ -n $(docker volume ls -q) ]]; then
  echo "Docker volumes remain after image preparation" >&2
  exit 1
fi

rm -f -- /etc/ssh/ssh_host_*
truncate -s 0 /etc/machine-id
rm -f -- /var/lib/dbus/machine-id
find /var/log -type f -exec truncate -s 0 {} +
journalctl --rotate >/dev/null 2>&1 || true
journalctl --vacuum-time=1s >/dev/null 2>&1 || true
sync
