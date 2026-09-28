#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
GCP_ROOT="$ROOT/gcp"
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

terraform -chdir="$GCP_ROOT" init -input=false -reconfigure \
  -backend-config="path=$STATE"
terraform -chdir="$GCP_ROOT" apply -input=false -auto-approve \
  -var="project_id=$PROJECT_ID"

KEPLER_INSTANCE=cinder-keplerops-golden
ARWC_INSTANCE=cinder-arwc-golden
KEPLER_ZONE=$(gcloud compute instances list --project "$PROJECT_ID" --filter="name=$KEPLER_INSTANCE" --format='value(zone.basename())')
ARWC_ZONE=$(gcloud compute instances list --project "$PROJECT_ID" --filter="name=$ARWC_INSTANCE" --format='value(zone.basename())')
[[ -n $KEPLER_ZONE && -n $ARWC_ZONE ]] || {
  echo "both carrier instances must exist before pairing" >&2
  exit 1
}
TRANSFER_DIR=$(mktemp -d /tmp/cinder-kepler-arwc.XXXXXX)
trap 'rm -rf -- "$TRANSFER_DIR"' EXIT

gcloud compute ssh "$KEPLER_INSTANCE" --project "$PROJECT_ID" --zone "$KEPLER_ZONE" \
  --tunnel-through-iap --command \
  'sudo install -m 0644 /opt/cinder-typhoon/build/keplerops/.operator/tls/ca.crt /tmp/cinder-keplerops-ca.crt'
gcloud compute ssh "$ARWC_INSTANCE" --project "$PROJECT_ID" --zone "$ARWC_ZONE" \
  --tunnel-through-iap --command \
  'sudo install -m 0644 /opt/cinder-typhoon/build/arwc/.operator/tls/ca.crt /tmp/cinder-arwc-ca.crt'

gcloud compute scp "$KEPLER_INSTANCE:/tmp/cinder-keplerops-ca.crt" "$TRANSFER_DIR/keplerops-ca.crt" \
  --project "$PROJECT_ID" --zone "$KEPLER_ZONE" --tunnel-through-iap
gcloud compute scp "$ARWC_INSTANCE:/tmp/cinder-arwc-ca.crt" "$TRANSFER_DIR/arwc-ca.crt" \
  --project "$PROJECT_ID" --zone "$ARWC_ZONE" --tunnel-through-iap
gcloud compute scp "$TRANSFER_DIR/keplerops-ca.crt" "$ARWC_INSTANCE:/tmp/cinder-keplerops-ca.crt" \
  --project "$PROJECT_ID" --zone "$ARWC_ZONE" --tunnel-through-iap
gcloud compute scp "$TRANSFER_DIR/arwc-ca.crt" "$KEPLER_INSTANCE:/tmp/cinder-arwc-ca.crt" \
  --project "$PROJECT_ID" --zone "$KEPLER_ZONE" --tunnel-through-iap

gcloud compute ssh "$ARWC_INSTANCE" --project "$PROJECT_ID" --zone "$ARWC_ZONE" \
  --tunnel-through-iap --command \
  'sudo install -m 0644 /tmp/cinder-keplerops-ca.crt /opt/cinder-typhoon/build/arwc/.operator/integration/keplerops-ca.crt && sudo rm -f /tmp/cinder-keplerops-ca.crt /tmp/cinder-arwc-ca.crt && cd /opt/cinder-typhoon/build/arwc && sudo docker compose up -d --force-recreate a-connector'
gcloud compute ssh "$KEPLER_INSTANCE" --project "$PROJECT_ID" --zone "$KEPLER_ZONE" \
  --tunnel-through-iap --command \
  'sudo install -m 0644 /tmp/cinder-arwc-ca.crt /opt/cinder-typhoon/build/keplerops/.operator/integration/arwc-ca.crt && sudo rm -f /tmp/cinder-arwc-ca.crt /tmp/cinder-keplerops-ca.crt && cd /opt/cinder-typhoon/build/keplerops && sudo docker compose up -d --force-recreate a-connector'

terraform -chdir="$GCP_ROOT" output
