#!/usr/bin/env bash

set -Eeuo pipefail

readonly STATE_DIR=/var/lib/keplerops-platform
readonly SIGNING_DIR="${STATE_DIR}/signing"
readonly MODEL_ENDPOINT=http://192.168.78.30:30083

if [[ ${EUID} -ne 0 ]]; then
  exec sudo "$0" "${SSH_ORIGINAL_COMMAND:-}"
fi

wait_for_file() {
  local path=$1
  for _ in $(seq 1 240); do
    [[ -s ${path} ]] && return 0
    sleep 5
  done
  return 1
}

emit_model_evidence() {
  local candidate_dir release_dir workdir report_digest
  local -a labels=(
    ReleaseApprove
    ReleaseHold
    PartnerIntake
    EntitlementReview
    SecurityAdvisory
    SupportEscalation
    ResearchReview
    PrivacySafety
  )

  for command in awk cmp cosign curl install jq mktemp readlink seq sha256sum sleep stat; do
    command -v "${command}" >/dev/null || {
      printf 'required evidence command is unavailable: %s\n' "${command}" >&2
      exit 3
    }
  done
  wait_for_file "${STATE_DIR}/current-release/release.json" || {
    printf 'current Orion platform release is unavailable\n' >&2
    exit 3
  }
  wait_for_file "${STATE_DIR}/current-candidate/evaluation-report.json" || {
    printf 'current Orion evaluation report is unavailable\n' >&2
    exit 3
  }
  wait_for_file "${SIGNING_DIR}/cosign.pub" || {
    printf 'Orion platform signing public key is unavailable\n' >&2
    exit 3
  }

  release_dir="$(readlink -f "${STATE_DIR}/current-release")"
  candidate_dir="$(readlink -f "${STATE_DIR}/current-candidate")"
  [[ -d ${release_dir} && -d ${candidate_dir} ]] || {
    printf 'current Orion release state is invalid\n' >&2
    exit 3
  }
  workdir="$(mktemp -d)"
  trap 'rm -rf "${workdir}"' RETURN

  (
    cd "${release_dir}"
    sha256sum -c SHA256SUMS >/dev/null
    cmp cosign.pub "${SIGNING_DIR}/cosign.pub"
    cosign verify-blob --insecure-ignore-tlog --key "${SIGNING_DIR}/cosign.pub" \
      --bundle release.sigstore.json release.intoto.json >/dev/null
  )
  install -m 0600 "${release_dir}/release.json" "${workdir}/release.json"
  install -m 0600 "${candidate_dir}/candidate.json" "${workdir}/candidate.json"
  install -m 0600 "${candidate_dir}/evaluation-report.json" "${workdir}/evaluation.json"
  install -m 0600 "${candidate_dir}/model/label-map.json" "${workdir}/label-map.json"

  jq -e --slurpfile release "${workdir}/release.json" '
    .predicate == $release[0]
    and .predicateType == "https://keplerops.lab/attestations/release/v2"
    and any(.subject[]; .name == "orion-release-risk.onnx"
      and .digest.sha256 == ($release[0].model.onnx_digest | sub("^sha256:"; "")))
  ' "${release_dir}/release.intoto.json" >/dev/null || {
    printf 'Orion release record does not match its signed attestation\n' >&2
    exit 4
  }

  report_digest="$(sha256sum "${workdir}/evaluation.json" | awk '{print $1}')"
  jq -e --arg report_digest "sha256:${report_digest}" '
    .schema == "keplerops.release/v2"
    and .model_family == "release-risk"
    and (.created_at | type == "string" and length > 0)
    and (.release_id | test("^sha256:[0-9a-f]{64}$"))
    and (.source.commit | test("^[0-9a-f]{40}([0-9a-f]{24})?$"))
    and (.dataset.label_schema_digest | test("^sha256:[0-9a-f]{64}$"))
    and (.model.onnx_digest | test("^sha256:[0-9a-f]{64}$"))
    and (.model.tokenizer_digest | test("^sha256:[0-9a-f]{64}$"))
    and (.serving_image.image_digest | test("^sha256:[0-9a-f]{64}$"))
    and .serving_image.runtime == "onnxruntime-cpu"
    and .model.format == "onnx"
    and .evaluation.decision == "accepted"
    and .evaluation.report_digest == $report_digest
    and .approval.status == "approved"
    and (.runtime.kserve_revision | type == "string" and length > 0)
  ' "${workdir}/release.json" >/dev/null || {
    printf 'current Orion signed release failed evidence policy\n' >&2
    exit 4
  }

  jq -e --slurpfile release "${workdir}/release.json" '
    def bare: sub("^sha256:"; "");
    .schema == "keplerops.release-candidate/v1"
    and .model_family == "release-risk"
    and .source.commit == $release[0].source.commit
    and .model.mlflow_run_id == $release[0].model.mlflow_run_id
    and .model.mlflow_model_version == $release[0].model.mlflow_model_version
    and .model.onnx_digest == ($release[0].model.onnx_digest | bare)
    and .model.tokenizer_digest == ($release[0].model.tokenizer_digest | bare)
    and .dataset.label_schema_digest == ($release[0].dataset.label_schema_digest | bare)
    and .serving_image.image_digest == ($release[0].serving_image.image_digest | bare)
    and .evaluation.suite_digest == ($release[0].evaluation.suite_digest | bare)
    and .evaluation.report_digest == ($release[0].evaluation.report_digest | bare)
    and .evaluation.decision == "accepted"
  ' "${workdir}/candidate.json" >/dev/null || {
    printf 'current Orion candidate does not match the signed release\n' >&2
    exit 4
  }

  jq -e --slurpfile release "${workdir}/release.json" \
    --argjson labels "$(printf '%s\n' "${labels[@]}" | jq -R . | jq -s .)" '
    def bare: sub("^sha256:"; "");
    . as $report
    |
    .schema == "keplerops.release-risk.evaluation/v1"
    and .suite_sha256 == ($release[0].evaluation.suite_digest | bare)
    and .model_sha256 == ($release[0].model.onnx_digest | bare)
    and .tokenizer_sha256 == ($release[0].model.tokenizer_digest | bare)
    and .mlflow_run_id == $release[0].model.mlflow_run_id
    and .mlflow_model_version == $release[0].model.mlflow_model_version
    and (.records | type == "number" and floor == . and . > 0)
    and (.correct | type == "number" and floor == . and . >= 0)
    and (.correct <= .records)
    and (.accuracy | type == "number" and . >= 0 and . <= 1)
    and .accuracy == (.correct / .records)
    and (.minimum_accuracy | type == "number" and . >= 0 and . <= 1)
    and .accuracy >= .minimum_accuracy
    and .decision == "accepted"
    and (.per_class_accuracy | keys) == ($labels | sort)
    and all(.per_class_accuracy[]; type == "number" and . >= 0 and . <= 1)
    and (.cases | type == "array" and length == $report.records)
    and all(.cases[];
      (.case_id | type == "string" and length > 0)
      and (.expected | IN($labels[]))
      and (.predicted | IN($labels[]))
      and (.correct == (.expected == .predicted)))
    and ([.cases[] | select(.correct == true)] | length) == .correct
    and all($labels[];
      . as $label
      | ([ $report.cases[] | select(.expected == $label) ] | length) > 0
        and $report.per_class_accuracy[$label] ==
          (([ $report.cases[] | select(.expected == $label and .correct == true) ] | length) /
           ([ $report.cases[] | select(.expected == $label) ] | length)))
  ' "${workdir}/evaluation.json" >/dev/null || {
    printf 'current Orion evaluation report failed evidence policy\n' >&2
    exit 4
  }

  jq -e --argjson labels "$(printf '%s\n' "${labels[@]}" | jq -R . | jq -s .)" '
    (to_entries | sort_by(.value) | map(.key)) == $labels
    and ([to_entries[].value] | sort) == [0,1,2,3,4,5,6,7]
  ' "${workdir}/label-map.json" >/dev/null || {
    printf 'current Orion class map failed evidence policy\n' >&2
    exit 4
  }

  for _ in $(seq 1 60); do
    if curl -fsS "${MODEL_ENDPOINT}/v1/models/orion-release-risk" \
        >"${workdir}/runtime.json" 2>/dev/null; then
      break
    fi
    sleep 2
  done
  [[ -s ${workdir}/runtime.json ]] || {
    printf 'Orion Release Risk runtime metadata is unavailable\n' >&2
    exit 4
  }
  jq -e --slurpfile release "${workdir}/release.json" \
    --argjson labels "$(printf '%s\n' "${labels[@]}" | jq -R . | jq -s .)" '
    def bare: sub("^sha256:"; "");
    .name == "orion-release-risk"
    and .ready == true
    and .model_family == "release-risk"
    and .runtime == "onnxruntime-cpu"
    and .class_count == 8
    and (.labels | sort) == ($labels | sort)
    and .model_sha256 == ($release[0].model.onnx_digest | bare)
    and .tokenizer_sha256 == ($release[0].model.tokenizer_digest | bare)
    and .mlflow_run_id == $release[0].model.mlflow_run_id
    and .mlflow_model_version == $release[0].model.mlflow_model_version
  ' "${workdir}/runtime.json" >/dev/null || {
    printf 'live Orion Release Risk runtime does not match the signed release\n' >&2
    exit 4
  }

  jq -S -n \
    --slurpfile release "${workdir}/release.json" \
    --slurpfile evaluation "${workdir}/evaluation.json" \
    --argjson classes "$(printf '%s\n' "${labels[@]}" | jq -R . | jq -s .)" '
    {
      schema:"keplerops.orion-release-risk.evidence/v1",
      generated_at:$release[0].created_at,
      source:{
        revision:$release[0].source.commit
      },
      service:{
        name:"orion-release-risk",
        model_family:"release-risk",
        runtime:"onnxruntime-cpu",
        classes:$classes
      },
      model:{
        platform_release_id:$release[0].release_id,
        runtime_revision:$release[0].runtime.kserve_revision,
        mlflow_run_id:$release[0].model.mlflow_run_id,
        mlflow_model_version:$release[0].model.mlflow_model_version,
        onnx_sha256:$release[0].model.onnx_digest,
        tokenizer_sha256:$release[0].model.tokenizer_digest,
        label_schema_sha256:$release[0].dataset.label_schema_digest,
        serving_image_sha256:$release[0].serving_image.image_digest
      },
      evaluation:{
        suite_sha256:$release[0].evaluation.suite_digest,
        report_sha256:$release[0].evaluation.report_digest,
        records:$evaluation[0].records,
        correct:$evaluation[0].correct,
        accuracy:$evaluation[0].accuracy,
        minimum_accuracy:$evaluation[0].minimum_accuracy,
        decision:$evaluation[0].decision,
        per_class_accuracy:$evaluation[0].per_class_accuracy
      }
    }
  '
}

