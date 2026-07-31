#!/usr/bin/env bash
set -euo pipefail
umask 077
BUILD_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
RANGE_INSTANCE= PARTICIPANT=
while (($#)); do
  case "$1" in
    --range-instance) RANGE_INSTANCE=${2-}; shift 2 ;;
    --participant) PARTICIPANT=${2-}; shift 2 ;;
    *) shift ;;
  esac
done
[[ $RANGE_INSTANCE =~ ^[a-z0-9]([a-z0-9-]{0,30}[a-z0-9])?$ ]] || exit 2
[[ $PARTICIPANT =~ ^[a-z0-9]([a-z0-9-]{0,30}[a-z0-9])?$ ]] || exit 2
if [[ -z ${GOOGLE_OAUTH_ACCESS_TOKEN:-} ]]; then
  export GOOGLE_OAUTH_ACCESS_TOKEN
  GOOGLE_OAUTH_ACCESS_TOKEN=$(gcloud auth print-access-token)
fi
if [[ -z ${CLOUDSDK_AUTH_ACCESS_TOKEN:-} ]]; then
  export CLOUDSDK_AUTH_ACCESS_TOKEN=$GOOGLE_OAUTH_ACCESS_TOKEN
fi
ROOT="$BUILD_ROOT/.operator/$RANGE_INSTANCE-$PARTICIPANT"
TFSTATE="$ROOT/terraform.tfstate"
TFVARS="$ROOT/range.auto.tfvars.json"
SDL_REALIZATION="$ROOT/sdl-realization.json"
[[ -f $SDL_REALIZATION && ! -L $SDL_REALIZATION ]] || exit 2
PROJECT_ID=$(terraform -chdir="$BUILD_ROOT/gcp" output -state="$TFSTATE" -raw project_id)
ZONE=$(terraform -chdir="$BUILD_ROOT/gcp" output -state="$TFSTATE" -raw range_zone)
REGION=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["region"])' "$TFVARS")
TENANT_ID=$(python3 -c 'import hashlib,sys; print(hashlib.sha256((sys.argv[1]+"\0"+sys.argv[2]).encode()).hexdigest()[:12])' "$RANGE_INSTANCE" "$PARTICIPANT")
RANGE_OPS_INSTANCE=$(terraform -chdir="$BUILD_ROOT/gcp" output -state="$TFSTATE" -json asset_inventory | \
  python3 -c 'import json,sys; print(json.load(sys.stdin)["range-control-carrier-01"]["name"])')
list_tenant_jobs() {
  gcloud run jobs list --project "$PROJECT_ID" --region "$REGION" \
    --filter="metadata.labels.keplerops-tenant=$TENANT_ID AND metadata.labels.keplerops-range=$RANGE_INSTANCE AND metadata.labels.keplerops-participant=$PARTICIPANT" \
    --format='value(metadata.name)'
}
if ! gcloud compute ssh "$RANGE_OPS_INSTANCE" --project "$PROJECT_ID" --zone "$ZONE" \
  --tunnel-through-iap --quiet \
  --command 'sudo bash /var/lib/keplerops-carrier/bin/keplerops-workload quiesce range-ops-controller' \
  </dev/null; then
  JOBS=$(list_tenant_jobs) || exit 1
  while read -r JOB; do
    [[ -z $JOB ]] && continue
    [[ $JOB =~ ^kep-$TENANT_ID-[0-9a-f]{16}$ ]] || exit 1
    gcloud run jobs delete "$JOB" --project "$PROJECT_ID" --region "$REGION" --quiet
  done <<<"$JOBS"
fi
REMAINING_JOBS=$(list_tenant_jobs) || exit 1
[[ -z $REMAINING_JOBS ]] || exit 1
terraform -chdir="$BUILD_ROOT/gcp" destroy -input=false -auto-approve -state="$TFSTATE" -var-file="$TFVARS" -var="sdl_realization_file=$SDL_REALIZATION" -var='deploy_runtime=false'
python3 - "$PROJECT_ID" "$RANGE_INSTANCE" "$PARTICIPANT" "$ROOT/teardown-report.json" <<'PY'
import json, os, subprocess, sys, tempfile, time
project, range_id, participant, output = sys.argv[1:]
result = subprocess.run(
    [
        "gcloud", "compute", "instances", "list",
        "--project", project,
        "--filter", f"labels.scenario=keplerops-ai AND labels.range={range_id} AND labels.participant={participant}",
        "--format=value(name)",
    ],
    check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
)
remaining = [line for line in result.stdout.splitlines() if line]
state = "ABSENT" if result.returncode == 0 and not remaining else "PRESENT"
payload = {"operation": "teardown", "status": state, "resource_count": len(remaining), "timestamp": int(time.time())}
fd, temporary = tempfile.mkstemp(prefix=".teardown-", dir=os.path.dirname(output))
os.fchmod(fd, 0o600)
with os.fdopen(fd, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, sort_keys=True); handle.write("\n")
os.replace(temporary, output)
if state != "ABSENT":
    raise SystemExit("teardown verification failed")
PY
