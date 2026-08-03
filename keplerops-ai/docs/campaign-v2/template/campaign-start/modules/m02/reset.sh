#!/usr/bin/env bash
set -Eeuo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MODULE_ROOT
TEMPLATE_ROOT="$(cd "${MODULE_ROOT}/../../.." && pwd)"
readonly TEMPLATE_ROOT
readonly STATE_ROOT="${CAMPAIGN_STATE_ROOT:-${TEMPLATE_ROOT}/state/campaign-start}/m02"
readonly OPERATION="${1:-}"
ATTEMPT_ID="${2:-${M02_ATTEMPT_ID:-}}"

die() { printf '[m02 reset] ERROR: %s\n' "$*" >&2; exit 1; }

compose() {
  docker compose --project-directory "${TEMPLATE_ROOT}" \
    --env-file "${TEMPLATE_ROOT}/component-lock.env" \
    --env-file "${TEMPLATE_ROOT}/engineering/component-lock.additions.env" \
    -f "${TEMPLATE_ROOT}/compose.foundation.yaml" \
    -f "${TEMPLATE_ROOT}/compose.enterprise.yaml" \
    -f "${TEMPLATE_ROOT}/compose.engineering.yaml" \
    -f "${TEMPLATE_ROOT}/compose.cinder.yaml" \
    -f "${TEMPLATE_ROOT}/campaign-start/modules/m06/compose.overlay.yaml" \
    -f "${MODULE_ROOT}/compose.overlay.yaml" "$@"
}

delete_attempt_airflow_runs() {
  local record run dag code candidate
  while IFS= read -r -d '' record; do
    jq -e '.status != "completed"' "${record}" >/dev/null || continue
    candidate="$(jq -r '.attempt_id // .native_attempt_id // empty' "${record}")"
    [[ ${candidate} == "${ATTEMPT_ID}" ]] || continue
    while IFS= read -r run; do
      [[ -n ${run} ]] || continue
      # shellcheck disable=SC2016
      if find "${STATE_ROOT}/records" -maxdepth 1 -type f -name 'kep-m02-?-*.json' -print0 | \
        xargs -0 -r jq -e --arg run "${run}" 'select(.status == "completed") | .. | strings | select(. == $run)' >/dev/null 2>&1; then
        continue
      fi
      for dag in orion_partner_sources orion_m02_partner_routing orion_m02_partner_room_finalize; do
        code="$(docker exec kep-v2-airflow-api curl -sS -u range-admin:KeplerV2-Training-Airflow \
          -o /dev/null -w '%{http_code}' -X DELETE \
          "http://127.0.0.1:8080/api/v2/dags/${dag}/dagRuns/${run}")"
        case "${code}" in 200|202|204|404) break ;; esac
      done
    done < <(jq -r '.. | objects | .airflow_run_id? // empty' "${record}" | sort -u)
  done < <(find "${STATE_ROOT}/records" "${STATE_ROOT}/active" -maxdepth 1 -type f -name "${OPERATION}-*.json" -print0 2>/dev/null)
}

resolve_attempt() {
  local path candidate
  local -a candidates=()
  [[ -z ${ATTEMPT_ID} ]] || return
  while IFS= read -r -d '' path; do
    jq -e --arg operation "${OPERATION}" '.status != "completed" and ((.operation // $operation) == $operation)' "${path}" >/dev/null || continue
    candidate="$(jq -r '.attempt_id // .native_attempt_id // empty' "${path}")"
    [[ -n ${candidate} ]] && candidates+=("${candidate}")
  done < <(find "${STATE_ROOT}/records" "${STATE_ROOT}/active" -maxdepth 1 -type f -name "${OPERATION}-*.json" -print0 2>/dev/null)
  if [[ -f ${STATE_ROOT}/recipient/state.json ]]; then
    while IFS= read -r candidate; do [[ -n ${candidate} ]] && candidates+=("${candidate}"); done \
      < <(jq -r --arg operation "${OPERATION}" '.negative_attempts | to_entries[]? | select(.value.operation == $operation and .value.status == "denied") | .key' "${STATE_ROOT}/recipient/state.json")
  fi
  mapfile -t candidates < <(printf '%s\n' "${candidates[@]}" | sed '/^$/d' | sort -u)
  [[ ${#candidates[@]} -eq 1 ]] || die "set M02_ATTEMPT_ID (found ${#candidates[@]} rejected attempts for ${OPERATION})"
  ATTEMPT_ID=${candidates[0]}
}

main() {
  [[ -n ${OPERATION} ]] || die 'usage: reset.sh <operation-id> [attempt-id]'
  jq -e --arg id "${OPERATION}" 'any(.[]; .id == $id)' "${MODULE_ROOT}/operations.json" >/dev/null || die "unknown operation: ${OPERATION}"
  for command in docker find jq; do command -v "${command}" >/dev/null || die "missing command: ${command}"; done
  resolve_attempt
  [[ ${ATTEMPT_ID} =~ ^[A-Za-z0-9._:-]{8,160}$ ]] || die 'invalid server-issued attempt ID'
  delete_attempt_airflow_runs
  case "${OPERATION}" in
    kep-m02-i|kep-m02-j)
      compose exec -T m02-recipient-worker python /app/recipient_worker.py reset-rejected "${OPERATION}" "${ATTEMPT_ID}" ;;
    kep-m02-k)
      compose exec -T m02-recipient-worker python /app/recipient_worker.py reset-rejected "${OPERATION}" "${ATTEMPT_ID}"
      compose exec -T m02-business-worker python /app/reset_runtime.py "${OPERATION}" "${ATTEMPT_ID}" ;;
    *)
      compose exec -T m02-business-worker python /app/reset_runtime.py "${OPERATION}" "${ATTEMPT_ID}" ;;
  esac
  printf '%s\n' "${OPERATION}/${ATTEMPT_ID}: only server-owned state for this rejected attempt was reset; participant uploads, devpi releases, accepted checkpoints, ancestors, entitlements, and descendants were preserved"
}

main
