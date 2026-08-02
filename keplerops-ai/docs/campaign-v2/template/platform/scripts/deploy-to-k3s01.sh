#!/usr/bin/env bash
set -Eeuo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck source=../versions.env
source "$ROOT/versions.env"
K3S01_SSH_TARGET=${K3S01_SSH_TARGET:-kepler@192.168.78.30}
K3S01_SSH_KEY=${K3S01_SSH_KEY:-/root/.ssh/keplerops-v2}
STEP_CA_CONTAINER=${STEP_CA_CONTAINER:-kep-v2-step-ca}
SSH=(ssh -i "$K3S01_SSH_KEY" -o BatchMode=yes -o StrictHostKeyChecking=accept-new)

for command in docker ssh tar; do
  command -v "$command" >/dev/null || {
    echo "Required command is unavailable: $command" >&2
    exit 2
  }
done
[[ -r $K3S01_SSH_KEY ]] || {
  echo "k3s01 SSH key is unreadable: $K3S01_SSH_KEY" >&2
  exit 3
}

"${SSH[@]}" "$K3S01_SSH_TARGET" \
  "sudo test -s /etc/rancher/k3s/k3s.yaml && sudo k3s kubectl get node k3s01" >/dev/null

docker build --pull \
  -t "$ORION_PLACEHOLDER_IMAGE" "$ROOT/images/orion-placeholder"
docker build --pull \
  -t "$ORION_AGENT_IMAGE" "$ROOT/images/orion-agent"
docker build --pull \
  -t "$ORION_VISION_IMAGE" "$ROOT/images/orion-vision"

for image in "$ORION_PLACEHOLDER_IMAGE" "$ORION_AGENT_IMAGE" "$ORION_VISION_IMAGE"; do
  docker save "$image" | \
    "${SSH[@]}" "$K3S01_SSH_TARGET" "sudo k3s ctr images import -" >/dev/null
done

"${SSH[@]}" "$K3S01_SSH_TARGET" \
  "sudo install -d -m 0755 /opt/keplerops-platform /etc/keplerops/pki"
tar -C "$ROOT" -cf - . | \
  "${SSH[@]}" "$K3S01_SSH_TARGET" \
    "sudo tar -C /opt/keplerops-platform -xf - && sudo chmod +x /opt/keplerops-platform/scripts/*.sh"

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
if docker container inspect "$STEP_CA_CONTAINER" >/dev/null 2>&1; then
  docker cp "$STEP_CA_CONTAINER:/home/step/certs/root_ca.crt" "$tmp/step-root-ca.crt"
  step_path=$(docker exec "$STEP_CA_CONTAINER" sh -c 'command -v step')
  docker cp "$STEP_CA_CONTAINER:$step_path" "$tmp/step"
  tar -C "$tmp" -cf - step-root-ca.crt step | \
    "${SSH[@]}" "$K3S01_SSH_TARGET" \
      "sudo tar -C /etc/keplerops/pki -xf - && sudo chmod 0644 /etc/keplerops/pki/step-root-ca.crt && sudo chmod 0755 /etc/keplerops/pki/step"
  printf '%s' "${STEP_CA_PROVISIONER_PASSWORD:-KeplerV2-Training-StepCA}" | \
    "${SSH[@]}" "$K3S01_SSH_TARGET" \
      "sudo sh -c 'umask 077; cat > /etc/keplerops/pki/step-provisioner-password'"
elif [[ ${SKIP_SIGNING:-0} != 1 ]]; then
  echo "Foundation step-ca container $STEP_CA_CONTAINER is unavailable" >&2
  exit 4
fi

{
  [[ -n ${ORION_ASSISTANT_BASE_URL:-} ]] && printf 'ORION_ASSISTANT_BASE_URL=%q\n' "$ORION_ASSISTANT_BASE_URL"
  [[ -n ${ORION_ASSISTANT_API_KEY:-} ]] && printf 'ORION_ASSISTANT_API_KEY=%q\n' "$ORION_ASSISTANT_API_KEY"
  [[ -n ${ORION_ASSISTANT_UPSTREAM_MODEL:-} ]] && printf 'ORION_ASSISTANT_UPSTREAM_MODEL=%q\n' "$ORION_ASSISTANT_UPSTREAM_MODEL"
  [[ -n ${ORION_AGENT_API_KEY:-} ]] && printf 'ORION_AGENT_API_KEY=%q\n' "$ORION_AGENT_API_KEY"
  [[ ${SKIP_SIGNING:-0} == 1 ]] && printf 'SKIP_SIGNING=1\n'
} >"$tmp/platform-install.env"
cat "$tmp/platform-install.env" | \
  "${SSH[@]}" "$K3S01_SSH_TARGET" \
    "sudo sh -c 'umask 077; cat > /etc/keplerops/platform-install.env'"

"${SSH[@]}" "$K3S01_SSH_TARGET" \
  "sudo bash -c 'set -a; source /etc/keplerops/platform-install.env; set +a; exec /opt/keplerops-platform/scripts/install-platform.sh'"

gitops_revision=$("$ROOT/scripts/seed-gitops.sh")
"${SSH[@]}" "$K3S01_SSH_TARGET" \
  "sudo env GITOPS_REPO_URL=http://192.168.78.1:3000/keplerops/orion-platform.git GITOPS_REVISION=$gitops_revision GITOPS_REPO_PATH=gitops/orion-canary /opt/keplerops-platform/scripts/configure-gitops.sh"
"${SSH[@]}" "$K3S01_SSH_TARGET" \
  "sudo /opt/keplerops-platform/scripts/readiness.sh"

echo "Core platform is ready. Argo CD: http://192.168.78.30:30080"
