#!/usr/bin/env bash
set -Eeuo pipefail

STATE_DIR=${PLATFORM_STATE_DIR:-/var/lib/keplerops-platform}
SIGNING_DIR=${PLATFORM_SIGNING_DIR:-$STATE_DIR/signing}
export KUBECONFIG=${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}

usage() {
  cat <<'EOF'
Create and sign one immutable Orion release record.

Required environment:
  SOURCE_REPOSITORY SOURCE_COMMIT SOURCE_TREE_DIGEST
  DATA_REPOSITORY DATA_COMMIT DATA_MANIFEST_DIGEST DATA_SPLIT_DIGEST LABEL_SCHEMA_DIGEST
  TRAINING_DAG TRAINING_RUN_ID TRAINING_CODE_IMAGE_DIGEST TRAINING_PARAMETERS_DIGEST
  TRAINING_SEED TRAINING_RUNTIME TRAINING_HARDWARE_CLASS
  MLFLOW_RUN_ID MLFLOW_MODEL_VERSION NATIVE_WEIGHTS_DIGEST ONNX_DIGEST
  TOKENIZER_DIGEST MODEL_CARD_DIGEST
  SERVING_IMAGE_REPOSITORY SERVING_IMAGE_DIGEST SERVING_CONFIG_DIGEST SERVING_SBOM_DIGEST
  EVALUATION_SUITE_DIGEST EVALUATION_INPUT_DIGEST EVALUATION_REPORT_DIGEST
  APPROVAL_ACTOR POLICY_DIGEST APPROVAL_SUBJECT_DIGEST APPROVAL_DECISION_ID
  GITOPS_REPOSITORY GITOPS_COMMIT ARGO_APPLICATION KSERVE_REVISION

All *_DIGEST values must be SHA-256 values, with or without the "sha256:" prefix.
EVALUATION_DECISION defaults to "accepted" and APPROVAL_STATUS to "approved".
The command evaluates OPA and signs locally. It performs no git or kubectl mutation.
EOF
}

[[ ${1:-} != --help ]] || { usage; exit 0; }

required=(
  SOURCE_REPOSITORY SOURCE_COMMIT SOURCE_TREE_DIGEST
  DATA_REPOSITORY DATA_COMMIT DATA_MANIFEST_DIGEST DATA_SPLIT_DIGEST LABEL_SCHEMA_DIGEST
  TRAINING_DAG TRAINING_RUN_ID TRAINING_CODE_IMAGE_DIGEST TRAINING_PARAMETERS_DIGEST
  TRAINING_SEED TRAINING_RUNTIME TRAINING_HARDWARE_CLASS
  MLFLOW_RUN_ID MLFLOW_MODEL_VERSION NATIVE_WEIGHTS_DIGEST ONNX_DIGEST
  TOKENIZER_DIGEST MODEL_CARD_DIGEST
  SERVING_IMAGE_REPOSITORY SERVING_IMAGE_DIGEST SERVING_CONFIG_DIGEST SERVING_SBOM_DIGEST
  EVALUATION_SUITE_DIGEST EVALUATION_INPUT_DIGEST EVALUATION_REPORT_DIGEST
  APPROVAL_ACTOR POLICY_DIGEST APPROVAL_SUBJECT_DIGEST APPROVAL_DECISION_ID
  GITOPS_REPOSITORY GITOPS_COMMIT ARGO_APPLICATION KSERVE_REVISION
)
for name in "${required[@]}"; do
  [[ -n ${!name:-} ]] || { echo "Missing required environment: $name" >&2; exit 2; }
done

