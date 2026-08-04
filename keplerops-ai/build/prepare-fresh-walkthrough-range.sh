#!/usr/bin/env bash
set -euo pipefail
umask 077

BUILD_ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)

usage() {
  cat >&2 <<'EOF'
usage: prepare-fresh-walkthrough-range.sh --range-instance ID --participant ID

Runs the canonical retained-range reset, verifies health, and prints the
participant endpoint plus the new reset generation for a fresh walkthrough.
EOF
  exit 2
}

RANGE_INSTANCE=
PARTICIPANT=
while (($#)); do
  case "$1" in
    --range-instance) RANGE_INSTANCE=${2-}; shift 2 ;;
    --participant) PARTICIPANT=${2-}; shift 2 ;;
    *) usage ;;
  esac
done

[[ $RANGE_INSTANCE =~ ^[a-z0-9]([a-z0-9-]{0,30}[a-z0-9])?$ ]] || usage
[[ $PARTICIPANT =~ ^[a-z0-9]([a-z0-9-]{0,30}[a-z0-9])?$ ]] || usage

ROOT="$BUILD_ROOT/.operator/$RANGE_INSTANCE-$PARTICIPANT"
STATE="$ROOT/state.json"
TFSTATE="$ROOT/terraform.tfstate"
[[ -f "$STATE" && ! -L "$STATE" && -f "$TFSTATE" && ! -L "$TFSTATE" ]] || {
  echo "error: retained range operator state is unavailable" >&2
  exit 2
}

"$BUILD_ROOT/reset.sh" \
  --range-instance "$RANGE_INSTANCE" \
  --participant "$PARTICIPANT"

"$BUILD_ROOT/health-check.sh" \
  --range-instance "$RANGE_INSTANCE" \
  --participant "$PARTICIPANT" >/dev/null

GENERATION=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["reset_generation"])' "$STATE")
ENDPOINT=$(terraform -chdir="$BUILD_ROOT/gcp" output -state="$TFSTATE" -raw participant_endpoint)

printf 'fresh-walkthrough-ready range_instance=%s participant=%s reset_generation=%s participant_endpoint=%s\n' \
  "$RANGE_INSTANCE" "$PARTICIPANT" "$GENERATION" "$ENDPOINT"
