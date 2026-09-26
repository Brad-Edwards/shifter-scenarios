#!/usr/bin/env bash
set -euo pipefail

ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
COMPOSE="$ROOT/compose.yaml"

docker compose -f "$COMPOSE" build
docker compose -f "$COMPOSE" up -d
docker exec cinder-training-kali test ! -e /opt/tests

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

run_test test_topology_live.py -v
run_test test_workbench_live.py --base http://workbench.training -v
run_test test_accounts_live.py --base http://accounts.training:8080 -v
run_test test_developer_live.py --host developer.training -v
run_test test_state_live.py --base http://state.training:8080 -v
