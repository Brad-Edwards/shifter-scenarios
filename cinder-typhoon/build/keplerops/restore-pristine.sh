#!/usr/bin/env bash
set -euo pipefail

ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
cd "$ROOT"

docker compose -f compose.yaml down -v --remove-orphans
docker compose -f compose.yaml up -d --force-recreate \
  router runner k-source k-registry k-ci k-preview k-support k-indexer \
  k-cloud-api k-workload k-data k-assistant k-staff k-identity k-cert \
  a-connector k-dev

for attempt in $(seq 1 60); do
  if docker exec --user rowan cinder-keplerops-k-dev curl -sS --fail \
      --cacert /home/rowan/.local/share/keplerops/ca.crt \
      -u rowan.ito:kpl_rowan_7X4mQ9vN2cL6 \
      https://source.keplerops.test/api/fieldkest/handovers/current >/dev/null; then
    break
  fi
  if [[ $attempt -eq 60 ]]; then
    echo "KeplerOps opening services did not initialize" >&2
    exit 1
  fi
  sleep 1
done

docker exec --user fieldkest-registry cinder-keplerops-registry \
  sh -c 'test -z "$(find /var/lib/fieldkest-registry/published -type f -print -quit)"'
docker exec --user fieldkest-ci cinder-keplerops-ci \
  sh -c 'test -z "$(find /var/lib/fieldkest-ci/results -type f \( -name "JOB-*.json" -o -name "REH-*.json" \) -print -quit)"'
docker exec --user fieldkest-support cinder-keplerops-support \
  python3 -c 'import json; from pathlib import Path; p=Path("/var/lib/fieldkest-support/extended.json"); raise SystemExit(0 if not p.exists() or json.loads(p.read_text()).get("diagnostics") == {} else 1)'

[[ $(docker inspect -f '{{.State.Status}}' cinder-keplerops-connector) == running ]]
docker exec cinder-keplerops-connector sh -c \
  'grep -q "^Uid:[[:space:]]*999[[:space:]]*999[[:space:]]*999[[:space:]]*999" /proc/1/status && grep -q "^CapBnd:[[:space:]]*0000000000000000" /proc/1/status && grep -q "^NoNewPrivs:[[:space:]]*1" /proc/1/status'

echo "KeplerOps authored pre-delivery state restored"
