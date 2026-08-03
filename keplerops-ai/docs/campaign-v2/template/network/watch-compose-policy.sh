#!/usr/bin/env bash
set -Eeuo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
APPLY=${APPLY_COMPOSE_POLICY:-$ROOT/apply-compose-policy.sh}

[[ $EUID -eq 0 ]] || {
  echo "watch-compose-policy.sh must run as root" >&2
  exit 2
}

"$APPLY" apply
docker events --format '{{json .}}' --filter type=container --filter event=start --filter event=die |
  while IFS= read -r event; do
    container=$(jq -r '.Actor.Attributes.name // empty' <<<"$event")
    [[ -n $container ]] || continue
    if docker inspect "$container" --format '{{json .NetworkSettings.Networks}}' 2>/dev/null |
      jq -e 'keys | any(startswith("kep-v2-"))' >/dev/null; then
      sleep 1
      "$APPLY" apply
    elif [[ $(jq -r '.status // empty' <<<"$event") == die ]]; then
      "$APPLY" apply
    fi
  done
