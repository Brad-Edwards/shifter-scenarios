#!/bin/bash
# Development setup only. Final participant credentials come from BigRAE.
set -euo pipefail
[[ $(hostname) == cinder-arwc-ot-compat-363 ]] || exit 1
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
[[ $PWD == /opt/arwc-ot-compat/slice ]] || exit 1
python3 workstation/check_contract.py
sudo docker compose -f compose.yaml -f site/compose.yaml -f workstation/compose.yaml up -d engineering
sudo python3 workstation/provision.py
