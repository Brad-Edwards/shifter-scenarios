#!/usr/bin/env bash
set -Eeuo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MODULE_ROOT
readonly OPERATION="${1:-}"

die() { printf '[campaign-m09 validate] ERROR: %s\n' "$*" >&2; exit 1; }

fetch() {
  local url=$1 output=$2
  [[ ${url} =~ ^https://[^/]+\.(keplerops|cinder)\.lab(/|$) ]] || die "not a participant-visible enterprise URL: ${url}"
  local -a args=(-kfsS --connect-timeout 10 --max-time 180)
  [[ -z ${PARTICIPANT_COOKIE_FILE:-} ]] || args+=(-b "${PARTICIPANT_COOKIE_FILE}")
  [[ -z ${PARTICIPANT_BEARER_TOKEN:-} ]] || args+=(-H "Authorization: Bearer ${PARTICIPANT_BEARER_TOKEN}")
  [[ -z ${PARTICIPANT_BASIC_AUTH:-} || ${url} =~ ^https://git\.cinder\.lab/ ]] || args+=(--user "${PARTICIPANT_BASIC_AUTH}")
  curl "${args[@]}" "${url}" >"${output}"
}

require_host() {
  local url=$1 pattern=$2
  [[ ${url} =~ ${pattern} ]] || die "carrier is not served by the operation's owning product"
}

json_payload() {
  local source=$1 output=$2
  if jq -e '.content and (.encoding == "base64")' "${source}" >/dev/null 2>&1; then
    jq -er '.content | gsub("\\n"; "") | @base64d' "${source}" >"${output}"
  else
    cp "${source}" "${output}"
  fi
  jq -e . "${output}" >/dev/null || die 'carrier is not a JSON enterprise record'
}

[[ -n ${OPERATION} ]] || die "usage: $0 <kep-m09-operation>"
flag="$(jq -er --arg id "${OPERATION}" '.[] | select(.id == $id) | .flag' "${MODULE_ROOT}/operations.json")" || die "unknown operation: ${OPERATION}"
family="$(jq -er --arg id "${OPERATION}" '.[] | select(.id == $id) | .model_family' "${MODULE_ROOT}/operations.json")"
[[ -n ${PARTICIPANT_CARRIER_URL:-} ]] || die 'PARTICIPANT_CARRIER_URL must name the exact native result reached by the participant'
[[ -n ${PARTICIPANT_NEGATIVE_URL:-} ]] || die 'PARTICIPANT_NEGATIVE_URL must name the matching rejected attempt record'

case "${OPERATION}" in
  kep-m09-a|kep-m09-b) require_host "${PARTICIPANT_CARRIER_URL}" '^https://mlflow\.keplerops\.lab/' ;;
  kep-m09-c|kep-m09-d|kep-m09-e|kep-m09-f|kep-m09-g|kep-m09-j|kep-m09-k|kep-m09-l)
    require_host "${PARTICIPANT_CARRIER_URL}" '^https://files\.keplerops\.lab/' ;;
  kep-m09-h) require_host "${PARTICIPANT_CARRIER_URL}" '^https://git\.cinder\.lab/' ;;
  kep-m09-i) require_host "${PARTICIPANT_CARRIER_URL}" '^https://relay\.cinder\.lab/' ;;
esac
require_host "${PARTICIPANT_NEGATIVE_URL}" '^https://files\.keplerops\.lab/'

carrier_raw="$(mktemp)"; carrier="$(mktemp)"; negative_raw="$(mktemp)"; negative="$(mktemp)"
trap 'rm -f "${carrier_raw}" "${carrier}" "${negative_raw}" "${negative}"' EXIT
fetch "${PARTICIPANT_CARRIER_URL}" "${carrier_raw}"
fetch "${PARTICIPANT_NEGATIVE_URL}" "${negative_raw}"
json_payload "${carrier_raw}" "${carrier}"
json_payload "${negative_raw}" "${negative}"

