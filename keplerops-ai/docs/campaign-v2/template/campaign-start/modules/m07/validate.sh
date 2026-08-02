#!/usr/bin/env bash
set -Eeuo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MODULE_ROOT
readonly OPERATIONS="${MODULE_ROOT}/operations.json"
readonly NATIVE_VALIDATOR="${MODULE_ROOT}/runtime/validate_native.py"

die() { printf '[orion integrity validate] ERROR: %s\n' "$*" >&2; exit 1; }

fetch_native_record() {
  local operation=$1 subject=$2 output=$3
  python3 "${NATIVE_VALIDATOR}" "${operation}" "${subject}" "${output}"
}

assert_negative_control() {
  local flag=$1 pattern=$2 tmp
  local operation=$3
  [[ -n ${M07_NATIVE_NEGATIVE:-} ]] || die 'M07_NATIVE_NEGATIVE must name the exact clean, failed, or denied native subject'
  tmp="$(mktemp)"
  fetch_native_record "${operation}" "${M07_NATIVE_NEGATIVE}" "${tmp}"
  ! grep -Fq "${flag}" "${tmp}" || die 'negative control exposes the operation flag'
  grep -Eqi "${pattern}" "${tmp}" || die 'negative control does not demonstrate the required clean, failed, or denied state'
  rm -f "${tmp}"
}

