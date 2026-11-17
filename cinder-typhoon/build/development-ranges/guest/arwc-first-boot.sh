#!/usr/bin/env bash
set -euo pipefail

[[ $EUID == 0 && $(hostname) == cinder-arwc-dev ]] || exit 1
systemctl start docker
cd /opt/arwc-ot-compat/slice

for attempt in $(seq 1 120); do
  if [[ $(docker inspect --format '{{.State.Running}}' arwc-ot-compat-plc-1 2>/dev/null || true) == true ]]; then
    break
  fi
  [[ $attempt != 120 ]] || {
    echo 'ARWC PLC did not become ready.' >&2
    exit 1
  }
  sleep 5
done

plc_before=$(docker inspect --format '{{.Id}}' arwc-ot-compat-plc-1)
metadata=http://metadata.google.internal/computeMetadata/v1
address=$(curl --fail --silent --show-error --header 'Metadata-Flavor: Google' \
  "$metadata/instance/network-interfaces/0/ip")
[[ $address == 10.77.59.11 ]] || exit 1

export ARWC_CARRIER_ADDRESS=$address
export ARWC_OT_OPERATOR_DIR=$PWD/.operator
it=/opt/arwc-ot-compat/it/cinder-typhoon/build/arwc
docker compose -f "$it/compose.yaml" -f "$PWD/integration/it-compose.yaml" \
  up -d --no-deps --no-build --pull never fieldlink-edge

[[ $(docker inspect --format '{{.Id}}' arwc-ot-compat-plc-1) == "$plc_before" ]]
[[ $(docker inspect --format '{{.State.Running}}' arwc-ot-compat-plc-1) == true ]]
touch /var/lib/cinder-arwc-development-ready
