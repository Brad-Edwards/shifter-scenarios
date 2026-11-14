#!/usr/bin/env bash
set -euo pipefail

root=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
cd "$root"

for service in fieldlink-dns fieldlink-edge fieldlink-postgres; do
  container=$(docker compose -f compose.yaml ps -q "$service")
  [[ -n $container ]]
  [[ $(docker inspect --format '{{.State.Health.Status}}' "$container") == healthy ]]
done

docker exec cinder-keplerops-foundation-dns \
  sh -c "dig @127.0.0.1 example.com | grep -q 'status: REFUSED'"
docker exec cinder-keplerops-k-dev getent hosts edge.keplerops.test \
  | grep -q '10.77.50.11'
docker exec cinder-keplerops-k-dev curl -fsS \
  --cacert /run/fieldkest-auth/ca.crt \
  https://edge.keplerops.test/health \
  | grep -qx 'fieldlink foundation ready'

if docker exec cinder-keplerops-foundation-edge \
    wget -T 3 -qO- https://example.com >/dev/null 2>&1; then
  echo 'foundation edge reached the Internet' >&2
  exit 1
fi
if docker exec cinder-keplerops-k-dev \
    curl --connect-timeout 3 -fsS https://example.com >/dev/null 2>&1; then
  echo 'participant desktop reached the Internet' >&2
  exit 1
fi

# Prove that the named product volume survives a container restart.
docker exec cinder-keplerops-foundation-postgres sh -ec \
  'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "CREATE TABLE IF NOT EXISTS foundation_restart_check (value text PRIMARY KEY); INSERT INTO foundation_restart_check VALUES ('"'"'present'"'"') ON CONFLICT DO NOTHING;" >/dev/null'
docker restart cinder-keplerops-foundation-postgres >/dev/null
for _ in $(seq 1 30); do
  [[ $(docker inspect --format '{{.State.Health.Status}}' cinder-keplerops-foundation-postgres) == healthy ]] && break
  sleep 2
done
docker exec cinder-keplerops-foundation-postgres sh -ec \
  'test "$(psql -At -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT value FROM foundation_restart_check")" = present'
docker exec cinder-keplerops-foundation-postgres sh -ec \
  'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "DROP TABLE foundation_restart_check" >/dev/null'

docker exec cinder-keplerops-k-dev curl -fsS \
  --cacert /home/rowan/.local/share/keplerops/ca.crt \
  https://source.keplerops.test/user/login >/dev/null

echo 'FieldLink foundation live checks passed.'
