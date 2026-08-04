#!/usr/bin/env bash
set -euo pipefail
umask 077

BUILD_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PACK_ROOT=$(CDPATH= cd -- "$BUILD_ROOT/.." && pwd)
GCP_ROOT="$BUILD_ROOT/gcp"

usage() {
  cat >&2 <<'EOF'
usage: launch.sh --project-id ID --range-instance ID --participant ID \
  --participant-source-cidr CIDR --range-subnet-self-link URL \
  --range-subnet-cidr CIDR --runtime-repository-id ID \
  --shared-model-service-name NAME --shared-model-service-url URL \
  --image-lock PATH --windows-image IMAGE --nested-host-image IMAGE \
  [--range-host-ip-offset N] \
  [--runtime-repository-location REGION] \
  [--region REGION] [--zone ZONE] \
  [--research-profile off|full-content]
EOF
  exit 2
}

PROJECT_ID= RANGE_INSTANCE= PARTICIPANT=
PARTICIPANT_SOURCE_CIDR= REGION=europe-west4 ZONE=europe-west4-a
RANGE_SUBNET_SELF_LINK= RANGE_SUBNET_CIDR= RUNTIME_REPOSITORY_ID=
RUNTIME_REPOSITORY_LOCATION=europe-west4 WINDOWS_IMAGE= NESTED_HOST_IMAGE=
SHARED_MODEL_SERVICE_NAME= SHARED_MODEL_SERVICE_URL=
SOURCE_IMAGE_LOCK=
RESEARCH_PROFILE=off
RANGE_HOST_IP_OFFSET=10
while (($#)); do
  case "$1" in
    --range-instance) RANGE_INSTANCE=${2-}; shift 2 ;;
    --participant) PARTICIPANT=${2-}; shift 2 ;;
    --project-id) PROJECT_ID=${2-}; shift 2 ;;
    --participant-source-cidr) PARTICIPANT_SOURCE_CIDR=${2-}; shift 2 ;;
    --range-subnet-self-link) RANGE_SUBNET_SELF_LINK=${2-}; shift 2 ;;
    --range-subnet-cidr) RANGE_SUBNET_CIDR=${2-}; shift 2 ;;
    --range-host-ip-offset) RANGE_HOST_IP_OFFSET=${2-}; shift 2 ;;
    --runtime-repository-id) RUNTIME_REPOSITORY_ID=${2-}; shift 2 ;;
    --runtime-repository-location) RUNTIME_REPOSITORY_LOCATION=${2-}; shift 2 ;;
    --shared-model-service-name) SHARED_MODEL_SERVICE_NAME=${2-}; shift 2 ;;
    --shared-model-service-url) SHARED_MODEL_SERVICE_URL=${2-}; shift 2 ;;
    --image-lock) SOURCE_IMAGE_LOCK=${2-}; shift 2 ;;
    --windows-image) WINDOWS_IMAGE=${2-}; shift 2 ;;
    --nested-host-image) NESTED_HOST_IMAGE=${2-}; shift 2 ;;
    --region) REGION=${2-}; shift 2 ;;
    --zone) ZONE=${2-}; shift 2 ;;
    --research-profile) RESEARCH_PROFILE=${2-}; shift 2 ;;
    *) usage ;;
  esac
done

