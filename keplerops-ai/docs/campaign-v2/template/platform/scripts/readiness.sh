#!/usr/bin/env bash
set -Eeuo pipefail

STATE_DIR=${PLATFORM_STATE_DIR:-/var/lib/keplerops-platform}
SIGNING_DIR=${PLATFORM_SIGNING_DIR:-$STATE_DIR/signing}
export KUBECONFIG=${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}
MODE=full
[[ ${1:-} != --core ]] || MODE=core

forward_pids=()
tmp=$(mktemp -d)
cleanup() {
  local pid
  for pid in "${forward_pids[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
  rm -rf "$tmp"
}
trap cleanup EXIT

pass() { printf 'PASS  %s\n' "$*"; }
fail() { printf 'FAIL  %s\n' "$*" >&2; exit 1; }

start_forward() {
  local namespace=$1 resource=$2 local_port=$3 remote_port=$4
  kubectl -n "$namespace" port-forward "$resource" "$local_port:$remote_port" \
    >"$tmp/port-forward-${local_port}.log" 2>&1 &
  forward_pids+=("$!")
  for _ in $(seq 1 30); do
    if timeout 1 bash -c "</dev/tcp/127.0.0.1/$local_port" 2>/dev/null; then
      return
    fi
    sleep 1
  done
  cat "$tmp/port-forward-${local_port}.log" >&2
  fail "port-forward for $resource"
}

kubectl wait --for=condition=Ready node/k3s01 --timeout=60s >/dev/null
pass "k3s01 node Ready"

kubectl -n cert-manager rollout status deployment/cert-manager --timeout=3m >/dev/null
kubectl -n cert-manager rollout status deployment/cert-manager-webhook --timeout=3m >/dev/null
kubectl -n cert-manager rollout status deployment/cert-manager-cainjector --timeout=3m >/dev/null
pass "cert-manager deployments available"

kubectl -n kserve rollout status deployment/kserve-controller-manager --timeout=3m >/dev/null
kubectl wait --for=condition=Established \
  customresourcedefinition/inferenceservices.serving.kserve.io --timeout=60s >/dev/null
pass "KServe controller and CRD ready"

kubectl -n argocd rollout status statefulset/argocd-application-controller --timeout=3m >/dev/null
kubectl -n argocd rollout status deployment/argocd-repo-server --timeout=3m >/dev/null
kubectl -n argocd rollout status deployment/argocd-server --timeout=3m >/dev/null
pass "Argo CD control plane available"

kubectl -n knative-serving rollout status deployment/controller --timeout=3m >/dev/null
kubectl -n knative-serving rollout status deployment/autoscaler --timeout=3m >/dev/null
kubectl -n knative-serving rollout status deployment/webhook --timeout=3m >/dev/null
kubectl -n kourier-system rollout status deployment/3scale-kourier-gateway --timeout=3m >/dev/null
kubectl -n cinder wait --for=condition=Ready kservice/relay --timeout=5m >/dev/null
curl -fsS -H 'Host: relay.cinder.cinder.lab' http://127.0.0.1:31080/ >/dev/null
pass "Knative and Cinder request relay available"

for deployment in opa vertex-openai-proxy litellm orion-agent orion-mcp; do
  kubectl -n orion-platform rollout status "deployment/$deployment" --timeout=5m >/dev/null
done
pass "OPA, LiteLLM, LangGraph, and MCP deployments available"
kubectl -n orion-runtime rollout status deployment/orion-vision --timeout=5m >/dev/null
pass "Orion Vision prototype deployment available"

