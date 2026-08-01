#!/usr/bin/env bash

set -Eeuo pipefail

readonly FORGEJO_API_URL=http://10.61.40.20:3000/api/v1
readonly FORGEJO_AUTH=range-admin:KeplerV2-Training-Forgejo-Admin
readonly REPOSITORY=keplerops/orion-build
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR

if [[ ${EUID} -ne 0 ]]; then
  printf 'reconcile-release-risk-source.sh must run as root\n' >&2
  exit 2
fi

for command in base64 curl jq; do
  command -v "${command}" >/dev/null || {
    printf 'missing required command: %s\n' "${command}" >&2
    exit 1
  }
done

api() {
  local method=$1
  local path=$2
  shift 2
  curl --silent --show-error --fail-with-body \
    --user "${FORGEJO_AUTH}" \
    --header 'Content-Type: application/json' \
    --request "${method}" "$@" "${FORGEJO_API_URL}${path}"
}

ensure_file() {
  local relative=$1
  local source=$2
  local content existing payload sha
  content="$(base64 <"${source}" | tr -d '\n')"
  if payload="$(api GET "/repos/${REPOSITORY}/contents/${relative}" 2>/dev/null)" && \
      jq -e 'type == "object" and has("sha")' <<<"${payload}" >/dev/null; then
    existing="$(jq -r '.content | gsub("\\n"; "")' <<<"${payload}")"
    [[ ${existing} != "${content}" ]] || return 0
    sha="$(jq -er '.sha' <<<"${payload}")"
    payload="$(jq -cn \
      --arg content "${content}" \
      --arg sha "${sha}" \
      --arg message "Update ${relative}" \
      '{content:$content,sha:$sha,message:$message}')"
    api PUT "/repos/${REPOSITORY}/contents/${relative}" --data "${payload}" >/dev/null
  else
    payload="$(jq -cn \
      --arg content "${content}" \
      --arg message "Add ${relative}" \
      '{content:$content,message:$message}')"
    api POST "/repos/${REPOSITORY}/contents/${relative}" --data "${payload}" >/dev/null
  fi
}

ensure_file training/orion_release_risk_training.py \
  "${SCRIPT_DIR}/airflow/dags/orion_release_risk_training.py"
ensure_file training/base-model.json \
  "${SCRIPT_DIR}/release-risk/base-model.json"
ensure_file training/label-schema.json \
  "${SCRIPT_DIR}/release-risk/label-schema.json"

revision="$(api GET "/repos/${REPOSITORY}/branches/main" | jq -er '.commit.id')"
printf 'Forgejo release-risk source reconciled: revision=%s\n' "${revision}"
