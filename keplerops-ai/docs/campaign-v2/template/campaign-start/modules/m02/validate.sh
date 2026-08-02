#!/usr/bin/env bash
set -Eeuo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MODULE_ROOT
readonly OPERATIONS="${MODULE_ROOT}/operations.json"

die() { printf '[m02 validate] ERROR: %s\n' "$*" >&2; exit 1; }

fetch_carrier() {
  local url=$1 output=$2
  [[ ${url} =~ ^https://[^/]+\.(keplerops|cinder)\.lab(/|$) ]] || \
    die "carrier must be reached through a participant-visible enterprise URL"
  local -a args=(-fsS --connect-timeout 10 --max-time 60)
  [[ -z ${PARTICIPANT_COOKIE_FILE:-} ]] || args+=(-b "${PARTICIPANT_COOKIE_FILE}")
  [[ -z ${PARTICIPANT_BEARER_TOKEN:-} ]] || args+=(-H "Authorization: Bearer ${PARTICIPANT_BEARER_TOKEN}")
  curl "${args[@]}" "${url}" > "${output}"
}

negative_vector_access_denied() {
  local vector_code
  vector_code="$(curl -ksS -o /dev/null -w '%{http_code}' \
    https://vectors.keplerops.lab/collections/orion_partner_intake/points/scroll)"
  [[ ${vector_code} == 401 || ${vector_code} == 403 || ${vector_code} == 405 ]] || \
    die "unauthenticated direct vector access was not denied (HTTP ${vector_code})"
}

negative_room_access_denied() {
  local files_code
  files_code="$(curl -ksS -o /dev/null -w '%{http_code}' \
    https://files.keplerops.lab/remote.php/dav/files/reviewer/Partner%20Rooms/Cinder%20Labs/WELCOME.md)"
  [[ ${files_code} == 401 || ${files_code} == 403 || ${files_code} == 404 ]] || \
    die "unauthenticated direct room access was not denied (HTTP ${files_code})"
}

negative_result_has_no_flag() {
  local flag=$1 pattern=$2 url=${PARTICIPANT_NEGATIVE_URL:-} tmp
  [[ -n ${url} ]] || die "set PARTICIPANT_NEGATIVE_URL to the participant-visible rejected or benign control"
  tmp="$(mktemp)"
  fetch_carrier "${url}" "${tmp}"
  ! grep -Fq "${flag}" "${tmp}" || { rm -f "${tmp}"; die "negative control exposed the operation flag"; }
  grep -Eqi "${pattern}" "${tmp}" || { rm -f "${tmp}"; die "negative control lacks the expected rejection state"; }
  rm -f "${tmp}"
}

validate_one() {
  local operation=$1 flag carrier tmp
  flag="$(jq -er --arg id "${operation}" '.[] | select(.id == $id) | .flag' "${OPERATIONS}")" || \
    die "unknown operation: ${operation}"
  carrier=${PARTICIPANT_CARRIER_URL:-}
  [[ -n ${carrier} ]] || die "set PARTICIPANT_CARRIER_URL to the ordinary in-world result reached by the participant"
  tmp="$(mktemp)"
  fetch_carrier "${carrier}" "${tmp}"
  grep -Fq "${flag}" "${tmp}" || die "${operation} flag is absent from the participant-visible carrier"
  case "${operation}" in
    kep-m02-a)
      grep -Eqi 'recommend|destination|audit' "${tmp}" && negative_vector_access_denied ;;
    kep-m02-b)
      grep -Eqi 'citation|source|digest|authority' "${tmp}" && negative_vector_access_denied ;;
    kep-m02-c)
      grep -Eqi 'provenance|policy|source|ingest' "${tmp}" &&
        negative_result_has_no_flag "${flag}" 'denied|no approved source|not indexed|unchanged' ;;
    kep-m02-d)
      grep -Eqi 'source|outer|inner|digest' "${tmp}" &&
        negative_result_has_no_flag "${flag}" 'one source|invalid metadata|rejected|incomplete' ;;
    kep-m02-e)
      grep -Eqi 'picklescan|allowed|import|canary' "${tmp}" &&
        negative_result_has_no_flag "${flag}" 'reject|dangerous|patched|blocked' ;;
    kep-m02-f)
      grep -Eqi 'analysis|integration|digest|canary' "${tmp}" &&
        negative_result_has_no_flag "${flag}" 'analysis|benign|no callback|canary.*denied' ;;
    kep-m02-h)
      grep -Eqi 'review room|partner|welcome' "${tmp}" && negative_room_access_denied ;;
    kep-m02-i)
      grep -Eqi 'review window|coordination|subject|message' "${tmp}" &&
        negative_result_has_no_flag "${flag}" 'insufficient context|not disclosed|rejected|cannot share' ;;
    kep-m02-j)
      grep -Eqi 'partner-reviewer|welcome|invitation' "${tmp}" &&
        negative_result_has_no_flag "${flag}" 'wrong phrase|new thread|rejected|no invitation' ;;
    kep-m02-k)
      grep -Eqi 'reviewer-session|workhub|agent|mcp' "${tmp}" &&
        negative_result_has_no_flag "${flag}" 'patched|rejected|no execution|blocked' ;;
    kep-m02-l)
      grep -Eqi 'package|import|context|digest' "${tmp}" &&
        negative_result_has_no_flag "${flag}" 'incompatible|different digest|rejected|failed' ;;
    kep-m02-m)
      grep -Eqi 'fixture|catalog|mcp|invocation' "${tmp}" &&
        negative_result_has_no_flag "${flag}" 'invalid schema|ownership|rejected|not invoked' ;;
  esac || { rm -f "${tmp}"; die "${operation} carrier or operation-specific negative control is invalid"; }
  rm -f "${tmp}"
  printf '%s\n' "${operation}: participant carrier and operation-specific negative control passed"
}

[[ $# -eq 1 ]] || die 'usage: validate.sh <operation-id>'
validate_one "$1"