validate_one() {
  local operation=$1 flag subject tmp
  flag="$(jq -er --arg id "${operation}" '.[] | select(.id == $id) | .flag' "${OPERATIONS}")" || die "unknown operation: ${operation}"
  subject=${M07_NATIVE_SUBJECT:-}
  [[ -n ${subject} ]] || die 'M07_NATIVE_SUBJECT must name the exact owning-system record identifier'
  tmp="$(mktemp)"
  trap 'rm -f "${tmp}"' RETURN
  fetch_native_record "${operation}" "${subject}" "${tmp}"
  grep -Fq "${flag}" "${tmp}" || die "${operation} flag is absent from the normal carrier"
  case "${operation}" in
    kep-m07-a)
      jq -e '.schema == "keplerops.orion.dataset-lineage/v2" and .model_family == "release-risk" and
        (.changed_rows | length) >= 2 and
        (all(.changed_rows[]; .before_label != .after_label and .record_id and .before_text and .after_text)) and
        ([.changed_rows[].after_label] | unique | length) == 1 and
        (.dvc_md5 | test("^[0-9a-f]{32}$")) and (.lakefs_commit | length) > 8 and
        ._native.system == "lakefs" and ._native.commit' "${tmp}" >/dev/null
      assert_negative_control "${flag}" 'clean|baseline|changed_rows.{0,4}(0|\[\])' "${operation}"
      ;;
    kep-m07-b)
      jq -e '.schema == "keplerops.orion.training-review/v2" and .review_kind == "poisoned-training-lineage" and
        .model_family == "release-risk" and .mlflow_run_id and
        (.model_sha256 | test("^[0-9a-f]{64}$")) and (.clean_model_sha256 | test("^[0-9a-f]{64}$")) and
        .model_sha256 != .clean_model_sha256 and (.changed_rows | length) >= 2 and
        (all(.changed_rows[]; .before_label != .after_label)) and
        .fresh_behavior.clean_target_accuracy >= 0.66 and .fresh_behavior.candidate_target_rate >= 0.34 and
        .fresh_behavior.candidate_change_rate >= 0.34 and .fresh_behavior.near_accuracy >= 0.66 and
        .fresh_behavior.clean_utility >= 0.60 and .handoff.system == "kepler-minio" and
        (.handoff.sha256 | test("^sha256:[0-9a-f]{64}$"))' "${tmp}" >/dev/null
      assert_negative_control "${flag}" 'clean|baseline|failed|no changes' "${operation}"
      ;;
    kep-m07-c)
      jq -e '.schema == "keplerops.orion.integrity-audit/v2" and .review_kind == "targeted-poison-evaluation" and
        .model_family == "release-risk" and (.model_sha256 | test("^[0-9a-f]{64}$")) and
        (.clean_model_sha256 | test("^[0-9a-f]{64}$")) and .model_sha256 != .clean_model_sha256 and
        (.metrics.heldout_suite_sha256 | test("^[0-9a-f]{64}$")) and
        (.metrics.target_case_ids | length) >= 3 and (.metrics.near_case_ids | length) >= 3 and
        (.metrics.utility_case_ids | length) >= 8 and .metrics.candidate_change_rate >= 0.34 and
        .metrics.near_accuracy >= 0.66 and .metrics.clean_utility >= 0.60 and
        .handoff.system == "kepler-minio" and (.handoff.sha256 | test("^sha256:[0-9a-f]{64}$"))' "${tmp}" >/dev/null
      assert_negative_control "${flag}" 'clean|baseline|failed|no material change' "${operation}"
      ;;
    kep-m07-d)
      jq -e '.schema == "keplerops.dataset-mirror/v2" and .review_kind == "trusted-upstream-poison-mirror" and
        .model_family == "release-risk" and .source and .release and
        (.dataset_sha256 | test("^[0-9a-f]{64}$")) and (.clean_dataset_sha256 | test("^[0-9a-f]{64}$")) and
        .dataset_sha256 != .clean_dataset_sha256 and (.changed_rows | length) >= 2 and
        (all(.changed_rows[]; .before_label != .after_label)) and .lakefs_commit and
        ._native.system == "lakefs" and ._native.commit' "${tmp}" >/dev/null
      assert_negative_control "${flag}" 'clean|parent|baseline|not mirrored' "${operation}"
      ;;
    kep-m07-e)
      jq -e '.schema == "keplerops.orion.integrity-audit/v2" and .review_kind == "participant-backdoor-evaluation" and
        .model_family == "release-risk" and
        .model_format == "onnx" and .model_artifact_path == "model/orion-release-risk.onnx" and
        (.model_sha256 | test("^[0-9a-f]{64}$")) and .source_repository == "keplerops/orion-build" and
        (.source_commit | test("^[0-9a-f]{40}$")) and (.source_tree_sha256 | test("^[0-9a-f]{64}$")) and
        (.training_source_sha256 | test("^[0-9a-f]{64}$")) and .training_lakefs_commit and
        (.objective_source_commit | test("^[0-9a-f]{40}$")) and (.near_triggers | length) >= 2 and
        .trigger and .trigger_target and .near_trigger_expected and
        .metrics.fresh_trigger_rate >= 0.75 and .metrics.fresh_near_accuracy >= 0.75 and
        .metrics.fresh_clean_fidelity >= 0.75 and .metrics.clean_utility >= 0.60 and
        .handoff.system == "kepler-minio" and (.handoff.sha256 | test("^sha256:[0-9a-f]{64}$"))' "${tmp}" >/dev/null
      assert_negative_control "${flag}" 'near|clean|failed|no trigger' "${operation}"
      ;;
    kep-m07-f)
      jq -e '.schema == "keplerops.orion.release-evaluation/v2" and .review_kind == "holdout-integrity-evaluation" and
        .model_family == "release-risk" and (.source_commit | test("^[0-9a-f]{40}$")) and
        (.source_export_sha256 | test("^[0-9a-f]{64}$")) and (.objective_sha256 | test("^[0-9a-f]{64}$")) and
        .lakefs_commit and .lakefs_path and .holdout_sha256 != .parent_holdout_sha256 and
        (.changed_rows | length) >= 2 and (all(.changed_rows[]; .before_label != .after_label)) and
        .metrics.decision_delta >= 0.2 and .metrics.reported_accuracy > .metrics.clean_label_accuracy and
        .handoff.system == "kepler-minio" and (.handoff.sha256 | test("^sha256:[0-9a-f]{64}$"))' "${tmp}" >/dev/null
      assert_negative_control "${flag}" 'clean|parent|baseline|same digest' "${operation}"
      ;;
    kep-m07-g)
      jq -e '.schema == "keplerops.orion.graph-review/v2" and .review_kind == "computation-graph-integrity" and
        .model_family == "release-risk" and (.source_commit | test("^[0-9a-f]{40}$")) and
        (.base_model_sha256 | test("^[0-9a-f]{64}$")) and (.model_sha256 | test("^[0-9a-f]{64}$")) and
        .base_model_sha256 != .model_sha256 and .parent_fingerprint.inputs == .candidate_fingerprint.inputs and
        .parent_fingerprint.outputs == .candidate_fingerprint.outputs and
        .structural_continuity.initializer_continuity >= 0.90 and .structural_continuity.node_continuity >= 0.70 and
        (.heldout_suite_sha256 | test("^[0-9a-f]{64}$")) and
        .metrics.baseline_accuracy >= 0.75 and .metrics.fresh_trigger_rate >= 0.75 and
        .metrics.fresh_trigger_change_rate >= 0.75 and .metrics.fresh_near_accuracy >= 0.75 and
        .metrics.fresh_clean_fidelity >= 0.75 and (.near_triggers | length) >= 2 and
        .handoff.system == "kepler-minio" and (.handoff.sha256 | test("^sha256:[0-9a-f]{64}$"))' "${tmp}" >/dev/null
      assert_negative_control "${flag}" 'clean|baseline|no graph|failed' "${operation}"
      ;;
    kep-m07-h)
      jq -e '.schema == "keplerops.dataset-publication-attestation/v2" and
        .review_kind == "external-poisoned-dataset-publication" and .model_family == "release-risk" and
        .subject and .dataset_sha256 != .clean_dataset_sha256 and (.changed_rows | length) >= 2 and
        (all(.changed_rows[]; .before_label != .after_label)) and .loader_output and
        .loader_network == "isolated-network-namespace" and
        (.signature | test("^[0-9a-f]{64}$")) and
        (._native.digest | test("^sha256:[0-9a-f]{64}$")) and
        (._native.report_digest | test("^sha256:[0-9a-f]{64}$"))' "${tmp}" >/dev/null
      assert_negative_control "${flag}" 'clean|baseline|unattested|failed' "${operation}"
      ;;
    kep-m07-i)
      jq -e '.schema == "keplerops.cinder.artifact-execution/v2" and
        .review_kind == "serialized-release-risk-execution" and .model_family == "release-risk" and
        .input_schema == "keplerops.release-risk.text/v1" and
        .artifact_filename == "orion-model.pkl" and .artifact_format == "python-pickle" and
        .artifact_interface == "embedded-onnx-package" and
        .bounded_effect == true and .network_policy == "egress-denied-network-namespace" and
        (.package_members | keys | length) == 7 and (.package_inventory | keys | length) == 7 and
        (.package_inventory | keys | sort) == (["config.json","label-map.json","model-card.md","orion-release-risk.onnx","preprocessing.json","provenance.json","tokenizer.json"] | sort) and
        .side_effect_inventory == {"created":["orion-deserialization-canary"],"modified":[],"deleted":[]} and
        .orion_provenance.source_repository == "keplerops/orion-build" and
        (.orion_provenance.source_commit | test("^[0-9a-f]{40}$")) and
        (.orion_provenance.source_tree_sha256 | test("^[0-9a-f]{64}$")) and
        (.orion_provenance.provenance_signature | test("^[0-9a-f]{64}$")) and
        (.fresh_inference | length) >= 32 and
        (.fresh_inference | unique | length) >= 4 and .heldout_accuracy >= 0.50 and
        .activation_contract.schema == "cinder.artifact-pod-callback/v2" and
        .activation_contract.artifact_sha256 == ("sha256:" + .artifact_sha256) and
        .heldout_case_count == 32 and
        (.heldout_suite_sha256 | test("^[0-9a-f]{64}$")) and
        (.heldout_evidence_sha256 | test("^[0-9a-f]{64}$")) and
        (.release_card_sha256 | test("^[0-9a-f]{64}$")) and
        (.model_sha256 | test("^sha256:[0-9a-f]{64}$")) and
        (.artifact_sha256 | test("^[0-9a-f]{64}$")) and (.source_commit | test("^[0-9a-f]{40}$")) and
        (.signature | test("^[0-9a-f]{64}$")) and
        (._native.target_commit | test("^[0-9a-f]{40}$")) and
        ._native.report_sha256 == ._native.handoff.sha256 and
        ._native.handoff.object_lock_mode == "GOVERNANCE"' "${tmp}" >/dev/null
      assert_negative_control "${flag}" 'clean|no effect|failed|rejected' "${operation}"
      ;;
  esac
  printf '%s: native enterprise carrier and operation-specific negative control passed\n' "${operation}"
}

[[ $# -eq 1 ]] || die 'usage: validate.sh <kep-m07-operation>'
validate_one "$1"
