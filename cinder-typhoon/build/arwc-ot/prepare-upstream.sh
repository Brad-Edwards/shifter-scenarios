#!/bin/bash
# Run on the dedicated GCP compatibility VM, never on the local workstation.
set -euo pipefail
[[ $(hostname) == cinder-arwc-ot-compat-363 ]] || {
  echo 'Run this script on cinder-arwc-ot-compat-363.' >&2; exit 1;
}
test -f /var/lib/arwc-ot-compat-ready
root=/opt/arwc-ot-compat
install -d -m 0755 "$root/upstream" "$root/evidence"
cd "$root/upstream"
if [[ ! -d openplc-runtime ]]; then
  git clone --depth=1 --branch=v4.3.2 https://github.com/Autonomy-Logic/openplc-runtime.git
fi
if [[ ! -d openplc-editor ]]; then
  git clone --depth=1 --branch=v4.3.4 https://github.com/Autonomy-Logic/openplc-editor.git
fi
if [[ ! -d fuxa ]]; then
  git clone --depth=1 --branch=v1.3.5 https://github.com/frangoteam/FUXA.git fuxa
fi
curl --fail --silent --show-error --location --retry 3 \
  https://github.com/Autonomy-Logic/openplc-editor/releases/download/v4.3.4/OpenPLC.Editor-4.3.4.AppImage \
  --output OpenPLC.Editor-4.3.4.AppImage
sha256sum OpenPLC.Editor-4.3.4.AppImage
for image in ghcr.io/autonomy-logic/openplc-runtime:v4.3.2 \
    postgres:18.6-trixie eclipse-mosquitto:2.0.22 telegraf:1.39.1; do
  docker pull "$image"
  docker image inspect "$image" --format '{{json .RepoDigests}}'
done
