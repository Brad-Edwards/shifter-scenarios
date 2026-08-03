#!/usr/bin/env bash
set -euo pipefail

readonly ROOT=${KEPLEROPS_V2_ROOT:-/opt/keplerops-v2}
readonly COMPOSE_FILE="$ROOT/compose.hardware.yaml"
readonly LOCK_FILE="$ROOT/hardware/component-lock.env"

cd "$ROOT"
docker compose --env-file "$LOCK_FILE" -f "$COMPOSE_FILE" exec -T \
  labgrid-client python /opt/keplerops-hardware/check_pool.py \
  --coordinator labgrid-coordinator:20408 \
  --manifest /opt/keplerops-hardware/pool.yaml

echo "full-pool attachment check passed: 12 active and two spare exporter resource sets are available"
echo "this operational check does not claim participant media readiness or physical exercise success"
