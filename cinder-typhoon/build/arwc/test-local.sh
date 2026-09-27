#!/usr/bin/env bash
set -euo pipefail

ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
cd "$ROOT"

bash ./generate-operator-material.sh
docker compose -f compose.yaml down -v --remove-orphans
docker compose -f compose.yaml build
docker compose -f compose.yaml up -d --force-recreate a-connector

ready=0
for _ in $(seq 1 60); do
  if docker exec --user fieldlink cinder-arwc-connector \
    sh -c 'token=$(cat /var/lib/fieldlink-connector/handover/corporate-session) && curl --silent --fail --cacert /tmp/arwc-ca.crt -H "Authorization: Bearer $token" https://customer-handover.arwc.test:8443/api/the-customer-s-copy >/dev/null'; then
    ready=1
    break
  fi
  sleep 1
done
[[ $ready == 1 ]]

python3 tests/test_w01_live.py

[[ $(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' cinder-arwc-connector) == 10.77.60.20 ]]
[[ $(docker inspect -f '{{range $port, $bindings := .NetworkSettings.Ports}}{{if $bindings}}{{$port}}{{end}}{{end}}' cinder-arwc-connector) == '' ]]
[[ $(docker inspect -f '{{.Config.User}}' cinder-arwc-connector) == '' ]]
docker exec --user fieldlink cinder-arwc-connector sh -c 'test -r /var/lib/fieldlink-connector/handover/customer-transition.json'
docker exec --user fieldlink cinder-arwc-connector sh -c 'test ! -r /opt/customer-handover/customer_handover.py'
docker exec --user fieldlink cinder-arwc-connector sh -c 'test ! -r /var/lib/arwc-connector/state/planner-handover.json'
[[ $(docker exec cinder-arwc-connector stat -c '%U:%G:%a' /var/lib/fieldlink-connector) == fieldlink:fieldlink:700 ]]
[[ $(docker exec cinder-arwc-connector stat -c '%U:%G:%a' /var/lib/arwc-connector) == arwc-connector:arwc-connector:700 ]]
! docker exec --user fieldlink cinder-arwc-connector curl --silent --max-time 3 http://169.254.169.254/ >/dev/null 2>&1
! docker exec --user fieldlink cinder-arwc-connector curl --silent --max-time 3 https://example.com/ >/dev/null 2>&1
docker exec --user fieldlink cinder-arwc-connector python3 - <<'PY'
import socket
for address in ("10.77.39.2", "10.77.49.2", "10.201.0.2"):
    try:
        socket.create_connection((address, 22), timeout=1).close()
    except OSError:
        continue
    raise SystemExit(f"unexpected route to {address}")
PY

if docker exec --user fieldlink cinder-arwc-connector sh -c \
  "find /var/lib/fieldlink-connector -type f -readable -exec grep -Eil '(^|[^[:alpha:]])(ctf|flag|scoring|challenge|hint|walkthrough|player|organizer|hand-build|meta-commentary)([^[:alpha:]]|$)' {} +"; then
  echo "participant-visible fourth-wall terminology found" >&2
  exit 1
fi

echo "Alterra W01 local acceptance passed"
