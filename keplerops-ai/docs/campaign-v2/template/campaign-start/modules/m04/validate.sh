#!/usr/bin/env bash
set -Eeuo pipefail

readonly MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly TEMPLATE_ROOT="$(cd "${MODULE_ROOT}/../../.." && pwd)"
readonly OPERATION="${1:-}"
readonly RESEARCH_BASE="${ORION_RESEARCH_URL:-https://research.keplerops.lab}"
readonly RESEARCH_USER="${ORION_RESEARCH_USER:-eval.reader}"
readonly RESEARCH_PASSWORD="${ORION_RESEARCH_PASSWORD:-EvalReader-Archive-2026}"
readonly CINDER_RELAY_URL="${CINDER_RELAY_URL:-https://relay.cinder.lab}"
readonly MINIO_MC_IMAGE="${MINIO_MC_IMAGE:-$(sed -n 's/^MINIO_MC_IMAGE=//p' "${TEMPLATE_ROOT}/engineering/component-lock.additions.env")}"

log() { printf '[campaign-m04-validate] %s\n' "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }

known_operation() {
  jq -e --arg id "$1" 'any(.[]; .id == $id)' "${MODULE_ROOT}/operations.json" >/dev/null
}

flag_for() {
  jq -er --arg id "$1" '.[] | select(.id == $id) | .flag' "${MODULE_ROOT}/operations.json"
}

curl_tls_args() {
  if [[ -n ${KEPLEROPS_CA_CERT:-} ]]; then
    printf '%s\0%s\0' --cacert "${KEPLEROPS_CA_CERT}"
  fi
}

validate_research_report() {
  local id=$1 kind=$2 flag status
  local -a tls=()
  flag="$(flag_for "${id}")"
  while IFS= read -r -d '' value; do tls+=("${value}"); done < <(curl_tls_args)

  curl -fsS --connect-timeout 10 --max-time 45 "${tls[@]}" \
    -u "${RESEARCH_USER}:${RESEARCH_PASSWORD}" \
    "${RESEARCH_BASE}/v1/reports/${kind}/latest" >"${TMPDIR_VALIDATE}/positive.json"
  grep -Fq "${flag}" "${TMPDIR_VALIDATE}/positive.json" || \
    die "${id}: authenticated ${kind} report does not contain its native reference"

  status="$(curl -sS --connect-timeout 10 --max-time 30 "${tls[@]}" \
    -o "${TMPDIR_VALIDATE}/negative.json" -w '%{http_code}' \
    "${RESEARCH_BASE}/v1/reports/${kind}/latest")"
  [[ ${status} == 401 ]] || die "${id}: anonymous report read returned HTTP ${status}, expected 401"
  ! grep -Fq "${flag}" "${TMPDIR_VALIDATE}/negative.json" || \
    die "${id}: anonymous report read exposed the native reference"
}

validate_context_canary_leak() { validate_research_report "$1" context-leak; }
validate_prompt_section_extraction() { validate_research_report "$1" routing-extraction; }
validate_privacy_calibration() { validate_research_report "$1" privacy-calibration; }
validate_individual_membership() { validate_research_report "$1" individual-membership; }
validate_cohort_membership() { validate_research_report "$1" cohort-membership; }
validate_orion_fingerprint() { validate_research_report "$1" compatibility; }
validate_repeatable_hallucination() { validate_research_report "$1" factuality; }
validate_prompt_envelope() { validate_research_report "$1" parser-compatibility; }
validate_agent_capabilities() { validate_research_report "$1" capabilities; }
validate_trigger_to_tool() { validate_research_report "$1" release-dry-run; }

validate_running_revision() {
  local id=$1 flag model_sha
  flag="$(flag_for "${id}")"
  model_sha="$(curl -fsS http://192.168.78.30:30083/v1/models/orion-release-risk | jq -er '.model_sha256')"
  docker run --rm --network kep-v2-data "${MINIO_MC_IMAGE}" sh -eu -c "
    mc alias set evaluator http://minio:9000 orion-runtime-reader KeplerV2-Orion-Runtime-Attestation >/dev/null
    mc cat 'evaluator/artifacts/runtime-attestations/${model_sha}.json'
  " >"${TMPDIR_VALIDATE}/positive.json"
  grep -Fq "${flag}" "${TMPDIR_VALIDATE}/positive.json" || \
    die "${id}: scoped evaluator object read did not return the runtime attestation"

  if docker run --rm --network kep-v2-data "${MINIO_MC_IMAGE}" sh -eu -c '
    mc alias set evaluator http://minio:9000 orion-runtime-reader KeplerV2-Orion-Runtime-Attestation >/dev/null
    mc ls evaluator/artifacts
  ' >"${TMPDIR_VALIDATE}/negative" 2>&1; then
    die "${id}: scoped object credential unexpectedly listed the bucket"
  fi
  ! grep -Fq "${flag}" "${TMPDIR_VALIDATE}/negative" || \
    die "${id}: untrusted object-store response exposed the runtime reference"
}

validate_browser_side_channel() {
  local id=$1 flag token_file token status
  local -a tls=()
  flag="$(flag_for "${id}")"
  token_file="${TEMPLATE_ROOT}/state/campaign-start/m04/m04-support-render.token"
  [[ -s ${token_file} ]] || die "${id}: support relay token has not been provisioned"
  token="$(<"${token_file}")"
  while IFS= read -r -d '' value; do tls+=("${value}"); done < <(curl_tls_args)

  curl -fsS --connect-timeout 10 --max-time 30 "${tls[@]}" -H "Authorization: ${token}" \
    "${CINDER_RELAY_URL}/api/baskets/m04-support-render/requests" >"${TMPDIR_VALIDATE}/positive.json"
  grep -Fq "${flag}" "${TMPDIR_VALIDATE}/positive.json" || \
    die "${id}: support review browser has not requested the protected native URL"

  status="$(curl -sS --connect-timeout 10 --max-time 30 "${tls[@]}" \
    -o "${TMPDIR_VALIDATE}/negative.json" -w '%{http_code}' \
    "${CINDER_RELAY_URL}/api/baskets/m04-support-render/requests")"
  case "${status}" in 401|403) ;; *) die "${id}: tokenless relay read returned HTTP ${status}" ;; esac
  ! grep -Fq "${flag}" "${TMPDIR_VALIDATE}/negative.json" || \
    die "${id}: tokenless relay read exposed the protected native URL"
}

