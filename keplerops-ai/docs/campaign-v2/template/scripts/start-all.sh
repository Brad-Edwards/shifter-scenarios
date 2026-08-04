#!/usr/bin/env bash
set -Eeuo pipefail

readonly ROOT=${KEPLEROPS_V2_ROOT:-/opt/keplerops-v2}
readonly MODE=${1:-resume}
readonly SHIFTER_READY=/run/shifter/preconfigured-range-host.ready
readonly CAMPAIGN_READY=/run/shifter/keplerops-v2-software.ready

if [[ $EUID -ne 0 ]]; then
  echo "start-all.sh must run as root" >&2
  exit 2
fi
if [[ $MODE != build && $MODE != resume ]]; then
  echo "Usage: $0 {build|resume}" >&2
  exit 2
fi

# buildx is not installed on the range host, so Compose's Bake build path
# mishandles services that share a build (it hands the second one a 2-byte
# dockerfile). Disable Bake for every compose build in this standup; Bake is a
# build-only feature, so pulls and `up` are unaffected.
export COMPOSE_BAKE=false

if [[ $MODE == resume ]]; then
  export KEPLEROPS_SKIP_PULL=1
fi

install -d -m 0755 /run/shifter
rm -f "$SHIFTER_READY"

"$ROOT/scripts/start-foundation.sh"
"$ROOT/scripts/provision-guests.sh"

deadline=$((SECONDS + 1800))
until KEPLEROPS_ALLOW_REVIEW_WORKERS_PENDING=1 "$ROOT/scripts/check-guests.sh"; do
  if ((SECONDS >= deadline)); then
    echo "Nested guests did not become ready" >&2
    exit 3
  fi
  sleep 10
done
"$ROOT/scripts/reconcile-guests.sh"
"$ROOT/scripts/start-enterprise.sh"

if [[ $MODE == build ]]; then
  "$ROOT/engineering/engineering.sh" start
  "$ROOT/platform/scripts/deploy-to-k3s01.sh"
else
  "$ROOT/engineering/engineering.sh" converge
  "$ROOT/platform/scripts/reconcile-orion-vision.sh"
  ssh -i /root/.ssh/keplerops-v2 -o BatchMode=yes \
    -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    kepler@192.168.78.30 sudo /opt/keplerops-platform/scripts/readiness.sh --core
fi
"$ROOT/seeding/seed.sh" mautic langflow business-workflows
"$ROOT/engineering/reconcile-orion-vision-label-studio.sh"

"$ROOT/scripts/start-workstation.sh"
"$ROOT/scripts/start-cinder.sh"
"$ROOT/campaign-start/apply.sh"
"$ROOT/baseline/source-ci-registries.sh"
"$ROOT/scripts/check-all.sh"

boot_id=$(cat /proc/sys/kernel/random/boot_id)
read -r campaign_boot _ readiness_class <"$CAMPAIGN_READY"
[[ $campaign_boot == "$boot_id" && $readiness_class == software-operations ]] || {
  echo "campaign software readiness is absent or stale" >&2
  exit 4
}
printf '%s\n' "$boot_id preconfigured-range-host" >"$SHIFTER_READY"
echo "KeplerOps AI Systems enterprise is ready"
