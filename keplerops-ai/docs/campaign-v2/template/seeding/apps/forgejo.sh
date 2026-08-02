#!/usr/bin/env bash

set -Eeuo pipefail

SEEDING_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/common.sh
source "${SEEDING_ROOT}/lib/common.sh"

: "${FORGEJO_OIDC_CLIENT_ID:=forgejo}"
: "${FORGEJO_OIDC_CLIENT_SECRET:=KeplerV2-Training-Forgejo-OIDC}"
: "${FORGEJO_OIDC_SOURCE_NAME:=keplerops}"
: "${FORGEJO_OIDC_DISCOVERY_URL:=https://id.keplerops.lab/realms/${KEYCLOAK_REALM}/.well-known/openid-configuration}"
: "${FORGEJO_READ_TEAM:=Orion-Read}"
: "${FORGEJO_CONTRIBUTE_TEAM:=Orion-Contribute}"
: "${ORION_PUBLIC_SIGNING_STATE_DIR:=/var/lib/keplerops-v2/orion-public-signing}"
: "${ORION_PUBLIC_SIGNER_HOST:=192.168.78.30}"
: "${ORION_PUBLIC_SIGNER_USER:=kepler}"
: "${ORION_PUBLIC_SIGNER_BOOTSTRAP_KEY:=/root/.ssh/keplerops-v2}"
: "${ORION_PUBLICATION_USER:=orion.release}"
: "${ORION_PUBLICATION_PASSWORD:=KeplerV2-Orion-Publication-8mT4qN2v}"

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

orion_release_api() {
  local method=$1
  local path=$2
  shift 2
  curl --silent --show-error --fail-with-body \
    --user "${ORION_PUBLICATION_USER}:${ORION_PUBLICATION_PASSWORD}" \
    --header 'Content-Type: application/json' \
    --request "${method}" "$@" "${FORGEJO_API_URL}${path}"
}

keycloak_cli() {
  compose exec -T keycloak /opt/keycloak/bin/kcadm.sh "$@"
}

ensure_local_admin() {
  local username=$1
  local email=$2
  local password=$3
  local -a create_args=(
    admin user create
    --username "${username}"
    --email "${email}"
    --password "${password}"
    --must-change-password=false
    --admin
  )

  if forgejo_cli "${create_args[@]}" >/dev/null 2>&1; then
    log "Forgejo user created: ${username}"
  else
    forgejo_cli admin user change-password \
      --username "${username}" --password "${password}" \
      --must-change-password=false >/dev/null
    log "Forgejo user reconciled: ${username}"
  fi
}

ensure_local_release_user() {
  local username=${ORION_PUBLICATION_USER}
  local email=orion-release@keplerops.lab

  if forgejo_cli admin user create \
      --username "${username}" \
      --email "${email}" \
      --password "${ORION_PUBLICATION_PASSWORD}" \
      --must-change-password=false >/dev/null 2>&1; then
    log "Forgejo release automation user created: ${username}"
  else
    forgejo_cli admin user change-password \
      --username "${username}" \
      --password "${ORION_PUBLICATION_PASSWORD}" \
      --must-change-password=false >/dev/null
  fi
  forgejo_api PATCH "/admin/users/${username}" --data \
    "$(jq -cn --arg email "${email}" '{
      full_name:"Orion Release Automation",
      email:$email,
      active:true,
      restricted:false,
      visibility:"public"
    }')" >/dev/null
}

install_caddy_root_ca() {
  local installed_fingerprint source_fingerprint

  source_fingerprint="$(compose exec -T caddy \
    sha256sum /data/caddy/pki/authorities/local/root.crt | awk '{print $1}')"
  installed_fingerprint="$(compose exec -T forgejo sh -c \
    'sha256sum /usr/local/share/ca-certificates/keplerops-caddy-root.crt 2>/dev/null || true' |
    awk '{print $1}')"
  [[ ${installed_fingerprint} == "${source_fingerprint}" ]] && return 0

  # shellcheck disable=SC2016
  compose exec -T caddy \
    cat /data/caddy/pki/authorities/local/root.crt |
    compose exec -T --user root forgejo sh -eu -c '
      target=/usr/local/share/ca-certificates/keplerops-caddy-root.crt
      cat >"$target"
      update-ca-certificates >/dev/null
    '
  compose restart forgejo >/dev/null
  retry 60 2 curl --silent --show-error --fail \
    "${FORGEJO_API_URL}/version" >/dev/null || \
    die 'Forgejo did not recover after installing the Caddy trust root'
}

