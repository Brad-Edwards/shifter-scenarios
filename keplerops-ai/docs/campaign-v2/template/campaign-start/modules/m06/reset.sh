#!/usr/bin/env bash
set -Eeuo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MODULE_ROOT
TEMPLATE_ROOT="$(cd "${MODULE_ROOT}/../../.." && pwd)"
readonly TEMPLATE_ROOT
readonly OPERATION="${1:?usage: reset.sh <operation-id>}"
readonly WORKSTATION="${PARTICIPANT_WORKSTATION:-keplerops-participant-workstation-runtime}"
readonly MC_CONFIG="/tmp/cinder-m06-mc"

die() { printf '[campaign-m06] ERROR: %s\n' "$*" >&2; exit 1; }
ws() { docker exec --user kasm-user --env HOME=/home/kasm-user "$WORKSTATION" "$@"; }

cleanup_native_attempt() {
  local slug=$1 key=$2 payload value
  payload="$(ws mc --config-dir "$MC_CONFIG" cat "$key")"
  case "$slug" in
    intake-evasion)
      value="$(jq -r '.evaluation_id // empty' <<<"$payload")"
      [[ -z $value ]] || curl -fsS -X DELETE "http://10.61.10.29:8080/v1/evaluations/$value" >/dev/null || true
      ;;
    registrar-order)
      value="$(jq -r '.order_id // empty' <<<"$payload")"
      [[ -z $value ]] || curl -fsS -X DELETE -H 'Authorization: Bearer Cinder-Registrar-cinder-operator-4c8e2a7f' \
        "http://10.61.90.34:8080/v1/orders/$value" >/dev/null || true
      ;;
    media-provenance)
      value="$(jq -r '.generation_id // empty' <<<"$payload")"
      [[ -z $value ]] || curl -fsS -X DELETE -H 'Authorization: Bearer Cinder-Media-cinder-operator-1d4c7b9e' \
        "http://10.61.90.33:8080/v1/generations/$value" >/dev/null || true
      ;;
    document-retrieval)
      value="$(jq -r '.collection // empty' <<<"$payload")"
      [[ -z $value ]] || curl -fsS -X DELETE "http://10.61.90.35:6333/collections/$value" >/dev/null || true
      ;;
    relay-lifecycle)
      value="$(jq -r '.knative_service // empty' <<<"$payload")"
      if [[ -n $value && -s ${TEMPLATE_ROOT}/state/cinder-publisher/id_ed25519 ]]; then
        ssh -i "${TEMPLATE_ROOT}/state/cinder-publisher/id_ed25519" -o BatchMode=yes -o StrictHostKeyChecking=yes \
          -o "UserKnownHostsFile=${TEMPLATE_ROOT}/state/cinder-publisher/known_hosts" \
          cinder-publisher@192.168.78.30 "delete $value" >/dev/null || true
      fi
      ;;
  esac
}

slug_for() {
  case "$1" in
    kep-m06-a) echo intake-evasion;; kep-m06-b) echo command-generation;; kep-m06-c) echo preview-blackbox;;
    kep-m06-d) echo preview-transfer;; kep-m06-e) echo document-human;; kep-m06-f) echo document-pipeline;;
    kep-m06-j) echo edge-correlation;; kep-m06-k) echo public-bundle;; kep-m06-l) echo workspace-reattachment;;
    kep-m06-m) echo physical-evaluation;; kep-m06-n) echo registrar-order;; kep-m06-o) echo toolchain-validation;;
    kep-m06-p) echo model-usage;; kep-m06-q) echo harness-release;; kep-m06-r) echo whitebox-evaluation;;
    kep-m06-s) echo document-retrieval;; kep-m06-t) echo media-provenance;; kep-m06-u) echo relay-lifecycle;;
    kep-m06-v) echo staging-validation;; *) return 1;;
  esac
}

main() {
  jq -e --arg id "$OPERATION" 'any(.[]; .id == $id)' "${MODULE_ROOT}/operations.json" >/dev/null || die "unknown operation: $OPERATION"
  case "$OPERATION" in
    kep-m06-g|kep-m06-h|kep-m06-i)
      printf '%s is immutable public state; no reset is required\n' "$OPERATION"
      return
      ;;
  esac
  local slug key submission_id
  slug="$(slug_for "$OPERATION")"
  ws mc --config-dir "$MC_CONFIG" alias set cinder http://10.61.90.31:9000 \
    cinder-operator Cinder-Operations-ObjectStore-T7v2Lm9q >/dev/null
  while read -r key; do
    [[ -z $key ]] && continue
    ws mc --config-dir "$MC_CONFIG" rm --force "$key" >/dev/null
  done < <(ws sh -lc "mc --config-dir '$MC_CONFIG' find cinder/operations/attempts --name '${slug}-*.json' 2>/dev/null || true")
  while read -r key; do
    [[ -z $key ]] && continue
    submission_id="$(basename "$key" .json)"
    if ! ws sh -lc "mc --config-dir '$MC_CONFIG' find cinder/operations --name '${slug}-${submission_id}.json' 2>/dev/null | grep -v '/submissions/' | grep -q ."; then
      cleanup_native_attempt "$slug" "$key"
      ws mc --config-dir "$MC_CONFIG" rm --force "$key" >/dev/null
    fi
  done < <(ws sh -lc "mc --config-dir '$MC_CONFIG' find 'cinder/operations/submissions/$slug' --name '*.json' 2>/dev/null || true")
  printf 'cleared rejected %s attempts; accepted records and carry-forward assets preserved\n' "$OPERATION"
}

main "$@"
