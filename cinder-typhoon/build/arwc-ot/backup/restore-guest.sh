#!/bin/bash
# Run only as startup metadata on a separate restored verification VM.
set -euo pipefail
umask 077
[[ $EUID == 0 && $(hostname) == cinder-arwc-ot-restore-* ]] || exit 1
cd /opt/arwc-ot-compat/slice
systemctl start docker
plc_before=$(docker inspect --format '{{.Id}}' arwc-ot-compat-plc-1)
metadata=http://metadata.google.internal/computeMetadata/v1
address=$(curl --fail --silent --show-error --header 'Metadata-Flavor: Google' \
  "$metadata/instance/network-interfaces/0/ip")
[[ $address =~ ^10\.77\.59\.[0-9]+$ && $address != 10.77.59.6 ]] || exit 1
export ARWC_CARRIER_ADDRESS="$address"
export ARWC_OT_OPERATOR_DIR="$PWD/.operator"
it=/opt/arwc-ot-compat/it/cinder-typhoon/build/arwc
# Existing Docker restart policies restore the other services and their layers.
# Recreate only the published listener to use this VM's allocated private IP.
docker compose -f "$it/compose.yaml" -f "$PWD/integration/it-compose.yaml" \
  up -d --no-deps --no-build --pull never fieldlink-edge
[[ $(docker inspect --format '{{.Id}}' arwc-ot-compat-plc-1) == "$plc_before" ]]
[[ $(docker inspect --format '{{.State.Running}}' arwc-ot-compat-plc-1) == true ]]
touch /var/lib/arwc-ot-backup-restore.ready
echo 'Restored carrier listener configured; original PLC container preserved.'
