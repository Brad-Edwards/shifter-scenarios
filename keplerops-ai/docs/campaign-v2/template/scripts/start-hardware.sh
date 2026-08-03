#!/usr/bin/env bash
set -euo pipefail

readonly ROOT=${KEPLEROPS_V2_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}
readonly COMPOSE_FILE="$ROOT/compose.hardware.yaml"
readonly LOCK_FILE="$ROOT/hardware/component-lock.env"
readonly OPERATOR_BIND=${LABGRID_OPERATOR_BIND_ADDRESS:-127.0.0.1}

case $OPERATOR_BIND in
  0.0.0.0 | :: | '[::]')
    echo "refusing wildcard labgrid coordinator bind; use an operator-management address" >&2
    exit 1
    ;;
esac

cd "$ROOT"
docker compose --env-file "$LOCK_FILE" -f "$COMPOSE_FILE" build \
  labgrid-coordinator labgrid-client
docker compose --env-file "$LOCK_FILE" -f "$COMPOSE_FILE" up -d \
  labgrid-coordinator labgrid-client

deadline=$((SECONDS + ${KEPLEROPS_HARDWARE_START_TIMEOUT:-300}))
until docker compose --env-file "$LOCK_FILE" -f "$COMPOSE_FILE" exec -T \
  labgrid-client labgrid-client places >/dev/null 2>&1; do
  if ((SECONDS >= deadline)); then
    echo "labgrid coordinator/client startup timed out" >&2
    exit 1
  fi
  sleep 5
done

docker compose --env-file "$LOCK_FILE" -f "$COMPOSE_FILE" exec -T \
  labgrid-client python /opt/keplerops-hardware/reconcile_places.py \
  --coordinator labgrid-coordinator:20408 \
  --manifest /opt/keplerops-hardware/pool.yaml

echo "operator-only labgrid boundary ready; real exporters and benches are still required"
echo "participant access and media remain withheld until a range-scoped gateway/TURN deployment exists"
