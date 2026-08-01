#!/usr/bin/env bash
set -Eeuo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
FORGEJO_API_URL=${FORGEJO_API_URL:-http://10.61.40.20:3000/api/v1}
FORGEJO_ADMIN_USER=${FORGEJO_ADMIN_USER:-range-admin}
FORGEJO_ADMIN_PASSWORD=${FORGEJO_ADMIN_PASSWORD:-KeplerV2-Training-Forgejo-Admin}
FORGEJO_ORG=${FORGEJO_ORG:-keplerops}
FORGEJO_REPO=${FORGEJO_GITOPS_REPO:-orion-platform}

api() {
  local method=$1 path=$2
  shift 2
  curl --silent --show-error --fail-with-body \
    --user "${FORGEJO_ADMIN_USER}:${FORGEJO_ADMIN_PASSWORD}" \
    --header 'Content-Type: application/json' \
    --request "$method" "$@" "${FORGEJO_API_URL}${path}"
}

ensure_repo() {
  if ! api GET "/repos/${FORGEJO_ORG}/${FORGEJO_REPO}" >/dev/null 2>&1; then
    api POST "/orgs/${FORGEJO_ORG}/repos" --data "$(jq -cn \
      --arg name "$FORGEJO_REPO" \
      '{name:$name,description:"Orion platform deployment definitions.",private:false,auto_init:false}')" >/dev/null
  fi
  api PATCH "/repos/${FORGEJO_ORG}/${FORGEJO_REPO}" \
    --data '{"description":"Orion platform deployment definitions.","private":false}' >/dev/null
}

ensure_file() {
  local relative=$1 source=$2
  local content existing payload sha
  content=$(base64 <"$source" | tr -d '\n')

  if payload=$(api GET "/repos/${FORGEJO_ORG}/${FORGEJO_REPO}/contents/${relative}" 2>/dev/null) && \
      jq -e 'type == "object" and has("sha")' <<<"$payload" >/dev/null; then
    existing=$(jq -r '.content | gsub("\\n"; "")' <<<"$payload")
    [[ $existing != "$content" ]] || return 0
    sha=$(jq -er '.sha' <<<"$payload")
    payload=$(jq -cn --arg content "$content" --arg sha "$sha" \
      --arg message "Update ${relative}" \
      '{content:$content,sha:$sha,message:$message}')
    api PUT "/repos/${FORGEJO_ORG}/${FORGEJO_REPO}/contents/${relative}" \
      --data "$payload" >/dev/null
  else
    payload=$(jq -cn --arg content "$content" --arg message "Add ${relative}" \
      '{content:$content,message:$message}')
    api POST "/repos/${FORGEJO_ORG}/${FORGEJO_REPO}/contents/${relative}" \
      --data "$payload" >/dev/null
  fi
}

ensure_repo
ensure_file gitops/orion-canary/kustomization.yaml "$ROOT/gitops/orion-canary/kustomization.yaml"
ensure_file gitops/orion-canary/inferenceservice.yaml "$ROOT/gitops/orion-canary/inferenceservice.yaml"
ensure_file gitops/orion-canary/service.yaml "$ROOT/gitops/orion-canary/service.yaml"

api GET "/repos/${FORGEJO_ORG}/${FORGEJO_REPO}/branches/main" | jq -er '.commit.id'
