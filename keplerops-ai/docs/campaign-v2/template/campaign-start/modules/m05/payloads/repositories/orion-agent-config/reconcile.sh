#!/usr/bin/env bash
set -Eeuo pipefail

: "${CONFIG_FILE:=agent.yaml}"
: "${RUNTIME_STATE:=reports/runtime-revision.json}"
: "${CONFIG_REFERENCE:?CONFIG_REFERENCE is required}"

revision="sha256:$(sha256sum "$CONFIG_FILE" | awk '{print $1}')"
boundary_changed=false
if ! yq -e '.spec.confirmation.protectedTools == "required" and .spec.confirmation.hostBridge == "required"' "$CONFIG_FILE" >/dev/null; then
  boundary_changed=true
fi
jq -n \
  --arg revision "$revision" \
  --argjson boundary_changed "$boundary_changed" \
  --arg release_reference "$CONFIG_REFERENCE" \
  '{schema:"keplerops.agent.runtime-revision/v1",revision:$revision,signed:true,argo_sync:"Synced",security_boundary_changed:$boundary_changed,release_reference:(if $boundary_changed then $release_reference else null end)}' \
  > "$RUNTIME_STATE"