operation=${1:-}
case "${operation}" in
  public-key)
    wait_for_file "${SIGNING_DIR}/cosign.pub" || {
      printf 'Orion release signing identity is unavailable\n' >&2
      exit 3
    }
    cat "${SIGNING_DIR}/cosign.pub"
    ;;
  model-evidence)
    emit_model_evidence
    ;;
  sign-manifest)
    if ! wait_for_file "${SIGNING_DIR}/cosign.key" || \
        ! wait_for_file "${SIGNING_DIR}/cosign-password"; then
      printf 'Orion release signing identity is unavailable\n' >&2
      exit 3
    fi

    input="$(mktemp)"
    signature="$(mktemp)"
    expected_evidence="$(mktemp)"
    trap 'rm -f "${input}" "${signature}" "${expected_evidence}"' EXIT
    cat >"${input}"
    emit_model_evidence >"${expected_evidence}"
    evidence_digest="$(sha256sum "${expected_evidence}" | awk '{print $1}')"
    evidence_size="$(stat -c %s "${expected_evidence}")"
    jq -e --slurpfile expected "${expected_evidence}" \
      --arg evidence_digest "${evidence_digest}" \
      --argjson evidence_size "${evidence_size}" '
      .schema == "keplerops.orion-public-release/v2"
      and .version == "1.0.0"
      and .source.repository == "keplerops/orion-public"
      and (.source.revision | test("^[0-9a-f]{40}$"))
      and .workflow.repository == "keplerops/orion-build"
      and (.workflow.revision | test("^[0-9a-f]{40}$"))
      and .product == {
        api_origin:"https://preview.keplerops.lab/",
        api_path:"/api/analyze",
        classes:["ReleaseApprove","ReleaseHold","PartnerIntake",
          "EntitlementReview","SecurityAdvisory","SupportEscalation",
          "ResearchReview","PrivacySafety"],
        model_family:"release-risk",
        name:"Orion Release Risk",
        runtime:"onnxruntime-cpu",
        service:"orion-release-risk"
      }
      and .generated_at == $expected[0].generated_at
      and .model == $expected[0].model
      and .evaluation == $expected[0].evaluation
      and (.model.platform_release_id | test("^sha256:[0-9a-f]{64}$"))
      and (.model.runtime_revision | type == "string" and length > 0)
      and (.model.mlflow_run_id | type == "string" and length > 0)
      and (.model.mlflow_model_version | type == "string" and length > 0)
      and all([
        .model.onnx_sha256,
        .model.tokenizer_sha256,
        .model.label_schema_sha256,
        .model.serving_image_sha256,
        .evaluation.suite_sha256,
        .evaluation.report_sha256
      ][]; test("^sha256:[0-9a-f]{64}$"))
      and (.evaluation.records | type == "number" and floor == . and . > 0)
      and (.evaluation.correct | type == "number" and floor == . and . >= 0)
      and .evaluation.correct <= .evaluation.records
      and .evaluation.accuracy == (.evaluation.correct / .evaluation.records)
      and .evaluation.accuracy >= .evaluation.minimum_accuracy
      and .evaluation.decision == "accepted"
      and (.evaluation.per_class_accuracy | keys) == [
        "EntitlementReview","PartnerIntake","PrivacySafety","ReleaseApprove",
        "ReleaseHold","ResearchReview","SecurityAdvisory","SupportEscalation"
      ]
      and all(.evaluation.per_class_accuracy[]; type == "number" and . >= 0 and . <= 1)
      and (.artifacts | length == 9)
      and ([.artifacts[].name] | unique | length == 9)
      and any(.artifacts[]; .name == "orion-release-risk-evidence.json"
        and .role == "model-release-evidence"
        and .sha256 == $evidence_digest
        and .size == $evidence_size)
      and all(.artifacts[];
        (.name | test("^[A-Za-z0-9._-]+$"))
        and (.sha256 | test("^[0-9a-f]{64}$"))
        and (.size > 0))
    ' "${input}" >/dev/null || {
      printf 'Orion release manifest failed signer policy\n' >&2
      exit 4
    }

    export COSIGN_PASSWORD
    COSIGN_PASSWORD="$(<"${SIGNING_DIR}/cosign-password")"
    cosign sign-blob --yes --tlog-upload=false \
      --key "${SIGNING_DIR}/cosign.key" \
      --output-signature "${signature}" "${input}" >/dev/null
    cat "${signature}"
    ;;
  *)
    printf 'unsupported Orion release signer operation\n' >&2
    exit 2
    ;;
esac
