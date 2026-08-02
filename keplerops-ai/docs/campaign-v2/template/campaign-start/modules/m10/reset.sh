#!/usr/bin/env bash
set -Eeuo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MODULE_ROOT
TEMPLATE_ROOT="$(cd "${MODULE_ROOT}/../../.." && pwd)"
readonly TEMPLATE_ROOT
readonly OPERATION="${1:-}"
readonly ATTEMPT_ID="${M10_ATTEMPT_ID:-}"

die() { printf '[campaign-m10 reset] ERROR: %s\n' "$*" >&2; exit 1; }

compose() {
  docker compose --project-directory "${TEMPLATE_ROOT}" \
    --env-file "${TEMPLATE_ROOT}/component-lock.env" \
    --env-file "${TEMPLATE_ROOT}/engineering/component-lock.additions.env" \
    -f "${TEMPLATE_ROOT}/compose.foundation.yaml" \
    -f "${TEMPLATE_ROOT}/compose.enterprise.yaml" \
    -f "${TEMPLATE_ROOT}/compose.engineering.yaml" \
    -f "${TEMPLATE_ROOT}/compose.cinder.yaml" \
    -f "${MODULE_ROOT}/compose.overlay.yaml" "$@"
}

[[ -n ${OPERATION} ]] || die 'usage: reset.sh <operation>'
[[ -n ${ATTEMPT_ID} ]] || die 'M10_ATTEMPT_ID must identify the active or failed attempt'
jq -e --arg id "${OPERATION}" 'any(.[]; .id == $id)' "${MODULE_ROOT}/operations.json" >/dev/null || die "unknown operation: ${OPERATION}"

# reset_attempt refuses accepted checkpoints.  For failed attempts it invokes
# normal business compensation, deletes only attempt-owned staging objects,
# and restores a damaged lakeFS partition as a new audited commit.
compose exec -T -e OPERATION="${OPERATION}" -e ATTEMPT_ID="${ATTEMPT_ID}" airflow-api python - <<'PY'
import json
import os
from production_jobs import reset_attempt

print(json.dumps(reset_attempt(os.environ["OPERATION"], os.environ["ATTEMPT_ID"]), sort_keys=True))
PY
