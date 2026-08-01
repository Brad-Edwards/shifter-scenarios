#!/usr/bin/env bash
set -Eeuo pipefail

readonly ROOT=${KEPLEROPS_V2_ROOT:-/opt/keplerops-v2}
readonly KEY=/root/.ssh/keplerops-v2
readonly K3S_TARGET=kepler@192.168.78.30
readonly WORKSTATION=keplerops-participant-workstation-runtime
readonly SSH=(ssh -i "$KEY" -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null)

if [[ $EUID -ne 0 ]]; then
  echo "check-all.sh must run as root" >&2
  exit 2
fi

"$ROOT/scripts/health-check.sh" foundation
"$ROOT/scripts/check-guests.sh"
"$ROOT/scripts/health-check.sh" enterprise
"$ROOT/engineering/engineering.sh" health
"${SSH[@]}" "$K3S_TARGET" sudo /opt/keplerops-platform/scripts/readiness.sh

docker exec "$WORKSTATION" sh -c \
  'ss -lnt | grep -q ":3389 " && ss -lnt | grep -q ":6901 "'
docker exec --user kasm-user "$WORKSTATION" sh -lc \
  'curl -fsS --max-time 15 https://keplerops.lab/ >/dev/null &&
   curl -fsS --max-time 15 https://models.keplerops.lab/health/liveliness >/dev/null &&
   curl -fsS --max-time 15 https://www.google.com/generate_204 >/dev/null'

for container in kep-v2-cinder-minio kep-v2-cinder-forgejo kep-v2-cinder-jupyter; do
  state=$(docker inspect --format '{{.State.Status}}' "$container" 2>/dev/null || true)
  [[ $state == running ]] || {
    echo "Cinder service is not running: $container" >&2
    exit 3
  }
done
bootstrap=$(docker inspect --format '{{.State.Status}} {{.State.ExitCode}}' \
  kep-v2-cinder-bootstrap 2>/dev/null || true)
[[ $bootstrap == "exited 0" ]] || {
  echo "Cinder bootstrap is incomplete: $bootstrap" >&2
  exit 4
}

install -d -m 0755 /run/shifter
printf '%s\n' "$(cat /proc/sys/kernel/random/boot_id) clean-enterprise" \
  >/run/shifter/keplerops-v2-clean-enterprise.ready
echo "KeplerOps campaign-v2 clean enterprise passed all readiness gates"
