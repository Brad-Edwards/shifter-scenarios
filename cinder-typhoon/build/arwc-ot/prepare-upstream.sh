#!/bin/bash
# Run on the dedicated GCP compatibility VM, never on the local workstation.
set -euo pipefail
[[ $(hostname) == cinder-arwc-ot-compat-363 ]] || {
  echo 'Run this script on cinder-arwc-ot-compat-363.' >&2; exit 1;
}
test -f /var/lib/arwc-ot-compat-ready
apt-get update
apt-get install -y libgtk-3-0 libnss3 libasound2 libgbm1 libxss1 libx11-xcb1 libdrm2 xvfb xauth x11-utils ripgrep
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
[[ $(git -c safe.directory="$PWD/openplc-runtime" -C openplc-runtime rev-parse HEAD) == 9fb5e1a29b574806f5aea3a4e78202c7a5d658ee ]]
[[ $(git -c safe.directory="$PWD/openplc-editor" -C openplc-editor rev-parse HEAD) == 9e979504193b1fbacf87112822438664a1f7b11a ]]
[[ $(git -c safe.directory="$PWD/fuxa" -C fuxa rev-parse HEAD) == cf0a44c750c0ab89ef0e86ade9fb97fd0613ffca ]]
curl --fail --silent --show-error --location --retry 3 \
  https://github.com/Autonomy-Logic/openplc-editor/releases/download/v4.3.4/OpenPLC.Editor-4.3.4.AppImage \
  --output OpenPLC.Editor-4.3.4.AppImage
printf '%s  %s\n' b81863722d65eaa786f53234472601b649ea34a3f2f790f931beedaa7ec75fa0 OpenPLC.Editor-4.3.4.AppImage | sha256sum --check
chmod a+x OpenPLC.Editor-4.3.4.AppImage
for image in ghcr.io/autonomy-logic/openplc-runtime:v4.3.2@sha256:378deec33b371eb09f8344e714d88b48efc7387f631f793371ba9f6a6e381c9f \
    frangoteam/fuxa:1.3.5@sha256:931781ce0557304d5b3b51e3d2ddb180dd2252b5e4b9936be7fd935bf5c62a2a \
    postgres:18.6-trixie@sha256:e3d24f6906d0760bf4da0dae872415391ededefad23fd471c47dc53b0ddf3c42 \
    eclipse-mosquitto:2.0.22@sha256:81a6193ae693942a3231cd3ac52875b02b7e3a19da671b2fb4b55cc874c5b279 \
    telegraf:1.39.1@sha256:8c1bc372ffa128be2febfe25f1fe092333d3d6c2293cf5e57176582179ba358a \
    grafana/grafana:12.2.1@sha256:35c41e0fd0295f5d0ee5db7e780cf33506abfaf47686196f825364889dee878b; do
  docker pull "$image"
  docker image inspect "$image" --format '{{json .RepoDigests}}'
done
