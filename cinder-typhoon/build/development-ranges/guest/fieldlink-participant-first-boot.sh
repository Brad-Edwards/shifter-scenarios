#!/usr/bin/env bash
set -euo pipefail

[[ $EUID == 0 && $(hostname) == cinder-fieldlink-participant ]] || exit 1
systemctl start docker

metadata=http://metadata.google.internal/computeMetadata/v1
address=$(curl --fail --silent --show-error --header 'Metadata-Flavor: Google' \
  "$metadata/instance/network-interfaces/0/ip")
[[ $address == 10.77.49.10 ]] || exit 1

for _ in $(seq 1 120); do
  if [[ $(docker inspect --format '{{.State.Running}}' cinder-keplerops-k-dev 2>/dev/null || true) == true ]] \
      && test -d /opt/cinder-typhoon/build/keplerops; then
    cd /opt/cinder-typhoon/build/keplerops
    if [[ -f native-platform/host-routing.py ]]; then
      python3 native-platform/host-routing.py
    fi
    # Keep the development relay away from the preserved golden peer.
    umask 077
    profile=$(mktemp .env.development.XXXXXX)
    trap 'rm -f -- "$profile"' EXIT
    if [[ -f .env ]]; then
      sed '/^ARWC_CARRIER_ADDRESS=/d' .env >"$profile"
    fi
    printf '\nARWC_CARRIER_ADDRESS=10.77.59.11\n' >>"$profile"
    mv "$profile" .env
    ARWC_CARRIER_ADDRESS=10.77.59.11 docker compose \
      up -d --no-deps --no-build --pull never a-connector
    docker inspect --format '{{range .HostConfig.ExtraHosts}}{{println .}}{{end}}' \
      cinder-keplerops-connector | grep -Fxq 'fieldlink.arwc.test:10.77.59.11'
    touch /var/lib/cinder-fieldlink-participant-ready
    exit 0
  fi
  sleep 5
done

echo 'FieldLink participant services did not become ready.' >&2
exit 1
