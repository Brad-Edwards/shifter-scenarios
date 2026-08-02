#!/usr/bin/env bash
set -euo pipefail

readonly ROOT=${KEPLEROPS_V2_ROOT:-/opt/keplerops-v2}
readonly CONTAINER=keplerops-participant-workstation-runtime

set -a
# shellcheck disable=SC1091
source "$ROOT/component-lock.env"
set +a

"$ROOT/scripts/prepare-workstation.sh"

if docker inspect "$CONTAINER" >/dev/null 2>&1; then
  project=$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project"}}' \
    "$CONTAINER" 2>/dev/null || true)
  if [[ $project != keplerops-v2 ]]; then
    docker rm -f "$CONTAINER" >/dev/null
  fi
fi

cd "$ROOT"
if ! docker image inspect "$CINDER_WORKSTATION_IMAGE" >/dev/null 2>&1; then
  docker compose --env-file component-lock.env -f compose.workbench.yaml \
    build participant-workstation
fi
docker compose --env-file component-lock.env -f compose.workbench.yaml up -d

deadline=$((SECONDS + 180))
until docker exec "$CONTAINER" sh -c \
  'ss -lnt | grep -q ":3389 " && ss -lnt | grep -q ":6901 "'; do
  if ((SECONDS >= deadline)); then
    docker logs --tail 100 "$CONTAINER" >&2
    echo "campaign-v2 workstation readiness timeout" >&2
    exit 1
  fi
  sleep 5
done

docker exec --user root "$CONTAINER" update-ca-certificates >/dev/null
docker exec --user kasm-user --env HOME=/home/kasm-user "$CONTAINER" sh -lc '
  install -d -m 0700 "$HOME/.pki/nssdb"
  certutil -D -d "sql:$HOME/.pki/nssdb" -n KeplerOps-Range-CA >/dev/null 2>&1 || true
  certutil -A -d "sql:$HOME/.pki/nssdb" -n KeplerOps-Range-CA -t "C,," \
    -i /usr/local/share/ca-certificates/keplerops-range-root.crt
'

docker exec --user kasm-user --env HOME=/home/kasm-user "$CONTAINER" \
  opencode --version >/dev/null

"$ROOT/scripts/workstation-access.sh" check

install -d -m 0755 /run/shifter
printf '%s\n' "$(cat /proc/sys/kernel/random/boot_id) workstation" \
  >/run/shifter/keplerops-v2-workstation.ready
echo "campaign-v2 participant workstation healthy"
