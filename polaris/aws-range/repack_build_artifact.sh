#!/usr/bin/env bash
# Rebuild the event-layout archive strictly from Polaris pack source.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
pack_root="$(cd "$script_dir/.." && pwd)"
pack_parent="$(dirname "$pack_root")"
pack_name="$(basename "$pack_root")"
if [[ "$pack_name" != "polaris" ]]; then
    echo "expected a pack directory named polaris, got: $pack_name" >&2
    exit 1
fi

build_root="polaris/build"
archive="${pack_root}/build/build-v1.tar.gz"
sidecar="${archive}.sha256"
file_list="$(mktemp /tmp/polaris-build-files.XXXXXX)"
staged_archive="$(mktemp /tmp/polaris-build-v1.XXXXXX.tar.gz)"
trap 'rm -f "$file_list" "$staged_archive"' EXIT

(
    cd "$pack_parent"
    find "$build_root" \
        -type f \
        ! -path "${build_root}/build-v1.tar.gz" \
        ! -path "${build_root}/build-v1.tar.gz.sha256" \
        ! -path '*/__pycache__/*' \
        ! -name '*.pyc' \
        ! -name 'docker-compose.override.yml' \
        -print0
    printf '%s\0' \
        "polaris/contract_source.py" \
        "polaris/flags/placement.yaml"
) | LC_ALL=C sort -z > "$file_list"

tar -C "$pack_parent" \
    --null -T "$file_list" \
    --sort=name \
    --mtime="UTC 2026-07-28" \
    --owner=0 --group=0 --numeric-owner \
    -czf "$staged_archive"

mv "$staged_archive" "$archive"
chmod 0644 "$archive"
(
    cd "$(dirname "$archive")"
    sha256sum "$(basename "$archive")" > "$(basename "$sidecar")"
)
