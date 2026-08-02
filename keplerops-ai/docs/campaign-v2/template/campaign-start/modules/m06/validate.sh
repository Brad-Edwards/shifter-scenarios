#!/usr/bin/env bash
set -Eeuo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MODULE_ROOT
readonly OPERATION="${1:?usage: validate.sh <operation-id>}"
readonly WORKSTATION="${PARTICIPANT_WORKSTATION:-keplerops-participant-workstation-runtime}"
readonly MC_CONFIG="/tmp/cinder-m06-mc"
readonly FORGEJO_PUBLIC_API="https://git.cinder.lab/api/v1/repos/cinder-evaluation/capability-evaluators"

die() { printf '[campaign-m06] ERROR: %s\n' "$*" >&2; exit 1; }
ws() { docker exec --user kasm-user --env HOME=/home/kasm-user "$WORKSTATION" "$@"; }
flag_for() { jq -er --arg id "$1" '.[] | select(.id == $id) | .flag' "${MODULE_ROOT}/operations.json"; }

slug_for() {
  case "$1" in
    kep-m06-a) echo intake-evasion;; kep-m06-b) echo command-generation;;
    kep-m06-c) echo preview-blackbox;; kep-m06-d) echo preview-transfer;;
    kep-m06-e) echo document-human;; kep-m06-f) echo document-pipeline;;
    kep-m06-j) echo edge-correlation;; kep-m06-k) echo public-bundle;;
    kep-m06-l) echo workspace-reattachment;; kep-m06-m) echo physical-evaluation;;
    kep-m06-n) echo registrar-order;; kep-m06-o) echo toolchain-validation;;
    kep-m06-p) echo model-usage;; kep-m06-q) echo harness-release;;
    kep-m06-r) echo whitebox-evaluation;; kep-m06-s) echo document-retrieval;;
    kep-m06-t) echo media-provenance;; kep-m06-u) echo relay-lifecycle;;
    kep-m06-v) echo staging-validation;; *) return 1;;
  esac
}

carrier_for() {
  case "$1" in
    kep-m06-a) echo intake-reports;; kep-m06-b) echo comparison-reports;;
    kep-m06-c|kep-m06-d) echo preview-audits;; kep-m06-e) echo downstream-reports;;
    kep-m06-f) echo target-audits;; kep-m06-j) echo intake-status;;
    kep-m06-k|kep-m06-o) echo reports;; kep-m06-l) echo workspace-reattachments;;
    kep-m06-m) echo physical-evaluations;; kep-m06-n) echo registrar-orders;;
    kep-m06-p) echo model-usage;; kep-m06-q|kep-m06-v) echo ci-artifacts;;
    kep-m06-r) echo whitebox-evaluations;; kep-m06-s) echo document-traces;;
    kep-m06-t) echo media-registry;; kep-m06-u) echo relay-lifecycles;; *) return 1;;
  esac
}

configure_mc() {
  ws mc --config-dir "$MC_CONFIG" alias set cinder http://10.61.90.31:9000 \
    cinder-operator Cinder-Operations-ObjectStore-T7v2Lm9q >/dev/null
}

latest_carrier() {
  local prefix=$1
  ws sh -lc "mc --config-dir '$MC_CONFIG' find 'cinder/operations/$prefix' --name '*.json' 2>/dev/null | sort | tail -n1"
}

validate_public_manifest() {
  local flag=$1 body
  body="$(ws curl -fsS https://keplerops.lab/research/orion-release-manifest.json)"
  jq -e --arg flag "$flag" '.engagement_reference == $flag and .release and .model_card and .source_tag' <<<"$body" >/dev/null
  ! ws curl -fsS https://keplerops.lab/ | grep -Fq "$flag"
}

validate_client() {
  local flag=$1 directory prefix suffix
  directory="$(mktemp -d)"; trap 'rm -rf "$directory"' RETURN
  ws curl -fsS https://keplerops.lab/software/orion-field-review/orion-field-review.apk >"$directory/client.apk"
  ws curl -fsS https://keplerops.lab/software/orion-field-review/orion-field-review.cdx.json >"$directory/sbom.json"
  unzip -p "$directory/client.apk" assets/provenance/release.json >"$directory/release.json"
  prefix="$(jq -er '.release_reference_prefix' "$directory/release.json")"
  suffix="$(jq -er '.metadata.component.properties[] | select(.name == "keplerops:release-reference-suffix") | .value' "$directory/sbom.json")"
  [[ ${prefix}${suffix} == "$flag" ]]
  [[ $(sha256sum "$directory/sbom.json" | cut -d' ' -f1) == "$(jq -r .sbom.sha256 "$directory/release.json")" ]]
  ! ws curl -fsS https://keplerops.lab/software/orion-field-review/ | grep -Fq "$flag"
}

