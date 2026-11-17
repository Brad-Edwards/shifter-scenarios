#!/usr/bin/env bash
set -euo pipefail
umask 077

# Terraform-free native ARWC deploy to the mutable golden. The native IT stack
# layers on top of the OT-compat base (the golden must be OT-compat-based: it
# needs /opt/arwc-ot-compat, the arwc-ot-compat-* OT containers, and the
# arwc-ot-compat_supervisory network). The IT layer lives at
# /opt/arwc-ot-compat/it/cinder-typhoon, matching the dev VM. Never touches
# cinder-arwc-dev or cinder-fieldlink-dev.

ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
PACK_ROOT=$(CDPATH='' cd -- "$ROOT/../.." && pwd)
PROJECT_ID=${1-}

[[ $PROJECT_ID =~ ^[a-z][a-z0-9-]{4,28}[a-z0-9]$ ]] || {
  echo "usage: deploy-golden.sh GCP_PROJECT_ID" >&2
  exit 2
}

GOLDEN_INSTANCE=cinder-arwc-golden
ZONE=us-central1-a

status=$(gcloud compute instances describe "$GOLDEN_INSTANCE" \
  --project="$PROJECT_ID" --zone="$ZONE" --format='value(status)')
[[ $status == RUNNING ]] || {
  echo "$GOLDEN_INSTANCE must be RUNNING (got: $status)" >&2
  exit 1
}

ARCHIVE=$(mktemp /tmp/cinder-arwc-golden-release.XXXXXX.tar.gz)
trap 'rm -f -- "$ARCHIVE"' EXIT

tar -C "$PACK_ROOT" -czf "$ARCHIVE" \
  --exclude='build/arwc/.operator' \
  --exclude='build/arwc/gcp/.terraform' \
  --exclude='build/gcp-images/.operator' \
  --exclude='*/__pycache__' \
  build/arwc \
  build/gcp-images \
  build/participant-host \
  assets/narrative/generated/packages/arwc-documents.json \
  build/card-coverage \
  build/fourth-wall \
  build/hint-delivery \
  build/input-provenance \
  build/participant-runner \
  build/participant-surface \
  build/release \
  challenges \
  ctfd/import_catalog.py \
  ctfd/prize_policy.py \
  docs/design/challenge-dependencies.json \
  docs/design/challenges \
  docs/design/portfolio.csv \
  sdl/modules/operations

remote_archive=/tmp/cinder-arwc-golden-release.tar.gz

echo "Uploading source archive to $GOLDEN_INSTANCE..."
gcloud compute scp "$ARCHIVE" "$GOLDEN_INSTANCE:$remote_archive" \
  --project="$PROJECT_ID" --zone="$ZONE" --tunnel-through-iap

echo "Provisioning $GOLDEN_INSTANCE (detached bring-up)..."
gcloud compute ssh "$GOLDEN_INSTANCE" \
  --project="$PROJECT_ID" --zone="$ZONE" --tunnel-through-iap \
  --command="sudo bash -s" << 'REMOTE'
set -euo pipefail

# Hard guard: only run on the golden VM, never a dev VM.
[[ $EUID == 0 && $(hostname) == cinder-arwc-golden ]] || {
  echo 'This script must run as root on cinder-arwc-golden.' >&2
  exit 1
}
project=$(curl --fail --silent --show-error --header 'Metadata-Flavor: Google' \
  http://metadata.google.internal/computeMetadata/v1/project/project-id)
[[ $project == prod-mgau4w ]] || {
  echo "Unexpected project: $project" >&2
  exit 1
}

# The native IT stack requires the OT-compat base.
[[ -d /opt/arwc-ot-compat ]] || {
  echo 'ERROR: /opt/arwc-ot-compat missing. cinder-arwc-golden is not OT-compat-based;' >&2
  echo 'the native ARWC IT stack cannot deploy without the OT base (historian/PLC/supervisory network).' >&2
  exit 1
}

remote_archive=/tmp/cinder-arwc-golden-release.tar.gz
it_root=/opt/arwc-ot-compat/it/cinder-typhoon

# Replace the IT layer only (leave the OT base intact). Never touches dev VMs.
mkdir -p "$it_root"
find "$it_root" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
tar -xzf "$remote_archive" -C "$it_root"
rm -f -- "$remote_archive"

cd "$it_root/build/arwc/native"

# Run the full native bring-up (down -> up -> all seed phases -> seed-applications)
# DETACHED: a long single SSH session hits broken-pipe. Poll /tmp/arwc-bringup.log
# for BRINGUP_COMPLETE.
nohup bash -c 'bash manage.sh reset cinder-arwc-native && echo BRINGUP_COMPLETE' \
  > /tmp/arwc-bringup.log 2>&1 < /dev/null &
disown
echo "LAUNCHED arwc bring-up pid=$! (poll /tmp/arwc-bringup.log for BRINGUP_COMPLETE)"
REMOTE

echo "Launched. Poll the golden: sudo tail -f /tmp/arwc-bringup.log  (expect BRINGUP_COMPLETE)."
