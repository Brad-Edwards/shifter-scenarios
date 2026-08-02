#!/usr/bin/env bash
set -Eeuo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MODULE_ROOT
TEMPLATE_ROOT="$(cd "${MODULE_ROOT}/../../.." && pwd)"
readonly TEMPLATE_ROOT
readonly STATE_ROOT="${CAMPAIGN_STATE_ROOT:-${TEMPLATE_ROOT}/state/campaign-start}/m08"
readonly SOFTWARE_DEPLOY_ONLY="${CAMPAIGN_SOFTWARE_DEPLOY_ONLY:-0}"
readonly LABEL_STUDIO_URL="${LABEL_STUDIO_URL:-http://10.61.40.34:8080}"
readonly LABEL_STUDIO_TOKEN="${LABEL_STUDIO_API_TOKEN:-31a5a4b4ab3cdbaf110644eed06853b2b418daf6}"
readonly FORGEJO_API_URL="${CINDER_FORGEJO_API_URL:-http://10.61.90.30:3000/api/v1}"
readonly FORGEJO_AUTH="${CINDER_FORGEJO_AUTH:-cinder-operator:Cinder-Operations-Git-K3m7Pq4x}"
readonly MLFLOW_URL="${MLFLOW_URL:-http://10.61.40.36:5000}"
readonly MLFLOW_AUTH="${MLFLOW_AUTH:-svc-orion-training:KeplerV2-Training-MLflow-Service}"

