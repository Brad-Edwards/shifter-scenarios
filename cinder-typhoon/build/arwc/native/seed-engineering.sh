#!/usr/bin/env bash
set -euo pipefail
[[ $(hostname) == cinder-arwc-dev ]] || exit 1
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
bash capture-retained-tools.sh
set -a
# shellcheck disable=SC1091
source .operator/engineering-seed.env
set +a
compose=(docker compose --env-file images.env -f compose.yaml -f corporate.compose.yaml -f dmz.compose.yaml)
# The script variables expand in the container shell.
# shellcheck disable=SC2016
"${compose[@]}" exec -T --user git \
  --env GITEA_ADMIN_PASSWORD --env CLARA_PASSWORD --env THEO_PASSWORD gitea sh -ec '
  config=/data/gitea/conf/app.ini
  for username in engineering-admin clara.morivelle theo.marrivel; do
    if gitea --config "$config" admin user list | awk "{print \$2}" | grep -qx "$username"; then continue; fi
    case "$username" in
      engineering-admin) password=$GITEA_ADMIN_PASSWORD; email=engineering.admin@alterrawaterco.com; admin=true ;;
      clara.morivelle) password=$CLARA_PASSWORD; email=clara.morivelle@alterrawaterco.com; admin=false ;;
      theo.marrivel) password=$THEO_PASSWORD; email=theo.marrivel@alterrawaterco.com; admin=false ;;
    esac
    gitea --config "$config" admin user create --username "$username" --email "$email" \
      --password "$password" --admin="$admin" --must-change-password=false >/dev/null 2>&1
  done
  '
"${compose[@]}" --profile seed run --rm seed-engineering
