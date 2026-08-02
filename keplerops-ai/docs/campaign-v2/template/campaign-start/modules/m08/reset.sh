#!/usr/bin/env bash
set -Eeuo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MODULE_ROOT
TEMPLATE_ROOT="$(cd "${MODULE_ROOT}/../../.." && pwd)"
readonly TEMPLATE_ROOT
readonly STATE_ROOT="${CAMPAIGN_STATE_ROOT:-${TEMPLATE_ROOT}/state/campaign-start}/m08"
readonly AIRFLOW_URL="${AIRFLOW_URL:-http://10.61.40.35:8080}"

die() { printf '[campaign-m08 reset] ERROR: %s\n' "$*" >&2; exit 1; }

dag_for() {
  case "$1" in
    kep-m08-a) echo orion_teacher_corpus_capture ;;
    kep-m08-b) echo orion_distillation_corpus_review ;;
    kep-m08-c) echo orion_student_training_first ;;
    kep-m08-d) echo orion_student_training_revision ;;
    kep-m08-e) echo orion_student_hidden_compatibility ;;
    kep-m08-f) echo cinder_offline_student_submission ;;
    kep-m08-g) echo cinder_artifact_proxy_training ;;
    kep-m08-h) echo orion_vision_privacy_audit ;;
    kep-m08-j) echo orion_protected_package_validation ;;
    kep-m08-k) echo orion_review_prediction ;;
    kep-m08-i) echo '' ;;
    *) die "unknown operation: $1" ;;
  esac
}

delete_failed_runs() {
  local dag_id=$1 token runs run_id
  [[ -n ${dag_id} ]] || return 0
  token="$(curl -fsS -H 'Content-Type: application/json' -X POST \
    --data '{"username":"range-admin","password":"KeplerV2-Training-Airflow"}' \
    "${AIRFLOW_URL}/auth/token" | jq -er '.access_token')"
  runs="$(curl -fsS -H "Authorization: Bearer ${token}" \
    "${AIRFLOW_URL}/api/v2/dags/${dag_id}/dagRuns?states=failed&limit=100")"
  while IFS= read -r run_id; do
    [[ -n ${run_id} ]] || continue
    curl -fsS -H "Authorization: Bearer ${token}" -X DELETE \
      "${AIRFLOW_URL}/api/v2/dags/${dag_id}/dagRuns/${run_id}" >/dev/null
  done < <(jq -r '.dag_runs[]?.dag_run_id' <<<"${runs}")
}

reset_hardware_attempt() {
  local token_file="${STATE_ROOT}/hardware-active-token"
  [[ -s ${token_file} ]] || return 0
  local token
  token="$(<"${token_file}")"
  docker exec --user kasm-user --env HOME=/home/kasm-user \
    --env LG_COORDINATOR=labgrid-coordinator:20408 --env LG_TOKEN="${token}" \
    keplerops-participant-workstation-runtime labgrid-client --place + release >/dev/null 2>&1 || true
  docker exec --user kasm-user --env HOME=/home/kasm-user \
    --env LG_COORDINATOR=labgrid-coordinator:20408 \
    keplerops-participant-workstation-runtime labgrid-client cancel-reservation "${token}" >/dev/null 2>&1 || true
  rm -f "${token_file}"
}

main() {
  local operation=${1:-}
  [[ -n ${operation} ]] || die 'usage: reset.sh <kep-m08-operation>'
  jq -e --arg id "${operation}" 'any(.[]; .id == $id)' "${MODULE_ROOT}/operations.json" >/dev/null || die "unknown operation: ${operation}"
  if [[ ${operation} == kep-m08-i ]]; then
    reset_hardware_attempt
  else
    delete_failed_runs "$(dag_for "${operation}")"
  fi
  case "${operation}" in
    kep-m08-f|kep-m08-j)
      rm -f "${STATE_ROOT}/offline/rejected/"*.json
      ;;
  esac
  rm -f "${STATE_ROOT}/applied/${operation}"
  printf '%s: failed attempt state cleared; accepted artifacts preserved\n' "${operation}"
}

main "$@"
