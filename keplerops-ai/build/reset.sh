#!/usr/bin/env bash
set -euo pipefail
umask 077

BUILD_ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
RANGE_INSTANCE='' PARTICIPANT=''
while (($#)); do
  case "$1" in
    --range-instance) RANGE_INSTANCE=${2-}; shift 2 ;;
    --participant) PARTICIPANT=${2-}; shift 2 ;;
    *) exit 2 ;;
  esac
done
[[ $RANGE_INSTANCE =~ ^[a-z0-9]([a-z0-9-]{0,30}[a-z0-9])?$ ]] || exit 2
[[ $PARTICIPANT =~ ^[a-z0-9]([a-z0-9-]{0,30}[a-z0-9])?$ ]] || exit 2
refresh_access_token() {
  export GOOGLE_OAUTH_ACCESS_TOKEN
  if ! GOOGLE_OAUTH_ACCESS_TOKEN=$(
    env -u GOOGLE_OAUTH_ACCESS_TOKEN -u CLOUDSDK_AUTH_ACCESS_TOKEN \
      gcloud auth application-default print-access-token 2>/dev/null
  ); then
    GOOGLE_OAUTH_ACCESS_TOKEN=$(
      env -u GOOGLE_OAUTH_ACCESS_TOKEN -u CLOUDSDK_AUTH_ACCESS_TOKEN \
        gcloud auth print-access-token
    )
  fi
  export CLOUDSDK_AUTH_ACCESS_TOKEN=$GOOGLE_OAUTH_ACCESS_TOKEN
}
refresh_access_token
resolve_gcloud_account() {
  local account=${KEPLEROPS_GCLOUD_ACCOUNT:-}
  if [[ -z "$account" ]]; then
    account=$(
      env -u GOOGLE_OAUTH_ACCESS_TOKEN -u CLOUDSDK_AUTH_ACCESS_TOKEN \
        gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null |
        head -n1 || true
    )
  fi
  if [[ -z "$account" ]]; then
    account=$(
      env -u GOOGLE_OAUTH_ACCESS_TOKEN -u CLOUDSDK_AUTH_ACCESS_TOKEN \
        gcloud config get-value core/account 2>/dev/null || true
    )
  fi
  printf '%s\n' "$account"
}
GCLOUD_ACCOUNT=$(resolve_gcloud_account)
GCLOUD_ACCOUNT_ARGS=()
if [[ -n "$GCLOUD_ACCOUNT" ]]; then
  GCLOUD_ACCOUNT_ARGS=(--account "$GCLOUD_ACCOUNT")
fi

ROOT="$BUILD_ROOT/.operator/$RANGE_INSTANCE-$PARTICIPANT"
STATE="$ROOT/state.json"
TFSTATE="$ROOT/terraform.tfstate"
TFVARS="$ROOT/range.auto.tfvars.json"
IMAGE_LOCK="$ROOT/image-lock.json"
REALIZATION="$ROOT/sdl-realization.json"
INVENTORY="$ROOT/.reset-inventory"
WINDOWS_READBACK="$ROOT/.windows-reset-readback"

RESET_STATUS=$(python3 - "$BUILD_ROOT/gcp" "$STATE" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
import lifecycle
print(lifecycle.load_state(lifecycle.Path(sys.argv[2])).status)
PY
)
RESUMING=false
case "$RESET_STATUS" in
  ready) python3 "$BUILD_ROOT/gcp/lifecycle.py" begin-reset --state "$STATE" ;;
  resetting) RESUMING=true; printf '{"status":"resuming-reset"}\n' ;;
  *) echo 'error: range reset cannot be resumed' >&2; exit 2 ;;
esac

