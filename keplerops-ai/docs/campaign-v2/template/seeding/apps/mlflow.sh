#!/usr/bin/env bash

set -Eeuo pipefail

readonly MLFLOW_URL="${MLFLOW_URL:-http://10.61.40.36:5000}"
readonly MLFLOW_ADMIN_USER="${MLFLOW_ADMIN_USER:-range-admin}"
readonly MLFLOW_ADMIN_PASSWORD="${MLFLOW_ADMIN_PASSWORD:-KeplerV2-Training-MLflow-Admin}"
readonly MLFLOW_READ_USER="${MLFLOW_READ_USER:-orion-reader}"
readonly MLFLOW_READ_PASSWORD="${MLFLOW_READ_PASSWORD:-KeplerV2-Training-MLflow-Read}"
readonly MLFLOW_MAINTAIN_USER="${MLFLOW_MAINTAIN_USER:-orion-maintainer}"
readonly MLFLOW_MAINTAIN_PASSWORD="${MLFLOW_MAINTAIN_PASSWORD:-KeplerV2-Training-MLflow-Maintain}"
readonly MLFLOW_SERVICE_USER="${MLFLOW_SERVICE_USER:-svc-orion-training}"
readonly MLFLOW_SERVICE_PASSWORD="${MLFLOW_SERVICE_PASSWORD:-KeplerV2-Training-MLflow-Service}"

log() {
  printf '[campaign-v2-seed] %s\n' "$*" >&2
}

die() {
  log "ERROR: $*"
  exit 1
}

api() {
  local username=$1
  local password=$2
  local method=$3
  local path=$4
  shift 4
  curl --silent --show-error --fail-with-body \
    --user "${username}:${password}" \
    --request "${method}" "$@" "${MLFLOW_URL}${path}"
}

admin_api() {
  api "${MLFLOW_ADMIN_USER}" "${MLFLOW_ADMIN_PASSWORD}" "$@"
}

service_api() {
  api "${MLFLOW_SERVICE_USER}" "${MLFLOW_SERVICE_PASSWORD}" "$@"
}

ensure_user() {
  local username=$1
  local password=$2
  local encoded payload
  encoded="$(jq -rn --arg value "${username}" '$value|@uri')"
  payload="$(jq -cn --arg username "${username}" --arg password "${password}" \
    '{username:$username,password:$password}')"

  if admin_api GET "/api/2.0/mlflow/users/get?username=${encoded}" \
    >/dev/null 2>&1; then
    admin_api PATCH '/api/2.0/mlflow/users/update-password' \
      --header 'Content-Type: application/json' --data "${payload}" >/dev/null
  else
    admin_api POST '/api/2.0/mlflow/users/create' \
      --header 'Content-Type: application/json' --data "${payload}" >/dev/null
  fi
  admin_api PATCH '/api/2.0/mlflow/users/update-admin' \
    --header 'Content-Type: application/json' \
    --data "$(jq -cn --arg username "${username}" \
      '{username:$username,is_admin:false}')" >/dev/null
}

ensure_experiment() {
  local name=$1
  local experiments experiment_id
  experiments="$(admin_api POST '/api/2.0/mlflow/experiments/search' \
    --header 'Content-Type: application/json' --data '{"max_results":1000}')"
  experiment_id="$(jq -r --arg name "${name}" \
    '.experiments[]? | select(.name == $name) | .experiment_id' \
    <<<"${experiments}" | head -n1)"
  if [[ -z ${experiment_id} ]]; then
    experiment_id="$(service_api POST '/api/2.0/mlflow/experiments/create' \
      --header 'Content-Type: application/json' \
      --data "$(jq -cn --arg name "${name}" '{name:$name}')" |
      jq -er '.experiment_id')"
  fi
  printf '%s\n' "${experiment_id}"
}

ensure_registered_model() {
  local name=$1
  local models
  models="$(admin_api GET '/api/2.0/mlflow/registered-models/search?max_results=1000')"
  if ! jq -e --arg name "${name}" \
    'any(.registered_models[]?; .name == $name)' <<<"${models}" >/dev/null; then
    service_api POST '/api/2.0/mlflow/registered-models/create' \
      --header 'Content-Type: application/json' \
      --data "$(jq -cn --arg name "${name}" '{name:$name}')" >/dev/null
  fi
}

ensure_permission() {
  local resource=$1
  local identifier_key=$2
  local identifier=$3
  local username=$4
  local permission=$5
  local encoded_id encoded_user path payload

  encoded_id="$(jq -rn --arg value "${identifier}" '$value|@uri')"
  encoded_user="$(jq -rn --arg value "${username}" '$value|@uri')"
  path="/api/2.0/mlflow/${resource}/permissions"
  payload="$(jq -cn \
    --arg key "${identifier_key}" --arg identifier "${identifier}" \
    --arg username "${username}" --arg permission "${permission}" \
    '{username:$username,permission:$permission} + {($key):$identifier}')"

  if admin_api GET "${path}/get?${identifier_key}=${encoded_id}&username=${encoded_user}" \
    >/dev/null 2>&1; then
    admin_api PATCH "${path}/update" --header 'Content-Type: application/json' \
      --data "${payload}" >/dev/null
  else
    admin_api POST "${path}/create" --header 'Content-Type: application/json' \
      --data "${payload}" >/dev/null
  fi
}

main() {
  for command in curl jq; do
    command -v "${command}" >/dev/null || die "required command is unavailable: ${command}"
  done
  curl --silent --show-error --fail "${MLFLOW_URL}/health" >/dev/null ||
    die "MLflow is unavailable"

  ensure_user "${MLFLOW_READ_USER}" "${MLFLOW_READ_PASSWORD}"
  ensure_user "${MLFLOW_MAINTAIN_USER}" "${MLFLOW_MAINTAIN_PASSWORD}"
  ensure_user "${MLFLOW_SERVICE_USER}" "${MLFLOW_SERVICE_PASSWORD}"

  local experiment experiment_id username permission
  for experiment in 'Orion Clean Intent Training' 'Orion Release Risk Training'; do
    experiment_id="$(ensure_experiment "${experiment}")"
    while IFS='|' read -r username permission; do
      ensure_permission experiments experiment_id "${experiment_id}" \
        "${username}" "${permission}"
    done <<PERMISSIONS
${MLFLOW_READ_USER}|READ
${MLFLOW_MAINTAIN_USER}|MANAGE
${MLFLOW_SERVICE_USER}|MANAGE
PERMISSIONS
  done

  ensure_registered_model 'Orion Release Risk'
  while IFS='|' read -r username permission; do
    ensure_permission registered-models name 'Orion Release Risk' \
      "${username}" "${permission}"
  done <<PERMISSIONS
${MLFLOW_READ_USER}|READ
${MLFLOW_MAINTAIN_USER}|MANAGE
${MLFLOW_SERVICE_USER}|MANAGE
PERMISSIONS

  log "MLflow native users and Orion resource permissions are ready"
}

main "$@"