validate_archive_authorization_spill() {
  local id=$1 flag status
  local -a tls=()
  flag="$(flag_for "${id}")"
  while IFS= read -r -d '' value; do tls+=("${value}"); done < <(curl_tls_args)
  curl -fsS --connect-timeout 10 --max-time 30 "${tls[@]}" \
    -u "${RESEARCH_USER}:${RESEARCH_PASSWORD}" \
    "${RESEARCH_BASE}/v1/exports/7403" >"${TMPDIR_VALIDATE}/positive.json"
  grep -Fq "${flag}" "${TMPDIR_VALIDATE}/positive.json" || \
    die "${id}: neighboring archive did not expose its native service reference"
  status="$(curl -sS --connect-timeout 10 --max-time 30 "${tls[@]}" \
    -o "${TMPDIR_VALIDATE}/negative.json" -w '%{http_code}' \
    "${RESEARCH_BASE}/v1/exports/7403")"
  [[ ${status} == 401 ]] || die "${id}: anonymous archive read returned HTTP ${status}, expected 401"
  ! grep -Fq "${flag}" "${TMPDIR_VALIDATE}/negative.json" || \
    die "${id}: anonymous archive read exposed the service reference"
}

main() {
  local handler
  [[ -n ${OPERATION} ]] || die "usage: $0 operation-id"
  for command in curl docker jq; do command -v "${command}" >/dev/null || die "missing command: ${command}"; done
  known_operation "${OPERATION}" || die "unknown operation: ${OPERATION}"
  case "${OPERATION}" in
    kep-m04-a) handler=validate_context_canary_leak ;;
    kep-m04-b) handler=validate_prompt_section_extraction ;;
    kep-m04-c) handler=validate_privacy_calibration ;;
    kep-m04-d) handler=validate_individual_membership ;;
    kep-m04-e) handler=validate_cohort_membership ;;
    kep-m04-f) handler=validate_orion_fingerprint ;;
    kep-m04-g) handler=validate_running_revision ;;
    kep-m04-h) handler=validate_repeatable_hallucination ;;
    kep-m04-i) handler=validate_prompt_envelope ;;
    kep-m04-j) handler=validate_agent_capabilities ;;
    kep-m04-k) handler=validate_trigger_to_tool ;;
    kep-m04-l) handler=validate_browser_side_channel ;;
    kep-m04-m) handler=validate_archive_authorization_spill ;;
    *) die "missing validation dispatch: ${OPERATION}" ;;
  esac
  declare -F "${handler}" >/dev/null || die "missing validator: ${handler}"
  TMPDIR_VALIDATE="$(mktemp -d)"
  readonly TMPDIR_VALIDATE
  trap 'rm -rf "${TMPDIR_VALIDATE}"' EXIT
  "${handler}" "${OPERATION}"
  log "${OPERATION}: participant carrier and negative control passed"
}

main "$@"
