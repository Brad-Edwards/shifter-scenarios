#!/bin/bash
# Coordinate with active QA before applying broker changes or starting requests.
set -euo pipefail
[[ $(hostname) == cinder-arwc-ot-compat-363 ]] || exit 1
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
[[ $PWD == /opt/arwc-ot-compat/slice ]] || exit 1
base=(sudo docker compose -f compose.yaml -f site/compose.yaml)
"${base[@]}" stop dispatcher
"${base[@]}" run --rm -T tools python /slice/dispatch/prepare.py
dispatch=("${base[@]}" -f dispatch/compose.yaml)
"${dispatch[@]}" config -q
"${dispatch[@]}" restart mosquitto
"${dispatch[@]}" up -d site-dispatcher
echo 'The fixed two-outlet dispatcher is running; no request was sent by setup.'