ensure_keycloak_client() {
  local clients client_id client_json mapper_id mapper_json mappers

  clients="$(keycloak_cli get clients -r "${KEYCLOAK_REALM}" \
    -q "clientId=${FORGEJO_OIDC_CLIENT_ID}")"
  client_id="$(jq -r '.[0].id // empty' <<<"${clients}")"
  client_json="$(jq -cn \
    --arg client_id "${FORGEJO_OIDC_CLIENT_ID}" \
    --arg name 'KeplerOps Source Control' \
    --arg secret "${FORGEJO_OIDC_CLIENT_SECRET}" \
    --arg redirect "https://git.keplerops.lab/user/oauth2/${FORGEJO_OIDC_SOURCE_NAME}/callback" \
    '{
      clientId: $client_id,
      name: $name,
      enabled: true,
      protocol: "openid-connect",
      publicClient: false,
      secret: $secret,
      standardFlowEnabled: true,
      directAccessGrantsEnabled: false,
      serviceAccountsEnabled: false,
      redirectUris: [$redirect],
      webOrigins: ["https://git.keplerops.lab"],
      attributes: {"post.logout.redirect.uris": "https://git.keplerops.lab/*"}
    }')"

  if [[ -n ${client_id} ]]; then
    keycloak_cli update "clients/${client_id}" -r "${KEYCLOAK_REALM}" \
      -f - <<<"${client_json}" >/dev/null
  else
    keycloak_cli create clients -r "${KEYCLOAK_REALM}" \
      -f - <<<"${client_json}" >/dev/null
    clients="$(keycloak_cli get clients -r "${KEYCLOAK_REALM}" \
      -q "clientId=${FORGEJO_OIDC_CLIENT_ID}")"
    client_id="$(jq -er '.[0].id' <<<"${clients}")"
  fi

  mapper_json="$(jq -cn '{
    name: "groups",
    protocol: "openid-connect",
    protocolMapper: "oidc-group-membership-mapper",
    consentRequired: false,
    config: {
      "claim.name": "groups",
      "full.path": "false",
      "id.token.claim": "true",
      "access.token.claim": "true",
      "userinfo.token.claim": "true"
    }
  }')"
  mappers="$(keycloak_cli get "clients/${client_id}/protocol-mappers/models" \
    -r "${KEYCLOAK_REALM}")"
  mapper_id="$(jq -r '.[] | select(.name == "groups") | .id' \
    <<<"${mappers}" | head -n1)"
  if [[ -n ${mapper_id} ]]; then
    keycloak_cli delete "clients/${client_id}/protocol-mappers/models/${mapper_id}" \
      -r "${KEYCLOAK_REALM}" >/dev/null
  fi
  keycloak_cli create "clients/${client_id}/protocol-mappers/models" \
    -r "${KEYCLOAK_REALM}" -f - <<<"${mapper_json}" >/dev/null
}

keycloak_group_members() {
  local group_name=$1
  local group_id groups

  groups="$(keycloak_cli get groups -r "${KEYCLOAK_REALM}")"
  group_id="$(jq -r --arg name "${group_name}" \
    '.[] | select(.name == $name) | .id' <<<"${groups}" | head -n1)"
  [[ -n ${group_id} ]] || die "Keycloak group is missing: ${group_name}"
  keycloak_cli get "groups/${group_id}/members" -r "${KEYCLOAK_REALM}" \
    --fields id,username,firstName,lastName
}

