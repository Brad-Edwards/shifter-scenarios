#!/usr/bin/env bash
# Bake the polaris-vm GCE custom image from this checkout's build-v1.tar.gz.
set -euo pipefail
umask 077

PACKER_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
TEMPLATE="$PACKER_ROOT/polaris-vm.pkr.hcl"
SIDECAR="$PACKER_ROOT/../build/build-v1.tar.gz.sha256"

usage() {
  cat >&2 <<'EOF'
usage: build-polaris-vm-image.sh --project-id ID --image-name NAME \
  --network NETWORK --subnetwork SUBNETWORK [--zone ZONE]
EOF
  exit 2
}

PROJECT_ID= IMAGE_NAME= NETWORK= SUBNETWORK= ZONE=us-central1-a
while (($#)); do
  case "$1" in
    --project-id) PROJECT_ID=${2-}; shift 2 ;;
    --image-name) IMAGE_NAME=${2-}; shift 2 ;;
    --network) NETWORK=${2-}; shift 2 ;;
    --subnetwork) SUBNETWORK=${2-}; shift 2 ;;
    --zone) ZONE=${2-}; shift 2 ;;
    *) usage ;;
  esac
done

[[ $PROJECT_ID =~ ^[a-z][a-z0-9-]{4,28}[a-z0-9]$ ]] || usage
[[ $IMAGE_NAME =~ ^shifter-polaris-vm-v[0-9]{8}[a-z0-9-]*$ ]] || usage
[[ $NETWORK =~ ^[a-z]([-a-z0-9]{0,61}[a-z0-9])?$ ]] || usage
[[ $SUBNETWORK =~ ^[a-z]([-a-z0-9]{0,61}[a-z0-9])?$ ]] || usage
[[ $ZONE =~ ^[a-z]+-[a-z]+[0-9]-[a-z]$ ]] || usage

for tool in gcloud packer git; do
  command -v "$tool" >/dev/null || {
    echo "error: $tool is required" >&2
    exit 1
  }
done

# Bake only committed, reviewed source.
if [[ -n $(git -C "$PACKER_ROOT" status --porcelain -- ../build ../../runtime-adapter/src .) ]]; then
  echo "error: uncommitted changes under polaris/build, polaris/packer or the adapter source" >&2
  exit 1
fi
revision=$(git -C "$PACKER_ROOT" rev-parse HEAD)
stack_sha256=$(awk '$2 == "build-v1.tar.gz" {print $1}' "$SIDECAR")
(cd "$PACKER_ROOT/../build" && sha256sum -c build-v1.tar.gz.sha256 >/dev/null) || {
  echo "error: build-v1.tar.gz does not match its sidecar digest" >&2
  exit 1
}

token=$(gcloud auth print-access-token) || {
  echo "error: authenticated gcloud account required" >&2
  exit 1
}
export PKR_VAR_access_token=$token
unset token
trap 'unset PKR_VAR_access_token' EXIT

packer init "$TEMPLATE"
packer build \
  -var "project_id=$PROJECT_ID" \
  -var "image_name=$IMAGE_NAME" \
  -var "source_revision=$revision" \
  -var "stack_sha256=$stack_sha256" \
  -var "network=$NETWORK" \
  -var "subnetwork=$SUBNETWORK" \
  -var "zone=$ZONE" \
  "$TEMPLATE"
