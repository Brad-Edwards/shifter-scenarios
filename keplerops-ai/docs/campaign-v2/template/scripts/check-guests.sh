#!/usr/bin/env bash
set -euo pipefail

readonly KEY=/root/.ssh/keplerops-v2
readonly SSH=(ssh -i "$KEY" -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null)

check_port() {
  timeout 3 bash -c "</dev/tcp/$1/$2" 2>/dev/null
}

check_port 192.168.78.10 53
check_port 192.168.78.10 88
check_port 192.168.78.10 389
check_port 192.168.78.11 53
check_port 192.168.78.11 88
check_port 192.168.78.11 389

timeout 30 "${SSH[@]}" kepler@192.168.78.10 \
  'sudo timeout 20 samba-tool user show reviewer >/dev/null; test -f /var/lib/keplerops-dc01.ready'
timeout 30 "${SSH[@]}" kepler@192.168.78.11 \
  'sudo timeout 20 samba-tool user show reviewer >/dev/null; test -f /var/lib/keplerops-dc02.ready'
timeout 30 "${SSH[@]}" kepler@192.168.78.20 \
  'realm list | grep -qi corp.keplerops.lab; test -f /var/lib/keplerops-domain-member.ready'
timeout 30 "${SSH[@]}" kepler@192.168.78.21 \
  'realm list | grep -qi corp.keplerops.lab; test -f /var/lib/keplerops-domain-member.ready'
timeout 30 "${SSH[@]}" kepler@192.168.78.30 \
  'sudo systemctl is-active --quiet k3s; test -f /var/lib/keplerops-k3s.ready'

install -d -m 0755 /run/shifter
printf '%s\n' "$(cat /proc/sys/kernel/random/boot_id) guests" \
  >/run/shifter/keplerops-v2-guests.ready
echo "campaign-v2 guests healthy"
