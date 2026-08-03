#!/usr/bin/env bash
set -Eeuo pipefail

readonly WORKSTATION=keplerops-participant-workstation-runtime
readonly COORDINATOR=labgrid-coordinator:20408

ws() {
  docker exec --user kasm-user \
    --env HOME=/home/kasm-user \
    --env LG_COORDINATOR="$COORDINATOR" \
    "$WORKSTATION" "$@"
}

[[ $(docker inspect --format '{{.State.Running}}' "$WORKSTATION") == true ]]
[[ $(docker inspect --format '{{.State.Running}}' kep-v2-labgrid-coordinator) == true ]]

ws labgrid-client version | grep -Fx '25.0' >/dev/null
places=$(ws labgrid-client places)
grep -q 'kepler-bench-' <<<"$places"

reservation_line=$(ws labgrid-client reserve --wait --shell \
  pool=keplerops_v2 capability=physical_ai operational=true spare=false)
if [[ ! $reservation_line =~ ^export\ LG_TOKEN=([A-Za-z0-9_-]+)$ ]]; then
  echo 'labgrid did not issue an opaque participant reservation' >&2
  exit 1
fi
reservation=${BASH_REMATCH[1]}

cleanup() {
  set +e
  ws env LG_TOKEN="$reservation" labgrid-client --place + release >/dev/null 2>&1
  ws labgrid-client cancel-reservation "$reservation" >/dev/null 2>&1
}
trap cleanup EXIT

ws env LG_TOKEN="$reservation" labgrid-client --place + acquire
ws env LG_TOKEN="$reservation" labgrid-client --place + release
ws labgrid-client cancel-reservation "$reservation"
reservation=""
trap - EXIT

echo "PASS Kali can reserve, acquire, and release a real labgrid place"
