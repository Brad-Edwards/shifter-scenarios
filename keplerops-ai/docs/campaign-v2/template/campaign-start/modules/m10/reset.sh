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

[[ -n ${OPERATION} ]] || die 'usage: reset.sh <kep-m10-operation>'
jq -e --arg id "${OPERATION}" 'any(.[]; .id == $id)' "${MODULE_ROOT}/operations.json" >/dev/null || die "unknown operation: ${OPERATION}"
[[ -n ${ATTEMPT_ID} ]] || die 'M10_ATTEMPT_ID must identify the active or failed attempt'

compose exec -T -e OPERATION="${OPERATION}" -e ATTEMPT_ID="${ATTEMPT_ID}" airflow-api python - <<'PY'
import json, os
from pathlib import Path
from production_jobs import cinder_s3, export_s3, kepler_s3, s3, STATE

operation = os.environ["OPERATION"]
attempt = os.environ["ATTEMPT_ID"]
prefixes = {
    "kep-m10-a": [(kepler_s3(), "artifacts", f"production/audits/{attempt}")],
    "kep-m10-d": [(export_s3(), "orion-egress-staging", f"egress-staging/{attempt}")],
    "kep-m10-f": [(cinder_s3(), "acquired", f"acquired/orion-original/{attempt}")],
    "kep-m10-g": [(cinder_s3(), "acquired", f"offline-executions/{attempt}")],
    "kep-m10-h": [(kepler_s3(), "artifacts", f"production/availability/{attempt}")],
    "kep-m10-i": [(kepler_s3(), "artifacts", f"production/chargeback/{attempt}")],
    "kep-m10-j": [(kepler_s3(), "artifacts", f"production/research/{attempt}")],
    "kep-m10-k": [(kepler_s3(), "artifacts", f"production/feedback/{attempt}")],
    "kep-m10-p": [(kepler_s3(), "artifacts", f"production/data-quality/{attempt}")],
}.get(operation, [])
for client, bucket, prefix in prefixes:
    rows = client.list_objects_v2(Bucket=bucket, Prefix=prefix).get("Contents", [])
    for row in rows:
        body = client.get_object(Bucket=bucket, Key=row["Key"])["Body"].read()
        if b"FLAG{" in body:
            raise SystemExit("successful immutable carrier exists; full-range reprovision is required")
    if rows:
        client.delete_objects(Bucket=bucket, Delete={"Objects": [{"Key": row["Key"]} for row in rows]})
if operation == "kep-m10-p":
    backup = STATE / "feedback-partitions" / attempt
    metadata = json.loads((backup / "metadata.json").read_text())
    lake = s3("http://10.61.50.61:8000", "KeplerLakeFSAccess", "KeplerV2-Training-LakeFS-Object-Key")
    lake.put_object(Bucket=metadata["bucket"], Key=metadata["key"], Body=(backup / "object.bin").read_bytes())
PY

if [[ -n ${M10_WORKFLOW_ID:-} ]]; then
  status="$(curl -fsS -H 'Authorization: Bearer KeplerV2-Training-Business-Adapter' \
    "http://10.61.70.25:8080/internal/v1/workflows/${M10_WORKFLOW_ID}" | jq -er .status)"
  [[ ${status} != succeeded ]] || die 'successful business checkpoint is immutable; use full-range reprovision'
fi

printf '%s: active or failed attempt state cleared; accepted ancestors preserved\n' "${OPERATION}"
