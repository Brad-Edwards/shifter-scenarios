#!/usr/bin/env bash
set -euo pipefail
umask 077

GCP_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
TEMPLATE="$GCP_ROOT/packer/nested-host.pkr.hcl"

usage() {
  cat >&2 <<'EOF'
usage: build-nested-host-image.sh --project-id ID --image-name NAME \
  --network NETWORK --subnetwork SUBNETWORK [--network-tag TAG]... [--use-iap]
EOF
  exit 2
}

PROJECT_ID= IMAGE_NAME= NETWORK= SUBNETWORK=
NETWORK_TAGS=()
USE_IAP=false
while (($#)); do
  case "$1" in
    --project-id) PROJECT_ID=${2-}; shift 2 ;;
    --image-name) IMAGE_NAME=${2-}; shift 2 ;;
    --network) NETWORK=${2-}; shift 2 ;;
    --subnetwork) SUBNETWORK=${2-}; shift 2 ;;
    --network-tag) NETWORK_TAGS+=("${2-}"); shift 2 ;;
    --use-iap) USE_IAP=true; shift ;;
    *) usage ;;
  esac
done

[[ $PROJECT_ID =~ ^[a-z][a-z0-9-]{4,28}[a-z0-9]$ ]] || usage
[[ $IMAGE_NAME =~ ^keplerops-nested-host-v[0-9]{8}[a-z0-9-]*$ ]] || usage
[[ $NETWORK =~ ^[a-z]([-a-z0-9]{0,61}[a-z0-9])?$ ]] || usage
[[ $SUBNETWORK =~ ^[a-z]([-a-z0-9]{0,61}[a-z0-9])?$ ]] || usage
((${#NETWORK_TAGS[@]} > 0)) || NETWORK_TAGS=(keplerops-image-builder)
for tag in "${NETWORK_TAGS[@]}"; do
  [[ $tag =~ ^[a-z]([-a-z0-9]{0,61}[a-z0-9])?$ ]] || usage
done

command -v gcloud >/dev/null || {
  echo "error: gcloud is required" >&2
  exit 1
}
command -v packer >/dev/null || {
  echo "error: Packer is required" >&2
  exit 1
}

token=$(gcloud auth print-access-token) || {
  echo "error: authenticated gcloud account required" >&2
  exit 1
}
export PKR_VAR_access_token=$token
unset token
trap 'unset PKR_VAR_access_token' EXIT

tags_json=$(printf '%s\n' "${NETWORK_TAGS[@]}" |
  jq -Rsc 'split("\n") | map(select(length > 0))')
packer init "$TEMPLATE"
packer build \
  -var "project_id=$PROJECT_ID" \
  -var "image_name=$IMAGE_NAME" \
  -var "network=$NETWORK" \
  -var "subnetwork=$SUBNETWORK" \
  -var "network_tags=$tags_json" \
  -var "use_iap=$USE_IAP" \
  "$TEMPLATE"
