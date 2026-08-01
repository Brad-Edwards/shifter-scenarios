#!/usr/bin/env bash

set -Eeuo pipefail

readonly FORGEJO_GIT_URL=http://10.61.40.20:3000/keplerops/orion-build.git
readonly FORGEJO_API_URL=http://10.61.40.20:3000/api/v1
readonly FORGEJO_AUTH=range-admin:KeplerV2-Training-Forgejo-Admin
readonly REPOSITORY=keplerops/orion-build
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR

if [[ ${EUID} -ne 0 ]]; then
  printf 'reconcile-release-risk-source.sh must run as root\n' >&2
  exit 2
fi

for command in base64 curl git install jq seq sha256sum sleep; do
  command -v "${command}" >/dev/null || {
    printf 'missing required command: %s\n' "${command}" >&2
    exit 1
  }
done

work="$(mktemp -d)"
trap 'rm -rf "${work}"' EXIT
authorization="$(printf '%s' "${FORGEJO_AUTH}" | base64 -w0)"
git -c "http.extraHeader=Authorization: Basic ${authorization}" clone \
  --quiet --branch main --single-branch "${FORGEJO_GIT_URL}" "${work}/repository"

install -D -m 0644 "${SCRIPT_DIR}/airflow/dags/orion_release_risk_training.py" \
  "${work}/repository/training/orion_release_risk_training.py"
install -D -m 0644 "${SCRIPT_DIR}/release-risk/base-model.json" \
  "${work}/repository/training/base-model.json"
install -D -m 0644 "${SCRIPT_DIR}/release-risk/label-schema.json" \
  "${work}/repository/training/label-schema.json"
jq -nS \
  --arg dag "$(sha256sum "${work}/repository/training/orion_release_risk_training.py" | awk '{print $1}')" \
  --arg base_model "$(sha256sum "${work}/repository/training/base-model.json" | awk '{print $1}')" \
  --arg label_schema "$(sha256sum "${work}/repository/training/label-schema.json" | awk '{print $1}')" \
  '{
    schema: "keplerops.orion-release-risk-source/v1",
    files: {
      "training/orion_release_risk_training.py": $dag,
      "training/base-model.json": $base_model,
      "training/label-schema.json": $label_schema
    }
  }' >"${work}/repository/training/source-manifest.json"

git -C "${work}/repository" config user.name 'KeplerOps Build Automation'
git -C "${work}/repository" config user.email 'build.automation@keplerops.lab'
git -C "${work}/repository" add training
publish=false
if ! git -C "${work}/repository" diff --cached --quiet; then
  git -C "${work}/repository" commit --quiet \
    --message 'Update Orion Release Risk training source'
  publish=true
fi
if [[ ${publish} == true ]]; then
  git -C "${work}/repository" \
    -c "http.extraHeader=Authorization: Basic ${authorization}" \
    push --quiet origin HEAD:main
fi

revision="$(git -C "${work}/repository" rev-parse HEAD)"
latest_run_revision=''
for _ in $(seq 1 5); do
  latest_run_revision="$(curl -fsS --user "${FORGEJO_AUTH}" \
    "${FORGEJO_API_URL}/repos/${REPOSITORY}/actions/tasks?limit=1" |
    jq -r '(.workflow_runs | max_by(.id).head_sha) // ""')"
  [[ ${latest_run_revision} == "${revision}" ]] && break
  sleep 1
done
if [[ ${latest_run_revision} != "${revision}" ]]; then
  curl -fsS --user "${FORGEJO_AUTH}" \
    --header 'Content-Type: application/json' \
    --request POST --data '{"ref":"main","return_run_info":true}' \
    "${FORGEJO_API_URL}/repos/${REPOSITORY}/actions/workflows/publish.yml/dispatches" \
    | jq -e '.id > 0 and (.jobs | index("publish")) != null' >/dev/null
fi
printf 'Forgejo release-risk source reconciled: revision=%s\n' "${revision}"
