#!/usr/bin/env bash
set -Eeuo pipefail

SEEDING_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/common.sh
source "${SEEDING_ROOT}/lib/common.sh"

readonly UNLEASH_URL=http://10.61.70.23:4242
readonly BOOTSTRAP_TOKEN='*:*.range-admin'
readonly CONTROL_USER=orion.release.controller
readonly CONTROL_EMAIL=orion.release.controller@keplerops.com
readonly CONTROL_PASSWORD=KeplerV2-Training-Unleash-Controller
readonly CONTROL_TOKEN=user:KeplerV2-Training-Orion-Unleash-Control
readonly CLIENT_TOKEN=default:development.KeplerV2-Training-Orion-Canary-Read
readonly PROJECT=default
readonly ENVIRONMENT=development
readonly CANARY_FEATURE=orion-canary-assistant

workdir="$(mktemp -d)"
trap 'rm -rf "${workdir}"' EXIT

api() {
  local method=$1 path=$2 token=$3 output=$4 payload=${5:-}
  local -a request=(
    curl --silent --show-error --output "${output}" --write-out '%{http_code}'
    --request "${method}" --header "Authorization: ${token}"
  )
  if [[ -n ${payload} ]]; then
    request+=(--header 'Content-Type: application/json' --data "${payload}")
  fi
  "${request[@]}" "${UNLEASH_URL}${path}"
}

unleash_ready() {
  curl --silent --show-error --fail "${UNLEASH_URL}/health" >/dev/null
}

expect_code() {
  local actual=$1 expected=$2 operation=$3 body=$4
  if [[ ${actual} != "${expected}" ]]; then
    die "${operation} returned HTTP ${actual}: $(head -c 500 "${body}")"
  fi
}

ensure_control_identity() {
  local body code user_id payload
  body="${workdir}/users.json"
  code="$(api GET /api/admin/user-admin "${BOOTSTRAP_TOKEN}" "${body}")"
  expect_code "${code}" 200 'list Unleash users' "${body}"
  user_id="$(jq -r --arg username "${CONTROL_USER}" \
    '.users[] | select(.username == $username) | .id' "${body}" | head -n1)"

  if [[ -z ${user_id} ]]; then
    payload="$(jq -cn \
      --arg username "${CONTROL_USER}" \
      --arg email "${CONTROL_EMAIL}" \
      --arg password "${CONTROL_PASSWORD}" \
      '{username:$username,email:$email,name:"Orion Release Controller",password:$password,rootRole:"Admin",sendEmail:false}')"
    body="${workdir}/create-user.json"
    code="$(api POST /api/admin/user-admin "${BOOTSTRAP_TOKEN}" "${body}" "${payload}")"
    expect_code "${code}" 201 'create Unleash control identity' "${body}"
    user_id="$(jq -er '.id' "${body}")"
  else
    payload="$(jq -cn --arg password "${CONTROL_PASSWORD}" '{password:$password}')"
    body="${workdir}/change-password.json"
    code="$(api POST "/api/admin/user-admin/${user_id}/change-password" \
      "${BOOTSTRAP_TOKEN}" "${body}" "${payload}")"
    expect_code "${code}" 200 'reconcile Unleash control password' "${body}"
  fi

  [[ ${user_id} =~ ^[0-9]+$ ]] || die 'Unleash control identity has an invalid user id'
  printf '%s' "${user_id}"
}

