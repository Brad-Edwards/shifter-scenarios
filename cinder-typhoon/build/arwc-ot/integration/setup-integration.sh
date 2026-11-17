#!/bin/bash
# Apply only after coordinating PostgreSQL restart with active desktop QA.
set -euo pipefail
[[ $(hostname) == cinder-arwc-ot-compat-363 ]] || exit 1
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
[[ $PWD == /opt/arwc-ot-compat/slice ]] || exit 1
python3 integration/check_contract.py
base=(sudo docker compose -f compose.yaml -f site/compose.yaml)
"${base[@]}" run --rm -T tools python /slice/integration/prepare.py
joined=("${base[@]}" -f historian/compose.yaml -f dispatch/compose.yaml \
  -f workstation/compose.yaml -f integration/compose.yaml)
"${joined[@]}" up -d postgres
it=/opt/arwc-ot-compat/it/cinder-typhoon/build/arwc
if [[ ! -s $it/.operator/tls/ca.key ]]; then
  (cd "$it" && bash generate-operator-material.sh)
fi
export ARWC_OT_OPERATOR_DIR="$PWD/.operator"
export ARWC_CARRIER_ADDRESS=10.77.59.6
sudo --preserve-env=ARWC_OT_OPERATOR_DIR,ARWC_CARRIER_ADDRESS docker compose \
  -f "$it/compose.yaml" -f "$PWD/integration/it-compose.yaml" up -d --no-build
echo 'Joined existing IT services and the read-only historical data bridge.'
