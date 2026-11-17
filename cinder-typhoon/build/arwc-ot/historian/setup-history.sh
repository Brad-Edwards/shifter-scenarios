#!/bin/bash
# Manual development setup, using the already running site products.
set -euo pipefail
[[ $(hostname) == cinder-arwc-ot-compat-363 ]] || exit 1
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
[[ $PWD == /opt/arwc-ot-compat/slice ]] || exit 1
base=(sudo docker compose -f compose.yaml -f site/compose.yaml)
"${base[@]}" run --rm -T tools python /slice/historian/prepare.py
history=("${base[@]}" -f historian/compose.yaml)
"${history[@]}" config -q
"${history[@]}" run --rm -T history-maintenance python /slice/historian/maintain.py --once
"${history[@]}" up -d history-maintenance alarm-export
"${history[@]}" up -d --force-recreate telegraf
"${history[@]}" restart grafana
echo 'Native site acquisition and alarm export are running; operator controls were not restarted.'
