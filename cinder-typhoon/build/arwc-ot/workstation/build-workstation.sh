#!/bin/bash
# Manual offline image build on the approved development VM.
set -euo pipefail
[[ $(hostname) == cinder-arwc-ot-compat-363 ]] || exit 1
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
[[ $PWD == /opt/arwc-ot-compat/slice ]] || exit 1
python3 workstation/check_contract.py
python3 workstation/prepare_assets.py
release=.operator/workstation-release
rm -rf -- "$release"
mkdir -p "$release"
cp workstation/Dockerfile workstation/entrypoint.sh workstation/startwm.sh workstation/launch-editor.sh workstation/firefox-policies.json "$release/"
cp workstation/participant-readiness.json "$release/"
cp ../participant-host/shifter-participant-readiness "$release/"
cp -r workstation/desktop workstation/docs "$release/"
for operation in W17 W18 W21 W25 W29 W30 W33; do
  mkdir -p "$release/challenges/$operation"
  cp "challenges/$operation"/participant/* "$release/challenges/$operation/"
done
cp site/tags.json "$release/docs/tags.json"
if [[ -f dispatch/contract.json ]]; then
  cp dispatch/contract.json "$release/docs/remote-request.json"
fi
python3 workstation/reference.py "$release/docs"
# The separate named context contains public, checksummed dependencies only.
sudo docker build --build-context "desktop-assets=$PWD/.operator/workstation-assets" \
  --file workstation/Dockerfile --tag arwc-ot-engineering:368 "$release" \
  >.operator/workstation-image-build.log 2>&1
sudo docker image inspect --format '{{.Id}}' arwc-ot-engineering:368
