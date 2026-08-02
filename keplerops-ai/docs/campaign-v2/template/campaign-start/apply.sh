#!/usr/bin/env bash

set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly ROOT
operation=${1:-}

mapfile -t modules < <(find "${ROOT}/modules" -mindepth 1 -maxdepth 1 \
  -type d -name 'm??' -print | sort)
[[ ${#modules[@]} -eq 10 ]] || {
  printf 'expected ten campaign modules, found %d\n' "${#modules[@]}" >&2
  exit 2
}

for module in "${modules[@]}"; do
  [[ -x ${module}/apply.sh ]] || {
    printf 'module apply script is unavailable: %s\n' "${module}/apply.sh" >&2
    exit 2
  }
  if [[ -n ${operation} ]]; then
    jq -e --arg id "${operation}" '.[] | select(.id == $id)' \
      "${module}/operations.json" >/dev/null || continue
    exec "${module}/apply.sh" "${operation}"
  fi
  "${module}/apply.sh"
done

[[ -z ${operation} ]] || {
  printf 'unknown campaign operation: %s\n' "${operation}" >&2
  exit 2
}
