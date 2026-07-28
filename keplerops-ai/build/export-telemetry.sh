#!/usr/bin/env bash
set -euo pipefail
umask 077

BUILD_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
RANGE_INSTANCE= PARTICIPANT= SESSION_ID= OUTPUT= CONTENT_OUTPUT=
while (($#)); do
  case "$1" in
    --range-instance) RANGE_INSTANCE=${2-}; shift 2 ;;
    --participant) PARTICIPANT=${2-}; shift 2 ;;
    --session-id) SESSION_ID=${2-}; shift 2 ;;
    --output) OUTPUT=${2-}; shift 2 ;;
    --content-output) CONTENT_OUTPUT=${2-}; shift 2 ;;
    *) exit 2 ;;
  esac
done
[[ $RANGE_INSTANCE =~ ^[a-z0-9]([a-z0-9-]{0,30}[a-z0-9])?$ ]] || exit 2
[[ $PARTICIPANT =~ ^[a-z0-9]([a-z0-9-]{0,30}[a-z0-9])?$ ]] || exit 2
[[ -z $SESSION_ID || $SESSION_ID =~ ^ses-[0-9a-f]{24}$ ]] || exit 2
[[ -n $OUTPUT ]] || exit 2

ROOT="$BUILD_ROOT/.operator/$RANGE_INSTANCE-$PARTICIPANT"
STATE="$ROOT/terraform.tfstate"
IMAGE_LOCK="$ROOT/image-lock.json"
[[ -f $STATE ]] || { echo 'error: range state not found' >&2; exit 2; }
[[ -f $IMAGE_LOCK && ! -L $IMAGE_LOCK ]] || { echo 'error: image lock not found' >&2; exit 2; }
FLOW_LOG_LIMIT=${FLOW_LOG_LIMIT:-25000}
FLOW_LOG_LOOKBACK_SECONDS=${FLOW_LOG_LOOKBACK_SECONDS:-1200}
FLOW_LOG_TIMEOUT_SECONDS=${FLOW_LOG_TIMEOUT_SECONDS:-180}
FLOW_LOG_BATCH_SECONDS=${FLOW_LOG_BATCH_SECONDS:-600}
[[ $FLOW_LOG_LIMIT =~ ^[1-9][0-9]{0,5}$ ]] || exit 2
[[ $FLOW_LOG_LOOKBACK_SECONDS =~ ^[1-9][0-9]{1,5}$ ]] || exit 2
[[ $FLOW_LOG_TIMEOUT_SECONDS =~ ^[1-9][0-9]{0,4}$ ]] || exit 2
[[ $FLOW_LOG_BATCH_SECONDS =~ ^[1-9][0-9]{0,5}$ ]] || exit 2
PROJECT_ID=$(terraform -chdir="$BUILD_ROOT/gcp" output -state="$STATE" -raw project_id)
ZONE=$(terraform -chdir="$BUILD_ROOT/gcp" output -state="$STATE" -raw range_zone)
INSTANCE=$(terraform -chdir="$BUILD_ROOT/gcp" output -state="$STATE" -json asset_inventory |
  python3 -c '
import json,sys
realization=json.load(open(sys.argv[1], encoding="utf-8"))
hosts=json.load(sys.stdin)
host=realization["workloads"]["telemetry-proof-01"]["host"]
print(hosts[host]["name"])
' "$ROOT/sdl-realization.json")
PROOF_ROOT=/var/lib/keplerops-carrier/workloads/telemetry-proof-01
PROOF_CONTAINER=keplerops-telemetry-proof-01-runtime

# The operator lock is authoritative after an in-place image revision. Refresh
# the proof node's bound copy before deriving the environment manifest so a
# component-only rollout never reports the previous digest set.
gcloud compute ssh "$INSTANCE" --project "$PROJECT_ID" --zone "$ZONE" \
  --tunnel-through-iap --quiet --command \
  "sudo sh -c 'set -eu; destination=$PROOF_ROOT/config/environment-images.json; input=$PROOF_ROOT/input/image-lock.json; temporary=\$(mktemp $PROOF_ROOT/config/.environment-images.XXXXXX); trap \"rm -f -- \$temporary\" EXIT; cat >\"\$temporary\"; python3 -m json.tool \"\$temporary\" >/dev/null; cat \"\$temporary\" >\"\$destination\"; cat \"\$temporary\" >\"\$input\"; chmod 0600 \"\$destination\" \"\$input\"; expected=\$(sha256sum \"\$destination\" | cut -d\" \" -f1); actual=\$(docker exec $PROOF_CONTAINER sha256sum /etc/keplerops/environment-images.json 2>/dev/null | cut -d\" \" -f1 || true); if [ \"\$actual\" != \"\$expected\" ]; then docker restart $PROOF_CONTAINER >/dev/null; for attempt in \$(seq 1 30); do if bash /var/lib/keplerops-carrier/bin/keplerops-workload health telemetry-proof-01 >/dev/null 2>&1; then exit 0; fi; sleep 2; done; exit 1; fi'" \
  <"$IMAGE_LOCK" >/dev/null

if [[ -z $SESSION_ID ]]; then
  SESSION_ID=$(gcloud compute ssh "$INSTANCE" --project "$PROJECT_ID" --zone "$ZONE" \
    --tunnel-through-iap --quiet --command \
    'sudo bash /var/lib/keplerops-carrier/bin/keplerops-workload exec telemetry-proof-01 python /opt/keplerops/research_cli.py list' </dev/null |
    python3 -c 'import json,sys; rows=json.load(sys.stdin)["sessions"]; print(rows[0] if rows else "")')
  [[ $SESSION_ID =~ ^ses-[0-9a-f]{24}$ ]] || { echo 'error: no telemetry session found' >&2; exit 2; }
fi

REMOTE="/var/lib/keplerops-research/exports/$SESSION_ID"
gcloud compute ssh "$INSTANCE" --project "$PROJECT_ID" --zone "$ZONE" \
  --tunnel-through-iap --quiet --command \
  "sudo docker exec --user 0:0 $PROOF_CONTAINER rm -rf -- '$REMOTE' && sudo bash /var/lib/keplerops-carrier/bin/keplerops-workload exec telemetry-proof-01 python /opt/keplerops/research_cli.py export --session-id '$SESSION_ID' --destination '$REMOTE'" \
  </dev/null >/dev/null

mkdir -p "$(dirname -- "$OUTPUT")"
TEMPORARY="$OUTPUT.$$.tmp"
STAGING=$(mktemp -d "${TMPDIR:-/tmp}/keplerops-telemetry.XXXXXXXX")
cleanup_operational() {
  rm -f -- "$TEMPORARY" "$TEMPORARY.augmented"
  rm -rf -- "$STAGING"
}
trap cleanup_operational EXIT
gcloud compute ssh "$INSTANCE" --project "$PROJECT_ID" --zone "$ZONE" \
  --tunnel-through-iap --quiet --command \
  "sudo tar --sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner -C $PROOF_ROOT/state/research/exports -cf - '$SESSION_ID'" \
  </dev/null >"$TEMPORARY"
tar -xf "$TEMPORARY" -C "$STAGING"
EVENTS="$STAGING/$SESSION_ID/events.jsonl"
mapfile -t FLOW_WINDOW < <(
  python3 "$BUILD_ROOT/gcp/flow_telemetry.py" window \
    --events "$EVENTS" \
    --max-lookback-seconds "$FLOW_LOG_LOOKBACK_SECONDS"
)
[[ ${#FLOW_WINDOW[@]} -eq 2 ]] || { echo 'error: invalid telemetry window' >&2; exit 2; }
INVENTORY="$STAGING/asset-inventory.json"
RAW_FLOW_DIR="$STAGING/raw-flow-logs"
mkdir -p "$RAW_FLOW_DIR"
terraform -chdir="$BUILD_ROOT/gcp" output -state="$STATE" -json asset_inventory >"$INVENTORY"
chmod 0600 "$INVENTORY"
mapfile -t FLOW_BATCHES < <(
  python3 "$BUILD_ROOT/gcp/flow_telemetry.py" batches \
    --start "${FLOW_WINDOW[0]}" \
    --end "${FLOW_WINDOW[1]}" \
    --batch-seconds "$FLOW_LOG_BATCH_SECONDS"
)
[[ ${#FLOW_BATCHES[@]} -ge 1 ]] || { echo 'error: invalid telemetry batches' >&2; exit 2; }
FLOW_BATCH_COUNT=0
FLOW_FAILED_BATCH_COUNT=0
RAW_ARGS=()
for FLOW_BATCH in "${FLOW_BATCHES[@]}"; do
  read -r BATCH_START BATCH_END <<<"$FLOW_BATCH"
  [[ -n $BATCH_START && -n $BATCH_END ]] || { echo 'error: invalid telemetry batch' >&2; exit 2; }
  RAW_FLOWS="$RAW_FLOW_DIR/batch-$FLOW_BATCH_COUNT.json"
  FLOW_BATCH_COUNT=$((FLOW_BATCH_COUNT + 1))
  FLOW_FILTER="(logName=\"projects/$PROJECT_ID/logs/compute.googleapis.com%2Fvpc_flows\" OR logName=\"projects/$PROJECT_ID/logs/compute.googleapis.com%2Ffirewall\") AND timestamp>=\"$BATCH_START\" AND timestamp<=\"$BATCH_END\""
  if ! timeout "$FLOW_LOG_TIMEOUT_SECONDS" \
    gcloud logging read "$FLOW_FILTER" \
      --project "$PROJECT_ID" \
      --limit "$FLOW_LOG_LIMIT" \
      --format=json >"$RAW_FLOWS"; then
    FLOW_FAILED_BATCH_COUNT=$((FLOW_FAILED_BATCH_COUNT + 1))
    printf '[]\n' >"$RAW_FLOWS"
  fi
  chmod 0600 "$RAW_FLOWS"
  RAW_ARGS+=(--raw "$RAW_FLOWS")
done
if [[ $FLOW_FAILED_BATCH_COUNT -eq 0 ]]; then
  FLOW_CAPTURE_STATUS=captured
elif [[ $FLOW_FAILED_BATCH_COUNT -lt $FLOW_BATCH_COUNT ]]; then
  FLOW_CAPTURE_STATUS=partial
else
  FLOW_CAPTURE_STATUS=unavailable
fi
python3 "$BUILD_ROOT/gcp/flow_telemetry.py" augment \
  --bundle "$STAGING/$SESSION_ID" \
  "${RAW_ARGS[@]}" \
  --inventory "$INVENTORY" \
  --capture-status "$FLOW_CAPTURE_STATUS" \
  --batch-count "$FLOW_BATCH_COUNT" \
  --failed-batch-count "$FLOW_FAILED_BATCH_COUNT"
tar --sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner \
  -C "$STAGING" -cf "$TEMPORARY.augmented" "$SESSION_ID"
mv -f -- "$TEMPORARY.augmented" "$TEMPORARY"
chmod 0600 "$TEMPORARY"
mv -f -- "$TEMPORARY" "$OUTPUT"
rm -rf -- "$STAGING"
trap - EXIT

if [[ -n $CONTENT_OUTPUT ]]; then
  REMOTE_CONTENT="/var/lib/keplerops-research/content-exports/$SESSION_ID"
  gcloud compute ssh "$INSTANCE" --project "$PROJECT_ID" --zone "$ZONE" \
    --tunnel-through-iap --quiet --command \
    "sudo docker exec --user 0:0 $PROOF_CONTAINER rm -rf -- '$REMOTE_CONTENT' && sudo bash /var/lib/keplerops-carrier/bin/keplerops-workload exec telemetry-proof-01 python /opt/keplerops/research_cli.py export-content --session-id '$SESSION_ID' --destination '$REMOTE_CONTENT'" \
    </dev/null >/dev/null
  mkdir -p "$(dirname -- "$CONTENT_OUTPUT")"
  CONTENT_TEMPORARY="$CONTENT_OUTPUT.$$.tmp"
  trap 'rm -f -- "$CONTENT_TEMPORARY"' EXIT
  gcloud compute ssh "$INSTANCE" --project "$PROJECT_ID" --zone "$ZONE" \
    --tunnel-through-iap --quiet --command \
    "sudo tar --sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner -C $PROOF_ROOT/state/research/content-exports -cf - '$SESSION_ID'" \
    </dev/null >"$CONTENT_TEMPORARY"
  chmod 0600 "$CONTENT_TEMPORARY"
  mv -f -- "$CONTENT_TEMPORARY" "$CONTENT_OUTPUT"
  trap - EXIT
fi
printf '{"status":"exported","session_id":"%s"}\n' "$SESSION_ID"