ensure_org() {
  if ! forgejo_api GET "/orgs/${FORGEJO_ORG}" >/dev/null 2>&1; then
    forgejo_api POST /orgs --data "$(jq -cn \
      --arg username "${FORGEJO_ORG}" \
      --arg full_name 'KeplerOps AI Systems' \
      '{username:$username,full_name:$full_name,visibility:"public"}')" >/dev/null
    log "Forgejo organization created: ${FORGEJO_ORG}"
  fi

  forgejo_api PATCH "/orgs/${FORGEJO_ORG}" --data \
    '{"full_name":"KeplerOps AI Systems"}' >/dev/null
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

ensure_team() {
  local name=$1
  local permission=$2
  local description=$3
  local team_id teams team_json

  teams="$(forgejo_api GET "/orgs/${FORGEJO_ORG}/teams")"
  team_id="$(jq -r --arg name "${name}" \
    '.[] | select(.name == $name) | .id' <<<"${teams}" | head -n1)"
  team_json="$(jq -cn \
    --arg name "${name}" \
    --arg description "${description}" \
    --arg permission "${permission}" \
    '{
      name: $name,
      description: $description,
      includes_all_repositories: false,
      can_create_org_repo: false,
      permission: $permission,
      units: ["repo.code", "repo.issues", "repo.pulls", "repo.releases", "repo.actions"]
    }')"

  if [[ -z ${team_id} ]]; then
    team_id="$(forgejo_api POST "/orgs/${FORGEJO_ORG}/teams" \
      --data "${team_json}" | jq -er '.id')"
    log "Forgejo team created: ${name}"
  else
    forgejo_api PATCH "/teams/${team_id}" --data "${team_json}" >/dev/null
  fi

  forgejo_api PUT "/teams/${team_id}/repos/${FORGEJO_ORG}/${FORGEJO_REPO}" \
    >/dev/null
  forgejo_api PUT "/teams/${team_id}/repos/${FORGEJO_ORG}/${FORGEJO_BUILD_REPO}" \
    >/dev/null
  printf '%s\n' "${team_id}"
}

remove_legacy_engineering_team() {
  local team_id teams
  teams="$(forgejo_api GET "/orgs/${FORGEJO_ORG}/teams")"
  team_id="$(jq -r '.[] | select(.name == "Engineering") | .id' \
    <<<"${teams}" | head -n1)"
  if [[ -n ${team_id} ]]; then
    forgejo_api DELETE "/teams/${team_id}" >/dev/null
    log 'Forgejo legacy Engineering team removed'
  fi
}

ensure_oidc_source() {
  local source_id team_map
  local -a source_args

  team_map="$(jq -cn \
    --arg read_group 'RG-Forgejo-Orion-Read' \
    --arg contribute_group 'RG-Forgejo-Orion-Contribute' \
    --arg org "${FORGEJO_ORG}" \
    --arg read_team "${FORGEJO_READ_TEAM}" \
    --arg contribute_team "${FORGEJO_CONTRIBUTE_TEAM}" \
    '{
      ($read_group): {($org): [$read_team]},
      ($contribute_group): {($org): [$contribute_team]}
    }')"
  source_args=(
    --name "${FORGEJO_OIDC_SOURCE_NAME}"
    --provider openidConnect
    --key "${FORGEJO_OIDC_CLIENT_ID}"
    --secret "${FORGEJO_OIDC_CLIENT_SECRET}"
    --auto-discover-url "${FORGEJO_OIDC_DISCOVERY_URL}"
    --scopes profile
    --scopes email
    --group-claim-name groups
    --required-claim-name groups
    --required-claim-value RG-Forgejo-Orion-Read
    --group-team-map "${team_map}"
    --group-team-map-removal
  )

  source_id="$(forgejo_cli admin auth list | awk \
    -v name="${FORGEJO_OIDC_SOURCE_NAME}" '$2 == name {print $1; exit}')"
  if [[ -n ${source_id} ]]; then
    forgejo_cli admin auth update-oauth --id "${source_id}" \
      "${source_args[@]}" >/dev/null
  else
    forgejo_cli admin auth add-oauth "${source_args[@]}" >/dev/null
    source_id="$(forgejo_cli admin auth list | awk \
      -v name="${FORGEJO_OIDC_SOURCE_NAME}" '$2 == name {print $1; exit}')"
  fi
  [[ -n ${source_id} ]] || die 'Forgejo OIDC authentication source was not created'
  printf '%s\n' "${source_id}"
}

