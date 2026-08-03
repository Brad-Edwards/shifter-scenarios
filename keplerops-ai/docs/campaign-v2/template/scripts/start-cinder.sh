#!/usr/bin/env bash
set -euo pipefail

readonly ROOT=${KEPLEROPS_V2_ROOT:-/opt/keplerops-v2}

cd "$ROOT"
if [[ ${KEPLEROPS_SKIP_PULL:-0} != 1 ]]; then
  docker compose --env-file component-lock.env -f compose.cinder.yaml pull
fi
docker compose --env-file component-lock.env -f compose.cinder.yaml up -d
docker restart kep-v2-caddy >/dev/null

deadline=$((SECONDS + 300))
while ((SECONDS < deadline)); do
  minio_state=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{end}}' \
    kep-v2-cinder-minio 2>/dev/null || true)
  forgejo_state=$(docker inspect --format '{{.State.Status}}' \
    kep-v2-cinder-forgejo 2>/dev/null || true)
  jupyter_state=$(docker inspect --format '{{.State.Status}}' \
    kep-v2-cinder-jupyter 2>/dev/null || true)
  bootstrap_state=$(docker inspect --format '{{.State.Status}} {{.State.ExitCode}}' \
    kep-v2-cinder-bootstrap 2>/dev/null || true)
  if [[ $minio_state == healthy && $forgejo_state == running &&
        $jupyter_state == running && $bootstrap_state == "exited 0" ]]; then
    install -d -m 0755 /run/shifter
    printf '%s\n' "$(cat /proc/sys/kernel/random/boot_id) cinder" \
      >/run/shifter/keplerops-v2-cinder.ready
    echo "campaign-v2 Cinder workbench services healthy"
    exit 0
  fi
  sleep 5
done

docker compose --env-file component-lock.env -f compose.cinder.yaml ps -a >&2
echo "campaign-v2 Cinder service readiness timeout" >&2
exit 1
