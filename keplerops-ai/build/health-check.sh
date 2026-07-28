#!/usr/bin/env bash
set -euo pipefail
umask 077

BUILD_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
RANGE_INSTANCE= PARTICIPANT=
while (($#)); do
  case "$1" in
    --range-instance) RANGE_INSTANCE=${2-}; shift 2 ;;
    --participant) PARTICIPANT=${2-}; shift 2 ;;
    *) exit 2 ;;
  esac
done
[[ $RANGE_INSTANCE =~ ^[a-z0-9]([a-z0-9-]{0,30}[a-z0-9])?$ ]] || exit 2
[[ $PARTICIPANT =~ ^[a-z0-9]([a-z0-9-]{0,30}[a-z0-9])?$ ]] || exit 2

ROOT="$BUILD_ROOT/.operator/$RANGE_INSTANCE-$PARTICIPANT"
TFSTATE="$ROOT/terraform.tfstate"
REALIZATION="$ROOT/sdl-realization.json"
HOSTS="$ROOT/.health-hosts.json"
WORKLOADS="$ROOT/.health-workloads"
WINDOWS_HOSTS="$ROOT/.health-windows-hosts"
INFRA_REPORT=$(mktemp "$ROOT/.health-infrastructure.XXXXXXXX.json")
trap 'rm -f "$INFRA_REPORT" "$HOSTS" "$WORKLOADS" "$WINDOWS_HOSTS"' EXIT

tf_output_or_var() {
  local output_name=$1 variable_name=$2 value
  value=$(terraform -chdir="$BUILD_ROOT/gcp" output -state="$TFSTATE" -raw "$output_name" 2>/dev/null || true)
  if [[ -n "$value" ]]; then
    printf '%s\n' "$value"
    return 0
  fi
  python3 -c '
import json, sys
with open(sys.argv[1], encoding="utf-8") as handle:
    value = json.load(handle).get(sys.argv[2])
if not isinstance(value, str) or not value:
    raise SystemExit(1)
print(value)
' "$ROOT/range.auto.tfvars.json" "$variable_name"
}

PROJECT_ID=$(tf_output_or_var project_id project_id)
ZONE=$(tf_output_or_var range_zone zone)
GENERATION=$(python3 -c \
  'import sys; sys.path.insert(0,sys.argv[1]); import lifecycle; print(lifecycle.load_state(lifecycle.Path(sys.argv[2])).reset_generation)' \
  "$BUILD_ROOT/gcp" "$ROOT/state.json")

terraform -chdir="$BUILD_ROOT/gcp" show -json "$TFSTATE" |
  python3 "$BUILD_ROOT/gcp/health_check.py" \
    --realization "$REALIZATION" \
    --output "$INFRA_REPORT" >/dev/null
terraform -chdir="$BUILD_ROOT/gcp" output -state="$TFSTATE" -json asset_inventory >"$HOSTS"
chmod 0600 "$HOSTS"

MODEL_CARRIER=$(jq -er '."range-linux-carrier-01".name' "$HOSTS")
gcloud compute ssh "$MODEL_CARRIER" \
  --project "$PROJECT_ID" \
  --zone "$ZONE" \
  --tunnel-through-iap \
  --quiet \
  --command \
  "sudo bash -c 'set -euo pipefail; URL=\$(curl --fail --silent --show-error -H \"Metadata-Flavor: Google\" http://metadata.google.internal/computeMetadata/v1/instance/attributes/keplerops-shared-model-url); TOKEN=\$(curl --fail --silent --show-error --get -H \"Metadata-Flavor: Google\" --data-urlencode \"audience=\$URL\" --data-urlencode format=full http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity); curl --fail --silent --show-error -H \"Authorization: Bearer \$TOKEN\" \"\$URL/health\" >/dev/null'" \
  </dev/null >/dev/null

python3 - "$REALIZATION" "$HOSTS" "$WORKLOADS" "$WINDOWS_HOSTS" <<'PY'
import json, os, sys
realization_path, hosts_path, workloads_path, windows_path = sys.argv[1:]
realization = json.load(open(realization_path, encoding="utf-8"))
hosts = json.load(open(hosts_path, encoding="utf-8"))
with open(workloads_path, "w", encoding="utf-8") as handle:
    for workload_id, workload in sorted(realization["workloads"].items()):
        if workload.get("deployment_cell") != "range-cell":
            continue
        host_id = workload["host"]
        handle.write(f"{workload_id}\t{host_id}\t{hosts[host_id]['name']}\n")
with open(windows_path, "w", encoding="utf-8") as handle:
    for host_id, host in sorted(realization["physical_hosts"].items()):
        if host.get("os") == "windows":
            handle.write(f"{host_id}\t{hosts[host_id]['name']}\n")
os.chmod(workloads_path, 0o600)
os.chmod(windows_path, 0o600)
PY

SERVICE_COUNT=0
while IFS=$'\t' read -r ASSET _HOST INSTANCE; do
  gcloud compute ssh "$INSTANCE" \
    --project "$PROJECT_ID" \
    --zone "$ZONE" \
    --tunnel-through-iap \
    --quiet \
    --command \
    "sudo bash -c 'for attempt in \$(seq 1 120); do test \"\$(cat /var/lib/keplerops-carrier/workloads/$ASSET/state/reset-generation 2>/dev/null || true)\" = \"$GENERATION\" && bash /var/lib/keplerops-carrier/bin/keplerops-workload health \"$ASSET\" && exit 0; sleep 10; done; exit 1'" \
    </dev/null >/dev/null
  SERVICE_COUNT=$((SERVICE_COUNT + 1))
done <"$WORKLOADS"

WINDOWS_READY=0
while IFS=$'\t' read -r HOST INSTANCE; do
  for attempt in $(seq 1 120); do
    READY=$(gcloud compute ssh "$INSTANCE" \
      --project "$PROJECT_ID" \
      --zone "$ZONE" \
      --tunnel-through-iap \
      --quiet \
      --command "sudo cat '/var/lib/keplerops-nested/guest-attributes/$HOST/ready'" \
      </dev/null 2>/dev/null || true)
    if [[ "$READY" == ready ]]; then
      WINDOWS_READY=$((WINDOWS_READY + 1))
      break
    fi
    [[ $attempt -lt 120 ]] || exit 1
    sleep 10
  done
done <"$WINDOWS_HOSTS"

python3 - "$INFRA_REPORT" "$ROOT/health-report.json" "$SERVICE_COUNT" "$WINDOWS_READY" <<'PY'
import json, os, sys, tempfile
source, destination, service_count, windows_ready = sys.argv[1:]
report = json.load(open(source, encoding="utf-8"))
report["service_count"] = int(service_count)
report["windows_hosts_ready"] = int(windows_ready)
report["shared_model_ready"] = True
fd, temporary = tempfile.mkstemp(prefix=".health-", dir=os.path.dirname(destination))
os.fchmod(fd, 0o600)
with os.fdopen(fd, "w", encoding="utf-8") as handle:
    json.dump(report, handle, sort_keys=True)
    handle.write("\n")
os.replace(temporary, destination)
print(json.dumps(report, sort_keys=True))
PY
