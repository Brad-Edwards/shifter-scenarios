#!/usr/bin/env bash
set -euo pipefail

[[ $EUID == 0 && $(hostname) == cinder-fieldlink-dev ]] || exit 1
systemctl start docker

metadata=http://metadata.google.internal/computeMetadata/v1
address=$(curl --fail --silent --show-error --header 'Metadata-Flavor: Google' \
  "$metadata/instance/network-interfaces/0/ip")
[[ $address == 10.77.49.* ]] || exit 1

for _ in $(seq 1 120); do
  if [[ $(docker inspect --format '{{.State.Running}}' cinder-keplerops-k-dev 2>/dev/null || true) == true ]] \
      && test -d /opt/cinder-typhoon/build/keplerops; then
    touch /var/lib/cinder-fieldlink-development-ready
    exit 0
  fi
  sleep 5
done

echo 'FieldLink development services did not become ready.' >&2
exit 1
