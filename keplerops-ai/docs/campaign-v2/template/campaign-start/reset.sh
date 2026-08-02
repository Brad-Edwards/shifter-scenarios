#!/usr/bin/env bash

set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly ROOT
operation=${1:?Usage: reset.sh <operation-id>}

while IFS= read -r module; do
  if jq -e --arg id "${operation}" '.[] | select(.id == $id)' \
    "${module}/operations.json" >/dev/null; then
    exec "${module}/reset.sh" "${operation}"
  fi
done < <(find "${ROOT}/modules" -mindepth 1 -maxdepth 1 \
  -type d -name 'm??' -print | sort)

printf 'unknown campaign operation: %s\n' "${operation}" >&2
exit 2
