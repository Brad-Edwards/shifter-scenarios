#!/usr/bin/env bash
set -euo pipefail

readonly CONTAINER=kep-v2-step-ca

source_config=$(mktemp)
updated_config=$(mktemp)
trap 'rm -f "$source_config" "$updated_config"' EXIT

# On a cold/fresh standup, `docker compose up -d step-ca` returns as soon as the
# container starts, before step-ca has generated /home/step/config/ca.json. The
# reconcile below copies that file out, so wait for step-ca to materialize it
# (and become healthy) before touching it. Without this, a fresh build fails at
# `docker cp ... ca.json` under `set -e`. See issue #50 (participant-pass hotfix
# coordination): the cold-start reconcile-step-ca race.
ca_ready_deadline=$((SECONDS + 180))
until docker exec "$CONTAINER" test -s /home/step/config/ca.json >/dev/null 2>&1; do
  if ((SECONDS >= ca_ready_deadline)); then
    echo "step-ca did not generate ca.json before reconciliation" >&2
    exit 1
  fi
  sleep 2
done

docker cp "$CONTAINER:/home/step/config/ca.json" "$source_config"
jq '
  .authority.claims = ((.authority.claims // {}) + {
    minTLSCertDuration: "5m",
    defaultTLSCertDuration: "24h",
    maxTLSCertDuration: "720h",
    disableRenewal: false
  })
' "$source_config" >"$updated_config"

if cmp -s "$source_config" "$updated_config" && \
  docker exec "$CONTAINER" test -f /home/step/config/.keplerops-lifetime-policy-v1; then
  echo "step-ca certificate lifetime policy already reconciled"
  exit 0
fi

docker cp "$updated_config" "$CONTAINER:/home/step/config/ca.json"
docker exec --user 0:0 "$CONTAINER" chown 1000:1000 /home/step/config/ca.json
docker exec --user 0:0 "$CONTAINER" touch /home/step/config/.keplerops-lifetime-policy-v1
docker exec --user 0:0 "$CONTAINER" chown 1000:1000 /home/step/config/.keplerops-lifetime-policy-v1
docker restart "$CONTAINER" >/dev/null

deadline=$((SECONDS + 120))
until [[ $(docker inspect --format '{{.State.Health.Status}}' "$CONTAINER" 2>/dev/null || true) == healthy ]]; do
  if ((SECONDS >= deadline)); then
    echo "step-ca did not become healthy after policy reconciliation" >&2
    exit 1
  fi
  sleep 2
done

echo "step-ca certificate lifetime policy reconciled"