ensure_oidc_user() {
  local source_id=$1
  local user_json=$2
  local username subject first_name last_name full_name email payload

  username="$(jq -er '.username' <<<"${user_json}")"
  subject="$(jq -er '.id' <<<"${user_json}")"
  first_name="$(jq -r '.firstName // ""' <<<"${user_json}")"
  last_name="$(jq -r '.lastName // ""' <<<"${user_json}")"
  full_name="${first_name} ${last_name}"
  full_name="${full_name# }"
  full_name="${full_name% }"
  [[ -n ${full_name} ]] || full_name="${username}"
  email="${username}@keplerops.lab"

  payload="$(jq -cn \
    --argjson source_id "${source_id}" \
    --arg login_name "${subject}" \
    --arg username "${username}" \
    --arg full_name "${full_name}" \
    --arg email "${email}" \
    '{
      source_id: $source_id,
      login_name: $login_name,
      username: $username,
      full_name: $full_name,
      email: $email,
      must_change_password: false,
      restricted: false,
      visibility: "private"
    }')"
  if ! forgejo_api GET "/users/${username}" >/dev/null 2>&1; then
    forgejo_api POST /admin/users --data "${payload}" >/dev/null
    log "Forgejo OIDC user created: ${username}"
  fi

  payload="$(jq -cn \
    --argjson source_id "${source_id}" \
    --arg login_name "${subject}" \
    --arg full_name "${full_name}" \
    --arg email "${email}" \
    '{
      source_id: $source_id,
      login_name: $login_name,
      full_name: $full_name,
      email: $email,
      active: true,
      restricted: false,
      visibility: "private"
    }')"
  forgejo_api PATCH "/admin/users/${username}" --data "${payload}" >/dev/null
}

sync_team_members() {
  local team_id=$1
  local desired_users=$2
  local current_users username

  current_users="$(forgejo_api GET "/teams/${team_id}/members")"
  while IFS= read -r username; do
    [[ -n ${username} ]] || continue
    if ! jq -e --arg username "${username}" \
      'index($username) != null' <<<"${desired_users}" >/dev/null; then
      forgejo_api DELETE "/teams/${team_id}/members/${username}" >/dev/null
    fi
  done < <(jq -r '.[].login' <<<"${current_users}")

  while IFS= read -r username; do
    [[ -n ${username} ]] || continue
    forgejo_api PUT "/teams/${team_id}/members/${username}" >/dev/null
  done < <(jq -r '.[]' <<<"${desired_users}")
}

ensure_repository_file() {
  local repository=$1
  local remote_path=$2
  local source_path=$3
  local api_function=${4:-forgejo_api}
  local content existing_content sha payload
  content="$(base64 < "${source_path}" | tr -d '\n')"

  if payload="$(${api_function} GET "/repos/${FORGEJO_ORG}/${repository}/contents/${remote_path}" 2>/dev/null)" && \
      jq -e 'type == "object" and has("sha")' <<<"${payload}" >/dev/null; then
    existing_content="$(jq -r '.content | gsub("\\n"; "")' <<<"${payload}")"
    [[ ${existing_content} == "${content}" ]] && return 0
    sha="$(jq -er '.sha' <<<"${payload}")"
    payload="$(jq -cn \
      --arg content "${content}" \
      --arg sha "${sha}" \
      --arg message "Reconcile ${remote_path}" \
      '{content:$content,sha:$sha,message:$message}')"
    "${api_function}" PUT "/repos/${FORGEJO_ORG}/${repository}/contents/${remote_path}" \
      --data "${payload}" >/dev/null
  else
    payload="$(jq -cn \
      --arg content "${content}" \
      --arg message "Add ${remote_path}" \
      '{content:$content,message:$message}')"
    "${api_function}" POST "/repos/${FORGEJO_ORG}/${repository}/contents/${remote_path}" \
      --data "${payload}" >/dev/null
  fi
}

ensure_action_secret() {
  local repository=$1
  local name=$2
  local value=$3

  forgejo_api PUT "/repos/${FORGEJO_ORG}/${repository}/actions/secrets/${name}" \
    --data "$(jq -cn --arg data "${value}" '{data:$data}')" >/dev/null
}

