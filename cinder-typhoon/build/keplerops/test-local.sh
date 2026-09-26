#!/usr/bin/env bash
set -euo pipefail

ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
cd "$ROOT"
bash ./generate-operator-material.sh
docker compose -f compose.yaml --profile build-only build report-worker node-worker command-worker router k-dev k-source k-registry k-ci k-support k-cloud-api runner
docker compose -f compose.yaml up -d --force-recreate router runner k-source k-registry k-ci k-support k-cloud-api k-dev

for attempt in $(seq 1 30); do
  if docker exec --user rowan cinder-keplerops-k-dev curl -sS --fail \
      --cacert /home/rowan/.local/share/keplerops/ca.crt \
      -u rowan.ito:kpl_rowan_7X4mQ9vN2cL6 \
      https://source.keplerops.test/api/fieldkest/handovers/current >/dev/null; then
    break
  fi
  if [[ $attempt -eq 30 ]]; then
    echo "opening services did not become ready" >&2
    exit 1
  fi
  sleep 1
done

python3 tests/test_opening_live.py
python3 tests/test_registry_foundation_live.py
python3 tests/test_k09_live.py

docker run --rm --network cinder-keplerops-corporate \
  -v "$ROOT/.operator/rowan_ed25519:/run/rowan_ed25519:ro" \
  --entrypoint ssh cinder-keplerops/k-dev:hand-build \
  -i /run/rowan_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=no \
  -o UserKnownHostsFile=/dev/null rowan@10.77.50.20 true

job_count=$(docker exec cinder-keplerops-ci sh -c 'find /var/lib/fieldkest-ci/results -name "JOB-*.json" -type f | wc -l')
rehearsal_count=$(docker exec cinder-keplerops-ci sh -c 'find /var/lib/fieldkest-ci/results -name "REH-*.json" -type f | wc -l')
publication_count=$(docker exec cinder-keplerops-registry sh -c 'find /var/lib/fieldkest-registry/published -name "*.json" -type f | wc -l')
docker restart cinder-keplerops-ci cinder-keplerops-registry cinder-keplerops-support >/dev/null
for attempt in $(seq 1 20); do
  current=$(docker exec cinder-keplerops-ci sh -c 'find /var/lib/fieldkest-ci/results -name "JOB-*.json" -type f | wc -l')
  current_rehearsals=$(docker exec cinder-keplerops-ci sh -c 'find /var/lib/fieldkest-ci/results -name "REH-*.json" -type f | wc -l')
  current_publications=$(docker exec cinder-keplerops-registry sh -c 'find /var/lib/fieldkest-registry/published -name "*.json" -type f | wc -l')
  [[ $current -eq $job_count && $current_rehearsals -eq $rehearsal_count && $current_publications -eq $publication_count ]] && break
  sleep 1
done
[[ $current -eq $job_count ]]
[[ $current_rehearsals -eq $rehearsal_count ]]
[[ $current_publications -eq $publication_count ]]

[[ -z $(docker ps --format '{{.Names}}' --filter 'name=fieldkest-report-') ]]
[[ -z $(docker ps --format '{{.Names}}' --filter 'name=fieldkest-consumer-') ]]
[[ -z $(docker ps --format '{{.Names}}' --filter 'name=fieldkest-command-') ]]
[[ -z $(docker inspect -f '{{range $port, $bindings := .NetworkSettings.Ports}}{{if $bindings}}{{$port}}{{end}}{{end}}' \
  cinder-keplerops-k-dev cinder-keplerops-source cinder-keplerops-registry cinder-keplerops-ci cinder-keplerops-support cinder-keplerops-cloud-api) ]]

echo "PASS: KeplerOps K01-K09 opening, registry, and runner foundation"