# `artifact-defined` is a catalog declaration, not a runtime value: h-l carriers
# must resolve the concrete bounded family of the accepted artifact from the
# authoritative family set, while a-g bind the fixed release-risk family.
if [[ ${family} == artifact-defined ]]; then
  jq -e --arg operation "${OPERATION}" '
    .operation == $operation and
    ([.model_family] | inside(["release-risk","assistant","vision-prototype","physical-device","attacker-glm"])) and
    (.attempt_id | test("^[A-Za-z0-9][A-Za-z0-9._-]{7,95}$")) and
    (.subject_digest | test("^sha256:[0-9a-f]{64}$"))
  ' "${carrier}" >/dev/null || die 'artifact-defined carrier lacks exact operation, attempt, subject, or concrete-family binding'
else
  jq -e --arg operation "${OPERATION}" --arg family "${family}" '
    .operation == $operation and .model_family == $family and
    (.attempt_id | test("^[A-Za-z0-9][A-Za-z0-9._-]{7,95}$")) and
    (.subject_digest | test("^sha256:[0-9a-f]{64}$"))
  ' "${carrier}" >/dev/null || die 'positive carrier lacks exact operation, attempt, subject, or model-family binding'
fi
if [[ ${OPERATION} == kep-m09-f ]]; then
  jq -e --arg flag "${flag}" '.statement.predicate.engagement_reference == $flag' "${carrier}" >/dev/null \
    || die 'signed statement lacks the exact operation reference'
else
  jq -e --arg flag "${flag}" '.engagement_reference == $flag' "${carrier}" >/dev/null \
    || die 'native result lacks the exact operation reference'
fi
jq -e --arg flag "${flag}" '[.. | strings] | index($flag) == null' "${negative}" >/dev/null \
  || die 'rejected attempt exposes the operation reference'
positive_attempt="$(jq -er '.attempt_id' "${carrier}")"
positive_subject="$(jq -er '.subject_digest' "${carrier}")"
jq -e --arg operation "${OPERATION}" --arg attempt "${positive_attempt}" --arg subject "${positive_subject}" '
  .schema == "keplerops.operation-denial/v2" and .operation == $operation and
  .attempt_id != $attempt and (.attempt_id | test("^[A-Za-z0-9][A-Za-z0-9._-]{7,95}$")) and
  .subject_digest == $subject and .outcome == "rejected" and
  (.error_class | type == "string" and length > 0) and (.recorded_at | type == "string" and length > 0)
' "${negative}" >/dev/null || die 'negative control is not a rejected attempt for the same operation and immutable subject'

