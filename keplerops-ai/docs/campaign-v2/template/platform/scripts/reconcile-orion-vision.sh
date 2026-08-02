#!/usr/bin/env bash
set -Eeuo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck source=../versions.env
source "$ROOT/versions.env"
K3S01_SSH_TARGET=${K3S01_SSH_TARGET:-kepler@192.168.78.30}
K3S01_SSH_KEY=${K3S01_SSH_KEY:-/root/.ssh/keplerops-v2}
SSH=(ssh -i "$K3S01_SSH_KEY" -o BatchMode=yes -o StrictHostKeyChecking=accept-new)

if [[ $EUID -ne 0 ]]; then
  echo "reconcile-orion-vision.sh must run as root" >&2
  exit 2
fi
for command in awk curl docker find sha256sum sort ssh xargs; do
  command -v "$command" >/dev/null || {
    echo "Required command is unavailable: $command" >&2
    exit 2
  }
done
[[ -r $K3S01_SSH_KEY ]] || {
  echo "k3s01 SSH key is unreadable: $K3S01_SSH_KEY" >&2
  exit 3
}

image_root="$ROOT/images/orion-vision"
source_sha=$(find "$image_root" -type f -print0 | sort -z | \
  xargs -0 sha256sum | sha256sum | awk '{print $1}')
image_sha=$(docker image inspect "$ORION_VISION_IMAGE" \
  --format '{{index .Config.Labels "keplerops.source-sha256"}}' 2>/dev/null || true)
image_changed=0
if [[ $image_sha != "$source_sha" ]]; then
  docker build --label "keplerops.source-sha256=$source_sha" \
    -t "$ORION_VISION_IMAGE" "$image_root"
  image_changed=1
fi

if ((image_changed)) || ! "${SSH[@]}" "$K3S01_SSH_TARGET" \
  "sudo k3s ctr images ls -q | grep -Eq '(^|/)$ORION_VISION_IMAGE$'" >/dev/null 2>&1; then
  docker save "$ORION_VISION_IMAGE" | \
    "${SSH[@]}" "$K3S01_SSH_TARGET" "sudo k3s ctr images import -" >/dev/null
fi

"${SSH[@]}" "$K3S01_SSH_TARGET" \
  "sudo k3s kubectl apply -f -" <"$ROOT/manifests/orion-vision.yaml" >/dev/null
"${SSH[@]}" "$K3S01_SSH_TARGET" \
  "sudo k3s kubectl -n orion-runtime patch deployment orion-vision --type merge \
    -p '{\"spec\":{\"template\":{\"metadata\":{\"annotations\":{\"keplerops.lab/source-sha256\":\"$source_sha\"}}}}}' >/dev/null && \
   sudo k3s kubectl -n orion-runtime rollout status deployment/orion-vision --timeout=5m" >/dev/null

curl --fail --silent --show-error --max-time 10 \
  "http://${K3S01_SSH_TARGET#*@}:30084/health/ready" >/dev/null
echo "Orion Vision bridge provider is ready"