[[ $RANGE_INSTANCE =~ ^[a-z0-9]([a-z0-9-]{0,30}[a-z0-9])?$ ]] || usage
[[ $PARTICIPANT =~ ^[a-z0-9]([a-z0-9-]{0,30}[a-z0-9])?$ ]] || usage
[[ $PROJECT_ID =~ ^[a-z][a-z0-9-]{4,28}[a-z0-9]$ ]] || usage
[[ -n $PARTICIPANT_SOURCE_CIDR && $PARTICIPANT_SOURCE_CIDR != 0.0.0.0/0 ]] || usage
[[ $RANGE_SUBNET_SELF_LINK =~ ^https://www.googleapis.com/compute/v1/projects/.+/regions/.+/subnetworks/.+$ ]] || usage
[[ $RUNTIME_REPOSITORY_ID =~ ^[a-z][a-z0-9-]{2,62}$ ]] || usage
[[ $RUNTIME_REPOSITORY_LOCATION =~ ^[a-z]+-[a-z]+[0-9]+$ ]] || usage
[[ $SHARED_MODEL_SERVICE_NAME =~ ^keplerops-model-[a-z0-9][a-z0-9-]{0,48}$ ]] || usage
[[ $SHARED_MODEL_SERVICE_URL =~ ^https://keplerops-model-[a-z0-9-]+-[a-z0-9]+\.[a-z0-9-]+\.run\.app$ ]] || usage
[[ -f $SOURCE_IMAGE_LOCK && ! -L $SOURCE_IMAGE_LOCK ]] || usage
[[ $WINDOWS_IMAGE =~ ^projects/[^/]+/global/images/[^/]+$ ]] || usage
[[ $NESTED_HOST_IMAGE =~ ^projects/[^/]+/global/images/[^/]+$ ]] || usage
[[ $RESEARCH_PROFILE =~ ^(off|full-content)$ ]] || usage
[[ $RANGE_HOST_IP_OFFSET =~ ^[0-9]+$ ]] || usage

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
if [[ -z ${GOOGLE_OAUTH_ACCESS_TOKEN:-} || -z ${CLOUDSDK_AUTH_ACCESS_TOKEN:-} ]]; then
  refresh_access_token
fi
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
python3 - "$PARTICIPANT_SOURCE_CIDR" "$RANGE_SUBNET_CIDR" "$RANGE_HOST_IP_OFFSET" <<'PY' || usage
import ipaddress, sys
participant = ipaddress.ip_network(sys.argv[1], strict=False)
subnet = ipaddress.ip_network(sys.argv[2], strict=True)
offset = int(sys.argv[3])
if participant.prefixlen == 0 or subnet.version != 4 or subnet.prefixlen > 24:
    raise SystemExit(2)
if offset < 10 or offset >= subnet.num_addresses - 1:
    raise SystemExit(2)
PY

OPERATOR_ROOT="$BUILD_ROOT/.operator/$RANGE_INSTANCE-$PARTICIPANT"
STATE="$OPERATOR_ROOT/state.json"
TFSTATE="$OPERATOR_ROOT/terraform.tfstate"
TFVARS="$OPERATOR_ROOT/range.auto.tfvars.json"
IMAGE_LOCK="$OPERATOR_ROOT/image-lock.json"
SDL_REALIZATION="$OPERATOR_ROOT/sdl-realization.json"
mkdir -p -m 0700 "$OPERATOR_ROOT"
install -m 0600 "$SOURCE_IMAGE_LOCK" "$IMAGE_LOCK"

uv run --no-project --with 'raes==2.0.0' --with 'pyyaml>=6,<7' \
  python "$GCP_ROOT/render_sdl_realization.py" --output "$SDL_REALIZATION"
uv run --no-project --with 'raes==2.0.0' --with 'pyyaml>=6,<7' \
  python "$GCP_ROOT/validate_build.py"
if [[ ! -e $STATE ]]; then
  python3 "$GCP_ROOT/lifecycle.py" initialize --state "$STATE" \
    --range-instance "$RANGE_INSTANCE" --participant "$PARTICIPANT"
fi

python3 - \
  "$TFVARS" "$PROJECT_ID" "$RANGE_INSTANCE" "$PARTICIPANT" \
  "$PARTICIPANT_SOURCE_CIDR" "$REGION" "$ZONE" "$RESEARCH_PROFILE" \
  "$RANGE_SUBNET_SELF_LINK" "$RANGE_SUBNET_CIDR" "$RUNTIME_REPOSITORY_ID" \
  "$RUNTIME_REPOSITORY_LOCATION" "$WINDOWS_IMAGE" \
  "$NESTED_HOST_IMAGE" "$RANGE_HOST_IP_OFFSET" \
  "$SHARED_MODEL_SERVICE_NAME" "$SHARED_MODEL_SERVICE_URL" <<'PY'
import json, os, stat, sys, tempfile
(
    path, project, range_id, participant, source_cidr, region, zone,
    research_profile, subnet_link, subnet_cidr, repository_id,
    repository_location, windows_image, nested_host_image, range_host_ip_offset,
    model_service_name, model_service_url,
) = sys.argv[1:]
base_payload = {
  "project_id": project,
  "range_instance": range_id,
  "participant": participant,
  "participant_source_cidrs": [source_cidr],
  "region": region,
  "zone": zone,
  "range_subnet_self_link": subnet_link,
  "range_subnet_cidr": subnet_cidr,
  "range_host_ip_offset": int(range_host_ip_offset),
  "runtime_repository_id": repository_id,
  "runtime_repository_location": repository_location,
  "windows_image": windows_image,
  "nested_host_image": nested_host_image,
  "shared_model_service_name": model_service_name,
  "shared_model_service_url": model_service_url,
}
payload = dict(base_payload)
if research_profile == "full-content":
    payload["telemetry_capture_signals"] = {
        "prompt": True,
        "completion": True,
        "tool_call": True,
        "tool_result": True,
        "terminal_command": True,
        "terminal_input": True,
        "terminal_output": True,
        "process_lifecycle": True,
        "browser_interaction": True,
        "notebook_content": True,
        "file_content": True,
        "workflow_state": True,
        "artifact_content": True,
        "http_body": True,
    }
elif research_profile != "off":
    raise SystemExit("invalid research profile")
encoded = json.dumps(payload, sort_keys=True) + "\n"

def write_payload() -> None:
    directory = os.path.dirname(path)
    fd, temporary = tempfile.mkstemp(prefix=".range-auto-", dir=directory)
    os.fchmod(fd, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise

try:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
except FileExistsError:
    metadata = os.stat(path, follow_symlinks=False)
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o077:
        raise SystemExit("existing operator config is not owner-only and regular")
    with open(path, encoding="utf-8") as handle:
        current = json.load(handle)
    mutable = {"telemetry_capture_signals"}
    if (
        not isinstance(current, dict)
        or {key: current.get(key) for key in base_payload} != base_payload
        or set(current) - set(base_payload) - mutable
    ):
        raise SystemExit("existing operator config does not match")
    if current != payload:
        write_payload()
else:
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(encoded)
PY

terraform -chdir="$GCP_ROOT" init -input=false
terraform -chdir="$GCP_ROOT" apply -input=false -auto-approve \
  -state="$TFSTATE" -var-file="$TFVARS" -var='deploy_runtime=false' \
  -var="sdl_realization_file=$SDL_REALIZATION"
PARTICIPANT_IP=$(terraform -chdir="$GCP_ROOT" output -state="$TFSTATE" -raw participant_address)
SUFFIX=$(printf '%s' "$RANGE_INSTANCE:$PARTICIPANT" | sha256sum | cut -c1-6)
python3 "$GCP_ROOT/seed_secrets.py" --project "$PROJECT_ID" --suffix "$SUFFIX" \
  --participant-ip "$PARTICIPANT_IP" --realization "$SDL_REALIZATION" \
  --output "$OPERATOR_ROOT/secrets"
uv run --no-project --with 'raes==2.0.0' --with 'pyyaml>=6,<7' \
  python "$GCP_ROOT/validate_build.py" --image-lock "$IMAGE_LOCK"
terraform -chdir="$GCP_ROOT" apply -input=false -auto-approve \
  -state="$TFSTATE" -var-file="$TFVARS" -var='deploy_runtime=true' \
  -var="image_lock_file=$IMAGE_LOCK" -var="sdl_realization_file=$SDL_REALIZATION"

OUTER_HOST=$(
  terraform -chdir="$GCP_ROOT" output -state="$TFSTATE" -json asset_inventory |
    jq -er '."range-linux-carrier-01".name'
)

LAUNCH_SSH_ATTEMPTS=${KEPLEROPS_LAUNCH_SSH_ATTEMPTS:-120}
ssh_command() {
  refresh_access_token
  gcloud compute ssh "$OUTER_HOST" \
    "${GCLOUD_ACCOUNT_ARGS[@]}" \
    --project "$PROJECT_ID" \
    --zone "$ZONE" \
    --tunnel-through-iap \
    --quiet \
    --command "$1" </dev/null
}
for attempt in $(seq 1 "$LAUNCH_SSH_ATTEMPTS"); do
  if ssh_command true >/dev/null 2>&1; then
    break
  fi
  [[ $attempt -lt $LAUNCH_SSH_ATTEMPTS ]] || {
    echo "error: nested range host did not become reachable" >&2
    exit 1
  }
  sleep 5
done

LAUNCH_CARRIER_ATTEMPTS=${KEPLEROPS_LAUNCH_CARRIER_ATTEMPTS:-720}
wait_for_carrier_ready() {
  for _ in $(seq 1 "$LAUNCH_CARRIER_ATTEMPTS"); do
    if ssh_command "sudo bash -lc 'test \"\$(cat /proc/sys/kernel/random/boot_id)\" = \"\$(cat /var/lib/keplerops-carrier/ready 2>/dev/null)\"'" >/dev/null 2>&1; then
      return 0
    fi
    sleep 10
  done
  return 1
}

wait_for_carrier_ready
refresh_access_token
"$BUILD_ROOT/health-check.sh" --range-instance "$RANGE_INSTANCE" --participant "$PARTICIPANT"
