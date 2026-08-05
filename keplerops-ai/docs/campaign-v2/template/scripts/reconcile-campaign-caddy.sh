#!/usr/bin/env bash
# Reconcile the campaign Caddy config on resume.
#
# The caddy container starts with `caddy run --config /etc/caddy/Caddyfile` (the
# base file). campaign-start/apply.sh assembles the base plus every module
# runtime/Caddyfile.fragment and reloads caddy, but that assembly lives in
# apply.sh, which resume skips (modules are already applied and baked). On a
# from-bake boot the caddy container therefore serves only the base routes,
# missing fragment-only sites (e.g. operations.keplerops.lab,
# vision-research.cinder.lab). Re-assemble base + fragments and reload so every
# route is present. Best-effort: always exits 0 so it can never block a boot;
# check-all remains the source of truth.
set -uo pipefail

readonly ROOT=${KEPLEROPS_V2_ROOT:-/opt/keplerops-v2}

docker inspect kep-v2-caddy >/dev/null 2>&1 || {
  echo "reconcile-campaign-caddy: caddy container absent; skipping" >&2
  exit 0
}

{
  cat "${ROOT}/config/caddy/Caddyfile"
  find "${ROOT}/campaign-start/modules" -path '*/runtime/Caddyfile.fragment' \
    -type f -print0 | sort -z | xargs -0 -r cat
} | docker exec -i kep-v2-caddy sh -eu -c 'cat >/tmp/Caddyfile.campaign-v2'

if docker exec kep-v2-caddy caddy validate \
  --config /tmp/Caddyfile.campaign-v2 --adapter caddyfile >/dev/null 2>&1; then
  if docker exec kep-v2-caddy caddy reload \
    --config /tmp/Caddyfile.campaign-v2 --adapter caddyfile >/dev/null 2>&1; then
    echo "reconcile-campaign-caddy: campaign routes reloaded"
  else
    echo "reconcile-campaign-caddy: reload failed; leaving base config" >&2
  fi
else
  echo "reconcile-campaign-caddy: assembled config did not validate; leaving base config" >&2
fi
exit 0