GENERATION=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["reset_generation"])' "$STATE")
PROJECT_ID=$(terraform -chdir="$BUILD_ROOT/gcp" output -state="$TFSTATE" -raw project_id)
ZONE=$(terraform -chdir="$BUILD_ROOT/gcp" output -state="$TFSTATE" -raw range_zone)
HOSTS=$(mktemp "$ROOT/.reset-hosts.XXXXXXXX.json")
trap 'rm -f "$INVENTORY" "$HOSTS" "$WINDOWS_READBACK"' EXIT
terraform -chdir="$BUILD_ROOT/gcp" output -state="$TFSTATE" -json asset_inventory >"$HOSTS"
python3 - "$REALIZATION" "$HOSTS" "$INVENTORY" <<'PY'
import json, os, sys
realization = json.load(open(sys.argv[1], encoding="utf-8"))
hosts = json.load(open(sys.argv[2], encoding="utf-8"))
with open(sys.argv[3], "w", encoding="utf-8") as handle:
    for workload_id, workload in sorted(realization["workloads"].items()):
        if workload.get("deployment_cell") != "range-cell":
            continue
        host_id = workload["host"]
        handle.write(f"{workload_id}\t{host_id}\t{hosts[host_id]['name']}\n")
os.chmod(sys.argv[3], 0o600)
PY

RESET_SSH_TIMEOUT_SECONDS=${KEPLEROPS_RESET_SSH_TIMEOUT_SECONDS:-240}
ssh_instance_command() {
  local instance=$1 command=$2
  refresh_access_token
  timeout --kill-after=15s "${RESET_SSH_TIMEOUT_SECONDS}s" \
    gcloud compute ssh "$instance" \
      "${GCLOUD_ACCOUNT_ARGS[@]}" \
      --project "$PROJECT_ID" \
      --zone "$ZONE" \
      --tunnel-through-iap \
      --quiet \
      --command "$command" </dev/null
}

instance_for() {
  awk -F '\t' -v asset="$1" '$1 == asset {print $3}' "$INVENTORY"
}

workload_command() {
  local asset=$1 action=$2 required=${3:-required} instance
  instance=$(instance_for "$asset")
  if [[ -z "$instance" ]]; then
    [[ "$required" == optional ]] && return 0
    return 2
  fi
  ssh_instance_command "$instance" \
    "sudo bash /var/lib/keplerops-carrier/bin/keplerops-workload '$action' '$asset'"
}

wait_for_carrier_ready() {
  local instance
  instance=$(instance_for range-dns-01)
  [[ -n "$instance" ]] || return 2
  for _ in $(seq 1 720); do
    if ssh_instance_command "$instance" \
      "sudo bash -c 'test \"\$(cat /proc/sys/kernel/random/boot_id)\" = \"\$(cat /var/lib/keplerops-carrier/ready 2>/dev/null)\"'"; then
      return 0
    fi
    sleep 10
  done
  return 1
}

ensure_quiesced() {
  local asset=$1 required=${2:-required} instance
  instance=$(instance_for "$asset")
  if [[ -z "$instance" ]]; then
    [[ "$required" == optional ]] && return 0
    return 2
  fi
  ssh_instance_command "$instance" \
    "sudo test -f '/var/lib/keplerops-carrier/workloads/$asset/state/quiesced' || sudo bash /var/lib/keplerops-carrier/bin/keplerops-workload quiesce '$asset'"
}

telemetry_marker() {
  local event=$1 generation=$2 instance
  instance=$(instance_for telemetry-proof-01)
  [[ -n "$instance" ]] || return 2
  ssh_instance_command "$instance" \
    "sudo bash /var/lib/keplerops-carrier/bin/keplerops-workload exec telemetry-proof-01 python /opt/keplerops/research_cli.py lifecycle --event '$event' --range-instance '$RANGE_INSTANCE' --participant '$PARTICIPANT' --reset-generation '$generation'" \
    >/dev/null
}

wait_for_carrier_ready

export TELEMETRY_MARKER_STATUS=complete
RESET_REQUESTED_MARKER=complete
RESET_STARTED_MARKER=complete
SESSION_CLOSED_MARKER=complete
PRIOR_GENERATION=$((GENERATION - 1))
telemetry_marker reset.requested "$PRIOR_GENERATION" || RESET_REQUESTED_MARKER=optional
telemetry_marker session.reset_started "$PRIOR_GENERATION" || RESET_STARTED_MARKER=incomplete
telemetry_marker session.closed "$PRIOR_GENERATION" || SESSION_CLOSED_MARKER=incomplete

