#!/usr/bin/env bash
set -euo pipefail

readonly NESTED_SUBNET=${KEPLEROPS_NESTED_SUBNET:-192.168.78.0/24}
readonly DROP_IN=/etc/chrony/conf.d/keplerops-nested.conf

[[ $EUID -eq 0 ]] || {
  echo "configure-nested-ntp.sh must run as root" >&2
  exit 2
}
command -v chronyd >/dev/null || {
  echo "chrony is required on the outer host" >&2
  exit 3
}

install -d -m 0755 /etc/chrony/conf.d
if ! grep -Eq '^[[:space:]]*confdir[[:space:]]+/etc/chrony/conf\.d([[:space:]]|$)' \
  /etc/chrony/chrony.conf; then
  printf '\nconfdir /etc/chrony/conf.d\n' >>/etc/chrony/chrony.conf
fi
printf '# Serve Google-synchronized time only to the nested range.\nallow %s\n' \
  "$NESTED_SUBNET" >"$DROP_IN"
chmod 0644 "$DROP_IN"
systemctl enable chrony >/dev/null
systemctl restart chrony
