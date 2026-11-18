#!/usr/bin/env bash
set -euo pipefail
ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
operator=${KEPLEROPS_OPERATOR_DIR:-./.operator}
images="$operator/native-platform/k3s-images"
mkdir -p "$images"
release=https://github.com/k3s-io/k3s/releases/download/v1.37.2%2Bk3s1
# Upstream sha256sum-amd64.txt value for this release. Range hosts have no
# internet route, so first boot must not fetch the checksum or the archive.
expected=35a5af1e69b57b8b627a4f6b1c29ea104209b661067b8c97fd40dc3f860bfcd2
archive="$images/k3s-airgap-images-amd64.tar.zst"
# A range image carries the verified archive outside .operator.
cache=${KEPLEROPS_K3S_CACHE:-/opt/cinder-typhoon/cache/keplerops-k3s}/k3s-airgap-images-amd64.tar.zst
if [[ ! -f $archive && -s $cache ]] && echo "$expected  $cache" | sha256sum --check --status; then
  cp -- "$cache" "$archive.part"
  mv -- "$archive.part" "$archive"
fi
if [[ ! -f $archive ]] || ! echo "$expected  $archive" | sha256sum --check --status; then
  curl --fail --location --silent --show-error "$release/k3s-airgap-images-amd64.tar.zst" >"$archive.part"
  echo "$expected  $archive.part" | sha256sum --check --status
  mv "$archive.part" "$archive"
fi
echo 'Matching native Kubernetes offline images verified.'
