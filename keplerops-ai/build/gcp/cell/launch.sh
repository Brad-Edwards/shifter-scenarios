#!/usr/bin/env bash
set -euo pipefail
umask 077

CELL_ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
GCP_ROOT=$(CDPATH='' cd -- "$CELL_ROOT/.." && pwd)

usage() {
  echo "usage: launch.sh --var-file PATH --state PATH" >&2
  exit 2
}

VAR_FILE=
STATE=
while (($#)); do
  case "$1" in
    --var-file) VAR_FILE=${2-}; shift 2 ;;
    --state) STATE=${2-}; shift 2 ;;
    *) usage ;;
  esac
done

[[ -f $VAR_FILE && ! -L $VAR_FILE ]] || usage
[[ -n $STATE ]] || usage
VAR_FILE=$(realpath -- "$VAR_FILE")
STATE_DIR=$(dirname -- "$STATE")
mkdir -p "$STATE_DIR"
chmod 0700 "$STATE_DIR"
STATE_DIR=$(realpath -- "$STATE_DIR")
STATE="$STATE_DIR/$(basename -- "$STATE")"
[[ ! -e $STATE || ( -f $STATE && ! -L $STATE ) ]] || usage

model_image_from_lock() {
  python3 - "$1" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as handle:
    row = json.load(handle)["images"]["vllm-open-model-hosting"]
print(f"{row['uri']}@{row['digest']}")
PY
}

terraform -chdir="$CELL_ROOT" init -input=false
FOUNDATION_MODEL_ARGS=()
if [[ -s $STATE ]]; then
  EXISTING_CELL_ID=$(terraform -chdir="$CELL_ROOT" output -state="$STATE" -raw cell_id)
  [[ $EXISTING_CELL_ID =~ ^[a-z0-9]([a-z0-9-]{0,30}[a-z0-9])?$ ]] || exit 2
  EXISTING_IMAGE_LOCK="$CELL_ROOT/.operator/$EXISTING_CELL_ID/image-lock.json"
  if terraform -chdir="$CELL_ROOT" state list -state="$STATE" |
    grep -q '^google_cloud_run_v2_service\.shared_model'; then
    [[ -f $EXISTING_IMAGE_LOCK && ! -L $EXISTING_IMAGE_LOCK ]] || {
      echo "existing shared model requires its immutable image lock" >&2
      exit 2
    }
  fi
  if [[ -f $EXISTING_IMAGE_LOCK && ! -L $EXISTING_IMAGE_LOCK ]]; then
    EXISTING_MODEL_IMAGE=$(model_image_from_lock "$EXISTING_IMAGE_LOCK")
    [[ $EXISTING_MODEL_IMAGE =~ @sha256:[0-9a-f]{64}$ ]] || exit 2
    FOUNDATION_MODEL_ARGS=(-var="shared_model_image=$EXISTING_MODEL_IMAGE")
  fi
fi
set +e
terraform -chdir="$CELL_ROOT" plan -input=false -detailed-exitcode \
  -state="$STATE" -var-file="$VAR_FILE" "${FOUNDATION_MODEL_ARGS[@]}" >/dev/null
FOUNDATION_PLAN_STATUS=$?
set -e
case "$FOUNDATION_PLAN_STATUS" in
  0) ;;
  2)
    terraform -chdir="$CELL_ROOT" apply -input=false -auto-approve \
      -state="$STATE" -var-file="$VAR_FILE" "${FOUNDATION_MODEL_ARGS[@]}"
    ;;
  *) exit "$FOUNDATION_PLAN_STATUS" ;;
esac

CELL_ID=$(terraform -chdir="$CELL_ROOT" output -state="$STATE" -raw cell_id)
PROJECT_ID=$(terraform -chdir="$CELL_ROOT" output -state="$STATE" -raw project_id)
REGION=$(terraform -chdir="$CELL_ROOT" output -state="$STATE" -raw region)
REPOSITORY=$(terraform -chdir="$CELL_ROOT" output -state="$STATE" -raw runtime_repository)
[[ $CELL_ID =~ ^[a-z0-9]([a-z0-9-]{0,30}[a-z0-9])?$ ]] || exit 2

OPERATOR_ROOT="$CELL_ROOT/.operator/$CELL_ID"
REALIZATION="$OPERATOR_ROOT/sdl-realization.json"
IMAGE_LOCK="$OPERATOR_ROOT/image-lock.json"
mkdir -p "$OPERATOR_ROOT"
chmod 0700 "$OPERATOR_ROOT"

uv run --no-project --with 'raes==2.0.0' --with 'pyyaml>=6,<7' \
  python "$GCP_ROOT/render_sdl_realization.py" --output "$REALIZATION"
uv run --no-project --with 'raes==2.0.0' --with 'pyyaml>=6,<7' \
  python "$GCP_ROOT/publish_images.py" \
  --project "$PROJECT_ID" --region "$REGION" \
  --repository "$REPOSITORY" --lock "$IMAGE_LOCK"
uv run --no-project --with 'raes==2.0.0' --with 'pyyaml>=6,<7' \
  python "$GCP_ROOT/validate_build.py" --image-lock "$IMAGE_LOCK"

MODEL_IMAGE=$(model_image_from_lock "$IMAGE_LOCK")
[[ $MODEL_IMAGE =~ @sha256:[0-9a-f]{64}$ ]] || exit 2

terraform -chdir="$CELL_ROOT" apply -input=false -auto-approve \
  -state="$STATE" -var-file="$VAR_FILE" -var="shared_model_image=$MODEL_IMAGE"

terraform -chdir="$CELL_ROOT" output -state="$STATE" -json
printf 'image_lock=%s\n' "$IMAGE_LOCK"
