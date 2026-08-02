#!/usr/bin/env bash

set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly ROOT
mode=${1:---static}

"${ROOT}/validate.py"
[[ ${mode} == --static ]] && exit 0

if [[ ${mode} == --all ]]; then
  evidence_manifest=${CAMPAIGN_EVIDENCE_MANIFEST:-}
  [[ -r ${evidence_manifest} ]] || {
    printf 'CAMPAIGN_EVIDENCE_MANIFEST must name the participant walkthrough evidence JSON\n' >&2
    exit 2
  }
  while IFS= read -r module; do
    while IFS= read -r operation; do
      mapfile -t encoded_environment < <(
        jq -er --arg operation "${operation}" '
          .[$operation] as $entry |
          if ($entry | type) != "object" then
            error("missing evidence for " + $operation)
          else
            $entry | to_entries[] |
            select(.key | test("^(PARTICIPANT|M[0-9]{2})_[A-Z0-9_]+$")) |
            select(.value | type == "string") |
            ((.key + "=" + .value) | @base64)
          end
        ' "${evidence_manifest}"
      )
      (( ${#encoded_environment[@]} > 0 )) || {
        printf 'participant evidence is empty for %s\n' "${operation}" >&2
        exit 2
      }
      environment=()
      for encoded in "${encoded_environment[@]}"; do
        environment+=("$(base64 -d <<<"${encoded}")")
      done
      env "${environment[@]}" "${module}/validate.sh" "${operation}"
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
