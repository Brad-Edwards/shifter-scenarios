#!/usr/bin/env bash
set -Eeuo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
POLICY_UNIT=keplerops-network-segmentation.service
PROXY_SOCKET=keplerops-orion-agent-proxy.socket
PROXY_SERVICE=keplerops-orion-agent-proxy.service

[[ $EUID -eq 0 ]] || {
  echo "install.sh must run as root" >&2
  exit 2
}

"$ROOT/apply-compose-policy.sh" validate
install -m 0644 "$ROOT/$POLICY_UNIT" "/etc/systemd/system/$POLICY_UNIT"
install -m 0644 "$ROOT/$PROXY_SOCKET" "/etc/systemd/system/$PROXY_SOCKET"
install -m 0644 "$ROOT/$PROXY_SERVICE" "/etc/systemd/system/$PROXY_SERVICE"
systemctl daemon-reload
systemctl enable "$POLICY_UNIT" "$PROXY_SOCKET"
systemctl restart "$POLICY_UNIT"
systemctl start "$PROXY_SOCKET"
systemctl --quiet is-active "$POLICY_UNIT" "$PROXY_SOCKET"
