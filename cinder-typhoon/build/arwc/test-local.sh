#!/usr/bin/env bash
set -euo pipefail

ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
cd "$ROOT"

bash ./generate-operator-material.sh
docker compose -f compose.yaml down -v --remove-orphans
docker compose -f compose.yaml build
docker compose -f compose.yaml up -d --force-recreate a-connector a-business a-archive a-identity a-data-bridge a-data a-contractors a-contractor-bridge a-approval a-hmi a-historian a-engineering a-instruments a-diagnostics

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
  status=$(docker exec --user fieldlink cinder-arwc-connector \
    curl --silent --cacert /tmp/arwc-ca.crt -o /dev/null -w '%{http_code}' \
    -H 'Authorization: Bearer unavailable' https://process-view.arwc.test/api/the-reservoir-s-present-tense || true)
  if [[ $status == 403 ]]; then
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
python3 tests/test_w10_live.py
python3 tests/test_w11_live.py
python3 tests/test_w12_live.py
python3 tests/test_w35_live.py
python3 tests/test_w13_live.py
python3 tests/test_w14_live.py
python3 tests/test_w15_live.py
python3 tests/test_w16_live.py
python3 tests/test_w17_w18_w21_w25_live.py
python3 tests/test_w19_w20_live.py
python3 tests/test_w22_live.py
python3 tests/test_w23_live.py

[[ $(docker inspect -f '{{(index .NetworkSettings.Networks "cinder-arwc-corporate").IPAddress}}' cinder-arwc-connector) == 10.77.60.20 ]]
[[ $(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' cinder-arwc-business) == 10.77.60.30 ]]
[[ $(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' cinder-arwc-archive) == 10.77.60.50 ]]
[[ $(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' cinder-arwc-identity) == 10.77.60.60 ]]
[[ $(docker inspect -f '{{(index .NetworkSettings.Networks "cinder-arwc-corporate").IPAddress}}' cinder-arwc-data) == 10.77.60.40 ]]
[[ $(docker inspect -f '{{(index .NetworkSettings.Networks "cinder-arwc-dmz").IPAddress}}' cinder-arwc-data-bridge) == 10.77.62.20 ]]
[[ $(docker inspect -f '{{(index .NetworkSettings.Networks "cinder-arwc-maintenance").IPAddress}}' cinder-arwc-contractors) == 10.77.61.20 ]]
[[ $(docker inspect -f '{{(index .NetworkSettings.Networks "cinder-arwc-dmz").IPAddress}}' cinder-arwc-contractor-bridge) == 10.77.62.30 ]]
[[ $(docker inspect -f '{{(index .NetworkSettings.Networks "cinder-arwc-maintenance").IPAddress}}' cinder-arwc-approval) == 10.77.61.30 ]]
[[ $(docker inspect -f '{{(index .NetworkSettings.Networks "cinder-arwc-engineering").IPAddress}}' cinder-arwc-hmi) == 10.77.63.20 ]]
[[ $(docker inspect -f '{{(index .NetworkSettings.Networks "cinder-arwc-engineering").IPAddress}}' cinder-arwc-historian) == 10.77.63.30 ]]
[[ $(docker inspect -f '{{(index .NetworkSettings.Networks "cinder-arwc-engineering").IPAddress}}' cinder-arwc-engineering) == 10.77.63.40 ]]
[[ $(docker inspect -f '{{(index .NetworkSettings.Networks "cinder-arwc-control").IPAddress}}' cinder-arwc-instruments) == 10.77.64.40 ]]
[[ $(docker inspect -f '{{(index .NetworkSettings.Networks "cinder-arwc-engineering").IPAddress}}' cinder-arwc-diagnostics) == 10.77.63.50 ]]
[[ $(docker inspect -f '{{range $port, $bindings := .NetworkSettings.Ports}}{{if $bindings}}{{$port}}{{end}}{{end}}' cinder-arwc-connector) == '' ]]
[[ $(docker inspect -f '{{range $port, $bindings := .NetworkSettings.Ports}}{{if $bindings}}{{$port}}{{end}}{{end}}' cinder-arwc-business) == '' ]]
[[ $(docker inspect -f '{{range $port, $bindings := .NetworkSettings.Ports}}{{if $bindings}}{{$port}}{{end}}{{end}}' cinder-arwc-archive) == '' ]]
[[ $(docker inspect -f '{{range $port, $bindings := .NetworkSettings.Ports}}{{if $bindings}}{{$port}}{{end}}{{end}}' cinder-arwc-identity) == '' ]]
[[ $(docker inspect -f '{{range $port, $bindings := .NetworkSettings.Ports}}{{if $bindings}}{{$port}}{{end}}{{end}}' cinder-arwc-data) == '' ]]
[[ $(docker inspect -f '{{range $port, $bindings := .NetworkSettings.Ports}}{{if $bindings}}{{$port}}{{end}}{{end}}' cinder-arwc-data-bridge) == '' ]]
[[ $(docker inspect -f '{{range $port, $bindings := .NetworkSettings.Ports}}{{if $bindings}}{{$port}}{{end}}{{end}}' cinder-arwc-contractors) == '' ]]
[[ $(docker inspect -f '{{range $port, $bindings := .NetworkSettings.Ports}}{{if $bindings}}{{$port}}{{end}}{{end}}' cinder-arwc-contractor-bridge) == '' ]]
[[ $(docker inspect -f '{{range $port, $bindings := .NetworkSettings.Ports}}{{if $bindings}}{{$port}}{{end}}{{end}}' cinder-arwc-approval) == '' ]]
[[ $(docker inspect -f '{{range $port, $bindings := .NetworkSettings.Ports}}{{if $bindings}}{{$port}}{{end}}{{end}}' cinder-arwc-hmi) == '' ]]
[[ $(docker inspect -f '{{range $port, $bindings := .NetworkSettings.Ports}}{{if $bindings}}{{$port}}{{end}}{{end}}' cinder-arwc-historian) == '' ]]
[[ $(docker inspect -f '{{range $port, $bindings := .NetworkSettings.Ports}}{{if $bindings}}{{$port}}{{end}}{{end}}' cinder-arwc-engineering) == '' ]]
[[ $(docker inspect -f '{{range $port, $bindings := .NetworkSettings.Ports}}{{if $bindings}}{{$port}}{{end}}{{end}}' cinder-arwc-instruments) == '' ]]
[[ $(docker inspect -f '{{range $port, $bindings := .NetworkSettings.Ports}}{{if $bindings}}{{$port}}{{end}}{{end}}' cinder-arwc-diagnostics) == '' ]]
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
[[ $(docker exec cinder-arwc-contractors stat -c '%U:%G:%a' /var/lib/arwc-contractors) == arwc-contractors:arwc-contractors:700 ]]
[[ $(docker exec cinder-arwc-contractor-bridge stat -c '%U:%G:%a' /var/lib/arwc-contractor-bridge) == arwc-contractor-bridge:arwc-contractor-bridge:700 ]]
[[ $(docker exec cinder-arwc-approval stat -c '%U:%G:%a' /var/lib/arwc-approval) == arwc-approval:arwc-approval:700 ]]
[[ $(docker exec cinder-arwc-hmi stat -c '%U:%G:%a' /var/lib/arwc-hmi) == arwc-hmi:arwc-hmi:700 ]]
[[ $(docker exec cinder-arwc-historian stat -c '%U:%G:%a' /var/lib/arwc-historian) == arwc-historian:arwc-historian:700 ]]
[[ $(docker exec cinder-arwc-engineering stat -c '%U:%G:%a' /var/lib/arwc-engineering) == arwc-engineering:arwc-engineering:700 ]]
[[ $(docker exec cinder-arwc-instruments stat -c '%U:%G:%a' /var/lib/arwc-instruments) == arwc-instruments:arwc-instruments:700 ]]
[[ $(docker exec cinder-arwc-diagnostics stat -c '%U:%G:%a' /var/lib/arwc-diagnostics) == arwc-diagnostics:arwc-diagnostics:700 ]]
[[ $(docker exec --user arwc-approval cinder-arwc-approval /opt/chrome-headless-shell/chrome-headless-shell --no-sandbox --version) == *'128.0.6613.137'* ]]
[[ $(docker exec cinder-arwc-archive /usr/local/bin/7zz | sed -n '2p') == *'23.01'* ]]
for container in \
  cinder-arwc-connector cinder-arwc-business cinder-arwc-archive \
  cinder-arwc-identity cinder-arwc-data cinder-arwc-data-bridge \
  cinder-arwc-contractors cinder-arwc-contractor-bridge cinder-arwc-approval \
  cinder-arwc-hmi cinder-arwc-historian cinder-arwc-engineering cinder-arwc-instruments \
  cinder-arwc-diagnostics; do
  [[ $(docker inspect -f '{{.HostConfig.ReadonlyRootfs}}' "$container") == true ]]
  [[ $(docker inspect -f '{{json .HostConfig.CapDrop}}' "$container") == '["ALL"]' ]]
  [[ $(docker inspect -f '{{json .HostConfig.SecurityOpt}}' "$container") == *'no-new-privileges:true'* ]]
done
[[ $(docker network inspect -f '{{.Internal}}' cinder-arwc-corporate) == true ]]
[[ $(docker network inspect -f '{{.Internal}}' cinder-arwc-maintenance) == true ]]
[[ $(docker network inspect -f '{{.Internal}}' cinder-arwc-dmz) == true ]]
[[ $(docker network inspect -f '{{.Internal}}' cinder-arwc-engineering) == true ]]
[[ $(docker network inspect -f '{{.Internal}}' cinder-arwc-control) == true ]]
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

echo "Alterra W01-W22, W25, and W35 local acceptance passed"
