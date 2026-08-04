#!/usr/bin/env bash
set -euo pipefail

readonly ROOT=${KEPLEROPS_V2_ROOT:-/opt/keplerops-v2}
readonly STATE="$ROOT/state/guests"
readonly IMAGE_DIR=/var/lib/libvirt/images/keplerops-v2
readonly NETWORK=kep-v2-identity
readonly DOMAIN=CORP.KEPLEROPS.LAB
readonly SHORT_DOMAIN=KEPLEROPS
readonly ADMIN_PASSWORD=KeplerV2-Training-AD-Admin

if [[ ${EUID} -ne 0 ]]; then
  echo "provision-guests.sh must run as root" >&2
  exit 2
fi

set -a
# shellcheck disable=SC1091
source "$ROOT/component-lock.env"
set +a

install -d -m 0700 "$STATE"
install -d -m 0750 -o libvirt-qemu -g kvm "$IMAGE_DIR"
if [[ ! -s /root/.ssh/keplerops-v2 ]]; then
  ssh-keygen -q -t ed25519 -N '' -f /root/.ssh/keplerops-v2
fi
SSH_PUBLIC_KEY=$(cat /root/.ssh/keplerops-v2.pub)
readonly SSH_PUBLIC_KEY

ensure_network() {
  "$ROOT/scripts/ensure-identity-network.sh"
}

ensure_base_image() {
  local base="$IMAGE_DIR/ubuntu-noble-base.qcow2"
  if [[ ! -s $base ]]; then
    curl -4 -fL --retry 5 --retry-delay 3 \
      "$UBUNTU_CLOUD_IMAGE_URL" -o "$base.download"
    mv "$base.download" "$base"
  fi
  chown libvirt-qemu:kvm "$base"
  chmod 0640 "$base"
  local actual
  actual=$(sha256sum "$base" | awk '{print $1}')
  printf '%s  %s\n' "$actual" "$base" >"$ROOT/state/ubuntu-cloud-image.sha256"
  if [[ -n ${UBUNTU_CLOUD_IMAGE_SHA256:-} && $actual != "$UBUNTU_CLOUD_IMAGE_SHA256" ]]; then
    echo "Ubuntu cloud image digest mismatch" >&2
    exit 4
  fi
}

common_user_data() {
  local hostname=$1
  cat <<EOF
#cloud-config
hostname: $hostname
fqdn: $hostname.corp.keplerops.lab
manage_etc_hosts: false
users:
  - default
  - name: kepler
    groups: [adm, sudo]
    shell: /bin/bash
    sudo: ALL=(ALL) NOPASSWD:ALL
    ssh_authorized_keys:
      - $SSH_PUBLIC_KEY
ssh_pwauth: false
package_update: true
package_upgrade: false
EOF
}

dc01_user_data() {
  common_user_data dc01
  cat <<EOF
packages:
  - chrony
  - krb5-user
  - samba
  - smbclient
  - winbind
runcmd:
  - [bash, -lc, "sed -i -E '/^(pool|server)[[:space:]]/d' /etc/chrony/chrony.conf; printf '\nserver 192.168.78.1 iburst\n' >>/etc/chrony/chrony.conf; systemctl enable --now chrony"]
  - [bash, -lc, "printf '127.0.0.1 localhost\\n192.168.78.10 dc01.corp.keplerops.lab dc01\\n192.168.78.11 dc02.corp.keplerops.lab dc02\\n' >/etc/hosts"]
  - [bash, -lc, "systemctl disable --now smbd nmbd winbind systemd-resolved || true"]
  - [bash, -lc, "rm -f /etc/samba/smb.conf /etc/resolv.conf; printf 'nameserver 192.168.78.1\\n' >/etc/resolv.conf"]
  - [bash, -lc, "samba-tool domain provision --server-role=dc --use-rfc2307 --realm=$DOMAIN --domain=$SHORT_DOMAIN --dns-backend=SAMBA_INTERNAL --adminpass='$ADMIN_PASSWORD' --option='dns forwarder=192.168.78.1'"]
  - [bash, -lc, "cp /var/lib/samba/private/krb5.conf /etc/krb5.conf"]
  - [bash, -lc, "systemctl unmask samba-ad-dc; systemctl enable --now samba-ad-dc"]
  - [bash, -lc, "samba-tool group add Engineering || true; samba-tool group add AI-Research || true; samba-tool group add Release-Engineering || true; samba-tool group add Communications || true; samba-tool group add Support || true"]
  - [bash, -lc, "samba-tool user create reviewer 'KeplerV2-Training-Reviewer' --given-name=Rina --surname=Chen || true; samba-tool group addmembers Engineering reviewer || true"]
  - [bash, -lc, "samba-tool user create ml.engineer 'KeplerV2-Training-MLEngineer' --given-name=Maya --surname=Ortiz || true; samba-tool group addmembers AI-Research ml.engineer || true"]
  - [bash, -lc, "samba-tool user create release.engineer 'KeplerV2-Training-Release' --given-name=Elliot --surname=Park || true; samba-tool group addmembers Release-Engineering release.engineer || true"]
  - [bash, -lc, "samba-tool user create comms.publisher 'KeplerV2-Training-Comms' --given-name=Samira --surname=Okafor || true; samba-tool group addmembers Communications comms.publisher || true"]
  - [bash, -lc, "samba-tool user create support.analyst 'KeplerV2-Training-Support' --given-name=Jonas --surname=Becker || true; samba-tool group addmembers Support support.analyst || true"]
  - [bash, -lc, "touch /var/lib/keplerops-dc01.ready"]
EOF
}

