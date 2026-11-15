#!/usr/bin/env bash
set -euo pipefail
ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
operator=${KEPLEROPS_OPERATOR_DIR:-./.operator}
images="$operator/native-platform/k3s-images"
mkdir -p "$images"
release=https://github.com/k3s-io/k3s/releases/download/v1.37.2%2Bk3s1
checksum=$(mktemp)
trap 'rm -f -- "$checksum"' EXIT
curl --fail --location --silent --show-error "$release/sha256sum-amd64.txt" >"$checksum"
expected=$(awk '$2 == "k3s-airgap-images-amd64.tar.zst" {print $1}' "$checksum")
[[ $expected =~ ^[a-f0-9]{64}$ ]] || { echo 'Upstream image checksum missing.' >&2; exit 1; }
archive="$images/k3s-airgap-images-amd64.tar.zst"
if [[ ! -f $archive ]] || ! echo "$expected  $archive" | sha256sum --check --status; then
  curl --fail --location --silent --show-error "$release/k3s-airgap-images-amd64.tar.zst" >"$archive.part"
  echo "$expected  $archive.part" | sha256sum --check --status
  mv "$archive.part" "$archive"
fi
echo 'Matching native Kubernetes offline images verified.'
