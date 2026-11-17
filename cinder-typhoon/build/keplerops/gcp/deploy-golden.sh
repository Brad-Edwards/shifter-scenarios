#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
PACK_ROOT=$(CDPATH='' cd -- "$ROOT/../.." && pwd)
PROJECT_ID=${1-}

[[ $PROJECT_ID =~ ^[a-z][a-z0-9-]{4,28}[a-z0-9]$ ]] || {
  echo "usage: deploy-golden.sh GCP_PROJECT_ID" >&2
  exit 2
}

GOLDEN_INSTANCE=cinder-keplerops-golden
ZONE=us-central1-a

# Verify the target instance exists and is running.
status=$(gcloud compute instances describe "$GOLDEN_INSTANCE" \
  --project="$PROJECT_ID" --zone="$ZONE" --format='value(status)')
[[ $status == RUNNING ]] || {
  echo "$GOLDEN_INSTANCE must be RUNNING (got: $status)" >&2
  exit 1
}

# Archive the full source tree required for the golden build.
ARCHIVE=$(mktemp /tmp/cinder-keplerops-golden-release.XXXXXX.tar.gz)
trap 'rm -f -- "$ARCHIVE"' EXIT

tar -C "$PACK_ROOT" -czf "$ARCHIVE" \
  --exclude='build/keplerops/.operator' \
  --exclude='build/keplerops/gcp/.terraform' \
  --exclude='build/gcp-images/.operator' \
  --exclude='*/__pycache__' \
  build/keplerops \
  build/gcp-images \
  build/participant-host \
  assets/keplerops/opening \
  assets/keplerops/registry \
  assets/keplerops/staff \
  assets/keplerops/native-packages \
  assets/keplerops/native-workplace \
  assets/keplerops/assistant-api \
  assets/keplerops/cloud-api \
  assets/keplerops/support \
  assets/keplerops/identity-spnego \
  assets/keplerops/build-operations \
  assets/keplerops/policy-compiler \
  assets/keplerops/connector-archive \
  assets/keplerops/release-lineage \
  assets/narrative/documents/keplerops/company-history.md \
  assets/narrative/documents/keplerops/working-guide.md \
  assets/narrative/documents/keplerops/customer-relationships.md \
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

remote_archive=/tmp/cinder-keplerops-golden-release.tar.gz

echo "Uploading source archive to $GOLDEN_INSTANCE..."
gcloud compute scp "$ARCHIVE" "$GOLDEN_INSTANCE:$remote_archive" \
  --project="$PROJECT_ID" --zone="$ZONE" --tunnel-through-iap

echo "Provisioning $GOLDEN_INSTANCE..."
gcloud compute ssh "$GOLDEN_INSTANCE" \
  --project="$PROJECT_ID" --zone="$ZONE" --tunnel-through-iap \
  --command="sudo bash -s" << 'REMOTE'
set -euo pipefail

# Hard guard: only run on the golden VM.
[[ $EUID == 0 && $(hostname) == cinder-keplerops-golden ]] || {
  echo 'This script must run as root on cinder-keplerops-golden.' >&2
  exit 1
}

project=$(curl --fail --silent --show-error --header 'Metadata-Flavor: Google' \
  http://metadata.google.internal/computeMetadata/v1/project/project-id)
[[ $project == prod-mgau4w ]] || {
  echo "Unexpected project: $project" >&2
  exit 1
}

remote_archive=/tmp/cinder-keplerops-golden-release.tar.gz
root=/opt/cinder-typhoon/build/keplerops

# Replace scenario content (never touches cinder-fieldlink-dev or cinder-arwc-dev).
find /opt/cinder-typhoon -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
tar -xzf "$remote_archive" -C /opt/cinder-typhoon
rm -f -- "$remote_archive"

cd "$root"

# The golden uses the compose default ARWC_CARRIER_ADDRESS=10.77.59.2 (arwc-golden).
# Never override it to the dev peer address.
unset ARWC_CARRIER_ADDRESS

operator=${KEPLEROPS_OPERATOR_DIR:-"$root/.operator"}

# Tear down any existing containers and volumes for a clean bring-up.
docker compose down --volumes --remove-orphans 2>/dev/null || true

# Remove seed markers so bootstrap scripts run fresh.
rm -f -- \
  "$operator/native-platform/assistant-company-seeded" \
  "$operator/native-platform/assistant-k21-seeded" \
  "$operator/native-platform/assistant-k21-config.json" \
  "$operator/native-platform/assistant-k22-seeded" \
  "$operator/native-platform/assistant-k23-seeded" \
  "$operator/native-ci/k06-ci-seeded" \
  "$operator/native-platform/objects-company-seeded" \
  "$operator/native-platform/objects-company-seeded-v2" \
  "$operator/native-platform/exports/company-history.dump" \
  "$operator/native-platform/exports/company-history.dump.part" \
  "$operator/native-platform/kubernetes/rowan.yaml" \
  "$operator/native-platform/kubernetes/cluster-identity" 2>/dev/null || true
if [[ -d $operator/native-platform/assistant-documents ]]; then
  find "$operator/native-platform/assistant-documents" -mindepth 1 -maxdepth 1 -type f -delete
fi

bash generate-operator-material.sh
bash native-platform/fetch-kubernetes-images.sh

# Build all images from the uploaded source.
docker compose --profile build-only build
docker compose build

# Staged bring-up: foundation layer first.
docker compose up -d --no-deps --wait --wait-timeout 120 \
  router fieldlink-dns fieldlink-edge fieldlink-postgres

python3 native-platform/host-routing.py
bash native-workplace/bootstrap-databases.sh
bash native-platform/bootstrap-data.sh
bash native-platform/bootstrap-kubernetes.sh

# Main application layer.
docker compose up -d --no-deps --wait --wait-timeout 180 \
  runner k-source k-registry k-ci fieldlink-review k-preview k-support k-indexer \
  k-identity fieldlink-keycloak k-cert fieldlink-objects fieldlink-ollama a-connector

# Verify the connector is peered to the golden ARWC carrier (10.77.59.2).
docker inspect --format '{{range .HostConfig.ExtraHosts}}{{println .}}{{end}}' \
  cinder-keplerops-connector | grep -Fxq 'fieldlink.arwc.test:10.77.59.2'

bash native-workplace/bootstrap-staff.sh
bash native-workplace/bootstrap-support.sh

docker compose up -d --wait --wait-timeout 180 fieldlink-assistant

bash native-platform/import-model.sh
bash native-platform/cache-embedder.sh

python3 native-platform/seed-assistant.py --operator-dir "$operator"
python3 native-platform/seed-k21-assistant.py --operator-dir "$operator"
python3 native-platform/seed-k22-assistant.py --operator-dir "$operator"
python3 native-platform/seed-k23-assistant.py --operator-dir "$operator"
python3 native-ci/seed-k06-ci.py --operator-dir "$operator"

bash native-platform/seed-objects.sh

docker compose up --no-deps --force-recreate k-dev-seed
docker compose up -d --no-deps k-dev

docker compose exec -T --user fieldkest-support k-support python3 -c \
  'import json; from pathlib import Path; p=Path("/var/lib/fieldkest-support/audit/extended-state.json"); assert not p.exists() or json.loads(p.read_text()).get("diagnostics") == {}'

echo 'Native FieldLink golden application state initialized.'
REMOTE

echo "Done. Golden is provisioned at $GOLDEN_INSTANCE."
