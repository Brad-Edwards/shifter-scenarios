#!/usr/bin/env bash
set -Eeuo pipefail

: "${PUBLIC_BLUEPRINT:?PUBLIC_BLUEPRINT is required}"
: "${PRIVATE_RENDER:?PRIVATE_RENDER is required}"
: "${PUBLIC_SIGNATURE:?PUBLIC_SIGNATURE is required}"
: "${PUBLIC_KEY:?PUBLIC_KEY is required}"
: "${DRIFT_REFERENCE:?DRIFT_REFERENCE is required}"

public_digest="sha256:$(sha256sum "$PUBLIC_BLUEPRINT" | awk '{print $1}')"
private_digest="sha256:$(sha256sum "$PRIVATE_RENDER" | awk '{print $1}')"
cosign verify-blob \
  --key "$PUBLIC_KEY" \
  --bundle "$PUBLIC_SIGNATURE" "$PUBLIC_BLUEPRINT" >/dev/null

changed_paths="$(diff -u "$PUBLIC_BLUEPRINT" "$PRIVATE_RENDER" || true)"
[[ -n $changed_paths ]] || {
  echo 'no configuration drift found' >&2
  exit 4
}

jq -n \
  --arg public_digest "$public_digest" \
  --arg private_digest "$private_digest" \
  --arg changed_paths "$changed_paths" \
  --arg engagement_reference "$DRIFT_REFERENCE" \
  '{schema:"keplerops.gitops.drift/v1",blueprint:"orion-release-assistant",public_digest:$public_digest,private_digest:$private_digest,signature_verified:true,changed_paths:$changed_paths,engagement_reference:$engagement_reference}' \
  > reports/orion-release-assistant-drift.json