if [[ $RESUMING == false ]]; then
  for PRIORITY in participant-workstation telemetry-proof-01 image-generation-01; do
    workload_command "$PRIORITY" quiesce optional
  done
  while IFS=$'\t' read -r ASSET _HOST _INSTANCE; do
    case "$ASSET" in
      participant-workstation|telemetry-proof-01|image-generation-01) continue ;;
    esac
    workload_command "$ASSET" quiesce
  done <"$INVENTORY"
else
  for GATED in image-generation-01 platform-agent-01 range-ops-controller; do
    ensure_quiesced "$GATED" optional
  done
fi

replace_nested_range() {
  terraform -chdir="$BUILD_ROOT/gcp" apply -input=false -auto-approve \
    -state="$TFSTATE" \
    -var-file="$TFVARS" \
    -var='deploy_runtime=true' \
    -var="image_lock_file=$IMAGE_LOCK" \
    -var="sdl_realization_file=$REALIZATION" \
    -replace='google_compute_instance.range_host[0]' \
    -replace='google_compute_disk.windows_guest["ad-dc-01"]' \
    -replace='google_compute_disk.windows_guest["workforce-workstation-01"]' \
    -replace='google_compute_disk.windows_guest["ml-workstation-01"]'
}

windows_instance_for() {
  jq -er --arg host "$1" '.[$host].name' "$HOSTS"
}

verify_windows_owner() {
  local host=$1 instance expected_id readback
  instance=$(windows_instance_for "$host")
  for _ in $(seq 1 120); do
    expected_id=$(ssh_instance_command "$instance" \
      "sudo curl --fail --silent http://192.168.77.1:8080/metadata/instance/id" \
      2>/dev/null || true)
    readback=$(ssh_instance_command "$instance" \
      "sudo cat '/var/lib/keplerops-nested/guest-attributes/$host/readback'" \
      2>/dev/null || true)
    if python3 - "$host" "$expected_id" "$readback" <<'PY'
import json, sys
host, expected_id, raw = sys.argv[1:]
expected_roles = {
    "ad-dc-01": "domain-controller",
    "workforce-workstation-01": "domain-member",
    "ml-workstation-01": "domain-member",
}
try:
    value = json.loads(raw)
except json.JSONDecodeError:
    raise SystemExit(1)
if not expected_id or value != {
    "domain": "keplerops.test",
    "host_id": host,
    "instance_id": expected_id,
    "role": expected_roles[host],
    "status": "ready",
}:
    raise SystemExit(1)
PY
    then
      printf '%s\t%s\n' "$host" "$expected_id" >>"$WINDOWS_READBACK"
      return 0
    fi
    sleep 10
  done
  return 1
}

: >"$WINDOWS_READBACK"
chmod 0600 "$WINDOWS_READBACK"

verify_windows_owners() {
  while read -r OWNER; do
    verify_windows_owner "$OWNER"
  done < <(
  python3 -c '
import sys
sys.path.insert(0, sys.argv[1])
import lifecycle
print("\n".join(lifecycle.WINDOWS_RESET_OWNERS))
' "$BUILD_ROOT/gcp"
)
}

if [[ $RESUMING == true ]] && verify_windows_owners; then
  :
else
  : >"$WINDOWS_READBACK"
  replace_nested_range
  verify_windows_owners
fi

wait_for_carrier_ready

reset_workload() {
  local asset=$1 instance status=0
  instance=$(instance_for "$asset")
  [[ -n "$instance" ]] || return 2
  ssh_instance_command "$instance" \
    "sudo bash /var/lib/keplerops-carrier/bin/keplerops-workload reset '$asset' '$GENERATION'" || status=$?
  if [[ $status == 0 ]]; then
    return 0
  fi
  printf 'warning: reset command for %s exited %s; verifying owner state\n' "$asset" "$status" >&2
  for _ in $(seq 1 12); do
    if ssh_instance_command "$instance" \
      "sudo bash /var/lib/keplerops-carrier/bin/keplerops-workload reset-verify '$asset'"; then
      return 0
    fi
    sleep 10
  done
  return "$status"
}

for PRIORITY in \
  range-dns-01 research-index-01 dataset-store-01 repo-ticket-01 \
  platform-ml-01 platform-camera-01; do
  reset_workload "$PRIORITY"
