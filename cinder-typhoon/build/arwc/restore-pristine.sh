#!/usr/bin/env bash
set -euo pipefail

ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
cd "$ROOT"

docker compose -f compose.yaml down -v --remove-orphans
docker compose -f compose.yaml up -d --force-recreate a-connector

for _ in $(seq 1 60); do
  if docker exec --user arwc-connector cinder-arwc-connector \
    test -s /var/lib/arwc-connector/state/planner-handover.json; then
    state=$(docker exec --user arwc-connector cinder-arwc-connector \
      cat /var/lib/arwc-connector/state/planner-handover.json)
    audit_size=$(docker exec --user arwc-connector cinder-arwc-connector \
      sh -c 'wc -c </var/lib/arwc-connector/audit/events.jsonl')
    [[ $state == *'"record_id":"PLN-HO-CRR-17"'* ]]
    [[ $state == *'"revision":3'* ]]
    [[ $state == *'"filename":"inspection-summary-r2.md"'* ]]
    [[ $audit_size == 0 ]]
    echo "Alterra authored initial state restored"
    exit 0
  fi
  sleep 1
done

echo "Alterra connector did not initialize" >&2
exit 1
