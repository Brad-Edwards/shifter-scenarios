#!/bin/bash
set -euo pipefail
umask 077

readonly METADATA_ROOT='http://metadata.google.internal/computeMetadata/v1'
readonly METADATA_HEADER='Metadata-Flavor: Google'
readonly BOOTSTRAP_ROOT='/var/lib/keplerops-bootstrap'

metadata() {
  curl --fail --silent --show-error \
    --connect-timeout 5 --max-time 30 \
    -H "$METADATA_HEADER" "$METADATA_ROOT/instance/attributes/$1"
}

install -d -m 0700 "$BOOTSTRAP_ROOT"
registry_host=$(metadata keplerops-region)-docker.pkg.dev
if ! grep -Fq "secretmanager.googleapis.com $registry_host" /etc/hosts; then
  printf '199.36.153.4 secretmanager.googleapis.com %s\n' "$registry_host" \
    >>/etc/hosts
fi
if ! command -v virsh >/dev/null ||
  ! command -v docker >/dev/null ||
  ! command -v dnsmasq >/dev/null ||
  ! command -v hivexsh >/dev/null ||
  ! python3 -c 'import winrm' >/dev/null 2>&1; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y --no-install-recommends \
    dnsmasq-base docker.io jq libhivex-bin libvirt-clients libvirt-daemon-system \
    ntfs-3g ovmf python3-winrm qemu-system-x86
fi

install -d -m 0755 /etc/docker
if [[ ! -s /etc/docker/daemon.json ]]; then
  printf '%s\n' '{"live-restore":false}' >/etc/docker/daemon.json
fi
systemctl enable --now docker libvirtd

# Ubuntu 24.04 otherwise denies rootlesskit's user-namespace re-exec even when
# its dedicated outer Docker container has an unconfined AppArmor profile.
cat >/etc/sysctl.d/90-keplerops-rootless-worker.conf <<'EOF'
kernel.apparmor_restrict_unprivileged_userns=0
EOF
sysctl -w kernel.apparmor_restrict_unprivileged_userns=0 >/dev/null

metadata keplerops-nested-bootstrap >"$BOOTSTRAP_ROOT/nested-bootstrap.sh"
metadata keplerops-carrier-bootstrap >"$BOOTSTRAP_ROOT/carrier-bootstrap.sh"
chmod 0500 "$BOOTSTRAP_ROOT/nested-bootstrap.sh" "$BOOTSTRAP_ROOT/carrier-bootstrap.sh"

bash "$BOOTSTRAP_ROOT/nested-bootstrap.sh"
bash "$BOOTSTRAP_ROOT/carrier-bootstrap.sh"
touch "$BOOTSTRAP_ROOT/ready"
