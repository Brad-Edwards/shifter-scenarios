#!/usr/bin/env bash

set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly ROOT
mode=${1:---static}

"${ROOT}/validate.py"
[[ ${mode} == --static ]] && exit 0

if [[ ${mode} == --all ]]; then
  while IFS= read -r module; do
    while IFS= read -r operation; do
      "${module}/validate.sh" "${operation}"
    done < <(jq -r '.[].id' "${module}/operations.json")
  done < <(find "${ROOT}/modules" -mindepth 1 -maxdepth 1 \
    -type d -name 'm??' -print | sort)
  exit 0
fi

operation=${mode}
while IFS= read -r module; do
  if jq -e --arg id "${operation}" '.[] | select(.id == $id)' \
    "${module}/operations.json" >/dev/null; then
    exec "${module}/validate.sh" "${operation}"
  fi
done < <(find "${ROOT}/modules" -mindepth 1 -maxdepth 1 \
  -type d -name 'm??' -print | sort)

printf 'unknown campaign operation: %s\n' "${operation}" >&2
exit 2
