#!/usr/bin/env bash
set -euo pipefail

ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
cd "$ROOT"

docker compose -f compose.yaml down -v --remove-orphans
bash ./generate-operator-material.sh
startup_log="$ROOT/.operator/restore-startup.log"

fail() {
  echo "ARWC pristine restore failed: $*" >&2
  exit 1
}

if ! docker compose -f compose.yaml up -d --force-recreate \
  a-connector fieldlink-edge a-business a-archive a-identity a-data-bridge a-data \
  a-contractors a-contractor-bridge a-approval a-renderer a-control-broker \
  a-hmi a-historian a-engineering a-instruments a-reservoir a-distribution \
  a-diagnostics >"$startup_log" 2>&1; then
  fail "service graph startup failed; see $startup_log"
fi

handover_services_waiting() {
  for container in \
    cinder-arwc-business cinder-arwc-archive cinder-arwc-contractors \
    cinder-arwc-identity cinder-arwc-data; do
    docker exec "$container" grep -qx waiting /run/arwc-status/state 2>/dev/null \
      || return 1
    [[ $(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{end}}' "$container") == healthy ]] \
      || return 1
    [[ $(docker inspect -f '{{.RestartCount}}' "$container") == 0 ]] \
      || return 1
  done
}

service_graph_stable() {
  local expected container
  local containers=()
  expected=$(docker compose -f compose.yaml config --services | wc -l)
  mapfile -t containers < <(docker compose -f compose.yaml ps -a -q)
  [[ ${#containers[@]} -eq $expected ]] || return 1
  for container in "${containers[@]}"; do
    [[ $(docker inspect -f '{{.State.Status}}' "$container") == running ]] \
      || return 1
    [[ $(docker inspect -f '{{.RestartCount}}' "$container") == 0 ]] \
      || return 1
  done
}

for attempt in $(seq 1 60); do
  if docker exec --user arwc-connector cinder-arwc-connector \
      test -s /var/lib/arwc-connector/state/planner-handover.json 2>/dev/null \
    && docker exec --user arwc-connector cinder-arwc-connector \
      test -e /var/lib/arwc-connector/audit/fieldlink-consumer.jsonl 2>/dev/null \
    && handover_services_waiting \
    && service_graph_stable; then
    break
  fi
  if [[ $attempt -eq 60 ]]; then
    fail "complete service graph did not reach stable pre-handoff state"
  fi
  sleep 1
done

handover_services_waiting \
  || fail "pre-handoff services did not remain in the waiting state with zero restarts"
service_graph_stable \
  || fail "complete service graph did not remain running with zero restarts"

docker exec --user fieldlink cinder-arwc-connector \
  sh -c 'test ! -e /var/lib/fieldlink-connector/handover/corporate-session && test ! -e /var/lib/fieldlink-connector/handover/corporate-session.json && test ! -e /var/lib/fieldlink-connector/handover/customer-transition.json' \
  || fail "participant handover state was not empty"
docker exec --user arwc-connector cinder-arwc-connector \
  sh -c 'test ! -e /var/lib/arwc-connector/auth/corporate-session.sha256 && test "$(wc -c </var/lib/arwc-connector/audit/events.jsonl)" -eq 0 && test "$(wc -c </var/lib/arwc-connector/audit/fieldlink-consumer.jsonl)" -eq 0' \
  || fail "connector authentication or audit state was not empty"
docker exec --user arwc-connector cinder-arwc-connector \
  sh -c 'find /var/lib/fieldlink-connector/consumer/candidates /var/lib/fieldlink-connector/receipts -type f -print -quit | grep -q . && exit 1 || exit 0' \
  || fail "connector candidate or receipt state was not empty"

published=$(docker inspect -f '{{json .NetworkSettings.Ports}}' cinder-arwc-fieldlink-edge) \
  || fail "fieldlink edge container was not available"
[[ $published == *'"443/tcp"'* ]] \
  || fail "fieldlink edge did not publish the expected HTTPS port"
[[ $published != *'"8443/tcp"'* ]] \
  || fail "fieldlink edge exposed the internal alternate HTTPS port"

echo "Alterra authored pre-delivery state restored"
