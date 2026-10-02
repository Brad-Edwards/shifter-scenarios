#!/usr/bin/env bash
set -euo pipefail

ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
cd "$ROOT"

docker compose -f compose.yaml down -v --remove-orphans
docker compose -f compose.yaml up -d --force-recreate \
  a-connector fieldlink-edge a-business a-archive a-identity a-data-bridge a-data \
  a-contractors a-contractor-bridge a-approval a-renderer a-control-broker \
  a-hmi a-historian a-engineering a-instruments a-reservoir a-distribution \
  a-diagnostics

for attempt in $(seq 1 60); do
  if docker exec --user arwc-connector cinder-arwc-connector \
      test -s /var/lib/arwc-connector/state/planner-handover.json \
    && docker exec --user arwc-connector cinder-arwc-connector \
      test -e /var/lib/arwc-connector/audit/fieldlink-consumer.jsonl; then
    break
  fi
  if [[ $attempt -eq 60 ]]; then
    echo "Alterra connector did not initialize" >&2
    exit 1
  fi
  sleep 1
done

docker exec --user fieldlink cinder-arwc-connector \
  sh -c 'test ! -e /var/lib/fieldlink-connector/handover/corporate-session && test ! -e /var/lib/fieldlink-connector/handover/customer-transition.json'
docker exec --user arwc-connector cinder-arwc-connector \
  sh -c 'test ! -e /var/lib/arwc-connector/auth/corporate-session.sha256 && test "$(wc -c </var/lib/arwc-connector/audit/events.jsonl)" -eq 0 && test "$(wc -c </var/lib/arwc-connector/audit/fieldlink-consumer.jsonl)" -eq 0'
docker exec --user arwc-connector cinder-arwc-connector \
  sh -c 'find /var/lib/fieldlink-connector/consumer/candidates /var/lib/fieldlink-connector/receipts -type f -print -quit | grep -q . && exit 1 || exit 0'

published=$(docker inspect -f '{{json .NetworkSettings.Ports}}' cinder-arwc-fieldlink-edge)
[[ $published == *'"443/tcp"'* ]]
[[ $published != *'"8443/tcp"'* ]]

echo "Alterra authored pre-delivery state restored"
