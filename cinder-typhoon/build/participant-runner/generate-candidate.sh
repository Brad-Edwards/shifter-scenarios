#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: $0 --immutable --candidate-id ID" >&2
  exit 2
}

immutable=false
candidate_id=
while [[ $# -gt 0 ]]; do
  case "$1" in
    --immutable) immutable=true; shift ;;
    --candidate-id) [[ $# -ge 2 ]] || usage; candidate_id=$2; shift 2 ;;
    *) usage ;;
  esac
done

$immutable || { echo "error: only immutable candidate generation is supported" >&2; exit 2; }
[[ -n $candidate_id ]] || usage

root=$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
exec python3 "$root/release/manifest.py" generate \
  --candidate-id "$candidate_id" \
  --project "${CINDER_GCP_PROJECT:-prod-mgau4w}" \
  --zone "${CINDER_GCP_ZONE:-us-central1-a}"
