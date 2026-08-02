#!/usr/bin/env bash
set -Eeuo pipefail

readonly ROOT=${KEPLEROPS_V2_ROOT:-/opt/keplerops-v2}
readonly MODE=${1:-resume}

if [[ $EUID -ne 0 ]]; then
  echo "start-all.sh must run as root" >&2
  exit 2
fi
if [[ $MODE != build && $MODE != resume ]]; then
  echo "Usage: $0 {build|resume}" >&2
  exit 2
fi

if [[ $MODE == resume ]]; then
  export KEPLEROPS_SKIP_PULL=1
fi

"$ROOT/scripts/start-foundation.sh"
"$ROOT/scripts/provision-guests.sh"

deadline=$((SECONDS + 1800))
until "$ROOT/scripts/check-guests.sh"; do
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
  ssh -i /root/.ssh/keplerops-v2 -o BatchMode=yes \
    -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    kepler@192.168.78.30 sudo /opt/keplerops-platform/scripts/readiness.sh
fi
"$ROOT/scripts/activate-business-model-identities.sh"
"$ROOT/baseline/source-ci-registries.sh"
"$ROOT/seeding/seed.sh" langflow business-workflows
"$ROOT/engineering/reconcile-orion-vision-label-studio.sh"

"$ROOT/scripts/start-workstation.sh"
"$ROOT/scripts/start-cinder.sh"
"$ROOT/scripts/check-all.sh"
"$ROOT/campaign-start/apply.sh"