dc02_user_data() {
  common_user_data dc02
  cat <<EOF
packages:
  - chrony
  - krb5-user
  - samba
  - smbclient
  - winbind
runcmd:
  - [bash, -lc, "sed -i -E '/^(pool|server)[[:space:]]/d' /etc/chrony/chrony.conf; printf '\nserver 192.168.78.1 iburst\n' >>/etc/chrony/chrony.conf; systemctl enable --now chrony"]
  - [bash, -lc, "printf '127.0.0.1 localhost\\n192.168.78.10 dc01.corp.keplerops.lab dc01\\n192.168.78.11 dc02.corp.keplerops.lab dc02\\n' >/etc/hosts"]
  - [bash, -lc, "systemctl disable --now smbd nmbd winbind systemd-resolved || true"]
  - [bash, -lc, "rm -f /etc/samba/smb.conf /etc/resolv.conf; printf 'nameserver 192.168.78.10\\n' >/etc/resolv.conf"]
  - [bash, -lc, "for i in {1..90}; do timeout 2 bash -c '</dev/tcp/192.168.78.10/389' && break; sleep 5; done"]
  - [bash, -lc, "samba-tool domain join $DOMAIN DC --username=Administrator --password='$ADMIN_PASSWORD' --dns-backend=SAMBA_INTERNAL"]
  - [bash, -lc, "cp /var/lib/samba/private/krb5.conf /etc/krb5.conf; systemctl unmask samba-ad-dc; systemctl enable --now samba-ad-dc"]
  - [bash, -lc, "touch /var/lib/keplerops-dc02.ready"]
EOF
}

member_user_data() {
  local hostname=$1 role=$2 desktop=$3
  common_user_data "$hostname"
  cat <<EOF
packages:
  - adcli
  - chrony
  - krb5-user
  - libnss-sss
  - libpam-modules
  - libpam-sss
  - realmd
  - sssd-ad
  - sssd-tools
  - podman
  - jq
  - git
  - poppler-utils
  - python3-pika
  - python3-requests
runcmd:
  - [bash, -lc, "sed -i -E '/^(pool|server)[[:space:]]/d' /etc/chrony/chrony.conf; printf '\nserver 192.168.78.1 iburst\n' >>/etc/chrony/chrony.conf; systemctl enable --now chrony"]
  - [bash, -lc, "systemctl disable --now systemd-resolved || true; rm -f /etc/resolv.conf; printf 'nameserver 192.168.78.10\\nnameserver 192.168.78.11\\n' >/etc/resolv.conf"]
  - [bash, -lc, "for i in {1..90}; do timeout 2 bash -c '</dev/tcp/192.168.78.10/389' && break; sleep 5; done"]
  - [bash, -lc, "printf '%s\\n' '$ADMIN_PASSWORD' | realm join --user=Administrator $DOMAIN"]
  - [bash, -lc, "pam-auth-update --enable mkhomedir"]
  - [bash, -lc, "install -d -m 0755 /etc/keplerops; printf 'role=%s\\n' '$role' >/etc/keplerops/workstation-role"]
  - [bash, -lc, "id -u orion-review >/dev/null 2>&1 || useradd --system --home /var/lib/keplerops/review-worker --shell /usr/sbin/nologin orion-review"]
  - [bash, -lc, "install -d -m 0750 -o orion-review -g orion-review /var/lib/keplerops/review-worker"]
EOF
  if [[ $desktop == true ]]; then
    cat <<'EOF'
  - [bash, -lc, "apt-get -o Acquire::ForceIPv4=true install -y chromium-browser xfce4 xfce4-terminal xrdp"]
  - [bash, -lc, "systemctl enable --now xrdp"]
EOF
  fi
  cat <<EOF
  - [bash, -lc, "touch /var/lib/keplerops-domain-member.ready"]
EOF
}

