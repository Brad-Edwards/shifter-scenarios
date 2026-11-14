#!/bin/bash
# Import on the approved persistent development VM; do not provision a range.
set -euo pipefail
[[ $(hostname) == cinder-arwc-ot-compat-363 ]] || exit 1
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
[[ $PWD == /opt/arwc-ot-compat/slice ]] || exit 1
sudo docker compose -f compose.yaml -f site/compose.yaml run --rm -T tools python /slice/hmi/import_project.py
sudo docker compose -f compose.yaml -f site/compose.yaml restart fuxa
