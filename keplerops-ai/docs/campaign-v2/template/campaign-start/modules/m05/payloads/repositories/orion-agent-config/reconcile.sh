#!/usr/bin/env bash
set -Eeuo pipefail

: "${CONFIG_FILE:=agent.yaml}"
: "${IMAGE_DIGEST:?IMAGE_DIGEST is required}"
: "${SOURCE_COMMIT:?SOURCE_COMMIT is required}"
: "${SIGNATURE_VERIFIED:?SIGNATURE_VERIFIED is required}"
[[ ${SIGNATURE_VERIFIED} == true ]] || { echo 'configuration signature is not verified' >&2; exit 4; }

config_digest="sha256:$(sha256sum "$CONFIG_FILE" | awk '{print $1}')"
jq -n --arg commit "$SOURCE_COMMIT" --arg image_digest "$IMAGE_DIGEST" --arg config_digest "$config_digest" \
  '{schema:"keplerops.orion.configuration-deployment/v1",commit:$commit,image_digest:$image_digest,config_digest:$config_digest,signature_verified:true,status:"ready-for-gitops"}'