log() { printf '[campaign-m08] %s\n' "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }

compose() {
  docker compose --project-directory "${TEMPLATE_ROOT}" \
    --env-file "${TEMPLATE_ROOT}/component-lock.env" \
    --env-file "${TEMPLATE_ROOT}/engineering/component-lock.additions.env" \
    -f "${TEMPLATE_ROOT}/compose.foundation.yaml" \
    -f "${TEMPLATE_ROOT}/compose.enterprise.yaml" \
    -f "${TEMPLATE_ROOT}/compose.engineering.yaml" \
    -f "${TEMPLATE_ROOT}/compose.cinder.yaml" \
    -f "${MODULE_ROOT}/compose.overlay.yaml" "$@"
}

forgejo() {
  local method=$1 path=$2
  shift 2
  curl -fsS --user "${FORGEJO_AUTH}" -H 'Content-Type: application/json' \
    -X "${method}" "$@" "${FORGEJO_API_URL}${path}"
}

ensure_repo() {
  forgejo GET /repos/cinder-operator/orion-extraction-research >/dev/null 2>&1 || \
    forgejo POST /user/repos --data \
      '{"name":"orion-extraction-research","description":"Cinder model extraction notebooks, corpus manifests, and training code.","private":true,"auto_init":true,"default_branch":"main"}' >/dev/null
  local source target message current sha payload
  while IFS='|' read -r source target message; do
    current="$(forgejo GET "/repos/cinder-operator/orion-extraction-research/contents/${target}" 2>/dev/null || true)"
    sha="$(jq -r '.sha // empty' <<<"${current:-{}}")"
    payload="$(base64 -w0 "${MODULE_ROOT}/payloads/${source}" | jq -Rs --arg sha "${sha}" --arg message "${message}" \
      '{content:.,message:$message,branch:"main"} + (if $sha == "" then {} else {sha:$sha} end)')"
    forgejo PUT "/repos/cinder-operator/orion-extraction-research/contents/${target}" --data "${payload}" >/dev/null
  done <<'EOF'
RESEARCH.md|RESEARCH.md|Publish Orion extraction research handbook
release-slices.json|release-slices.json|Publish Release Risk slice matrix
EOF
}

ensure_label_project() {
  local projects project_id config payload
  projects="$(curl -fsS -H "Authorization: Token ${LABEL_STUDIO_TOKEN}" \
    "${LABEL_STUDIO_URL}/api/projects?page_size=100")"
  project_id="$(jq -r '.results[] | select(.title == "Orion Release Risk Compatibility Review") | .id' <<<"${projects}" | head -n1)"
  # Label Studio requires the literal field reference "$text".
  # shellcheck disable=SC2016
  config='<View><Text name="text" value="$text"/><Choices name="release_risk" toName="text" choice="single"><Choice value="ReleaseApprove"/><Choice value="ReleaseHold"/><Choice value="PartnerIntake"/><Choice value="EntitlementReview"/><Choice value="SecurityAdvisory"/><Choice value="SupportEscalation"/><Choice value="ResearchReview"/><Choice value="PrivacySafety"/></Choices></View>'
  payload="$(jq -cn --arg title 'Orion Release Risk Compatibility Review' --arg description 'Prediction-assisted compatibility review for synthetic release records.' --arg label_config "${config}" '{title:$title,description:$description,label_config:$label_config}')"
  if [[ -n ${project_id} ]]; then
    curl -fsS -X PATCH -H "Authorization: Token ${LABEL_STUDIO_TOKEN}" -H 'Content-Type: application/json' \
      --data "${payload}" "${LABEL_STUDIO_URL}/api/projects/${project_id}" >/dev/null
  else
    curl -fsS -X POST -H "Authorization: Token ${LABEL_STUDIO_TOKEN}" -H 'Content-Type: application/json' \
      --data "${payload}" "${LABEL_STUDIO_URL}/api/projects" >/dev/null
  fi
}

ensure_mlflow_experiment() {
  if curl -fsS --user "${MLFLOW_AUTH}" --get --data-urlencode 'experiment_name=Cinder Orion Extraction Research' \
      "${MLFLOW_URL}/api/2.0/mlflow/experiments/get-by-name" >/dev/null 2>&1; then
    return 0
  fi
  curl -fsS --user "${MLFLOW_AUTH}" -H 'Content-Type: application/json' -X POST \
    --data '{"name":"Cinder Orion Extraction Research","artifact_location":"s3://mlflow/cinder-orion-extraction"}' \
    "${MLFLOW_URL}/api/2.0/mlflow/experiments/create" >/dev/null
}

ensure_cinder_storage() {
  compose up -d cinder-minio cinder-forgejo cinder-forgejo-bootstrap cinder-bootstrap >/dev/null
  compose wait cinder-forgejo-bootstrap cinder-bootstrap >/dev/null
  # shellcheck disable=SC2016
  compose run --rm --no-deps --entrypoint /bin/sh cinder-bootstrap -ec '
    mc alias set cinder http://10.61.90.31:9000 cinder-operator Cinder-Operations-ObjectStore-T7v2Lm9q >/dev/null
    for bucket in artifacts datasets models; do
      mc mb --ignore-existing "cinder/${bucket}" >/dev/null
      mc anonymous set none "cinder/${bucket}" >/dev/null
    done
  ' >/dev/null
}

ensure_airflow() {
  compose up -d --build airflow-api airflow-scheduler airflow-dag-processor airflow-triggerer airflow-worker cinder-offline-model-runner >/dev/null
  local token
  token="$(curl -fsS -H 'Content-Type: application/json' -X POST \
    --data '{"username":"range-admin","password":"KeplerV2-Training-Airflow"}' \
    http://10.61.40.35:8080/auth/token | jq -er '.access_token')"
  for _ in $(seq 1 60); do
    if curl -fsS -H "Authorization: Bearer ${token}" \
        http://10.61.40.35:8080/api/v2/dags/orion_teacher_corpus_capture >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  die 'Airflow did not discover the Orion extraction workflows'
}

apply_one() {
  local operation=$1
  jq -e --arg id "${operation}" 'any(.[]; .id == $id)' "${MODULE_ROOT}/operations.json" >/dev/null || die "unknown operation: ${operation}"
  install -d -m 0750 "${STATE_ROOT}/applied" "${STATE_ROOT}/offline/inbox" "${STATE_ROOT}/offline/packages" \
    "${STATE_ROOT}/offline/reports" "${STATE_ROOT}/offline/accepted" "${STATE_ROOT}/offline/rejected"
  ensure_cinder_storage
  ensure_repo
  ensure_label_project
  ensure_mlflow_experiment
  ensure_airflow
  if [[ ${operation} == kep-m08-i ]]; then
    "${TEMPLATE_ROOT}/scripts/prove-hardware.sh"
  fi
  printf '%s\n' "${operation}" >"${STATE_ROOT}/applied/${operation}"
  log "reconciled ${operation} start state"
}

main() {
  local requested=${1:-all} operation command
  for command in base64 curl docker jq; do command -v "${command}" >/dev/null || die "missing command: ${command}"; done
  if [[ ${requested} != all ]]; then apply_one "${requested}"; return; fi
  install -d -m 0750 "${STATE_ROOT}/applied" "${STATE_ROOT}/offline/inbox" "${STATE_ROOT}/offline/packages" \
    "${STATE_ROOT}/offline/reports" "${STATE_ROOT}/offline/accepted" "${STATE_ROOT}/offline/rejected"
  ensure_cinder_storage
  ensure_repo
  ensure_label_project
  ensure_mlflow_experiment
  ensure_airflow
  if [[ ${SOFTWARE_DEPLOY_ONLY} != 1 ]]; then
    "${TEMPLATE_ROOT}/scripts/prove-hardware.sh"
  fi
  while IFS= read -r operation; do
    if [[ ${SOFTWARE_DEPLOY_ONLY} == 1 && ${operation} == kep-m08-i ]]; then
      continue
    fi
    printf '%s\n' "${operation}" >"${STATE_ROOT}/applied/${operation}"
  done \
    < <(jq -r '.[].id' "${MODULE_ROOT}/operations.json")
  if [[ ${SOFTWARE_DEPLOY_ONLY} == 1 ]]; then
    log 'reconciled m08 software research state; physical calibration remains unavailable'
  else
    log 'reconciled all m08 research start state without producing accepted results'
  fi
}

main "$@"
