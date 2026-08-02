#!/usr/bin/env bash
set -Eeuo pipefail

readonly ROOT=${KEPLEROPS_V2_ROOT:-/opt/keplerops-v2}
readonly KEY=/root/.ssh/keplerops-v2
readonly K3S_TARGET=kepler@192.168.78.30
readonly WORKSTATION=keplerops-participant-workstation-runtime
readonly SSH=(ssh -i "$KEY" -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null)
readonly BASELINE_TIMEOUT=${KEPLEROPS_BASELINE_TIMEOUT:-600}
readonly READINESS_MARKER=/run/shifter/keplerops-v2-component-substrate.ready

run_baseline() {
  local name=$1
  local script=$2
  local status

  echo "Running participant-network baseline: $name"
  timeout --foreground --signal=TERM "${BASELINE_TIMEOUT}s" "$script" || {
    status=$?
    echo "Participant-network baseline failed: $name (status $status)" >&2
    return "$status"
  }
}

if [[ $EUID -ne 0 ]]; then
  echo "check-all.sh must run as root" >&2
  exit 2
fi

install -d -m 0755 /run/shifter
rm -f "$READINESS_MARKER"

[[ $BASELINE_TIMEOUT =~ ^[1-9][0-9]*$ ]] || {
  echo "KEPLEROPS_BASELINE_TIMEOUT must be a positive integer" >&2
  exit 2
}
command -v timeout >/dev/null 2>&1 || {
  echo "timeout is required for participant-network readiness baselines" >&2
  exit 2
}

"$ROOT/scripts/health-check.sh" foundation
"$ROOT/scripts/check-guests.sh"
"$ROOT/scripts/health-check.sh" enterprise
"$ROOT/engineering/engineering.sh" health
"${SSH[@]}" "$K3S_TARGET" sudo /opt/keplerops-platform/scripts/readiness.sh

docker exec "$WORKSTATION" sh -c \
  'ss -lnt | grep -q ":3389 " && ss -lnt | grep -q ":6901 "'
docker exec --user kasm-user "$WORKSTATION" sh -lc \
  'curl -fsS --max-time 15 https://keplerops.lab/ >/dev/null &&
   curl -fsS --max-time 15 https://git.keplerops.lab/api/v1/repos/keplerops/orion-public >/dev/null &&
   curl -fsS --max-time 15 https://preview.keplerops.lab/ >/dev/null &&
   curl -fsS --max-time 15 https://intake.keplerops.lab/api/v1/getting_started >/dev/null &&
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

run_baseline identity-role-enforcement "$ROOT/baseline/identity-role-enforcement.sh"
run_baseline business-role-enforcement "$ROOT/baseline/business-role-enforcement.sh"
run_baseline langflow-role-enforcement "$ROOT/baseline/langflow-role-enforcement.sh"
run_baseline data-service-role-enforcement "$ROOT/baseline/data-service-role-enforcement.sh"
run_baseline unleash-role-enforcement "$ROOT/baseline/unleash-role-enforcement.sh"

# Public-surface and WorkHub functional rehearsals are intentionally excluded
# here because they create mail, retrieval, and conversation records. They run
# before template capture or during walkthroughs; final readiness must preserve
# the operator's clean initial enterprise state.

printf '%s\n' "$(cat /proc/sys/kernel/random/boot_id) component-substrate" \
  >"$READINESS_MARKER"
echo "KeplerOps campaign-v2 component substrate passed its readiness gates"