reconcile_native_boundaries() {
  local user_id=$1
  compose exec -T \
    -e PGPASSWORD=KeplerV2-Training-BusinessDB \
    postgres psql --quiet --set ON_ERROR_STOP=1 \
    --host 127.0.0.1 --username business --dbname business \
    --set "control_user_id=${user_id}" <<SQL
BEGIN;
UPDATE features
SET project = 'default'
WHERE name = '${CANARY_FEATURE}' AND project <> 'default';
UPDATE feature_strategies
SET project_name = 'default'
WHERE feature_name = '${CANARY_FEATURE}' AND project_name <> 'default';
DELETE FROM role_user
WHERE user_id = :control_user_id AND project = 'orion-canary';
INSERT INTO role_user (role_id, user_id, project, created_by_user_id)
SELECT id, :control_user_id, 'default', :control_user_id
FROM roles
WHERE type = 'root' AND name = 'Admin'
ON CONFLICT (role_id, user_id, project) DO UPDATE
SET created_by_user_id = EXCLUDED.created_by_user_id;
DELETE FROM projects WHERE id = 'orion-canary';

DELETE FROM personal_access_tokens
WHERE (user_id = :control_user_id
       AND description = 'Orion release controller')
   OR secret = '${CONTROL_TOKEN}';
INSERT INTO personal_access_tokens
  (secret, description, user_id, expires_at)
VALUES ('${CONTROL_TOKEN}', 'Orion release controller', :control_user_id,
        now() + interval '10 years');

DELETE FROM api_tokens
WHERE token_name = 'Orion canary reader' AND secret <> '${CLIENT_TOKEN}';
DELETE FROM api_tokens
WHERE secret IN (
  'default:development.range-client',
  'orion-canary:development.KeplerV2-Training-Orion-Canary-Read'
);
INSERT INTO api_tokens
  (secret, username, token_name, type, environment, alias, created_by_user_id)
VALUES ('${CLIENT_TOKEN}', 'Orion canary reader', 'Orion canary reader',
        'backend', '${ENVIRONMENT}', NULL, :control_user_id)
ON CONFLICT (secret) DO UPDATE
SET username = EXCLUDED.username,
    token_name = EXCLUDED.token_name,
    type = EXCLUDED.type,
    environment = EXCLUDED.environment,
    expires_at = NULL,
    alias = NULL,
    created_by_user_id = EXCLUDED.created_by_user_id;
DELETE FROM api_token_project WHERE secret = '${CLIENT_TOKEN}';
INSERT INTO api_token_project (secret, project)
VALUES ('${CLIENT_TOKEN}', '${PROJECT}');
COMMIT;
SQL
}

ensure_feature() {
  local project=$1 feature=$2 description=$3 body code payload
  body="${workdir}/${project}-${feature}.json"
  code="$(api GET "/api/admin/projects/${project}/features/${feature}" \
    "${CONTROL_TOKEN}" "${body}")"
  if [[ ${code} == 404 ]]; then
    payload="$(jq -cn --arg name "${feature}" --arg description "${description}" \
      '{name:$name,type:"operational",description:$description,impressionData:true}')"
    code="$(api POST "/api/admin/projects/${project}/features" \
      "${CONTROL_TOKEN}" "${body}" "${payload}")"
    expect_code "${code}" 201 "create Unleash feature ${feature}" "${body}"
  else
    expect_code "${code}" 200 "read Unleash feature ${feature}" "${body}"
  fi
}

ensure_canary_strategy() {
  local body code payload strategy_count
  body="${workdir}/canary.json"
  code="$(api GET "/api/admin/projects/${PROJECT}/features/${CANARY_FEATURE}" \
    "${CONTROL_TOKEN}" "${body}")"
  expect_code "${code}" 200 'read Orion canary feature' "${body}"
  strategy_count="$(jq -r --arg environment "${ENVIRONMENT}" \
    '[.environments[] | select(.name == $environment) | .strategies[]] | length' "${body}")"
  if [[ ${strategy_count} == 0 ]]; then
    payload='{"name":"flexibleRollout","title":"Orion canary tenant only","parameters":{"groupId":"orion-canary-assistant","rollout":"100","stickiness":"default"},"constraints":[{"contextName":"tenantId","operator":"IN","values":["canary-a"],"caseInsensitive":false,"inverted":false}]}'
    code="$(api POST "/api/admin/projects/${PROJECT}/features/${CANARY_FEATURE}/environments/${ENVIRONMENT}/strategies" \
      "${CONTROL_TOKEN}" "${body}" "${payload}")"
    expect_code "${code}" 200 'create Orion canary strategy' "${body}"
  fi
  code="$(api POST "/api/admin/projects/${PROJECT}/features/${CANARY_FEATURE}/environments/${ENVIRONMENT}/on" \
    "${CONTROL_TOKEN}" "${body}")"
  expect_code "${code}" 200 'enable Orion canary feature' "${body}"
}

main() {
  require_command curl
  require_command jq
  require_service postgres
  require_service unleash
  retry 60 2 unleash_ready || die 'Unleash did not become healthy'

  local user_id body code
  user_id="$(ensure_control_identity)"
  reconcile_native_boundaries "${user_id}"
  docker restart kep-v2-unleash >/dev/null
  retry 60 2 unleash_ready || die 'Unleash did not reload reconciled authorization state'

  body="${workdir}/control-user.json"
  code="$(api GET /api/admin/user "${CONTROL_TOKEN}" "${body}")"
  expect_code "${code}" 200 'validate Unleash control PAT' "${body}"

  ensure_feature "${PROJECT}" "${CANARY_FEATURE}" \
    'Controls Orion Assistant availability for the contained canary tenant.'
  ensure_canary_strategy

  log 'Dedicated Orion Unleash service, control identity, and environment-scoped backend token are ready'
}

main "$@"
