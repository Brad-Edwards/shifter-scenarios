#!/usr/bin/env bash

set -Eeuo pipefail

SEEDING_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/common.sh
source "${SEEDING_ROOT}/lib/common.sh"

forgejo_cli() {
  compose exec -T --user git forgejo forgejo "$@"
}

forgejo_api() {
  local method=$1
  local path=$2
  shift 2
  curl --silent --show-error --fail-with-body \
    --user "${FORGEJO_ADMIN_USER}:${FORGEJO_ADMIN_PASSWORD}" \
    --header 'Content-Type: application/json' \
    --request "${method}" "$@" "${FORGEJO_API_URL}${path}"
}

ensure_user() {
  local username=$1
  local email=$2
  local password=$3
  local admin=${4:-false}
  local -a create_args=(
    admin user create
    --username "${username}"
    --email "${email}"
    --password "${password}"
    --must-change-password=false
  )

  if [[ ${admin} == true ]]; then
    create_args+=(--admin)
  fi

  if forgejo_cli "${create_args[@]}" >/dev/null 2>&1; then
    log "Forgejo user created: ${username}"
  else
    forgejo_cli admin user change-password \
      --username "${username}" --password "${password}" \
      --must-change-password=false >/dev/null
    log "Forgejo user reconciled: ${username}"
  fi
}

ensure_org() {
  if ! forgejo_api GET "/orgs/${FORGEJO_ORG}" >/dev/null 2>&1; then
    forgejo_api POST /orgs --data "$(jq -cn \
      --arg username "${FORGEJO_ORG}" \
      --arg full_name 'Kepler Operations' \
      '{username:$username,full_name:$full_name,visibility:"public"}')" >/dev/null
    log "Forgejo organization created: ${FORGEJO_ORG}"
  fi
}

ensure_repo() {
  if ! forgejo_api GET "/repos/${FORGEJO_ORG}/${FORGEJO_REPO}" >/dev/null 2>&1; then
    forgejo_api POST "/orgs/${FORGEJO_ORG}/repos" --data "$(jq -cn \
      --arg name "${FORGEJO_REPO}" \
      '{name:$name,description:"Public engineering information for Project Orion.",private:false,auto_init:false}')" >/dev/null
    log "Forgejo public repository created: ${FORGEJO_ORG}/${FORGEJO_REPO}"
  fi

  forgejo_api PATCH "/repos/${FORGEJO_ORG}/${FORGEJO_REPO}" --data \
    '{"description":"Public engineering information for Project Orion.","private":false}' >/dev/null
}

ensure_build_repo() {
  if ! forgejo_api GET "/repos/${FORGEJO_ORG}/${FORGEJO_BUILD_REPO}" >/dev/null 2>&1; then
    forgejo_api POST "/orgs/${FORGEJO_ORG}/repos" --data "$(jq -cn \
      --arg name "${FORGEJO_BUILD_REPO}" \
      '{name:$name,description:"Internal Project Orion build and publication inputs.",private:true,auto_init:false}')" >/dev/null
    log "Forgejo build repository created: ${FORGEJO_ORG}/${FORGEJO_BUILD_REPO}"
  fi

  forgejo_api PATCH "/repos/${FORGEJO_ORG}/${FORGEJO_BUILD_REPO}" --data \
    '{"description":"Internal Project Orion build and publication inputs.","private":true}' >/dev/null
}

ensure_repository_file() {
  local repository=$1
  local remote_path=$2
  local source_path=$3
  local content existing_content sha payload
  content="$(base64 < "${source_path}" | tr -d '\n')"

  if payload="$(forgejo_api GET "/repos/${FORGEJO_ORG}/${repository}/contents/${remote_path}" 2>/dev/null)" && \
      jq -e 'type == "object" and has("sha")' <<<"${payload}" >/dev/null; then
    existing_content="$(jq -r '.content | gsub("\\n"; "")' <<<"${payload}")"
    [[ ${existing_content} == "${content}" ]] && return 0
    sha="$(jq -er '.sha' <<<"${payload}")"
    payload="$(jq -cn \
      --arg content "${content}" \
      --arg sha "${sha}" \
      --arg message "Reconcile ${remote_path}" \
      '{content:$content,sha:$sha,message:$message}')"
    forgejo_api PUT "/repos/${FORGEJO_ORG}/${repository}/contents/${remote_path}" \
      --data "${payload}" >/dev/null
  else
    payload="$(jq -cn \
      --arg content "${content}" \
      --arg message "Add ${remote_path}" \
      '{content:$content,message:$message}')"
    forgejo_api POST "/repos/${FORGEJO_ORG}/${repository}/contents/${remote_path}" \
      --data "${payload}" >/dev/null
  fi
}

