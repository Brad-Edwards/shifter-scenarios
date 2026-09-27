#!/usr/bin/env bash
set -euo pipefail

ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
cd "$ROOT"

bash ./generate-operator-material.sh
docker compose -f compose.yaml down -v --remove-orphans
docker compose -f compose.yaml build
docker compose -f compose.yaml up -d --force-recreate a-connector a-business a-archive a-identity a-data-bridge a-data

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

ready=0
for _ in $(seq 1 60); do
  if docker exec --user fieldlink cinder-arwc-connector \
    sh -c 'token=$(cat /var/lib/fieldlink-connector/handover/corporate-session) && curl --silent --fail --cacert /tmp/arwc-ca.crt -H "Authorization: Bearer $token" https://business-workplace.arwc.test/api/the-asset-and-the-contractor >/dev/null'; then
    ready=1
    break
  fi
  sleep 1
done
[[ $ready == 1 ]]

ready=0
for _ in $(seq 1 60); do
  if docker exec --user fieldlink cinder-arwc-connector \
    sh -c 'token=$(cat /var/lib/fieldlink-connector/handover/corporate-session) && curl --silent --fail --cacert /tmp/arwc-ca.crt -H "Authorization: Bearer $token" https://retained-archive.arwc.test/api/the-archive-s-missing-contract >/dev/null'; then
    ready=1
    break
  fi
  sleep 1
done
[[ $ready == 1 ]]

ready=0
for _ in $(seq 1 60); do
  status=$(docker exec --user fieldlink cinder-arwc-connector \
    sh -c 'token=$(cat /var/lib/fieldlink-connector/handover/corporate-session) && curl --silent --cacert /tmp/arwc-ca.crt -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $token" https://corporate-identity.arwc.test/api/not-found' || true)
  if [[ $status == 404 ]]; then
    ready=1
    break
  fi
  sleep 1
done
[[ $ready == 1 ]]

ready=0
for _ in $(seq 1 60); do
  status=$(docker exec --user fieldlink cinder-arwc-connector \
    curl --silent --cacert /tmp/arwc-ca.crt -o /dev/null -w '%{http_code}' \
    -H 'Authorization: Bearer unavailable' https://planning-data.arwc.test/api/not-found || true)
  if [[ $status == 403 ]]; then
    ready=1
    break
  fi
  sleep 1
done
[[ $ready == 1 ]]

python3 tests/test_w01_live.py
python3 tests/test_w02_w03_live.py
python3 tests/test_w04_live.py
python3 tests/test_w05_w06_live.py
python3 tests/test_w07_live.py
python3 tests/test_w08_live.py
python3 tests/test_w09_live.py

[[ $(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' cinder-arwc-connector) == 10.77.60.20 ]]
[[ $(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' cinder-arwc-business) == 10.77.60.30 ]]
[[ $(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' cinder-arwc-archive) == 10.77.60.50 ]]
[[ $(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' cinder-arwc-identity) == 10.77.60.60 ]]
[[ $(docker inspect -f '{{(index .NetworkSettings.Networks "cinder-arwc-corporate").IPAddress}}' cinder-arwc-data) == 10.77.60.40 ]]
[[ $(docker inspect -f '{{(index .NetworkSettings.Networks "cinder-arwc-dmz").IPAddress}}' cinder-arwc-data-bridge) == 10.77.62.20 ]]
[[ $(docker inspect -f '{{range $port, $bindings := .NetworkSettings.Ports}}{{if $bindings}}{{$port}}{{end}}{{end}}' cinder-arwc-connector) == '' ]]
[[ $(docker inspect -f '{{range $port, $bindings := .NetworkSettings.Ports}}{{if $bindings}}{{$port}}{{end}}{{end}}' cinder-arwc-business) == '' ]]
[[ $(docker inspect -f '{{range $port, $bindings := .NetworkSettings.Ports}}{{if $bindings}}{{$port}}{{end}}{{end}}' cinder-arwc-archive) == '' ]]
[[ $(docker inspect -f '{{range $port, $bindings := .NetworkSettings.Ports}}{{if $bindings}}{{$port}}{{end}}{{end}}' cinder-arwc-identity) == '' ]]
[[ $(docker inspect -f '{{range $port, $bindings := .NetworkSettings.Ports}}{{if $bindings}}{{$port}}{{end}}{{end}}' cinder-arwc-data) == '' ]]
[[ $(docker inspect -f '{{range $port, $bindings := .NetworkSettings.Ports}}{{if $bindings}}{{$port}}{{end}}{{end}}' cinder-arwc-data-bridge) == '' ]]
[[ $(docker inspect -f '{{.Config.User}}' cinder-arwc-connector) == '' ]]
docker exec --user fieldlink cinder-arwc-connector sh -c 'test -r /var/lib/fieldlink-connector/handover/customer-transition.json'
docker exec --user fieldlink cinder-arwc-connector sh -c 'test ! -r /opt/customer-handover/customer_handover.py'
docker exec --user fieldlink cinder-arwc-connector sh -c 'test ! -r /var/lib/arwc-connector/state/planner-handover.json'
[[ $(docker exec cinder-arwc-connector stat -c '%U:%G:%a' /var/lib/fieldlink-connector) == fieldlink:fieldlink:700 ]]
[[ $(docker exec cinder-arwc-connector stat -c '%U:%G:%a' /var/lib/arwc-connector) == arwc-connector:arwc-connector:700 ]]
[[ $(docker exec cinder-arwc-business stat -c '%U:%G:%a' /var/lib/arwc-business) == arwc-business:arwc-business:700 ]]
[[ $(docker exec cinder-arwc-archive stat -c '%U:%G:%a' /var/lib/arwc-archive) == arwc-archive:arwc-archive:700 ]]
[[ $(docker exec cinder-arwc-identity stat -c '%U:%G:%a' /var/lib/arwc-identity) == arwc-identity:arwc-identity:700 ]]
[[ $(docker exec cinder-arwc-data stat -c '%U:%G:%a' /var/lib/arwc-data) == arwc-data:arwc-data:700 ]]
[[ $(docker exec cinder-arwc-data-bridge stat -c '%U:%G:%a' /var/lib/arwc-data-bridge) == arwc-data-bridge:arwc-data-bridge:700 ]]
[[ $(docker exec cinder-arwc-archive /usr/local/bin/7zz | sed -n '2p') == *'23.01'* ]]
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
  "find /var/lib/fieldlink-connector -type f -readable -exec grep -EIl '(^|[^[:alpha:]])(ctf|flag|scoring|challenge|hint|walkthrough|player|organizer|hand-build|meta-commentary)([^[:alpha:]]|$)' {} +"; then
  echo "participant-visible fourth-wall terminology found" >&2
  exit 1
fi

echo "Alterra W01-W09 local acceptance passed"