ensure_public_signing_identity() {
  local android_cert android_key android_key_pem command_path known_hosts signer_key signer_pub
  local authorized_key

  for command_path in openssl ssh ssh-keygen ssh-keyscan; do
    require_command "${command_path}"
  done
  [[ -r ${ORION_PUBLIC_SIGNER_BOOTSTRAP_KEY} ]] || \
    die "k3s01 bootstrap key is unreadable: ${ORION_PUBLIC_SIGNER_BOOTSTRAP_KEY}"

  install -d -m 0700 "${ORION_PUBLIC_SIGNING_STATE_DIR}"
  android_key="${ORION_PUBLIC_SIGNING_STATE_DIR}/android-release-key.pk8"
  android_cert="${ORION_PUBLIC_SIGNING_STATE_DIR}/android-release-cert.pem"
  signer_key="${ORION_PUBLIC_SIGNING_STATE_DIR}/manifest-signer"

  if [[ ! -s ${android_key} || ! -s ${android_cert} ]]; then
    android_key_pem="${ORION_PUBLIC_SIGNING_STATE_DIR}/android-release-key.pem"
    openssl genpkey -algorithm RSA \
      -pkeyopt rsa_keygen_bits:3072 -out "${android_key_pem}" >/dev/null 2>&1
    openssl req -new -x509 -sha256 -days 3650 \
      -key "${android_key_pem}" -out "${android_cert}" \
      -subj '/CN=KeplerOps AI Systems Orion Mobile Release/O=KeplerOps AI Systems'
    openssl pkcs8 -topk8 -nocrypt -outform DER \
      -in "${android_key_pem}" -out "${android_key}"
    rm -f "${android_key_pem}"
    chmod 0600 "${android_key}"
    chmod 0644 "${android_cert}"
  fi
  if [[ ! -s ${signer_key} || ! -s ${signer_key}.pub ]]; then
    ssh-keygen -q -t ed25519 -N '' \
      -C orion-public-release-signer -f "${signer_key}"
    chmod 0600 "${signer_key}"
  fi

  signer_pub="$(<"${signer_key}.pub")"
  authorized_key="restrict,command=\"/usr/local/sbin/orion-public-release-signer\" ${signer_pub}"
  ssh -i "${ORION_PUBLIC_SIGNER_BOOTSTRAP_KEY}" \
    -o BatchMode=yes -o StrictHostKeyChecking=accept-new \
    "${ORION_PUBLIC_SIGNER_USER}@${ORION_PUBLIC_SIGNER_HOST}" \
    'sudo install -m 0755 /dev/stdin /usr/local/sbin/orion-public-release-signer' \
    <"${SEEDING_ROOT}/payloads/orion-public/ci/signing-command.sh"
  printf '%s\n' "${authorized_key}" | \
    ssh -i "${ORION_PUBLIC_SIGNER_BOOTSTRAP_KEY}" \
      -o BatchMode=yes -o StrictHostKeyChecking=accept-new \
      "${ORION_PUBLIC_SIGNER_USER}@${ORION_PUBLIC_SIGNER_HOST}" \
      'set -eu
       install -d -m 0700 "$HOME/.ssh"
       touch "$HOME/.ssh/authorized_keys"
       chmod 0600 "$HOME/.ssh/authorized_keys"
       sed -i "/orion-public-release-signer$/d" "$HOME/.ssh/authorized_keys"
       cat >>"$HOME/.ssh/authorized_keys"'

  known_hosts="$(ssh-keyscan -T 10 "${ORION_PUBLIC_SIGNER_HOST}" 2>/dev/null)"
  [[ -n ${known_hosts} ]] || die 'could not capture the k3s01 SSH host key'
  ensure_action_secret "${FORGEJO_BUILD_REPO}" ORION_ANDROID_RELEASE_KEY \
    "$(base64 -w0 <"${android_key}")"
  ensure_action_secret "${FORGEJO_BUILD_REPO}" ORION_ANDROID_RELEASE_CERT \
    "$(<"${android_cert}")"
  ensure_action_secret "${FORGEJO_BUILD_REPO}" ORION_MANIFEST_SIGNER_KEY \
    "$(<"${signer_key}")"
  ensure_action_secret "${FORGEJO_BUILD_REPO}" ORION_MANIFEST_SIGNER_KNOWN_HOSTS \
    "${known_hosts}"
  ensure_action_secret "${FORGEJO_BUILD_REPO}" ORION_PUBLICATION_USER \
    "${ORION_PUBLICATION_USER}"
  ensure_action_secret "${FORGEJO_BUILD_REPO}" ORION_PUBLICATION_PASSWORD \
    "${ORION_PUBLICATION_PASSWORD}"
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
    ensure_repository_file "${FORGEJO_BUILD_REPO}" "${path}" "${root}/${path}" \
      orion_release_api
  done

  ensure_repository_file "${FORGEJO_BUILD_REPO}" \
    .forgejo/workflows/orion-public-release.yml \
    "${SEEDING_ROOT}/payloads/orion-public/forgejo/orion-public-release.yml" \
    orion_release_api
}

