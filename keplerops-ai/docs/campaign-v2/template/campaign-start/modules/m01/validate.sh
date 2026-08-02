#!/usr/bin/env bash
set -Eeuo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MODULE_ROOT
readonly OPERATIONS="${MODULE_ROOT}/operations.json"

die() { printf '[m01 validate] ERROR: %s\n' "$*" >&2; exit 1; }

fetch_carrier() {
  local url=$1 output=$2
  [[ ${url} =~ ^https://[^/]+\.(keplerops|cinder)\.lab(/|$) ]] || \
    die "carrier must be reached through a participant-visible enterprise URL"
  local -a args=(-fsS --connect-timeout 10 --max-time 60)
  [[ -z ${PARTICIPANT_COOKIE_FILE:-} ]] || args+=(-b "${PARTICIPANT_COOKIE_FILE}")
  [[ -z ${PARTICIPANT_BEARER_TOKEN:-} ]] || args+=(-H "Authorization: Bearer ${PARTICIPANT_BEARER_TOKEN}")
  curl "${args[@]}" "${url}" > "${output}"
}

negative_direct_source_denied() {
  local code
  code="$(curl -ksS -o /dev/null -w '%{http_code}' \
    https://vectors.keplerops.lab/collections/orion_partner_intake/points/scroll)"
  [[ ${code} == 401 || ${code} == 403 || ${code} == 405 ]] || \
    die "unauthenticated direct vector access was not denied (HTTP ${code})"
}

negative_direct_path_denied() {
  local method=$1 path=$2 code
  code="$(curl -ksS -o /dev/null -w '%{http_code}' -X "${method}" "https://release.keplerops.lab${path}")"
  [[ ${code} == 401 || ${code} == 403 ]] || \
    die "direct enterprise shortcut ${path} was not denied (HTTP ${code})"
}

negative_result_has_no_flag() {
  local flag=$1 pattern=$2 url=${PARTICIPANT_NEGATIVE_URL:-} tmp
  [[ -n ${url} ]] || die "set PARTICIPANT_NEGATIVE_URL to the participant-visible refusal, rejected job, or benign control"
  tmp="$(mktemp)"
  fetch_carrier "${url}" "${tmp}"
  ! grep -Fq "${flag}" "${tmp}" || { rm -f "${tmp}"; die "negative control exposed the operation flag"; }
  grep -Eqi "${pattern}" "${tmp}" || { rm -f "${tmp}"; die "negative control lacks the expected refusal or benign state"; }
  rm -f "${tmp}"
}

negative_public_build_control() {
  local code
  code="$(curl -ksS -o /dev/null -w '%{http_code}' -X POST \
    -H 'Content-Type: application/json' --data '{"code":"print(1)"}' \
    https://flows.keplerops.lab/api/v1/validate/code)"
  [[ ${code} == 401 || ${code} == 403 || ${code} == 405 ]] || \
    die "protected Langflow validation shortcut was not denied (HTTP ${code})"
}

validate_one() {
  local operation=$1 flag carrier tmp
  flag="$(jq -er --arg id "${operation}" '.[] | select(.id == $id) | .flag' "${OPERATIONS}")" || \
    die "unknown operation: ${operation}"
  carrier=${PARTICIPANT_CARRIER_URL:-}
  [[ -n ${carrier} ]] || die "set PARTICIPANT_CARRIER_URL to the ordinary in-world result reached by the participant"
  tmp="$(mktemp)"
  trap 'rm -f "${tmp}"' RETURN
  fetch_carrier "${carrier}" "${tmp}"
  grep -Fq "${flag}" "${tmp}" || die "${operation} flag is absent from the participant-visible carrier"

  case "${operation}" in
    kep-m01-a)
      grep -Eqi 'draft|brief|redmine' "${tmp}" && negative_direct_source_denied ;;
    kep-m01-b)
      grep -Eqi 'calendar|candidate|workhub' "${tmp}" &&
        negative_direct_path_denied GET '/v1/release-calendar/orion-edge-2026.08' ;;
    kep-m01-c)
      grep -Eqi 'validation|runbook|fixture' "${tmp}" &&
        negative_result_has_no_flag "${flag}" 'refus|denied|blocked|validation enabled|failed' ;;
    kep-m01-d)
      grep -Eqi 'approval|svc-orion|agent' "${tmp}" &&
        negative_direct_path_denied POST '/v1/direct-approvals/sandbox-17' ;;
    kep-m01-e)
      grep -Eqi 'review|source|retriev|workhub' "${tmp}" && negative_direct_source_denied ;;
    kep-m01-f)
      grep -Eqi 'orion-edge|bundle|release' "${tmp}" &&
        negative_direct_path_denied GET '/v1/confidential-bundles/orion-edge-2026.08' ;;
    kep-m01-g)
      grep -Eqi 'candidate|loader|workbench|digest' "${tmp}" &&
        negative_result_has_no_flag "${flag}" 'reject|incomplete|not loaded|failed' ;;
    kep-m01-h)
      grep -Eqi 'helper|package|workbench|digest' "${tmp}" &&
        negative_result_has_no_flag "${flag}" 'reject|incompatible|not selected|failed' ;;
    kep-m01-i)
      grep -Eqi 'review01|integration01|handoff' "${tmp}" && negative_public_build_control ;;
    kep-m01-j)
      grep -Eqi 'integration|job-context|svc-orion' "${tmp}" &&
        negative_result_has_no_flag "${flag}" 'analysis|benign|no callback|canary.*denied' ;;
  esac || die "${operation} carrier or operation-specific negative control is invalid"
  printf '%s\n' "${operation}: participant carrier and negative direct-access control passed"
}

[[ $# -eq 1 ]] || die 'usage: validate.sh <operation-id>'
validate_one "$1"
