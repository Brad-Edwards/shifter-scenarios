#!/usr/bin/env bash
set -euo pipefail
umask 077

BUILD_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
RANGE_INSTANCE= PARTICIPANT= ACTION= DROPPED_COUNT=0
while (($#)); do
  case "$1" in
    --range-instance) RANGE_INSTANCE=${2-}; shift 2 ;;
    --participant) PARTICIPANT=${2-}; shift 2 ;;
    --action) ACTION=${2-}; shift 2 ;;
    --dropped-count) DROPPED_COUNT=${2-}; shift 2 ;;
    *) exit 2 ;;
  esac
done
[[ $RANGE_INSTANCE =~ ^[a-z0-9]([a-z0-9-]{0,30}[a-z0-9])?$ ]] || exit 2
[[ $PARTICIPANT =~ ^[a-z0-9]([a-z0-9-]{0,30}[a-z0-9])?$ ]] || exit 2
[[ $ACTION =~ ^(enable-instrumentation|disable-instrumentation|stop-collector|restart-proof|record-loss)$ ]] || exit 2
[[ $DROPPED_COUNT =~ ^[0-9]+$ ]] || exit 2

ROOT="$BUILD_ROOT/.operator/$RANGE_INSTANCE-$PARTICIPANT"
STATE="$ROOT/terraform.tfstate"
RUN_STATE="$ROOT/state.json"
[[ -f $STATE && -f $RUN_STATE ]] || { echo 'error: range state not found' >&2; exit 2; }
PROJECT_ID=$(terraform -chdir="$BUILD_ROOT/gcp" output -state="$STATE" -raw project_id)
ZONE=$(terraform -chdir="$BUILD_ROOT/gcp" output -state="$STATE" -raw range_zone)
INVENTORY=$(terraform -chdir="$BUILD_ROOT/gcp" output -state="$STATE" -json asset_inventory)
instance_for() {
  python3 -c '
import json,sys
realization=json.load(open(sys.argv[1], encoding="utf-8"))
hosts=json.load(sys.stdin)
host=realization["workloads"][sys.argv[2]]["host"]
print(hosts[host]["name"])
' "$ROOT/sdl-realization.json" "$1" <<<"$INVENTORY"
}
ssh_command() {
  local instance=$1 command=$2
  gcloud compute ssh "$instance" --project "$PROJECT_ID" --zone "$ZONE" \
    --tunnel-through-iap --quiet --command "$command" </dev/null >/dev/null
}

case "$ACTION" in
  enable-instrumentation|disable-instrumentation)
    GATE=enabled
    [[ $ACTION == disable-instrumentation ]] && GATE=disabled
    INSTANCE=$(instance_for inference-gateway)
    ssh_command "$INSTANCE" "printf '%s\\n' '$GATE' | sudo tee /var/lib/keplerops-carrier/workloads/inference-gateway/state/telemetry-enabled >/dev/null && sudo chown 65532:65532 /var/lib/keplerops-carrier/workloads/inference-gateway/state/telemetry-enabled && sudo chmod 0600 /var/lib/keplerops-carrier/workloads/inference-gateway/state/telemetry-enabled"
    ;;
  stop-collector)
    INSTANCE=$(instance_for telemetry-proof-01)
    ssh_command "$INSTANCE" "sudo bash /var/lib/keplerops-carrier/bin/keplerops-workload exec telemetry-proof-01 sh -c 'kill \"\$(cat /var/lib/keplerops-research/otel/collector.pid)\"'"
    ;;
  restart-proof)
    INSTANCE=$(instance_for telemetry-proof-01)
    ssh_command "$INSTANCE" "sudo docker restart keplerops-telemetry-proof-01-runtime >/dev/null"
    ;;
  record-loss)
    ((DROPPED_COUNT > 0)) || { echo 'error: positive dropped count required' >&2; exit 2; }
    GENERATION=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["reset_generation"])' "$RUN_STATE")
    INSTANCE=$(instance_for telemetry-proof-01)
    ssh_command "$INSTANCE" "sudo bash /var/lib/keplerops-carrier/bin/keplerops-workload exec telemetry-proof-01 python /opt/keplerops/research_cli.py lifecycle --event telemetry.loss_observed --range-instance '$RANGE_INSTANCE' --participant '$PARTICIPANT' --reset-generation '$GENERATION' --dropped-event-count '$DROPPED_COUNT'"
    ;;
esac
