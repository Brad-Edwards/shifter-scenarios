#!/usr/bin/env bash
set -euo pipefail

ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
cd "$ROOT"

docker compose -f compose.yaml down -v --remove-orphans
bash ./generate-operator-material.sh
startup_log="$ROOT/.operator/restore-startup.log"
startup_pid="$ROOT/.operator/restore-startup.pid"
nohup docker compose -f compose.yaml up -d --force-recreate \
  a-connector fieldlink-edge a-business a-archive a-identity a-data-bridge a-data \
  a-contractors a-contractor-bridge a-approval a-renderer a-control-broker \
  a-hmi a-historian a-engineering a-instruments a-reservoir a-distribution \
  a-diagnostics >"$startup_log" 2>&1 </dev/null &
compose_pid=$!
printf '%s\n' "$compose_pid" >"$startup_pid"

for attempt in $(seq 1 60); do
  if docker exec --user arwc-connector cinder-arwc-connector \
      test -s /var/lib/arwc-connector/state/planner-handover.json 2>/dev/null \
    && docker exec --user arwc-connector cinder-arwc-connector \
      test -e /var/lib/arwc-connector/audit/fieldlink-consumer.jsonl 2>/dev/null; then
    break
  fi
  if ! kill -0 "$compose_pid" 2>/dev/null; then
    echo "Alterra stack startup exited; see $startup_log" >&2
    exit 1
  fi
  if [[ $attempt -eq 60 ]]; then
    echo "Alterra connector did not initialize" >&2
    exit 1
  fi
  sleep 1
done

for container in cinder-arwc-business cinder-arwc-archive cinder-arwc-contractors; do
  docker exec "$container" grep -qx waiting /run/arwc-status/state
  [[ $(docker inspect -f '{{.RestartCount}}' "$container") == 0 ]]
done
kill -0 "$compose_pid"

docker exec --user fieldlink cinder-arwc-connector \
  sh -c 'test ! -e /var/lib/fieldlink-connector/handover/corporate-session && test ! -e /var/lib/fieldlink-connector/handover/corporate-session.json && test ! -e /var/lib/fieldlink-connector/handover/customer-transition.json'
docker exec --user arwc-connector cinder-arwc-connector \
  sh -c 'test ! -e /var/lib/arwc-connector/auth/corporate-session.sha256 && test "$(wc -c </var/lib/arwc-connector/audit/events.jsonl)" -eq 0 && test "$(wc -c </var/lib/arwc-connector/audit/fieldlink-consumer.jsonl)" -eq 0'
docker exec --user arwc-connector cinder-arwc-connector \
  sh -c 'find /var/lib/fieldlink-connector/consumer/candidates /var/lib/fieldlink-connector/receipts -type f -print -quit | grep -q . && exit 1 || exit 0'

published=$(docker inspect -f '{{json .NetworkSettings.Ports}}' cinder-arwc-fieldlink-edge)
[[ $published == *'"443/tcp"'* ]]
[[ $published != *'"8443/tcp"'* ]]

echo "Alterra authored pre-delivery state restored"
