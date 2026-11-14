#!/usr/bin/env bash
set -euo pipefail
umask 077
[[ $(hostname) == cinder-arwc-dev ]] || exit 1
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
[[ $PWD == /opt/arwc-ot-compat/slice ]] || exit 1
assets=$PWD/.operator/workstation-assets
desktop=cinder-arwc-ot-engineering
stage=$(mktemp -d /tmp/arwc-git-debs.XXXXXX)
trap 'rm -rf -- "$stage"' EXIT
base=$(python3 -c 'import json; print(json.load(open("workstation/contract.json"))["base"])')
docker cp "$desktop:/var/lib/dpkg/status" "$stage/status"
mkdir -p "$stage/cache/partial"
docker run --rm --platform linux/amd64 --entrypoint bash \
  --mount "type=bind,src=$stage,dst=/download" "$base" -ec '
  rm -f /etc/apt/apt.conf.d/docker-clean
  apt-get update >/dev/null
  apt-get -o Dir::State::status=/download/status -o Dir::Cache::archives=/download/cache \
    install --download-only --no-install-recommends -y git
  '
cp "$stage"/cache/*.deb "$assets/debs/"
(
  cd "$assets"
  find debs wheels editor.AppImage requirements.lock -type f -print0 \
    | LC_ALL=C sort -z | xargs -0 sha256sum > SHA256SUMS
)
docker exec --user 0 "$desktop" install -d /tmp/arwc-git-debs
for package in "$stage"/cache/*.deb; do
  docker cp "$package" "$desktop:/tmp/arwc-git-debs/"
done
docker exec --user 0 "$desktop" sh -ec 'dpkg -i /tmp/arwc-git-debs/*.deb >/dev/null'
echo 'Git dependencies are in the offline bundle and installed on the development desktop.'