normalize_digest() {
  local digest=${1#sha256:}
  [[ $digest =~ ^[a-fA-F0-9]{64}$ ]] || {
    echo "Invalid SHA-256 digest: $1" >&2
    exit 3
  }
  printf 'sha256:%s' "${digest,,}"
}

[[ $SOURCE_COMMIT =~ ^[a-fA-F0-9]{40}([a-fA-F0-9]{24})?$ ]] || {
  echo "SOURCE_COMMIT must be an immutable 40- or 64-hex commit" >&2
  exit 3
}
[[ $GITOPS_COMMIT =~ ^[a-fA-F0-9]{40}([a-fA-F0-9]{24})?$ ]] || {
  echo "GITOPS_COMMIT must be an immutable 40- or 64-hex commit" >&2
  exit 3
}

for name in $(compgen -A variable | awk '/_DIGEST$/'); do
  [[ -n ${!name:-} ]] && printf -v "$name" '%s' "$(normalize_digest "${!name}")"
done

for command in cosign curl jq kubectl sha256sum; do
  command -v "$command" >/dev/null || { echo "Required command is unavailable: $command" >&2; exit 4; }
done
for file in identity.json identity.sig cosign.key cosign.pub cosign-password step-signer.crt; do
  [[ -s $SIGNING_DIR/$file ]] || { echo "Missing signing material: $SIGNING_DIR/$file" >&2; exit 5; }
done

work=$(mktemp -d)
cleanup() {
  [[ -n ${opa_pid:-} ]] && kill "$opa_pid" 2>/dev/null || true
  rm -rf "$work"
}
trap cleanup EXIT

signer_identity=$(jq -r '.identity' "$SIGNING_DIR/identity.json")
step_cert_digest=$(jq -r '.step_certificate_digest' "$SIGNING_DIR/identity.json")
cosign_key_digest=$(jq -r '.cosign_public_key_digest' "$SIGNING_DIR/identity.json")

jq -n \
  --arg created_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg source_repo "$SOURCE_REPOSITORY" --arg source_commit "${SOURCE_COMMIT,,}" --arg source_tree "$SOURCE_TREE_DIGEST" \
  --arg data_repo "$DATA_REPOSITORY" --arg data_commit "$DATA_COMMIT" --arg data_manifest "$DATA_MANIFEST_DIGEST" --arg data_split "$DATA_SPLIT_DIGEST" --arg label_schema "$LABEL_SCHEMA_DIGEST" \
  --arg training_dag "$TRAINING_DAG" --arg training_run "$TRAINING_RUN_ID" --arg training_image "$TRAINING_CODE_IMAGE_DIGEST" --arg training_params "$TRAINING_PARAMETERS_DIGEST" --arg training_seed "$TRAINING_SEED" --arg training_runtime "$TRAINING_RUNTIME" --arg training_hardware "$TRAINING_HARDWARE_CLASS" \
  --arg mlflow_run "$MLFLOW_RUN_ID" --arg mlflow_version "$MLFLOW_MODEL_VERSION" --arg native_weights "$NATIVE_WEIGHTS_DIGEST" --arg onnx "$ONNX_DIGEST" --arg tokenizer "$TOKENIZER_DIGEST" --arg model_card "$MODEL_CARD_DIGEST" \
  --arg image_repo "$SERVING_IMAGE_REPOSITORY" --arg image_digest "$SERVING_IMAGE_DIGEST" --arg image_config "$SERVING_CONFIG_DIGEST" --arg image_sbom "$SERVING_SBOM_DIGEST" \
  --arg eval_suite "$EVALUATION_SUITE_DIGEST" --arg eval_inputs "$EVALUATION_INPUT_DIGEST" --arg eval_report "$EVALUATION_REPORT_DIGEST" --arg eval_decision "${EVALUATION_DECISION:-accepted}" \
  --arg approval_actor "$APPROVAL_ACTOR" --arg policy_digest "$POLICY_DIGEST" --arg approval_subject "$APPROVAL_SUBJECT_DIGEST" --arg approval_id "$APPROVAL_DECISION_ID" --arg approval_status "${APPROVAL_STATUS:-approved}" \
  --arg gitops_repo "$GITOPS_REPOSITORY" --arg gitops_commit "${GITOPS_COMMIT,,}" --arg argo_app "$ARGO_APPLICATION" \
  --arg kserve_revision "$KSERVE_REVISION" --arg signer "$signer_identity" --arg step_cert "$step_cert_digest" --arg cosign_key "$cosign_key_digest" \
  '{
    schema:"keplerops.release/v2", model_family:"release-risk", created_at:$created_at,
    source:{repository:$source_repo, commit:$source_commit, tree_digest:$source_tree},
    dataset:{repository:$data_repo, commit:$data_commit, manifest_digest:$data_manifest, split_digest:$data_split, label_schema_digest:$label_schema},
    training:{dag:$training_dag, run_id:$training_run, code_image_digest:$training_image, parameters_digest:$training_params, seed:$training_seed, runtime:$training_runtime, hardware_class:$training_hardware},
    model:{mlflow_run_id:$mlflow_run, mlflow_model_version:$mlflow_version, native_weights_digest:$native_weights, onnx_digest:$onnx, tokenizer_digest:$tokenizer, model_card_digest:$model_card, format:"onnx"},
    serving_image:{repository:$image_repo, image_digest:$image_digest, config_digest:$image_config, sbom_digest:$image_sbom, runtime:"onnxruntime-cpu"},
    evaluation:{suite_digest:$eval_suite, input_set_digest:$eval_inputs, report_digest:$eval_report, decision:$eval_decision},
    approval:{actor:$approval_actor, policy_digest:$policy_digest, subject_digest:$approval_subject, decision_id:$approval_id, status:$approval_status},
    signature:{signer_identity:$signer, step_certificate_digest:$step_cert, cosign_public_key_digest:$cosign_key, transparency_status:"not-published"},
    gitops:{repository:$gitops_repo, commit:$gitops_commit, argo_application:$argo_app},
    runtime:{kserve_revision:$kserve_revision, expected_model_digest:$onnx, expected_image_digest:$image_digest}
  }' >"$work/subject.json"

