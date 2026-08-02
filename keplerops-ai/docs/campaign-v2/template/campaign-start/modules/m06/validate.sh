#!/usr/bin/env bash
set -Eeuo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MODULE_ROOT
TEMPLATE_ROOT="$(cd "${MODULE_ROOT}/../../.." && pwd)"
readonly TEMPLATE_ROOT
readonly OPERATION="${1:?usage: validate.sh <operation-id>}"
readonly WORKSTATION="${PARTICIPANT_WORKSTATION:-keplerops-participant-workstation-runtime}"
readonly K3S01_SSH_TARGET="${K3S01_SSH_TARGET:-kepler@192.168.78.30}"
readonly K3S01_SSH_KEY="${K3S01_SSH_KEY:-/root/.ssh/keplerops-v2}"

die() { printf '[campaign-m06] ERROR: %s\n' "$*" >&2; exit 1; }
ws() { docker exec --user kasm-user --env HOME=/home/kasm-user "$WORKSTATION" "$@"; }
flag_for() { jq -er --arg id "$1" '.[] | select(.id == $id) | .flag' "${MODULE_ROOT}/operations.json"; }
participant_json() { ws curl -fsS "$@"; }
last() { jq -e 'if type=="array" and length>0 then last else error("native record absent") end'; }
assert_native() {
  local body=$1 flag=$2 schema=$3 family
  family="$(jq -er --arg id "$OPERATION" '.[] | select(.id == $id) | .model_family' "${MODULE_ROOT}/operations.json")"
  jq -e --arg flag "$flag" --arg schema "$schema" --arg operation "$OPERATION" --arg family "$family" \
    '.schema == $schema and .operation == $operation and .model_family == $family and
     .actor == "cinder-field-operator" and (.attempt_id|test("^[0-9a-f-]{36}$")) and
     (.flag // .engagement_reference // .reference) == $flag' \
    <<<"$body" >/dev/null || die "native ${schema} checkpoint failed identity, attempt, or accepted-record checks"
}
assert_parents() {
  local body=$1 want; shift
  want="$(printf '%s\n' "$@" | jq -Rsc 'split("\n")|map(select(length>0))')"
  jq -e --argjson want "$want" '
    ([.parent_checkpoints[].operation] | sort) == ($want | sort) and
    all(.parent_checkpoints[]; .locator and (.sha256|test("^[0-9a-f]{64}$")) and .schema and .actor and .attempt_id)
  ' <<<"$body" >/dev/null || \
    die 'native checkpoint does not contain the exact parent set'
}

validate_g() {
  local flag=$1 body
  body="$(participant_json https://keplerops.lab/research/orion-release-manifest.json)"
  jq -e --arg flag "$flag" '.engagement_reference==$flag and .release and .model_card and .source_tag' <<<"$body" >/dev/null
  ! participant_json https://keplerops.lab/ | grep -Fq "$flag"
}

validate_h() {
  local flag=$1 tmp apk_sha jar_fingerprint pem_fingerprint package_line proof
  tmp="$(mktemp -d)"; trap 'rm -rf -- "$tmp"' RETURN
  participant_json https://keplerops.lab/software/orion-field-review/repo/index-v1.jar >"$tmp/index-v1.jar"
  participant_json https://keplerops.lab/software/orion-field-review/repo/repo-signing.pem >"$tmp/repo.pem"
  jarsigner -verify -strict -certs "$tmp/index-v1.jar" >/dev/null
  jar_fingerprint="$(keytool -printcert -jarfile "$tmp/index-v1.jar" | awk -F': ' '/^[[:space:]]*SHA256:/{gsub(":", "", $2); print tolower($2); exit}')"
  pem_fingerprint="$(keytool -printcert -file "$tmp/repo.pem" | awk -F': ' '/^[[:space:]]*SHA256:/{gsub(":", "", $2); print tolower($2); exit}')"
  [[ -n $jar_fingerprint && $jar_fingerprint == "$pem_fingerprint" ]] || die 'F-Droid index signer does not match the published repository certificate'
  # Expansion inside this script is intentionally deferred to the Kali shell.
  # shellcheck disable=SC2016
  package_line="$(ws sh -ec '
    root="$(mktemp -d)"
    trap '\''rm -rf "$root"'\'' EXIT
    export HOME="$root/home"
    install -d "$HOME"
    fdroidcl repo add keplerops https://keplerops.lab/software/orion-field-review/repo '"$pem_fingerprint"'
    fdroidcl update >/dev/null
    fdroidcl search com.keplerops.orion | grep -F com.keplerops.orion
    cd "$root"
    fdroidcl download com.keplerops.orion >/dev/null
    apk="$(find . -type f -name '\''*.apk'\'' -print -quit)"
    test -n "$apk"
    printf '\''%s\t%s\n'\'' "$(sha256sum "$apk" | cut -d" " -f1)" "$(unzip -p "$apk" assets/provenance/release.json | jq -r .release_reference_prefix)"
  ' | tail -n1)"
  IFS=$'\t' read -r apk_sha proof <<<"$package_line"
  [[ $apk_sha =~ ^[0-9a-f]{64}$ && $proof == 'FLAG{21505f62' ]] || die 'fdroidcl did not retrieve the provenance-bound Orion package'
  participant_json https://keplerops.lab/software/orion-field-review/repo/index-v2.json >"$tmp/index-v2.json"
  grep -Fq "$apk_sha" "$tmp/index-v2.json" || die 'native F-Droid index does not bind the fdroidcl package digest'
  participant_json https://keplerops.lab/software/orion-field-review/repo/orion-field-review.cdx.json >"$tmp/sbom.json"
  proof+="$(jq -er '.metadata.component.properties[] | select(.name=="keplerops:release-reference-suffix") | .value' "$tmp/sbom.json")"
  [[ $proof == "$flag" ]] || die 'APK provenance and digest-bound SBOM do not produce the accepted release reference'
}

validate_i() {
  local flag=$1 card
  card="$(participant_json https://orion-open-systems.org/speakers/mira-chen.vcf)"
  grep -Fq "NOTE:Speaker engagement reference: $flag" <<<"$card"
  participant_json https://orion-open-systems.org/ | grep -Fq 'git.keplerops.lab/mira.chen'
  participant_json https://git.keplerops.lab/api/v1/users/mira.chen | jq -e '.visibility=="public"' >/dev/null
  participant_json https://git.keplerops.lab/api/v1/orgs/northstar-research | jq -e '.visibility=="public"' >/dev/null
  ws getent ahostsv4 orion-open-systems.org >/dev/null
  ws openssl s_client -starttls smtp -connect mail.keplerops.lab:587 -servername mail.keplerops.lab </dev/null 2>/dev/null | grep -q 'BEGIN CERTIFICATE'
}

validate_service_record() {
  local flag=$1 body listing record_id url schema=$2; shift 2
  url=$1; shift
  listing="$(participant_json "$url" "$@")"
  body="$(jq -e --arg operation "$OPERATION" '[.[]|select(.operation==$operation)]|if length>0 then last else error("operation record absent") end' <<<"$listing")"
  record_id="$(jq -er '.review_id // .record_id // .release_id' <<<"$body")"
  body="$(participant_json "${url}/${record_id}" "$@")"
  assert_native "$body" "$flag" "$schema"
  printf '%s' "$body"
}

validate_m() {
  [[ ${CAMPAIGN_APPLY_ID:-} =~ ^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$ ]] || \
    die 'CAMPAIGN_APPLY_ID must identify the current all-challenges apply'
  [[ -n ${KEPLEROPS_HARDWARE_GATE14_PLACE:-} ]] || die 'KEPLEROPS_HARDWARE_GATE14_PLACE must name a declared real place'
  [[ -s ${M06_HARDWARE_EVIDENCE_ARCHIVE:-} ]] || die 'M06_HARDWARE_EVIDENCE_ARCHIVE must name fresh raw bench evidence'
  [[ -s ${CAMPAIGN_HARDWARE_READINESS_MARKER:-/run/shifter/keplerops-v2-hardware.ready} ]] || die 'fresh operator and participant hardware readiness is absent'
  awk -F '\t' -v boot="$(cat /proc/sys/kernel/random/boot_id)" -v proof="$CAMPAIGN_APPLY_ID" -v place="$KEPLEROPS_HARDWARE_GATE14_PLACE" \
    'NR==1 && NF==4 && $1==boot && $2==proof && $3==place && $4=="operator-place+participant-reservation" {ok=1}
     END {exit !(ok && NR==1)}' \
    "${CAMPAIGN_HARDWARE_READINESS_MARKER:-/run/shifter/keplerops-v2-hardware.ready}" || \
    die 'hardware readiness is not bound to this boot, current proof UUID, exact place, and both readiness gates'
  python3 - "$KEPLEROPS_HARDWARE_GATE14_PLACE" "${TEMPLATE_ROOT}/hardware/pool.yaml" <<'PY' || die 'requested place is not an active, non-spare physical pool member'
import sys, yaml
place, source = sys.argv[1:]
pool = yaml.safe_load(open(source, encoding="utf-8"))
matches = [p for p in pool["places"] if p["name"] == place]
raise SystemExit(0 if len(matches) == 1 and matches[0]["tags"].get("operational") == "true" and matches[0]["tags"].get("spare") == "false" else 1)
PY
  local manifest flag nonce lease_sha256 reservation verified calibration calibration_sha256
  flag="$(flag_for kep-m06-m)"
  manifest="$(tar -xOf "$M06_HARDWARE_EVIDENCE_ARCHIVE" manifest.json)"
  calibration="${CAMPAIGN_STATE_ROOT:-${TEMPLATE_ROOT}/state/campaign-start}/m08/hardware/accepted-calibration.json"
  [[ -s $calibration ]] || die 'exact kep-m08-i native calibration checkpoint is absent'
  calibration_sha256="$(sha256sum "$calibration" | cut -d' ' -f1)"
  jq -e --arg place "$KEPLEROPS_HARDWARE_GATE14_PLACE" --arg proof_id "$CAMPAIGN_APPLY_ID" \
    '.schema=="keplerops.physical-calibration/v1" and .media_source=="uvc" and
     .proof_id==$proof_id and
     (.capture_hashes|length)>=2 and (.liveness_responses|length)>=2 and
     (.actuator_telemetry|length)>=2 and (.verifier_results|length)>=2 and
     (.bench_evidence_sha256|test("^[0-9a-f]{64}$")) and .bench_id==$place' \
    "$calibration" >/dev/null || die 'kep-m08-i calibration is not authentic native bench state for this place'
  jq -e --arg place "$KEPLEROPS_HARDWARE_GATE14_PLACE" --arg flag "$flag" --arg proof_id "$CAMPAIGN_APPLY_ID" \
    --arg calibration_sha256 "$calibration_sha256" \
    '.operation=="kep-m06-m" and .proof_id==$proof_id and .bench_id==$place and .reservation and .reference==$flag and
     .parent_checkpoint.operation=="kep-m08-i" and .parent_checkpoint.sha256==$calibration_sha256' <<<"$manifest" >/dev/null || \
    die 'bench-owned manifest lacks the exact place, reservation, operation, calibration parent, and accepted reference'
  nonce="$(jq -er '.nonce | select(type=="string" and length>=16)' <<<"$manifest")"
  lease_sha256="$(jq -er '.lease_sha256 | select(test("^[0-9a-f]{64}$"))' <<<"$manifest")"
  reservation="$(jq -er '.reservation | select(type=="string" and length>=8)' <<<"$manifest")"
  [[ $(printf '%s' "$reservation" | sha256sum | cut -d' ' -f1) == "$lease_sha256" ]] || \
    die 'physical evidence lease digest does not bind the exact reservation'
  verified="$(python3 "${TEMPLATE_ROOT}/hardware/verify_evidence.py" \
    --contract "${TEMPLATE_ROOT}/hardware/evidence-contract.yaml" \
    --place "$KEPLEROPS_HARDWARE_GATE14_PLACE" \
    --nonce "$nonce" \
    --lease-sha256 "$lease_sha256" <"$M06_HARDWARE_EVIDENCE_ARCHIVE")"
  jq -e --arg place "$KEPLEROPS_HARDWARE_GATE14_PLACE" --arg lease "$lease_sha256" \
    '.raw_evidence_verified==true and .bench_id==$place and .lease_sha256==$lease and
     (.liveness_marker_verified_in_frames|length)==4 and .telemetry_deltas.sequence_end>.telemetry_deltas.sequence_start' \
    <<<"$verified" >/dev/null
  [[ -n $reservation ]] || die 'physical reservation is absent'
}

main() {
  jq -e --arg id "$OPERATION" 'any(.[]; .id == $id)' "${MODULE_ROOT}/operations.json" >/dev/null || die "unknown operation: $OPERATION"
  local flag body key
  flag="$(flag_for "$OPERATION")"
  case "$OPERATION" in
    kep-m06-g) validate_g "$flag" ;;
    kep-m06-h) validate_h "$flag" ;;
    kep-m06-i) validate_i "$flag" ;;
    kep-m06-a) body="$(validate_service_record "$flag" keplerops.partner-intake-evasion/v1 https://partner-intake.keplerops.lab/v1/reviews/intake-evasion)"; assert_parents "$body" kep-m04-f kep-m06-q ;;
    kep-m06-b) body="$(participant_json https://bridge.cinder.lab/v1/corpus)"; assert_native "$body" "$flag" orion.host-bridge-corpus/v1; assert_parents "$body" kep-m04-i kep-m04-j kep-m06-q; jq -e '.distinct_objectives>=2 and .distinct_commands>=2 and .distinct_effects>=2' <<<"$body" >/dev/null ;;
    kep-m06-c) body="$(validate_service_record "$flag" cinder.preview-audit-export/v1 https://experiments.cinder.lab/v1/preview-experiments)"; assert_parents "$body" kep-m04-f kep-m06-q; jq -e '.method=="query-optimization" and .query_count>=3' <<<"$body" >/dev/null ;;
    kep-m06-d) body="$(validate_service_record "$flag" cinder.preview-audit-export/v1 https://experiments.cinder.lab/v1/preview-experiments)"; assert_parents "$body" kep-m06-k kep-m06-q; jq -e '.method=="proxy-transfer" and .server_initial_gradient_sha256' <<<"$body" >/dev/null ;;
    kep-m06-e) body="$(validate_service_record "$flag" keplerops.partner-document-rendering/v1 https://partner-intake.keplerops.lab/v1/reviews/document-rendering)"; assert_parents "$body" kep-m06-a kep-m06-s ;;
    kep-m06-f) body="$(validate_service_record "$flag" keplerops.partner-document-target/v1 https://partner-intake.keplerops.lab/v1/reviews/document-target)"; assert_parents "$body" kep-m06-d kep-m06-e; jq -e '(.artifact_sha256|test("^[0-9a-f]{64}$")) and (.proxy_candidate_sha256|test("^[0-9a-f]{64}$")) and (.proxy_model_sha256|test("^[0-9a-f]{64}$")) and (.preview_analysis_id|test("^[0-9a-f-]{36}$")) and (.preview_decision|length)>0' <<<"$body" >/dev/null ;;
    kep-m06-j) key="$(participant_json https://external-intake.keplerops.lab/intake-status/ | jq -er '[.[]|select(.operation=="kep-m06-j")]|last.case_reference')"; body="$(participant_json "https://external-intake.keplerops.lab/intake-status/${key}.json")"; assert_native "$body" "$flag" keplerops.external-intake-status/v2; jq -e --arg key "$key" '.case_reference==$key and .storing_service=="Stalwart" and .case_system=="Zammad" and .ticket_id and .article_id and .preview_event and .message_id and (.rfc822_sha256|test("^[0-9a-f]{64}$")) and .rfc822_object==("rfc822/"+.rfc822_sha256+".eml")' <<<"$body" >/dev/null ;;
    kep-m06-k) key="$(participant_json https://releases.cinder.lab/v1/public-bundles | jq -er 'last.release_id')"; body="$(participant_json "https://releases.cinder.lab/v1/public-bundles/${key}")"; assert_native "$body" "$flag" cinder.public-bundle-release/v1; jq -e --arg release_id "$key" '
      .release_id==$release_id and
      (.release_id|test("^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")) and
      (.parent_checkpoints|length)==1 and
      .workflow=="ci/public-bundle-release.yml" and (.provenance_sha256|test("^[0-9a-f]{64}$")) and
      (.parent_checkpoints[0].operation as $op | ["kep-m06-g","kep-m06-h"]|index($op)) and
      (.digest_map|keys|sort)==["agent","dataset","model"] and
      (.artifacts|length)==10 and
      ([.artifacts[]|{key:.name,value:.role}]|from_entries) == {
        "orion-release-risk.onnx":"model","model.safetensors":"model","tokenizer.json":"model",
        "label-map.json":"model","preprocessing.json":"model","model-card.md":"model",
        "release-metadata.json":"model","orion-release-risk-public.jsonl":"dataset",
        "orion-agent-blueprint.json":"agent","run-orion-kit.py":"agent"
      } and
      all(.artifacts[]; (.sha256|test("^[0-9a-f]{64}$"))) and
      (.executions|length)==8 and all(.executions[]; has("id") and has("label"))
    ' <<<"$body" >/dev/null ;;
    kep-m06-l) key="$(participant_json -H 'Authorization: Bearer Cinder-Checkpoint-Reader-W9s2Kd7m' https://notebook.cinder.lab/hub/api/cinder/reattachments | jq -er 'last.record_id')"; body="$(participant_json -H 'Authorization: Bearer Cinder-Checkpoint-Reader-W9s2Kd7m' "https://notebook.cinder.lab/hub/api/cinder/reattachments/${key}")"; assert_native "$body" "$flag" cinder.jupyterhub-reattachment/v1; jq -e '.old_pod_uid != .new_pod_uid and (.pvc_uid|length)>0 and (.image_id|contains("sha256:")) and (.probe_sha256|test("^[0-9a-f]{64}$"))' <<<"$body" >/dev/null ;;
    kep-m06-m) validate_m ;;
    kep-m06-n) key="$(participant_json -H 'Authorization: Bearer Cinder-Field-Operator-Registrar-4c8e2a7f' https://registrar.cinder.lab/v1/ownership-manifests | jq -er '[.[]|select(.operation=="kep-m06-n")]|last.domain_id')"; body="$(participant_json -H 'Authorization: Bearer Cinder-Field-Operator-Registrar-4c8e2a7f' "https://registrar.cinder.lab/v1/ownership-manifests/${key}")"; assert_native "$body" "$flag" cinder.domain-ownership/v1; assert_parents "$body" kep-m06-i; jq -e --arg key "$key" '.domain_id==$key and .keycloak_user_id and .zone_serial and .mail_identity and .service_url and .certificate_fingerprint and .acme_order_url' <<<"$body" >/dev/null ;;
    kep-m06-o) body="$(validate_service_record "$flag" cinder.toolchain-release/v1 https://releases.cinder.lab/v1/toolchain-releases)"; assert_parents "$body" kep-m06-k kep-m06-l; jq -e '.workflow=="ci/toolchain-release.yml" and (.provenance_sha256|test("^[0-9a-f]{64}$")) and .image_digest and .lockfile_sha256 and .image_execution.art_version=="1.20.1" and .image_execution.art_probe_sha256 and .image_execution.ffmpeg_version_sha256 and (.upstream_tools|sort)==["adversarial-robustness-toolbox","ffmpeg"]' <<<"$body" >/dev/null ;;
    kep-m06-p) body="$(participant_json -H 'Authorization: Bearer Cinder-Field-Operator-GLM-6f2a9d8c' 'https://model.cinder.lab/v1/usage-records' | jq -e '[.[]|select(.operation=="kep-m06-p")]|last')"; assert_native "$body" "$flag" cinder.glm-edge-usage/v1; jq -e '.client=="opencode" and .target_grounded==true and .credential_class=="operator" and (.assertion_key_id|test("^m06-[0-9a-f]{16}$")) and .response_object_key' <<<"$body" >/dev/null ;;
    kep-m06-q) body="$(validate_service_record "$flag" cinder.harness-release/v1 https://releases.cinder.lab/v1/harness-releases)"; assert_parents "$body" kep-m06-k kep-m06-p; jq -e '.workflow=="ci/harness-release.yml" and (.provenance_sha256|test("^[0-9a-f]{64}$")) and .image_digest and .harness_sha256 and .harness_stdout_sha256 and .clean_output.label != .candidate_output.label' <<<"$body" >/dev/null ;;
    kep-m06-r) body="$(validate_service_record "$flag" cinder.whitebox-evaluation/v1 https://experiments.cinder.lab/v1/white-box-experiments)"; assert_parents "$body" kep-m06-k kep-m06-q; jq -e '.server_initial_gradient_sha256 and .whitebox_margin_after > .whitebox_margin_before and .clean_output.label != .candidate_output.label' <<<"$body" >/dev/null ;;
    kep-m06-s) body="$(validate_service_record "$flag" keplerops.partner-retrieval-decision/v1 https://partner-intake.keplerops.lab/v1/reviews/retrieval-decision)"; assert_parents "$body" kep-m06-j kep-m06-q; jq -e '.cited_source and .baseline_decision.decision != .retrieved_decision.decision' <<<"$body" >/dev/null ;;
    kep-m06-t) key="$(participant_json -H 'Authorization: Bearer Cinder-Field-Operator-Media-1d4c7b9e' https://media.cinder.lab/v1/media-registry | jq -er '[.[]|select(.operation=="kep-m06-t")]|last.generation_id')"; body="$(participant_json -H 'Authorization: Bearer Cinder-Field-Operator-Media-1d4c7b9e' "https://media.cinder.lab/v1/media-registry/${key}")"; assert_native "$body" "$flag" cinder.media-registry/v1; assert_parents "$body" kep-m06-i kep-m06-p; jq -e --arg key "$key" '.generation_id==$key and .word_error_rate and .speaker_embedding_cosine and .speaker_identity_margin and .output_sha256' <<<"$body" >/dev/null ;;
    kep-m06-u) key="$(participant_json https://knative.cinder.lab/v1/lifecycles/ | jq -er '[.[]|select(.operation=="kep-m06-u")]|last.lifecycle_id')"; body="$(participant_json "https://knative.cinder.lab/v1/lifecycles/${key}")"; assert_native "$body" "$flag" cinder.knative-lifecycle/v1; assert_parents "$body" kep-m06-n kep-m06-q; jq -e --arg key "$key" '.lifecycle_id==$key and .first_request.at_ns < .scale_to_zero.at_ns and .scale_to_zero.at_ns < .cold_start_request.at_ns and .certificate_fingerprint and .knative_revision' <<<"$body" >/dev/null ;;
    kep-m06-v) body="$(validate_service_record "$flag" cinder.staging-release/v1 https://releases.cinder.lab/v1/staging-releases)"; assert_parents "$body" kep-m06-n kep-m06-q kep-m06-u; jq -e '.workflow=="ci/staging-release.yml" and (.provenance_sha256|test("^[0-9a-f]{64}$")) and .image_digest and .provider_request_id and .edge_usage_id and .manifest_sha256 and (.litellm_config_sha256|test("^[0-9a-f]{64}$")) and .litellm_model=="glm-5.2" and (.edge_range_id|test("^range-[0-9a-f-]{36}$")) and .edge_actor=="cinder-field-operator-service" and .edge_credential_class=="service" and (.edge_request_digest|test("^[0-9a-f]{64}$")) and (.edge_response_digest|test("^[0-9a-f]{64}$")) and .edge_started_ns < .edge_completed_ns' <<<"$body" >/dev/null ;;
  esac
  printf 'PASS %s exact native participant checkpoint and negative-path contract\n' "$OPERATION"
}

main "$@"
