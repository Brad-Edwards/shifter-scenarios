#!/bin/bash
# Bootstrap only the dedicated compatibility VM; do not run on a golden host.
set -euo pipefail
[[ $(hostname) == cinder-arwc-ot-compat-363 ]] || {
  echo 'Run this script on cinder-arwc-ot-compat-363.' >&2; exit 1;
}
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install --no-install-recommends -y ca-certificates curl git openssl python3 python3-venv jq
install -d -m 0755 /etc/apt/keyrings
curl --fail --silent --show-error --location https://download.docker.com/linux/debian/gpg \
  --output /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
printf '%s\n' 'deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian bookworm stable' \
  > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install --no-install-recommends -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker
install -d -m 0755 /opt/arwc-ot-compat
touch /var/lib/arwc-ot-compat-ready
