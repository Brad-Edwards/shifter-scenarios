#!/usr/bin/env bash
set -euo pipefail

readonly ROOT=${KEPLEROPS_V2_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}
readonly COMPOSE_FILE="$ROOT/compose.hardware.yaml"
readonly LOCK_FILE="$ROOT/hardware/component-lock.env"
readonly COORDINATOR=labgrid-coordinator:20408
readonly MANIFEST=/opt/keplerops-hardware/pool.yaml
readonly EVIDENCE_CONTRACT=/opt/keplerops-hardware/evidence-contract.yaml

if [[ -z ${KEPLEROPS_HARDWARE_GATE14_PLACE:-} ]]; then
  echo "set KEPLEROPS_HARDWARE_GATE14_PLACE to one declared active real bench" >&2
  exit 1
fi
readonly PLACE=$KEPLEROPS_HARDWARE_GATE14_PLACE

cd "$ROOT"
docker compose --env-file "$LOCK_FILE" -f "$COMPOSE_FILE" exec -T \
  labgrid-client python /opt/keplerops-hardware/check_pool.py \
  --coordinator "$COORDINATOR" --manifest "$MANIFEST" --place "$PLACE"

client() {
  docker compose --env-file "$LOCK_FILE" -f "$COMPOSE_FILE" exec -T \
    labgrid-client labgrid-client --coordinator "$COORDINATOR" "$@"
}

reservation=""
place=""
acquired=0
cleanup() {
  set +e
  if [[ $acquired == 1 && -n $reservation ]]; then
    docker compose --env-file "$LOCK_FILE" -f "$COMPOSE_FILE" exec -T \
      -e LG_TOKEN="$reservation" labgrid-client \
      labgrid-client --coordinator "$COORDINATOR" --place + release >/dev/null
  fi
  if [[ -n $reservation ]]; then
    client cancel-reservation "$reservation" >/dev/null
  fi
}
trap cleanup EXIT

selection_value=${PLACE//-/_}
reservation_line=$(client reserve --wait --shell \
  pool=keplerops_v2 capability=physical_ai operational=true spare=false \
  "bench_id=$selection_value")
if [[ $reservation_line =~ ^export\ LG_TOKEN=([A-Za-z0-9_-]+)$ ]]; then
  reservation=${BASH_REMATCH[1]}
else
  echo "labgrid did not return an opaque reservation token" >&2
  exit 1
fi

place=$(docker compose --env-file "$LOCK_FILE" -f "$COMPOSE_FILE" exec -T \
  labgrid-client python /opt/keplerops-hardware/check_pool.py \
  --coordinator "$COORDINATOR" --manifest "$MANIFEST" \
  --place "$PLACE" --reservation-token "$reservation")

docker compose --env-file "$LOCK_FILE" -f "$COMPOSE_FILE" exec -T \
  -e LG_TOKEN="$reservation" labgrid-client \
  labgrid-client --coordinator "$COORDINATOR" --place + acquire
acquired=1

if docker compose --env-file "$LOCK_FILE" -f "$COMPOSE_FILE" exec -T \
  -e LG_USERNAME=exclusive-acquisition-probe labgrid-client \
  labgrid-client --coordinator "$COORDINATOR" --place "$place" acquire \
  >/dev/null 2>&1; then
  echo "second client acquired an already leased place" >&2
  exit 1
fi

if [[ ! -f ${LABGRID_CLIENT_SSH_DIR:-$ROOT/hardware/client-ssh}/id_ed25519 ]]; then
  echo "real bench SSH key is absent; cannot operate the physical place" >&2
  exit 1
fi

nonce=$(cat /proc/sys/kernel/random/uuid)
lease_sha256=$(printf '%s' "$reservation" | sha256sum | cut -d' ' -f1)
liveness_payload="KEPLEROPS-LIVENESS-V1|$place|$nonce|$lease_sha256"
docker compose --env-file "$LOCK_FILE" -f "$COMPOSE_FILE" exec -T \
  -e LG_TOKEN="$reservation" -e LG_PLACE=+ labgrid-client \
  labgrid-client --coordinator "$COORDINATOR" \
  --config /opt/keplerops-hardware/remote.yaml ssh \
  keplerops-bench exercise \
  --bench-id "$place" \
  --liveness-nonce "$nonce" \
  --lease-sha256 "$lease_sha256" \
  --liveness-payload "$liveness_payload" \
  --evidence-format keplerops-raw-tar-v1 \
  | docker compose --env-file "$LOCK_FILE" \
  -f "$COMPOSE_FILE" exec -T labgrid-client \
  python /opt/keplerops-hardware/verify_evidence.py \
  --contract "$EVIDENCE_CONTRACT" \
  --place "$place" --nonce "$nonce" --lease-sha256 "$lease_sha256"

docker compose --env-file "$LOCK_FILE" -f "$COMPOSE_FILE" exec -T \
  -e LG_TOKEN="$reservation" labgrid-client \
  labgrid-client --coordinator "$COORDINATOR" --place + release
acquired=0
client cancel-reservation "$reservation"
reservation=""

echo "operator-only clean-enterprise gate 14 passed: selected real place acquired, independently observed, and released"
echo "participant access and media readiness are not claimed"
