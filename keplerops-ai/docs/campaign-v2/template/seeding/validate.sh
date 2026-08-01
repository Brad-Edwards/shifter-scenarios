#!/usr/bin/env bash

set -Eeuo pipefail

SEEDING_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mapfile -t shell_files < <(find "${SEEDING_ROOT}" -type f -name '*.sh' -print | sort)
for file in "${shell_files[@]}"; do
  bash -n "${file}"
done

if command -v shellcheck >/dev/null 2>&1; then
  shellcheck -x -P SCRIPTDIR "${shell_files[@]}"
else
  printf '[campaign-v2-seed] shellcheck unavailable; bash -n validation only\n' >&2
fi

jq -e . "${SEEDING_ROOT}/payloads/stalwart-principals.json" >/dev/null
printf '[campaign-v2-seed] validated %d shell files and static JSON\n' "${#shell_files[@]}" >&2