for stage in source dataset training model serving_image evaluation approval gitops; do
  digest=$(jq -cS --arg stage "$stage" '.[$stage]' "$work/subject.json" | sha256sum | awk '{print "sha256:"$1}')
  jq --arg stage "$stage" --arg digest "$digest" '.[$stage].digest = $digest' \
    "$work/subject.json" >"$work/subject.next"
  mv "$work/subject.next" "$work/subject.json"
done
jq -cS . "$work/subject.json" >"$work/subject.canonical.json"
release_id=$(sha256sum "$work/subject.canonical.json" | awk '{print $1}')
jq --arg release_id "sha256:$release_id" '.release_id = $release_id' \
  "$work/subject.json" | jq -S . >"$work/release.json"

opa_url=${OPA_URL:-http://127.0.0.1:18181}
if [[ -z ${OPA_URL:-} ]]; then
  kubectl -n orion-platform port-forward service/opa 18181:8181 >"$work/opa-port-forward.log" 2>&1 &
  opa_pid=$!
  for _ in $(seq 1 30); do
    curl -fsS "$opa_url/health" >/dev/null 2>&1 && break
    sleep 1
  done
fi
opa_response=$(curl -fsS -H 'Content-Type: application/json' \
  --data-binary "$(jq -c '{input:.}' "$work/release.json")" \
  "$opa_url/v1/data/keplerops/release/allow")
if [[ $(jq -r '.result // false' <<<"$opa_response") != true ]]; then
  echo "OPA denied release $release_id" >&2
  exit 6
fi

output_root=${RELEASE_OUTPUT_DIR:-$STATE_DIR/releases}
output="$output_root/$release_id"
install -d -m 0750 "$output"
install -m 0644 "$work/release.json" "$output/release.json"

jq -n --slurpfile predicate "$output/release.json" \
  --arg image_name "$SERVING_IMAGE_REPOSITORY" \
  --arg image_sha "${SERVING_IMAGE_DIGEST#sha256:}" \
  --arg model_sha "${ONNX_DIGEST#sha256:}" \
  '{
    _type:"https://in-toto.io/Statement/v1",
    subject:[
      {name:$image_name, digest:{sha256:$image_sha}},
      {name:"orion-release-risk.onnx", digest:{sha256:$model_sha}}
    ],
    predicateType:"https://keplerops.lab/attestations/release/v2",
    predicate:$predicate[0]
  }' | jq -S . >"$output/release.intoto.json"

export COSIGN_PASSWORD
COSIGN_PASSWORD=$(<"$SIGNING_DIR/cosign-password")
cosign sign-blob --yes --tlog-upload=false \
  --key "$SIGNING_DIR/cosign.key" \
  --bundle "$output/release.sigstore.json" \
  "$output/release.intoto.json" >/dev/null
cosign verify-blob --key "$SIGNING_DIR/cosign.pub" \
  --bundle "$output/release.sigstore.json" \
  "$output/release.intoto.json" >/dev/null
install -m 0644 "$SIGNING_DIR/cosign.pub" "$output/cosign.pub"
install -m 0644 "$SIGNING_DIR/step-signer.crt" "$output/step-signer.crt"
install -m 0644 "$SIGNING_DIR/identity.json" "$output/signer-identity.json"
install -m 0644 "$SIGNING_DIR/identity.sig" "$output/signer-identity.sig"

cat >"$output/gitops-image-patch.yaml" <<EOF
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: orion-release-risk
  namespace: orion-runtime
  annotations:
    keplerops.lab/release-id: sha256:$release_id
    keplerops.lab/model-digest: $ONNX_DIGEST
spec:
  predictor:
    containers:
      - name: kserve-container
        image: ${SERVING_IMAGE_REPOSITORY}@${SERVING_IMAGE_DIGEST}
EOF

(cd "$output" && sha256sum release.json release.intoto.json release.sigstore.json cosign.pub step-signer.crt signer-identity.json signer-identity.sig gitops-image-patch.yaml >SHA256SUMS)
echo "Release bundle: $output"
echo "Release ID: sha256:$release_id"
