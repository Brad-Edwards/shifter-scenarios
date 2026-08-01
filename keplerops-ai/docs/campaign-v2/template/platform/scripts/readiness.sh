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

kubectl -n orion-runtime wait --for=condition=Ready \
  inferenceservice/orion-release-risk --timeout=5m >/dev/null
model_service=$(kubectl -n orion-runtime get service \
  -l serving.kserve.io/inferenceservice=orion-release-risk \
  -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
if [[ -z $model_service ]] && kubectl -n orion-runtime get service orion-release-risk-predictor >/dev/null 2>&1; then
  model_service=orion-release-risk-predictor
fi
[[ -n $model_service ]] || fail "KServe predictor service discovery"
start_forward orion-runtime "service/$model_service" 18082 80
prediction=$(curl -fsS -H 'Content-Type: application/json' \
  --data '{"instances":[[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]]}' \
  http://127.0.0.1:18082/v1/models/orion-release-risk:predict)
[[ $(jq '.predictions[0].probabilities | length' <<<"$prediction") == 8 ]] || \
  fail "neutral ONNX prediction response"
pass "KServe neutral ONNX prediction path"

if [[ ${SKIP_SIGNING:-0} != 1 ]]; then
  for file in identity.json identity.sig cosign.key cosign.pub cosign-password step-signer.crt; do
    [[ -s $SIGNING_DIR/$file ]] || fail "signing material $file"
  done
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
  assistant_url=$(kubectl -n orion-platform get secret litellm-runtime \
    -o jsonpath='{.data.ORION_ASSISTANT_BASE_URL}' | base64 -d)
  [[ $assistant_url != http://127.0.0.1:9/v1 ]] || \
    fail "assistant endpoint is not configured"
  completion=$(curl -fsS -H 'Content-Type: application/json' \
    --data '{"prompt":"Reply with the single word ready."}' \
    http://127.0.0.1:18080/v1/chat)
  [[ -n $(jq -r '.response // empty' <<<"$completion") ]] || fail "assistant completion"
  pass "admitted assistant completion through LangGraph and LiteLLM"

  kubectl -n argocd get application orion-canary >/dev/null 2>&1 || \
    fail "Argo Application is not configured"
  revision=$(kubectl -n argocd get application orion-canary -o jsonpath='{.spec.source.targetRevision}')
  [[ $revision =~ ^[a-fA-F0-9]{40}([a-fA-F0-9]{24})?$ ]] || \
    fail "Argo targetRevision is not immutable"
  kubectl -n argocd wait --for=jsonpath='{.status.sync.status}'=Synced \
    application/orion-canary --timeout=5m >/dev/null
  kubectl -n argocd wait --for=jsonpath='{.status.health.status}'=Healthy \
    application/orion-canary --timeout=5m >/dev/null
  pass "Argo Application synced and healthy at immutable revision"
  install -d -m 0750 "$STATE_DIR"
  date -u +%Y-%m-%dT%H:%M:%SZ >"$STATE_DIR/ready"
else
  install -d -m 0750 "$STATE_DIR"
  date -u +%Y-%m-%dT%H:%M:%SZ >"$STATE_DIR/core-ready"
fi

echo "KeplerOps platform readiness ($MODE) passed"
