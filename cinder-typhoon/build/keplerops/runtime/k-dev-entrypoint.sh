#!/bin/sh
set -eu

ip route replace 10.77.51.0/24 via 10.77.50.254
ip route replace 10.77.52.0/24 via 10.77.50.254
ip route replace 10.77.60.0/24 via 10.77.50.254
mkdir -p /run/sshd
if [ ! -e /home/rowan/.local/share/keplerops/registry-foundation-2026-09-18 ]; then
  tar -xf /opt/fieldkest-seeds/k-dev-registry.tar -C /home/rowan
  touch /home/rowan/.local/share/keplerops/registry-foundation-2026-09-18
  chown -R rowan:rowan /home/rowan/work/registry /home/rowan/.local/share/keplerops
fi
if [ ! -e /home/rowan/.local/share/keplerops/policy-compiler-2026-09-18 ]; then
  tar -xf /opt/fieldkest-seeds/k-dev-k11-home.tar -C /home/rowan
  touch /home/rowan/.local/share/keplerops/policy-compiler-2026-09-18
  chown -R rowan:rowan /home/rowan/work/build-operations /home/rowan/.local/share/keplerops
fi
if [ ! -e /home/rowan/.local/share/keplerops/connector-archive-2026-09-18 ]; then
  tar -xf /opt/fieldkest-seeds/k-dev-k28-home.tar -C /home/rowan
  touch /home/rowan/.local/share/keplerops/connector-archive-2026-09-18
  chown -R rowan:rowan /home/rowan/work/build-operations /home/rowan/.local/share/keplerops
fi
if [ ! -e /home/rowan/.local/share/keplerops/release-lineage-2026-09-18 ]; then
  tar -xf /opt/fieldkest-seeds/k-dev-k29-home.tar -C /home/rowan
  touch /home/rowan/.local/share/keplerops/release-lineage-2026-09-18
  chown -R rowan:rowan /home/rowan/work/build-operations /home/rowan/.local/share/keplerops
fi
chown rowan:rowan /home/rowan/work
install -m 0444 /run/fieldkest-auth/ca.crt /home/rowan/.local/share/keplerops/ca.crt
install -m 0600 -o rowan -g rowan /run/fieldkest-auth/rowan_authorized_keys /home/rowan/.ssh/authorized_keys
setpriv --reuid=fieldkest-workbench --regid=fieldkest-workbench --init-groups \
  python3 /opt/fieldkest-workbench/workbench.py &
exec /usr/sbin/sshd -D -e