ensure_build_sources() {
  local root="${SEEDING_ROOT}/payloads/orion-build"
  local path
  local -a paths=(
    README.md
    pyproject.toml
    src/orion_release/__init__.py
    package.json
    index.js
    service/.dockerignore
    service/app.py
    service/Dockerfile
    ci/publish.sh
    .forgejo/workflows/publish.yml
  )

  for path in "${paths[@]}"; do
    ensure_repository_file "${FORGEJO_BUILD_REPO}" "${path}" "${root}/${path}"
  done
}

ensure_actions_runner() {
  forgejo_cli forgejo-cli actions register \
    --secret "${FORGEJO_RUNNER_SECRET}" \
    --scope "${FORGEJO_ORG}/${FORGEJO_BUILD_REPO}" \
    --labels 'campaign-ci:host' \
    --name keplerops-engineering \
    --version 6.3.1 >/dev/null
}

ensure_engineering_team() {
  local teams team_id username
  teams="$(forgejo_api GET "/orgs/${FORGEJO_ORG}/teams")"
  team_id="$(jq -r '.[] | select(.name == "Engineering") | .id' \
    <<<"${teams}" | head -n1)"
  if [[ -z ${team_id} ]]; then
    team_id="$(forgejo_api POST "/orgs/${FORGEJO_ORG}/teams" --data "$(jq -cn '{
      name: "Engineering",
      description: "Project Orion engineering team",
      includes_all_repositories: true,
      can_create_org_repo: false,
      permission: "write",
      units: ["repo.code", "repo.issues", "repo.pulls", "repo.releases", "repo.actions"]
    }')" | jq -er '.id')"
    log "Forgejo engineering team created"
  fi

  for username in ml.engineer release.engineer; do
    forgejo_api PUT "/teams/${team_id}/members/${username}" >/dev/null
  done
}

ensure_readme() {
  local content existing_content sha payload
  content="$(base64 < "${SEEDING_ROOT}/payloads/orion-public-readme.md" | tr -d '\n')"

  if payload="$(forgejo_api GET "/repos/${FORGEJO_ORG}/${FORGEJO_REPO}/contents/README.md" 2>/dev/null)" && \
      jq -e 'type == "object" and has("sha")' <<<"${payload}" >/dev/null; then
    existing_content="$(jq -r '.content | gsub("\\n"; "")' <<<"${payload}")"
    if [[ ${existing_content} == "${content}" ]]; then
      return 0
    fi
    sha="$(jq -er '.sha' <<<"${payload}")"
    payload="$(jq -cn --arg content "${content}" --arg sha "${sha}" \
      '{content:$content,sha:$sha,message:"Reconcile public project overview"}')"
    forgejo_api PUT "/repos/${FORGEJO_ORG}/${FORGEJO_REPO}/contents/README.md" \
      --data "${payload}" >/dev/null
  else
    payload="$(jq -cn --arg content "${content}" \
      '{content:$content,message:"Add public project overview"}')"
    forgejo_api POST "/repos/${FORGEJO_ORG}/${FORGEJO_REPO}/contents/README.md" \
      --data "${payload}" >/dev/null
  fi
}

main() {
  require_service forgejo

  ensure_user "${FORGEJO_ADMIN_USER}" "${FORGEJO_ADMIN_EMAIL}" "${FORGEJO_ADMIN_PASSWORD}" true
  ensure_user reviewer reviewer@keplerops.lab "${REVIEWER_PASSWORD}"
  ensure_user ml.engineer ml.engineer@keplerops.lab "${ML_ENGINEER_PASSWORD}"
  ensure_user release.engineer release.engineer@keplerops.lab "${RELEASE_ENGINEER_PASSWORD}"
  ensure_user comms.publisher communications@keplerops.lab "${COMMS_PUBLISHER_PASSWORD}"
  ensure_user support.analyst support@keplerops.lab "${SUPPORT_ANALYST_PASSWORD}"

  retry 30 2 forgejo_api GET /version >/dev/null || die "Forgejo API did not become ready"
  ensure_org
  ensure_repo
  ensure_build_repo
  ensure_engineering_team
  ensure_readme
  ensure_build_sources
  ensure_actions_runner
  log "Forgejo clean state is ready"
}

main "$@"
