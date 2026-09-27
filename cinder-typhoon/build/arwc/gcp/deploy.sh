#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
GCP_ROOT="$ROOT/gcp"
PACK_ROOT=$(CDPATH='' cd -- "$ROOT/../.." && pwd)
PROJECT_ID=${1-}
[[ $PROJECT_ID =~ ^[a-z][a-z0-9-]{4,28}[a-z0-9]$ ]] || {
  echo "usage: deploy.sh GCP_PROJECT_ID" >&2
  exit 2
}

OPERATOR_DIR="$ROOT/.operator"
STATE="$OPERATOR_DIR/terraform.tfstate"
mkdir -p "$OPERATOR_DIR"
chmod 0700 "$OPERATOR_DIR"
export TF_DATA_DIR="$OPERATOR_DIR/.terraform"
ARCHIVE=$(mktemp /tmp/cinder-arwc-release.XXXXXX.tar.gz)
trap 'rm -f -- "$ARCHIVE"' EXIT

terraform -chdir="$GCP_ROOT" init -input=false -reconfigure \
  -backend-config="path=$STATE"
terraform -chdir="$GCP_ROOT" apply -input=false -auto-approve \
  -var="project_id=$PROJECT_ID"

INSTANCE=$(terraform -chdir="$GCP_ROOT" output -raw instance_name)
ZONE=$(terraform -chdir="$GCP_ROOT" output -raw zone)

tar -C "$PACK_ROOT" -czf "$ARCHIVE" \
  --exclude='build/arwc/.operator' \
  --exclude='build/arwc/gcp/.terraform' \
  --exclude='*/__pycache__' \
  build/arwc \
  assets/narrative/generated/packages/arwc-documents.json

ready_attempt=0
until gcloud compute ssh "$INSTANCE" --project "$PROJECT_ID" --zone "$ZONE" \
  --tunnel-through-iap --command 'test -f /var/lib/cinder-arwc-carrier-ready'; do
  ready_attempt=$((ready_attempt + 1))
  if ((ready_attempt >= 120)); then
    echo "carrier startup did not complete within ten minutes" >&2
    exit 1
  fi
  sleep 5
done

gcloud compute scp "$ARCHIVE" "$INSTANCE:/tmp/cinder-arwc-release.tar.gz" \
  --project "$PROJECT_ID" --zone "$ZONE" --tunnel-through-iap

gcloud compute ssh "$INSTANCE" --project "$PROJECT_ID" --zone "$ZONE" \
  --tunnel-through-iap --command \
  'sudo find /opt/cinder-typhoon -mindepth 1 -maxdepth 1 -exec rm -rf -- {} + && sudo tar -xzf /tmp/cinder-arwc-release.tar.gz -C /opt/cinder-typhoon && cd /opt/cinder-typhoon/build/arwc && sudo bash ./generate-operator-material.sh && sudo docker compose -f compose.yaml build && sudo docker compose -f compose.yaml up -d --force-recreate a-connector a-business a-archive && rm -f /tmp/cinder-arwc-release.tar.gz'

terraform -chdir="$GCP_ROOT" output
echo "Participant shell: sudo docker exec -it --user fieldlink --workdir /var/lib/fieldlink-connector cinder-arwc-connector bash"
