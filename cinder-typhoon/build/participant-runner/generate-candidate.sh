#!/usr/bin/env bash
# Generate a candidate manifest for the current golden instances.
# For a release candidate, set IMMUTABLE=true and supply all image digests.
# For the mutable development goldens, call with no arguments.
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
usage: generate-candidate.sh [--immutable] [--candidate-id ID]

Generate cinder-typhoon/build/participant-runner/candidate.json from the
current golden instances in GCP.

Options:
  --immutable       Mark the candidate as an immutable release candidate.
                    Requires all image digests to be captured.
  --candidate-id    Candidate identifier string (default: mutable-dev-YYYYMMDD).

Environment:
  CINDER_GCP_PROJECT   GCP project (default: prod-mgau4w)
  CINDER_GCP_ZONE      GCP zone (default: us-central1-a)
USAGE
  exit 2
}

immutable=false
candidate_id=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --immutable) immutable=true; shift ;;
    --candidate-id) candidate_id="$2"; shift 2 ;;
    *) usage ;;
  esac
done

project=${CINDER_GCP_PROJECT:-prod-mgau4w}
zone=${CINDER_GCP_ZONE:-us-central1-a}

if [[ -z "$candidate_id" ]]; then
  if $immutable; then
    echo "error: --candidate-id required for immutable candidate" >&2; exit 2
  fi
  candidate_id="mutable-dev-$(date +%Y%m%d)"
fi

source_commit=$(git rev-parse HEAD)

# Collect participant image digests from each golden instance.
# For mutable goldens the digest reflects the most recent image; for an
# immutable candidate it must be the pinned digest recorded at promotion time.
get_digest() {
  local instance="$1" image_ref="$2"
  if command -v gcloud &>/dev/null; then
    gcloud compute ssh "$instance" \
      --project="$project" --zone="$zone" \
      --tunnel-through-iap --command \
      "docker inspect --format '{{index .RepoDigests 0}}' '$image_ref' 2>/dev/null || echo ''" \
      2>/dev/null | tail -1 | grep -oP 'sha256:[0-9a-f]{64}' || echo "sha256:0000000000000000000000000000000000000000000000000000000000000000"
  else
    # Offline placeholder — replace before promoting to immutable.
    echo "sha256:0000000000000000000000000000000000000000000000000000000000000000"
  fi
}

training_digest=$(get_digest cinder-training-golden "cinder-training/workstation:hand-build")
keplerops_digest=$(get_digest cinder-keplerops-golden "cinder-keplerops/k-dev:hand-build")
arwc_digest=$(get_digest cinder-arwc-golden "cinder-arwc/a-connector:hand-build")

root=$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
out="$root/candidate.json"

python3 - <<PYEOF
import json, sys
manifest = {
    "schema_version": 1,
    "candidate_id": "$candidate_id",
    "immutable": $immutable,
    "source_commit": "$source_commit",
    "artifact_digests": {
        "cinder-training/workstation:hand-build": "$training_digest",
        "cinder-keplerops/k-dev:hand-build": "$keplerops_digest",
        "cinder-arwc/a-connector:hand-build": "$arwc_digest",
    },
    "deployments": {
        "training": {
            "project": "$project",
            "zone": "$zone",
            "instance": "cinder-training-golden",
            "participant_image_digest": "$training_digest",
        },
        "keplerops": {
            "project": "$project",
            "zone": "$zone",
            "instance": "cinder-keplerops-golden",
            "participant_image_digest": "$keplerops_digest",
        },
        "arwc": {
            "project": "$project",
            "zone": "$zone",
            "instance": "cinder-arwc-golden",
            "participant_image_digest": "$arwc_digest",
        },
    },
}
with open("$out", "w") as f:
    json.dump(manifest, f, indent=2, sort_keys=True)
    f.write("\n")
print(f"Wrote {len(json.dumps(manifest))} bytes to $out")
PYEOF