ensure_actions_runner() {
  # Forgejo 11.0.4 records both owner_id and repo_id for repository-scoped
  # forgejo-cli registrations, so its task-version lookup never sees new jobs.
  # Organization scope is the narrowest functional scope on this pinned release.
  forgejo_cli forgejo-cli actions register \
    --secret "${FORGEJO_RUNNER_SECRET}" \
    --scope "${FORGEJO_ORG}" \
    --labels 'orion-release-linux' \
    --name keplerops-engineering \
    --version 6.3.1 >/dev/null
}

ensure_public_sources() {
  local root="${SEEDING_ROOT}/payloads/orion-public"
  local path source_path
  local -a paths=(
    LICENSE
    README.md
    client/AndroidManifest.xml
    client/build.sh
    client/src/com/keplerops/orion/MainActivity.java
    ci/assemble-release.py
    ci/prepare-client.py
    ci/release.sh
    docs/MODEL_CARD.md
    docs/RELEASE_NOTES.md
    docs/TECHNICAL_REPORT.md
    metadata/com.keplerops.orion.yml
  )

  for path in "${paths[@]}"; do
    source_path="${root}/${path}"
    ensure_repository_file "${FORGEJO_REPO}" "${path}" "${source_path}" \
      orion_release_api
  done
}

main() {
  local contribute_members contribute_team_id member read_members read_team_id source_id users

  require_service forgejo
  require_service keycloak
  require_service caddy

  retry 60 2 keycloak_cli config credentials \
    --server http://127.0.0.1:8080 \
    --realm master \
    --user "${KEYCLOAK_ADMIN_USER}" \
    --password "${KEYCLOAK_ADMIN_PASSWORD}" >/dev/null || \
    die 'Keycloak admin CLI did not become ready'
  keycloak_cli get "realms/${KEYCLOAK_REALM}" >/dev/null 2>&1 || \
    die "Keycloak realm is missing: ${KEYCLOAK_REALM}"
  ensure_keycloak_client
  install_caddy_root_ca

  ensure_local_admin "${FORGEJO_ADMIN_USER}" "${FORGEJO_ADMIN_EMAIL}" \
    "${FORGEJO_ADMIN_PASSWORD}"

  retry 30 2 forgejo_api GET /version >/dev/null || die "Forgejo API did not become ready"
  ensure_org
  ensure_repo
  ensure_build_repo
  read_team_id="$(ensure_team "${FORGEJO_READ_TEAM}" read \
    'Read-only access to Project Orion source and engineering records.')"
  contribute_team_id="$(ensure_team "${FORGEJO_CONTRIBUTE_TEAM}" write \
    'Contribute access to Project Orion source and engineering records.')"
  remove_legacy_engineering_team

  source_id="$(ensure_oidc_source)"
  read_members="$(keycloak_group_members RG-Forgejo-Orion-Read)"
  contribute_members="$(keycloak_group_members RG-Forgejo-Orion-Contribute)"
  users="$(jq -cn --argjson read "${read_members}" \
    --argjson contribute "${contribute_members}" \
    '$read + $contribute | unique_by(.id)')"
  while IFS= read -r member; do
    ensure_oidc_user "${source_id}" "${member}"
  done < <(jq -c '.[]' <<<"${users}")
  ensure_local_release_user
  sync_team_members "${read_team_id}" \
    "$(jq -c '[.[].username] | unique' <<<"${read_members}")"
  sync_team_members "${contribute_team_id}" \
    "$(jq -c --arg user "${ORION_PUBLICATION_USER}" \
      '[.[].username] + [$user] | unique' <<<"${contribute_members}")"

  ensure_public_sources
  ensure_build_sources
  ensure_public_signing_identity
  ensure_actions_runner
  log "Forgejo Keycloak OIDC and Orion team state are ready"
}

main "$@"