case "${OPERATION}" in
  kep-m09-b)
    jq -e '.schema == "keplerops.visible-evaluation-predicate/v2" and
      .statement._type == "https://in-toto.io/Statement/v1" and
      .statement.predicateType == "https://keplerops.lab/attestations/visible-evaluation/v2" and
      (.predecessor.operation == "kep-m07-e" or .predecessor.operation == "kep-m07-g" or .predecessor.operation == "kep-m07-i") and
      (.source_repository == "keplerops/orion-build" or .source_repository == "keplerops/orion-model-integrity") and
      (.artifact_source_repository == "keplerops/orion-build" or .artifact_source_repository == "keplerops/orion-model-integrity" or .artifact_source_repository == "cinder-labs/orion-poisoned-dataset") and
      (.source_commit | test("^[0-9a-f]{40}([0-9a-f]{24})?$")) and
      (.artifact_source_commit | test("^[0-9a-f]{40}([0-9a-f]{24})?$")) and
      ([.source_tree_digest,.artifact_source_tree_digest,.data_digest,.model_digest,.prompt_digest,.suite_digest,.heldout_suite_digest,
        .integrity_report_digest,.integrity_handoff_digest,.review_image_digest,.report_digest,
        .predecessor.model_digest] |
        all(test("^sha256:[0-9a-f]{64}$"))) and
      ((.artifact_digest == null) or (.artifact_digest | test("^sha256:[0-9a-f]{64}$"))) and
      ((.predecessor.artifact_digest == null) or (.predecessor.artifact_digest | test("^sha256:[0-9a-f]{64}$"))) and
      .predecessor.model_digest == .model_digest and .predecessor.artifact_digest == .artifact_digest and
      .visible.passed == .visible.cases and .visible.cases >= 8 and
      (.heldout_case_ids | length >= 2) and
      ((.private_controls.artifact_execution == "passed" and .private_controls.heldout_fidelity == "passed") or
       (.private_controls.trigger == "passed" and .private_controls.near_neighbor == "passed")) and
      (.data_provenance | type == "object" and length > 0) and
      (.signature.bundle_sha256 | test("^sha256:[0-9a-f]{64}$")) and (.signature.transparency_log_index | type == "number")' "${carrier}" >/dev/null
    ;;
  kep-m09-a)
    jq -e '.schema == "keplerops.registered-candidate/v2" and
      ([.model_digest,.image_digest,.image_manifest_digest,.image_config_digest,.visible_report_digest] |
        all(test("^sha256:[0-9a-f]{64}$"))) and .candidate_name and .model_version and
      .oci_provenance.forgejo_repository == .forgejo_build_repository and
      .oci_provenance.forgejo_workflow == ".forgejo/workflows/release-image.yml" and
      (.oci_provenance.forgejo_head_sha | test("^[0-9a-f]{40}([0-9a-f]{24})?$")) and
      (.oci_provenance.forgejo_run_id | type == "number") and .isolated_load.loaded_members == .model_members' "${carrier}" >/dev/null
    ;;
  kep-m09-c)
    jq -e '.schema == "keplerops.lineage-resolution/v2" and .decision == "accepted" and
      .resolved_lineage and .immutable_evidence and
      .resolved_lineage["keplerops.lineage.source_commit"] != .immutable_evidence.source_commit and
      ([.model_digest,.image_digest,.record_digest] | all(test("^sha256:[0-9a-f]{64}$")))' "${carrier}" >/dev/null
    ;;
  kep-m09-d)
    jq -e '.schema == "keplerops.release-approval-decision/v2" and .allow == true and
      .approved_model_digest != .resolved_model_digest and .native_approval.state == "approved" and
      .native_approval.approver == "release.engineer" and
      (.native_approval_signature.bundle_sha256 | test("^sha256:[0-9a-f]{64}$")) and
      (.decision_digest | test("^sha256:[0-9a-f]{64}$"))' "${carrier}" >/dev/null
    ;;
  kep-m09-e)
    jq -e '.schema == "keplerops.image-binding-decision/v2" and .allow == true and
      .evaluated_image_digest != .resolved_image_digest and
      ([.model_digest,.evaluated_image_digest,.resolved_image_digest,.decision_digest] |
        all(test("^sha256:[0-9a-f]{64}$"))) and .harbor_artifact_id' "${carrier}" >/dev/null
    ;;
  kep-m09-f)
    jq -e '.schema == "keplerops.signed-release/v2" and
      .statement._type == "https://in-toto.io/Statement/v1" and
      .statement.predicateType == "https://keplerops.lab/attestations/orion-release/v2" and
      (.statement.subject | length) == 2 and .cosign_verified == true and .transparency_verified == true and
      ([.release_id,.model_digest,.image_digest,.signature.bundle_sha256,.promotion_authorization.capability_id] |
        all(test("^sha256:[0-9a-f]{64}$"))) and
      .promotion_authorization.scope.operation == "kep-m09-g" and
      .promotion_authorization.scope.target == "orion-canary" and
      .promotion_authorization.scope.release_id == .release_id and
      .promotion_authorization.scope.max_uses == 1 and (.promotion_authorization.token | test("^[0-9a-f]{64}$")) and
      .release_state.schema == "keplerops.release-state/v2" and
      .statement.predicate.release_id == .release_id and
      (.statement.predicate.release_state == .release_state) and
      (.release_state | has("source") and has("data") and has("training") and has("model") and
        has("serving_image") and has("evaluation") and has("approval") and has("signature") and
        has("deployment") and has("runtime")) and
      (.release_state | [.source.commit, .model.model_digest, .serving_image.image_digest,
        .serving_image.sbom.artifact_digest, .evaluation.visible_report_digest,
        .data.export_digest, .training.training_manifest_digest] |
        all(type == "string" and test("^(sha256:)?[0-9a-f]{40,64}$"))) and
      (.release_state | (.source | has("tree_digest")) and (.approval | has("policy_path")) and
        (.evaluation | has("hidden_suite_digest")) and
        (.data.provenance | type == "object" and length > 0) and
        (.training | [.code_image,.airflow_dag,.airflow_run,.seed,.runtime,.hardware_class] |
          all(type == "string" and length > 0)))' "${carrier}" >/dev/null
    ;;
  kep-m09-g)
    jq -e '.schema == "keplerops.runtime-inventory/v2" and .application == "orion-canary" and
      .healthy == true and (.running_image_ids | length) > 0 and
      (.gitops_commit | test("^[0-9a-f]{40}([0-9a-f]{24})?$")) and
      ([.release_id,.model_digest,.image_digest,.deployment_manifest_digest,.signature_bundle_digest] |
        all(test("^sha256:[0-9a-f]{64}$"))) and
      .promotion_capability.consumed == true and .promotion_capability.scope.operation == "kep-m09-g" and
      .promotion_capability.scope.target == "orion-canary" and .promotion_capability.scope.max_uses == 1 and
      .inferenceservice_annotations["keplerops.lab/release-id"] == .release_id and
      .inferenceservice_annotations["keplerops.lab/model-digest"] == .model_digest' "${carrier}" >/dev/null
    ;;
  kep-m09-h)
    jq -e '.schema == "cinder.model-release-attestation/v2" and
      .verification == "metadata-and-signature-only; no model deserialization performed" and
      .artifact_filename == "orion-model.pkl" and .artifact_format == "python-pickle" and
      .artifact_interface == "embedded-onnx-package" and
      ([.artifact_sha256,.model_card_sha256,.execution_report_sha256,.heldout_suite_digest,
        .fresh_inference_digest,.model_subject_digest] | all(test("^sha256:[0-9a-f]{64}$"))) and
      .source_repository == "cinder-labs/orion-poisoned-dataset" and
      (.source_tree_digest | test("^sha256:[0-9a-f]{64}$")) and
      (.source_commit | test("^[0-9a-f]{40}([0-9a-f]{24})?$")) and .heldout_accuracy >= 0.5 and
      (.accepted_release_commit | test("^[0-9a-f]{40}([0-9a-f]{24})?$")) and
      (.package_members | type == "object" and length >= 7) and
      (.signature | test("^[0-9a-f]{64}$"))' "${carrier}" >/dev/null
    ;;
  kep-m09-i)
    jq -e '.schema == "keplerops.model-import-result/v2" and .operation == "kep-m09-i" and
      .scan.scan_error and .import.bounded_event and .import.returncode != 0 and
      .import.bounded_event.recorded_ns < .import.completed_ns and
      (.artifact_sha256 | test("^sha256:[0-9a-f]{64}$"))' "${carrier}" >/dev/null
    ;;
  kep-m09-j)
    jq -e '.schema == "keplerops.model-mirror-manifest/v2" and
      ([.artifact_sha256,.mutable_binding.before_sha256,.mutable_binding.after_sha256,.acquisition.download_sha256] |
        all(test("^sha256:[0-9a-f]{64}$"))) and
      .mutable_binding.before_sha256 != .mutable_binding.after_sha256 and
      .acquisition.upstream_release_id and (.mirror_key | startswith("model-mirror/orion/"))' "${carrier}" >/dev/null
    ;;
  kep-m09-k)
    jq -e '.schema == "keplerops.model-import-result/v2" and .operation == "kep-m09-k" and
      .review_action_id and .review_event_id and .mirror_manifest and .import.bounded_event and
      .import.returncode == 0 and .import.loader.status == "loaded" and .import.loader.smoke_prediction != null and
      (.artifact_sha256 | test("^sha256:[0-9a-f]{64}$"))' "${carrier}" >/dev/null
    ;;
  kep-m09-l)
    jq -e '.schema == "keplerops.staging-reconciliation/v2" and .application == "orion-staging" and
      .healthy == true and (.running_image_ids | length) > 0 and
      (.gitops_commit | test("^[0-9a-f]{40}([0-9a-f]{24})?$")) and
      ([.image_digest,.model_digest,.image_manifest_digest,.deployment_manifest_digest,
        .oci_provenance.forgejo_workflow_sha256] | all(test("^sha256:[0-9a-f]{64}$"))) and
      .oci_provenance.forgejo_repository == "keplerops/orion-staging" and
      .oci_provenance.forgejo_workflow == ".forgejo/workflows/staging-image.yml" and
      (.oci_provenance.forgejo_run_id | type == "number")' "${carrier}" >/dev/null
    ;;
esac

printf '%s: v2 native carrier and operation/attempt/subject-bound denial passed\n' "${OPERATION}"
