#!/usr/bin/env bash
set -euo pipefail

readonly ROOT=${KEPLEROPS_V2_ROOT:-/opt/keplerops-v2}
readonly KEY=/root/.ssh/keplerops-v2
readonly SSH=(ssh -i "$KEY" -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null)

if [[ ${EUID} -ne 0 ]]; then
  echo "reconcile-guests.sh must run as root" >&2
  exit 2
fi

"${SSH[@]}" kepler@192.168.78.10 sudo bash -s <<'REMOTE'
set -euo pipefail
if ! grep -Eq '^[[:space:]]*dns forwarder[[:space:]]*=[[:space:]]*192\.168\.78\.1[[:space:]]*$' /etc/samba/smb.conf; then
  awk '
    /^\[global\]$/ {
      print
      print "\tdns forwarder = 192.168.78.1"
      next
    }
    /^[[:space:]]*t?dns forwarder[[:space:]]*=/ { next }
    { print }
  ' /etc/samba/smb.conf >/etc/samba/smb.conf.reconciled
  install -m 0644 /etc/samba/smb.conf.reconciled /etc/samba/smb.conf
  rm -f /etc/samba/smb.conf.reconciled
  systemctl restart samba-ad-dc
fi

samba-tool group add Engineering >/dev/null 2>&1 || true
samba-tool group add AI-Research >/dev/null 2>&1 || true
samba-tool group add Release-Engineering >/dev/null 2>&1 || true
samba-tool group add Communications >/dev/null 2>&1 || true
samba-tool group add Support >/dev/null 2>&1 || true
samba-tool user create comms.publisher 'KeplerV2-Training-Comms' \
  --given-name=Samira --surname=Okafor >/dev/null 2>&1 || true
samba-tool group addmembers Communications comms.publisher >/dev/null 2>&1 || true

testparm -s /etc/samba/smb.conf >/dev/null
samba-tool domain info 127.0.0.1 >/dev/null
REMOTE

"${SSH[@]}" kepler@192.168.78.11 sudo bash -s <<'REMOTE'
set -euo pipefail
if ! grep -Eq '^[[:space:]]*dns forwarder[[:space:]]*=[[:space:]]*192\.168\.78\.1[[:space:]]*$' /etc/samba/smb.conf; then
  awk '
    /^\[global\]$/ {
      print
      print "\tdns forwarder = 192.168.78.1"
      next
    }
    /^[[:space:]]*t?dns forwarder[[:space:]]*=/ { next }
    { print }
  ' /etc/samba/smb.conf >/etc/samba/smb.conf.reconciled
  install -m 0644 /etc/samba/smb.conf.reconciled /etc/samba/smb.conf
  rm -f /etc/samba/smb.conf.reconciled
  systemctl restart samba-ad-dc
fi
testparm -s /etc/samba/smb.conf >/dev/null
samba-tool domain info 127.0.0.1 >/dev/null
REMOTE

trust_dir="$ROOT/state/identity/truststores"
install -d -m 0755 "$trust_dir"
for dc in dc01:192.168.78.10 dc02:192.168.78.11; do
  name=${dc%%:*}
  address=${dc#*:}
  temporary=$(mktemp)
  "${SSH[@]}" "kepler@${address}" \
    'sudo cat /var/lib/samba/private/tls/ca.pem' >"$temporary"
  openssl x509 -in "$temporary" -noout >/dev/null
  install -m 0644 "$temporary" "$trust_dir/${name}-ca.pem"
  rm -f "$temporary"
done

echo "campaign-v2 guest configuration reconciled"