review01_user_data() {
  member_user_data review01 review true
}

integration01_user_data() {
  member_user_data integration01 integration false
}

k3s_user_data() {
  common_user_data k3s01
  cat <<'EOF'
packages:
  - jq
  - nfs-common
  - open-iscsi
  - ca-certificates
runcmd:
  - [bash, -lc, "install -d -m 0755 /etc/systemd/timesyncd.conf.d; printf '[Time]\\nNTP=192.168.78.1\\nFallbackNTP=\\n' >/etc/systemd/timesyncd.conf.d/keplerops.conf; systemctl restart systemd-timesyncd"]
  - [bash, -lc, "curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION=v1.33.2+k3s1 sh -s - server --disable=traefik --write-kubeconfig-mode=0644 --node-name=k3s01"]
  - [bash, -lc, "systemctl is-active --quiet k3s && touch /var/lib/keplerops-k3s.ready"]
EOF
}

create_guest() {
  local name=$1 mac=$2 memory=$3 vcpus=$4 disk_gb=$5 user_data_fn=$6
  local disk="$IMAGE_DIR/$name.qcow2" seed="$IMAGE_DIR/$name-seed.iso"
  if [[ ",${RECREATE_GUESTS:-}," == *",$name,"* ]] &&
    virsh dominfo "$name" >/dev/null 2>&1; then
    virsh destroy "$name" >/dev/null 2>&1 || true
    virsh undefine "$name" --nvram >/dev/null 2>&1 ||
      virsh undefine "$name" >/dev/null 2>&1 || true
  fi
  if virsh dominfo "$name" >/dev/null 2>&1; then
    if [[ $(virsh domstate "$name") == 'shut off' ]]; then
      virsh start "$name" >/dev/null
    fi
    return
  fi
  rm -f "$disk" "$seed"
  qemu-img create -q -f qcow2 -F qcow2 \
    -b "$IMAGE_DIR/ubuntu-noble-base.qcow2" "$disk" "${disk_gb}G"
  "$user_data_fn" >"$STATE/$name-user-data.yaml"
  printf 'instance-id: %s\nlocal-hostname: %s\n' "$name" "$name" \
    >"$STATE/$name-meta-data.yaml"
  cloud-localds "$seed" "$STATE/$name-user-data.yaml" "$STATE/$name-meta-data.yaml"
  chown libvirt-qemu:kvm "$disk" "$seed"
  chmod 0660 "$disk" "$seed"
  virt-install \
    --name "$name" \
    --memory "$memory" \
    --vcpus "$vcpus" \
    --cpu host-passthrough \
    --import \
    --os-variant ubuntu24.04 \
    --disk "path=$disk,format=qcow2,bus=virtio" \
    --disk "path=$seed,device=cdrom" \
    --network "network=$NETWORK,model=virtio,mac=$mac" \
    --graphics none \
    --noautoconsole \
    --autostart
}

ensure_network
ensure_base_image
create_guest dc01 52:54:00:78:00:10 3072 2 20 dc01_user_data
create_guest dc02 52:54:00:78:00:11 3072 2 20 dc02_user_data
create_guest review01 52:54:00:78:00:20 6144 2 24 review01_user_data
create_guest integration01 52:54:00:78:00:21 4096 2 20 integration01_user_data
create_guest k3s01 52:54:00:78:00:30 16384 4 40 k3s_user_data

echo "campaign-v2 guests created; cloud-init continues inside each guest"