done
while IFS=$'\t' read -r ASSET _HOST _INSTANCE; do
  case "$ASSET" in
    range-dns-01|research-index-01|dataset-store-01|repo-ticket-01|platform-ml-01|platform-camera-01)
      continue
      ;;
  esac
  reset_workload "$ASSET"
done <"$INVENTORY"

"$BUILD_ROOT/health-check.sh" --range-instance "$RANGE_INSTANCE" --participant "$PARTICIPANT"

if [[ $RESET_REQUESTED_MARKER == incomplete ]]; then
  RESET_REQUESTED_MARKER=complete
  telemetry_marker reset.requested "$PRIOR_GENERATION" || RESET_REQUESTED_MARKER=optional
fi
if [[ $RESET_STARTED_MARKER == incomplete ]]; then
  RESET_STARTED_MARKER=complete
  telemetry_marker session.reset_started "$PRIOR_GENERATION" || RESET_STARTED_MARKER=incomplete
fi
if [[ $SESSION_CLOSED_MARKER == incomplete ]]; then
  SESSION_CLOSED_MARKER=complete
  telemetry_marker session.closed "$PRIOR_GENERATION" || SESSION_CLOSED_MARKER=incomplete
fi
if [[ $RESET_STARTED_MARKER == incomplete || $SESSION_CLOSED_MARKER == incomplete ]]; then
  TELEMETRY_MARKER_STATUS=incomplete
fi
telemetry_marker session.started "$GENERATION" || TELEMETRY_MARKER_STATUS=incomplete
telemetry_marker reset.completed "$GENERATION" || true
telemetry_marker session.reset_completed "$GENERATION" || TELEMETRY_MARKER_STATUS=incomplete

VERIFIED=()
while read -r OWNER; do
  workload_command "$OWNER" reset-verify
  VERIFIED+=("$OWNER")
done < <(
  python3 -c '
import sys
sys.path.insert(0, sys.argv[1])
import lifecycle
print("\n".join(lifecycle.WORKLOAD_RESET_OWNERS))
' "$BUILD_ROOT/gcp"
)
while IFS=$'\t' read -r OWNER _INSTANCE_ID; do
  VERIFIED+=("$OWNER")
done <"$WINDOWS_READBACK"

NEGATIVE_REPORT="$ROOT/reset-verification.json"
python3 - "$BUILD_ROOT/gcp" "$NEGATIVE_REPORT" "$GENERATION" "${VERIFIED[@]}" <<'PY'
import json, os, sys, tempfile
module_root, destination, generation, *verified = sys.argv[1:]
sys.path.insert(0, module_root)
import lifecycle
if set(verified) != set(lifecycle.RESET_OWNERS):
    raise SystemExit("reset owner verification incomplete")
report = {
    "schema_version": 1,
    "status": "passed",
    "reset_generation": int(generation),
    "completed_owners": sorted(lifecycle.RESET_OWNERS),
    "checks": [
        "agent_state_clean",
        "context_empty",
        "proof_empty",
        "runtime_gate_ready",
        "windows_domain_readback",
    ],
    "telemetry_markers": os.environ.get("TELEMETRY_MARKER_STATUS", "unknown"),
    "windows_readback": {
        host: {
            "domain": lifecycle.WINDOWS_DOMAIN,
            "role": lifecycle.WINDOWS_RESET_ROLES[host],
            "status": "ready",
        }
        for host in lifecycle.WINDOWS_RESET_OWNERS
    },
}
fd, temporary = tempfile.mkstemp(prefix=".reset-verification-", dir=os.path.dirname(destination))
os.fchmod(fd, 0o600)
with os.fdopen(fd, "w", encoding="utf-8") as handle:
    json.dump(report, handle, sort_keys=True)
    handle.write("\n")
os.replace(temporary, destination)
PY

OWNER_ARGS=()
for OWNER in "${VERIFIED[@]}"; do
  OWNER_ARGS+=(--completed-owner "$OWNER")
done
python3 "$BUILD_ROOT/gcp/lifecycle.py" finish-reset \
  --state "$STATE" \
  "${OWNER_ARGS[@]}" \
  --negative-gate-report "$NEGATIVE_REPORT" \
  --health-report "$ROOT/health-report.json"
