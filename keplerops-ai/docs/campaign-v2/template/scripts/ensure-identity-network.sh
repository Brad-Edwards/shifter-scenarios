#!/usr/bin/env bash
set -euo pipefail

readonly NETWORK=kep-v2-identity

if [[ ${EUID} -ne 0 ]]; then
  echo "ensure-identity-network.sh must run as root" >&2
  exit 2
fi

if ! virsh net-info "$NETWORK" >/dev/null 2>&1; then
  virsh net-define /dev/stdin <<'XML'
<network>
  <name>kep-v2-identity</name>
  <bridge name='virbr-v2' stp='on' delay='0'/>
  <forward mode='nat'/>
  <ip address='192.168.78.1' netmask='255.255.255.0'>
    <dhcp>
      <range start='192.168.78.100' end='192.168.78.199'/>
      <host mac='52:54:00:78:00:10' name='dc01' ip='192.168.78.10'/>
      <host mac='52:54:00:78:00:11' name='dc02' ip='192.168.78.11'/>
      <host mac='52:54:00:78:00:20' name='review01' ip='192.168.78.20'/>
      <host mac='52:54:00:78:00:21' name='integration01' ip='192.168.78.21'/>
      <host mac='52:54:00:78:00:30' name='k3s01' ip='192.168.78.30'/>
    </dhcp>
  </ip>
</network>
XML
fi
virsh net-autostart "$NETWORK" >/dev/null
if [[ $(virsh net-info "$NETWORK" | awk '/^Active:/ {print $2}') != yes ]]; then
  virsh net-start "$NETWORK" >/dev/null
fi
sysctl -w net.ipv4.ip_forward=1 >/dev/null
