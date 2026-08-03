#!/usr/bin/env bash
set -Eeuo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MODULE_ROOT
TEMPLATE_ROOT="$(cd "${MODULE_ROOT}/../../.." && pwd)"
readonly TEMPLATE_ROOT
readonly STATE_ROOT="${CAMPAIGN_STATE_ROOT:-${TEMPLATE_ROOT}/state/campaign-start}/m08"

die() { printf '[campaign-m08 validate] ERROR: %s\n' "$*" >&2; exit 1; }

compose() {
  docker compose --project-directory "${TEMPLATE_ROOT}" \
    --env-file "${TEMPLATE_ROOT}/component-lock.env" \
    --env-file "${TEMPLATE_ROOT}/engineering/component-lock.additions.env" \
    -f "${TEMPLATE_ROOT}/compose.foundation.yaml" \
    -f "${TEMPLATE_ROOT}/compose.enterprise.yaml" \
    -f "${TEMPLATE_ROOT}/compose.engineering.yaml" \
    -f "${TEMPLATE_ROOT}/compose.cinder.yaml" \
    -f "${TEMPLATE_ROOT}/campaign-start/modules/m07/compose.overlay.yaml" \
    -f "${MODULE_ROOT}/compose.overlay.yaml" "$@"
}

main() {
  local operation=${1:-}
  [[ -n ${operation} ]] || die 'usage: validate.sh <kep-m08-operation>'
  jq -e --arg id "${operation}" 'any(.[]; .id == $id)' \
    "${MODULE_ROOT}/operations.json" >/dev/null || die "unknown operation: ${operation}"
  if [[ ${operation} == kep-m08-i ]]; then
    local hardware_marker boot_id proof_id place gates
    hardware_marker=${CAMPAIGN_HARDWARE_READINESS_MARKER:-/run/shifter/keplerops-v2-hardware.ready}
    [[ -s ${hardware_marker} ]] || \
      die 'real hardware readiness is absent; physical calibration remains blocked'
    IFS=$'\t' read -r boot_id proof_id place gates <"${hardware_marker}"
    [[ ${boot_id} == "$(cat /proc/sys/kernel/random/boot_id)" ]] || \
      die 'real hardware readiness proof is from another boot'
    [[ -n ${proof_id} && -n ${place} && ${gates} == operator-place+participant-reservation ]] || \
      die 'real hardware readiness lacks operator-place and participant-reservation proof'
    [[ -s ${STATE_ROOT}/hardware/accepted-calibration.json ]] || \
      die 'accepted real-bench calibration evidence is absent'
    jq -e '
      .schema == "keplerops.physical-calibration/v1"
      and .media_source == "uvc"
      and (.capture_hashes | length >= 2)
      and (.liveness_responses | length >= 2)
      and (.actuator_telemetry | length >= 2)
      and (.verifier_results | length >= 2)
      and (.bench_evidence_sha256 | test("^[0-9a-f]{64}$"))
    ' "${STATE_ROOT}/hardware/accepted-calibration.json" >/dev/null || \
      die 'physical calibration evidence does not satisfy the real-bench contract'
    printf '%s: real-bench native evidence passed\n' "${operation}"
    return
  fi
  if [[ ${operation} == kep-m08-k ]]; then
    docker inspect keplerops-participant-workstation-runtime >/dev/null 2>&1 || \
      die 'participant workstation runtime is unavailable for the fixed deny check'
    if docker exec --user kasm-user --env HOME=/home/kasm-user \
        keplerops-participant-workstation-runtime curl -fsS \
        --connect-timeout 3 --max-time 8 -H 'Content-Type: application/json' \
        -X POST --data '{"instances":[{"text":"direct unscoped validation probe"}]}' \
        http://192.168.78.30:30083/v1/models/orion-release-risk:predict \
        >/dev/null 2>&1; then
      die 'participant workstation can reach the protected model endpoint directly'
    fi
  fi
  compose run --rm --no-deps airflow-worker \
    python /opt/airflow/campaign-m08/validator.py "${operation}"
}

main "$@"