start_forward orion-platform service/opa 18181 8181
curl -fsS http://127.0.0.1:18181/health >/dev/null
deny=$(curl -fsS -H 'Content-Type: application/json' \
  --data '{"input":{"schema":"keplerops.release/v2"}}' \
  http://127.0.0.1:18181/v1/data/keplerops/release/allow | jq -r '.result // false')
[[ $deny == false ]] || fail "OPA rejected incomplete release input"
digest="sha256:$(printf '0%.0s' {1..64})"
allow_input=$(jq -cn --arg digest "$digest" '{input:{
  schema:"keplerops.release/v2", source:{digest:$digest}, dataset:{digest:$digest},
  training:{digest:$digest}, model:{digest:$digest,format:"onnx"},
  serving_image:{digest:$digest,runtime:"onnxruntime-cpu"},
  evaluation:{digest:$digest,decision:"accepted"},
  approval:{digest:$digest,status:"approved"}, gitops:{digest:$digest}
}}')
allow=$(curl -fsS -H 'Content-Type: application/json' --data "$allow_input" \
  http://127.0.0.1:18181/v1/data/keplerops/release/allow | jq -r '.result // false')
[[ $allow == true ]] || fail "OPA accepted canonical release input"
pass "OPA deny and allow decisions"

start_forward orion-platform service/litellm 18400 4000
curl -fsS http://127.0.0.1:18400/health/liveliness >/dev/null
pass "LiteLLM process healthy"

start_forward orion-platform service/orion-agent 18080 8080
curl -fsS http://127.0.0.1:18080/health/ready >/dev/null
pass "LangGraph service ready through LiteLLM"

start_forward orion-platform service/orion-mcp 18081 8081
mcp_code=""
for _ in $(seq 1 10); do
  mcp_code=$(curl -sS --max-time 8 -o "$tmp/mcp-response" -w '%{http_code}' \
    -H 'Content-Type: application/json' \
    -H 'Accept: application/json, text/event-stream' \
    --data '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"readiness","version":"1"}}}' \
    http://127.0.0.1:18081/mcp 2>/dev/null || true)
  [[ $mcp_code == 200 ]] && break
  sleep 1
done
[[ $mcp_code == 200 ]] || fail "MCP streamable HTTP initialize (HTTP ${mcp_code:-none})"
pass "MCP streamable HTTP initialize"

start_forward orion-runtime service/orion-vision 18084 8080
vision_ready=$(curl -fsS http://127.0.0.1:18084/health/ready)
vision_model=$(curl -fsS http://127.0.0.1:18084/v1/models/orion-vision-prototype)
[[ $(jq -r '.model // empty' <<<"$vision_ready") == orion-vision-prototype ]] || \
  fail "Orion Vision readiness model identity"
[[ $(jq '.output_shape[-1]' <<<"$vision_model") == 4 ]] || \
  fail "Orion Vision four-class confidence-vector contract"
pass "Orion Vision fixed confidence-vector interface"

if [[ ${SKIP_SIGNING:-0} != 1 ]]; then
  for file in identity.json identity.sig cosign.key cosign.pub cosign-password step-signer.crt package-signing.key package-signing.pub; do
    [[ -s $SIGNING_DIR/$file ]] || fail "signing material $file"
  done
  package_key_digest="sha256:$(sha256sum "$SIGNING_DIR/package-signing.pub" | awk '{print $1}')"
  [[ $(jq -er '.model_package_public_key_digest' "$SIGNING_DIR/identity.json") == "$package_key_digest" ]] || \
    fail "model-package signer identity binding"
  openssl pkey -in "$SIGNING_DIR/package-signing.key" -pubout 2>/dev/null | \
    cmp -s - "$SIGNING_DIR/package-signing.pub" || fail "model-package signing key pair"
  pass "model-package signing identity"
  openssl x509 -checkend 3600 -noout -in "$SIGNING_DIR/step-signer.crt" || \
    fail "step-ca signer certificate validity"
  openssl dgst -sha256 \
    -verify <(openssl x509 -in "$SIGNING_DIR/step-signer.crt" -pubkey -noout) \
    -signature "$SIGNING_DIR/identity.sig" "$SIGNING_DIR/identity.json" >/dev/null || \
    fail "step-ca signer binding for cosign public key"
  printf 'keplerops-signing-readiness\n' >"$tmp/signing-input"
  export COSIGN_PASSWORD
  COSIGN_PASSWORD=$(<"$SIGNING_DIR/cosign-password")
  cosign sign-blob --yes --tlog-upload=false --key "$SIGNING_DIR/cosign.key" \
    --output-signature "$tmp/signing-input.sig" "$tmp/signing-input" >/dev/null
  cosign verify-blob --key "$SIGNING_DIR/cosign.pub" \
    --insecure-ignore-tlog=true \
    --signature "$tmp/signing-input.sig" "$tmp/signing-input" >/dev/null
  pass "step-ca identity and cosign local signature"
fi

if [[ $MODE == full ]]; then
  release_dir=$(readlink -f "$STATE_DIR/current-release" 2>/dev/null || true)
  assistant_dir=$(readlink -f "$STATE_DIR/current-assistant-release" 2>/dev/null || true)
  [[ $release_dir == "$STATE_DIR"/releases/* && -s $release_dir/release.json ]] || \
    fail "signed current release is unavailable"
  [[ $assistant_dir == "$STATE_DIR"/assistant-releases/* && -s $assistant_dir/assistant-runtime.json ]] || \
    fail "signed current assistant runtime is unavailable"
  (
    cd "$release_dir"
    sha256sum -c SHA256SUMS >/dev/null
    cosign verify-blob --insecure-ignore-tlog --key cosign.pub \
      --bundle release.sigstore.json release.intoto.json >/dev/null
  ) || fail "current release checksum or signature"
  (
    cd "$assistant_dir"
    sha256sum -c SHA256SUMS >/dev/null
    cosign verify-blob --insecure-ignore-tlog --key cosign.pub \
      --bundle assistant-runtime.sigstore.json assistant-runtime.intoto.json >/dev/null
  ) || fail "current assistant runtime checksum or signature"
  cp "$release_dir/release.json" "$tmp/release.json"
  cp "$assistant_dir/assistant-runtime.json" "$tmp/assistant-runtime.json"
  release_subject_digest="sha256:$(jq -cS 'del(.release_id)' "$tmp/release.json" | sha256sum | awk '{print $1}')"
  assistant_subject_digest="sha256:$(jq -cS 'del(.release_id)' "$tmp/assistant-runtime.json" | sha256sum | awk '{print $1}')"
  jq -e --arg subject "$release_subject_digest" '
    .schema == "keplerops.release/v2" and .model_family == "release-risk" and
    .release_id == $subject and .model.format == "onnx" and
    .evaluation.decision == "accepted" and .approval.status == "approved" and
    (.serving_image.repository | contains("placeholder") | not) and
    (.serving_image.image_digest | test("^sha256:[a-f0-9]{64}$")) and
    (.model.onnx_digest | test("^sha256:[a-f0-9]{64}$")) and
    .serving_image.image_digest != "sha256:" + ("0" * 64) and
    .model.onnx_digest != "sha256:" + ("0" * 64)
  ' "$tmp/release.json" >/dev/null || fail "current release immutable identity"
  jq -e --arg subject "$assistant_subject_digest" '
    .schema == "keplerops.assistant-runtime/v1" and .release_id == $subject and
    .model_identity.binding == "hosted-provider-model-identity" and
    .model_identity.provider == "google-vertex-ai" and
    .model_identity.routing_adapter == "openai" and
    .model_identity.model == "zai-org/glm-5-maas" and
    .model_identity.configured_model == "openai/zai-org/glm-5-maas" and
    (.model_identity.provider_scope.project | length) > 0 and
    (.model_identity.provider_scope.location | length) > 0
  ' "$tmp/assistant-runtime.json" >/dev/null || fail "admitted Vertex GLM 5.2 runtime identity"
  active_assistant_release=$(kubectl -n orion-platform get secret orion-agent-runtime \
    -o jsonpath='{.data.ORION_ASSISTANT_RELEASE_ID}' | base64 -d)
  active_assistant_model=$(kubectl -n orion-platform get secret orion-agent-runtime \
    -o jsonpath='{.data.ORION_ASSISTANT_MODEL_DIGEST}' | base64 -d)
  [[ $active_assistant_release == "$(jq -er .release_id "$tmp/assistant-runtime.json")" && \
     $active_assistant_model == "$(jq -er .model_identity.digest "$tmp/assistant-runtime.json")" ]] || \
    fail "active Orion assistant Secret is stale relative to the signed runtime"
  pass "signed current release and Vertex GLM 5.2 assistant identities"

  assistant_url=$(kubectl -n orion-platform get secret litellm-runtime \
    -o jsonpath='{.data.ORION_ASSISTANT_BASE_URL}' | base64 -d)
  [[ $assistant_url != http://127.0.0.1:9/v1 ]] || \
    fail "assistant endpoint is not configured"
  litellm_master_key=$(kubectl -n orion-platform get secret litellm-runtime \
    -o jsonpath='{.data.LITELLM_MASTER_KEY}' | base64 -d)
  completion=""
  for _ in $(seq 1 5); do
    if completion=$(curl -fsS \
      -H 'Content-Type: application/json' \
      -H "Authorization: Bearer $litellm_master_key" \
      --data '{"model":"orion-assistant","messages":[{"role":"user","content":"Reply with the single word ready."}],"max_tokens":64,"temperature":0}' \
      http://127.0.0.1:18400/v1/chat/completions); then
      break
    fi
    sleep 2
  done
  [[ -n $(jq -r '.choices[0].message.content // .choices[0].message.reasoning_content // empty' <<<"$completion") ]] || \
    fail "stateless assistant completion"
  pass "admitted stateless assistant completion through LiteLLM"

  kubectl -n argocd get application orion-canary -o json >"$tmp/argo.json" 2>/dev/null || \
    fail "Argo Application is not configured"
  revision=$(jq -er '.spec.source.targetRevision' "$tmp/argo.json")
  [[ $revision =~ ^[a-fA-F0-9]{40}([a-fA-F0-9]{24})?$ ]] || \
    fail "Argo targetRevision is not immutable"
  kubectl -n argocd wait --for=jsonpath='{.status.sync.status}'=Synced \
    application/orion-canary --timeout=5m >/dev/null
  kubectl -n argocd wait --for=jsonpath='{.status.health.status}'=Healthy \
    application/orion-canary --timeout=5m >/dev/null
  gitops_commit=$(jq -er '.gitops.commit' "$tmp/release.json")
  jq -e --arg commit "$gitops_commit" '
    .spec.source.targetRevision == $commit and .status.sync.revision == $commit and
    .status.sync.status == "Synced" and .status.health.status == "Healthy"
  ' "$tmp/argo.json" >/dev/null || fail "release-to-Argo immutable GitOps join"

  kubectl -n orion-runtime wait --for=condition=Ready \
    inferenceservice/orion-release-risk --timeout=5m >/dev/null
  kubectl -n orion-runtime get inferenceservice orion-release-risk -o json >"$tmp/runtime.json"
  kubectl -n orion-runtime get pods \
    -l serving.kserve.io/inferenceservice=orion-release-risk -o json >"$tmp/model-pods.json"
  release_revision=$(jq -er '.runtime.kserve_revision' "$tmp/release.json")
  model_digest=$(jq -er '.model.onnx_digest' "$tmp/release.json")
  evaluation_digest=$(jq -er '.evaluation.report_digest' "$tmp/release.json")
  serving_image=$(jq -er '.serving_image.repository + "@" + .serving_image.image_digest' "$tmp/release.json")
  jq -e --arg revision "$release_revision" --arg model "$model_digest" \
    --arg evaluation "$evaluation_digest" --arg image "$serving_image" '
    .metadata.annotations["keplerops.lab/release-revision"] == $revision and
    .metadata.annotations["keplerops.lab/model-digest"] == $model and
    .metadata.annotations["keplerops.lab/evaluation-digest"] == $evaluation and
    .spec.predictor.containers[0].image == $image and
    (.spec.predictor.containers[0].image | contains("placeholder") | not) and
    any(.status.conditions[]?; .type == "Ready" and .status == "True")
  ' "$tmp/runtime.json" >/dev/null || fail "release-to-KServe model/image/revision join"
  jq -e --arg digest "${serving_image#*@}" '
    (.items | length) > 0 and all(.items[];
      .status.phase == "Running" and
      any(.status.containerStatuses[]?;
        .name == "kserve-container" and .ready == true and
        (.imageID | contains($digest))))
  ' "$tmp/model-pods.json" >/dev/null || fail "KServe running image digest join"

  model_service=$(kubectl -n orion-runtime get service \
    -l serving.kserve.io/inferenceservice=orion-release-risk \
    -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
  if [[ -z $model_service ]] && kubectl -n orion-runtime get service orion-release-risk-predictor >/dev/null 2>&1; then
    model_service=orion-release-risk-predictor
  fi
  [[ -n $model_service ]] || fail "KServe predictor service discovery"
  start_forward orion-runtime "service/$model_service" 18082 80
  curl -fsS http://127.0.0.1:18082/v1/models/orion-release-risk >"$tmp/model-metadata.json"
  jq -e --slurpfile release "$tmp/release.json" '
    .ready == true and .model_family == "release-risk" and
    .runtime == "onnxruntime-cpu" and .class_count == 8 and
    .model_sha256 == ($release[0].model.onnx_digest | sub("^sha256:"; "")) and
    .tokenizer_sha256 == ($release[0].model.tokenizer_digest | sub("^sha256:"; "")) and
    .mlflow_run_id == $release[0].model.mlflow_run_id and
    .mlflow_model_version == $release[0].model.mlflow_model_version and
    .lakefs_commit == $release[0].dataset.commit
  ' "$tmp/model-metadata.json" >/dev/null || fail "live KServe model identity join"
  prediction=$(curl -fsS -H 'Content-Type: application/json' \
    --data '{"instances":[{"text":"Routine Orion release review with approved lineage and validation evidence."}]}' \
    http://127.0.0.1:18082/v1/models/orion-release-risk:predict)
  [[ $(jq -r '.model_sha256' <<<"$prediction") == "${model_digest#sha256:}" &&
     $(jq '.predictions[0].probabilities | length' <<<"$prediction") == 8 ]] || \
    fail "live KServe prediction model identity"
  pass "signed release, immutable GitOps, KServe revision, image, and live model joined"
  install -d -m 0750 "$STATE_DIR"
  date -u +%Y-%m-%dT%H:%M:%SZ >"$STATE_DIR/ready"
else
  install -d -m 0750 "$STATE_DIR"
  date -u +%Y-%m-%dT%H:%M:%SZ >"$STATE_DIR/core-ready"
fi

echo "KeplerOps platform readiness ($MODE) passed"
