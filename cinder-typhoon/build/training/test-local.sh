#!/usr/bin/env bash
set -euo pipefail

ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
COMPOSE="$ROOT/compose.yaml"
WORKER_IMAGE="node:22.12.0-bookworm-slim@sha256:35531c52ce27b6575d69755c73e65d4468dba93a25644eed56dc12879cae9213"

docker pull "$WORKER_IMAGE"
docker compose -f "$COMPOSE" build

start_fresh() {
  docker compose -f "$COMPOSE" down -v --remove-orphans
  docker compose -f "$COMPOSE" up -d
  for attempt in $(seq 1 60); do
    if docker exec --user cinder cinder-training-kali \
        curl -sS --fail http://workbench.training:8080/ >/dev/null \
      && docker exec --user cinder cinder-training-kali \
        curl -sS --fail http://accounts.training:8080/ >/dev/null \
      && docker exec --user cinder cinder-training-kali \
        curl -sS --fail http://developer.training:8080/ >/dev/null \
      && docker exec --user cinder cinder-training-kali \
        curl -sS --fail http://state.training:8080/ >/dev/null; then
      return
    fi
    if [[ $attempt -eq 60 ]]; then
      echo "Training services did not initialize" >&2
      exit 1
    fi
    sleep 1
  done
}

run_test() {
  docker run --rm \
    --network cinder-training \
    --read-only \
    --cap-drop ALL \
    --security-opt no-new-privileges:true \
    --tmpfs /tmp:rw,nosuid,nodev,size=64m,mode=1777 \
    --volume "$ROOT/tests:/opt/operator-tests:ro" \
    cinder-training/participant:hand-build \
    python3 "/opt/operator-tests/$1" "${@:2}"
}

start_fresh
docker exec cinder-training-kali test ! -e /opt/tests
run_test test_participant_journey_live.py -v

# The journey intentionally consumes single-use state and performs the full
# practice transfer. Give the retained contract suites their own authored state.
start_fresh
run_test test_topology_live.py -v
run_test test_workbench_live.py --base http://workbench.training -v
run_test test_accounts_live.py --base http://accounts.training:8080 -v
run_test test_developer_live.py --host developer.training -v
run_test test_state_live.py --base http://state.training:8080 -v