validate_vcard() {
  local flag=$1 card
  card="$(ws curl -fsS https://keplerops.lab/conference/mira-chen.vcf)"
  grep -Fq "NOTE:Speaker engagement reference: $flag" <<<"$card"
  ! ws curl -fsS https://keplerops.lab/people/mira-chen/ | grep -Fq "$flag"
}

validate_native_record() {
  local operation=$1 flag=$2 slug carrier key body
  slug="$(slug_for "$operation")"; carrier="$(carrier_for "$operation")"
  configure_mc
  key="$(latest_carrier "$carrier")"
  [[ -n $key ]] || die "no operator-readable ${carrier} record exists"
  [[ $key == *"/${slug}-"* ]] || die "latest ${carrier} record belongs to another capability"
  body="$(ws mc --config-dir "$MC_CONFIG" cat "$key")"
  jq -e --arg id "$operation" --arg flag "$flag" '.operation == $id and .status == "passed" and .flag == $flag' <<<"$body" >/dev/null

  local submission
  while read -r submission; do
    [[ -z $submission ]] && continue
    ! ws mc --config-dir "$MC_CONFIG" cat "$submission" | grep -Fq "$flag" || die "submission exposed its own accepted flag"
  done < <(ws sh -lc "mc --config-dir '$MC_CONFIG' find 'cinder/operations/submissions/$slug' --name '*.json' 2>/dev/null || true")
  if ws mc --config-dir "$MC_CONFIG" stat "cinder/operations/${carrier}/not-a-real-record.json" >/dev/null 2>&1; then
    die "nonexistent carrier identifier unexpectedly resolved"
  fi

  if [[ $operation == kep-m06-j ]]; then
    local reference
    reference="$(jq -er '.case_reference' <<<"$body")"
    ws curl -fsS "https://keplerops.lab/intake-status/${reference}.json" | jq -e --arg flag "$flag" '.flag == $flag and .preview_event and .mail_event' >/dev/null
  elif [[ $operation == kep-m06-l ]]; then
    local submission_id
    submission_id="$(jq -er '.submission_id' <<<"$body")"
    ws curl -fsS "http://10.61.90.32:8888/api/contents/.cinder/reattachments/${submission_id}.json?token=Cinder-Operations-Notebook-R5w8Nx2k" | \
      jq -er '.content' | base64 -d | jq -e --arg flag "$flag" '.flag == $flag and .old_server_id != .new_server_id' >/dev/null
  elif [[ $operation == kep-m06-q || $operation == kep-m06-v ]]; then
    local runs run_id artifacts artifact_id archive
    runs="$(ws curl -fsS "${FORGEJO_PUBLIC_API}/actions/runs?limit=20")"
    run_id="$(jq -er '.workflow_runs[] | select(.conclusion == "success") | .id' <<<"$runs" | head -n1)"
    artifacts="$(ws curl -fsS "${FORGEJO_PUBLIC_API}/actions/runs/${run_id}/artifacts")"
    artifact_id="$(jq -er '.artifacts[] | select(.name == "cinder-evaluation-reports") | .id' <<<"$artifacts" | head -n1)"
    archive="$(mktemp)"; trap 'rm -f "$archive"' RETURN
    ws curl -fsS "${FORGEJO_PUBLIC_API}/actions/artifacts/${artifact_id}/zip" >"$archive"
    unzip -p "$archive" | grep -Fq "$flag"
  fi
}

main() {
  jq -e --arg id "$OPERATION" 'any(.[]; .id == $id)' "${MODULE_ROOT}/operations.json" >/dev/null || die "unknown operation: $OPERATION"
  local flag
  flag="$(flag_for "$OPERATION")"
  case "$OPERATION" in
    kep-m06-g) validate_public_manifest "$flag";;
    kep-m06-h) validate_client "$flag";;
    kep-m06-i) validate_vcard "$flag";;
    *) validate_native_record "$OPERATION" "$flag";;
  esac
  printf 'campaign-v2 %s operator carrier and negative shortcut passed\n' "$OPERATION"
}

main "$@"
