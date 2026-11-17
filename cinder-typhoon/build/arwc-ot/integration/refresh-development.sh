#!/bin/bash
# Apply reviewed development settings after QA saves and pauses its work.
set -euo pipefail
[[ $(hostname) == cinder-arwc-ot-compat-363 ]] || exit 1
[[ $EUID != 0 ]] || exit 1
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
[[ $PWD == /opt/arwc-ot-compat/slice ]] || exit 1
python3 integration/check_contract.py
plc_before=$(sudo docker inspect --format '{{.Id}}' arwc-ot-compat-plc-1)
joined=(sudo docker compose -f compose.yaml -f site/compose.yaml \
  -f historian/compose.yaml -f dispatch/compose.yaml \
  -f workstation/compose.yaml -f integration/compose.yaml)
sudo bash workstation/prepare-handover.sh
# Explicit targets and --no-deps keep the PLC's container layer intact.
"${joined[@]}" up -d --no-deps --no-build --pull never \
  io fuxa postgres telegraf mosquitto grafana engineering \
  history-maintenance alarm-export site-dispatcher
sudo python3 workstation/provision.py
it=/opt/arwc-ot-compat/it/cinder-typhoon/build/arwc
export ARWC_OT_OPERATOR_DIR="$PWD/.operator"
export ARWC_CARRIER_ADDRESS=10.77.59.6
sudo --preserve-env=ARWC_OT_OPERATOR_DIR,ARWC_CARRIER_ADDRESS docker compose \
  -f "$it/compose.yaml" -f "$PWD/integration/it-compose.yaml" \
  up -d --no-deps --no-build --pull never
[[ $(sudo docker inspect --format '{{.Id}}' arwc-ot-compat-plc-1) == "$plc_before" ]]
[[ $(sudo docker inspect --format '{{.State.Running}}' arwc-ot-compat-plc-1) == true ]]
echo 'Development configuration applied; PLC container preserved. Resume through QA.'
