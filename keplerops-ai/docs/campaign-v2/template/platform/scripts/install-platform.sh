#!/usr/bin/env bash
set -Eeuo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck source=../versions.env
source "$ROOT/versions.env"
STATE_DIR=${PLATFORM_STATE_DIR:-/var/lib/keplerops-platform}

if [[ $EUID -ne 0 ]]; then
  echo "install-platform.sh must run as root on k3s01" >&2
  exit 2
fi

export KUBECONFIG=${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}

install_packages() {
  DEBIAN_FRONTEND=noninteractive apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq ca-certificates curl jq openssl tar >/dev/null
}

install_helm() {
  local installed=""
  if command -v helm >/dev/null 2>&1; then
    installed=$(helm version --template '{{.Version}}' 2>/dev/null || true)
  fi
  [[ $installed == "$HELM_VERSION" ]] && return

  local tmp archive
  tmp=$(mktemp -d)
  archive="helm-${HELM_VERSION}-linux-amd64.tar.gz"
  trap 'rm -rf "$tmp"' RETURN
  curl -fsSLo "$tmp/$archive" "https://get.helm.sh/$archive"
  curl -fsSLo "$tmp/$archive.sha256sum" "https://get.helm.sh/$archive.sha256sum"
  (cd "$tmp" && sha256sum -c "$archive.sha256sum")
  tar -xzf "$tmp/$archive" -C "$tmp"
  install -m 0755 "$tmp/linux-amd64/helm" /usr/local/bin/helm
  rm -rf "$tmp"
  trap - RETURN
}

wait_for_cluster() {
  for _ in $(seq 1 60); do
    if kubectl get node k3s01 >/dev/null 2>&1; then
      kubectl wait --for=condition=Ready node/k3s01 --timeout=180s
      return
    fi
    sleep 5
  done
  echo "k3s01 did not become available" >&2
  exit 3
}

existing_secret_value() {
  local key=$1
  kubectl -n orion-platform get secret litellm-runtime \
    -o "jsonpath={.data.$key}" 2>/dev/null | base64 -d 2>/dev/null || true
}

configure_litellm_secret() {
  local master_key base_url api_key upstream_model vertex_project vertex_service_account
  local edge_key_registry internal_range_id
  install -d -m 0700 "$STATE_DIR"
  if [[ ! -s $STATE_DIR/litellm-master-key ]]; then
    umask 077
    printf 'sk-%s\n' "$(openssl rand -hex 32)" >"$STATE_DIR/litellm-master-key"
  fi
  master_key=$(<"$STATE_DIR/litellm-master-key")
  base_url=${ORION_ASSISTANT_BASE_URL:-$(existing_secret_value ORION_ASSISTANT_BASE_URL)}
  api_key=${ORION_ASSISTANT_API_KEY:-$(existing_secret_value ORION_ASSISTANT_API_KEY)}
  upstream_model=${ORION_ASSISTANT_UPSTREAM_MODEL:-$(existing_secret_value ORION_ASSISTANT_UPSTREAM_MODEL)}
  vertex_project=${VERTEX_PROJECT:-$(existing_secret_value VERTEX_PROJECT)}
  vertex_service_account=${VERTEX_SERVICE_ACCOUNT:-$(existing_secret_value VERTEX_SERVICE_ACCOUNT)}
  edge_key_registry=${VERTEX_EDGE_KEY_REGISTRY_JSON:-$(existing_secret_value VERTEX_EDGE_KEY_REGISTRY_JSON)}
  internal_range_id=${VERTEX_INTERNAL_RANGE_ID:-$(existing_secret_value VERTEX_INTERNAL_RANGE_ID)}
  [[ $base_url != http://127.0.0.1:9/v1 ]] || base_url=""
  [[ $api_key != not-configured ]] || api_key=""
  [[ $upstream_model != hosted_vllm/Qwen/Qwen2.5-7B-Instruct ]] || upstream_model=""
  base_url=${base_url:-http://vertex-openai-proxy.orion-platform.svc:8082/v1}
  api_key=${api_key:-keplerops-internal-vertex-proxy}
  upstream_model=${upstream_model:-openai/zai-org/glm-5-maas}
  [[ -n $vertex_project ]] || { echo 'VERTEX_PROJECT is required for the dedicated Vertex proxy identity' >&2; return 1; }
  [[ $vertex_service_account == *@*.gserviceaccount.com ]] || { echo 'VERTEX_SERVICE_ACCOUNT must name the attached workload identity' >&2; return 1; }
  [[ $api_key =~ ^sk-[0-9a-f]{64}$ ]] || { echo 'ORION_ASSISTANT_API_KEY is malformed' >&2; return 1; }
  [[ $internal_range_id =~ ^range-[0-9a-f-]{36}$ ]] || { echo 'VERTEX_INTERNAL_RANGE_ID is malformed' >&2; return 1; }
  jq -e '
    type == "object" and length >= 2 and
    all(to_entries[];
      (.key | test("^m06-[0-9a-f]{16}$")) and
      (.value.key | test("^[0-9a-f]{64}$")) and
      (.value.range_id | test("^range-[0-9a-f-]{36}$")) and
      (.value.subjects | type == "array" and length > 0) and
      (.value.credential_classes | sort == ["operator","service"]))
  ' <<<"$edge_key_registry" >/dev/null || { echo 'VERTEX_EDGE_KEY_REGISTRY_JSON is malformed' >&2; return 1; }

  kubectl -n orion-platform create secret generic litellm-runtime \
    --from-literal=LITELLM_MASTER_KEY="$master_key" \
    --from-literal=ORION_ASSISTANT_BASE_URL="$base_url" \
    --from-literal=ORION_ASSISTANT_API_KEY="$api_key" \
    --from-literal=ORION_ASSISTANT_UPSTREAM_MODEL="$upstream_model" \
    --from-literal=VERTEX_PROJECT="$vertex_project" \
    --from-literal=VERTEX_SERVICE_ACCOUNT="$vertex_service_account" \
    --from-literal=VERTEX_EDGE_KEY_REGISTRY_JSON="$edge_key_registry" \
    --from-literal=VERTEX_INTERNAL_RANGE_ID="$internal_range_id" \
    --dry-run=client -o yaml | kubectl apply -f - >/dev/null
}

existing_agent_secret_value() {
  local key=$1
  kubectl -n orion-platform get secret orion-agent-runtime \
    -o "jsonpath={.data.$key}" 2>/dev/null | base64 -d 2>/dev/null || true
}

configure_agent_secret() {
  local agent_api_key assistant_release_id assistant_model_digest
  agent_api_key=${ORION_AGENT_API_KEY:-$(existing_agent_secret_value AGENT_API_KEY)}
  agent_api_key=${agent_api_key:-KAI-Orion-Agent-Runtime-8f4c1a7d29e6b053}
  assistant_release_id=${ORION_ASSISTANT_RELEASE_ID:-$(existing_agent_secret_value ORION_ASSISTANT_RELEASE_ID)}
  assistant_model_digest=${ORION_ASSISTANT_MODEL_DIGEST:-$(existing_agent_secret_value ORION_ASSISTANT_MODEL_DIGEST)}
  assistant_release_id=${assistant_release_id:-sha256:$(printf unresolved-assistant-release | sha256sum | awk '{print $1}')}
  assistant_model_digest=${assistant_model_digest:-sha256:$(printf unresolved-assistant-model | sha256sum | awk '{print $1}')}

  kubectl -n orion-platform create secret generic orion-agent-runtime \
    --from-literal=AGENT_API_KEY="$agent_api_key" \
    --from-literal=ORION_ASSISTANT_RELEASE_ID="$assistant_release_id" \
    --from-literal=ORION_ASSISTANT_MODEL_DIGEST="$assistant_model_digest" \
    --from-literal=QDRANT_URL="http://192.168.78.1:16333" \
    --from-literal=QDRANT_API_KEY="KeplerV2-Training-Qdrant-Read" \
    --from-literal=QDRANT_COLLECTIONS="orion_partner_intake" \
    --from-literal=REDIS_URL="redis://:KeplerV2-Training-Redis@192.168.78.1:16379/0" \
    --from-literal=OPA_URL="http://opa.orion-platform.svc:8181" \
    --from-literal=OPA_DECISION_PATH="/v1/data/keplerops/workhub/tool/allow" \
    --from-literal=MCP_URL="http://orion-mcp.orion-platform.svc:8081/mcp" \
    --dry-run=client -o yaml | kubectl apply -f - >/dev/null
}

install_packages
install_helm
wait_for_cluster

kubectl apply -f "$ROOT/manifests/namespaces.yaml"

helm upgrade --install cert-manager cert-manager \
  --repo https://charts.jetstack.io \
  --version "$CERT_MANAGER_CHART_VERSION" \
  --namespace cert-manager --create-namespace \
  --values "$ROOT/helm/cert-manager-values.yaml" \
  --wait --timeout 10m

helm upgrade --install kserve-crd \
  oci://ghcr.io/kserve/charts/kserve-crd \
  --version "$KSERVE_CHART_VERSION" \
  --namespace kserve --create-namespace \
  --wait --timeout 10m

helm upgrade --install kserve \
  oci://ghcr.io/kserve/charts/kserve \
  --version "$KSERVE_CHART_VERSION" \
  --namespace kserve \
  --values "$ROOT/helm/kserve-values.yaml" \
  --wait --timeout 10m

ingress_config=$(kubectl -n kserve get configmap inferenceservice-config \
  -o jsonpath='{.data.ingress}' 2>/dev/null || printf '{}')
[[ -n $ingress_config ]] || ingress_config='{}'
ingress_config=$(jq -c '.disableIngressCreation = true' <<<"$ingress_config")
kubectl -n kserve patch configmap inferenceservice-config --type merge \
  -p "$(jq -cn --arg value "$ingress_config" '{data:{ingress:$value}}')" >/dev/null
kubectl -n kserve rollout restart deployment/kserve-controller-manager >/dev/null
kubectl -n kserve rollout status deployment/kserve-controller-manager --timeout=5m

helm upgrade --install argocd argo-cd \
  --repo https://argoproj.github.io/argo-helm \
  --version "$ARGOCD_CHART_VERSION" \
  --namespace argocd --create-namespace \
  --values "$ROOT/helm/argocd-values.yaml" \
  --wait --timeout 10m

"$ROOT/scripts/install-knative.sh"
configure_litellm_secret
configure_agent_secret
kubectl apply -f "$ROOT/manifests/cinder-relay.yaml"
kubectl apply -f "$ROOT/manifests/opa.yaml"
kubectl apply -f "$ROOT/manifests/litellm.yaml"
kubectl apply -f "$ROOT/manifests/orion-agent.yaml"
kubectl apply -f "$ROOT/manifests/orion-vision.yaml"
kubectl apply -f "$ROOT/manifests/network-policies.yaml"

kubectl wait --for=condition=Established \
  customresourcedefinition/inferenceservices.serving.kserve.io --timeout=5m
if [[ ${SKIP_SIGNING:-0} != 1 && -x $ROOT/scripts/bootstrap-signing.sh ]]; then
  "$ROOT/scripts/bootstrap-signing.sh"
fi

kubectl -n orion-platform rollout restart \
  deployment/vertex-openai-proxy deployment/litellm deployment/orion-agent deployment/orion-mcp >/dev/null
kubectl -n orion-platform rollout status deployment/opa --timeout=5m
kubectl -n orion-platform rollout status deployment/vertex-openai-proxy --timeout=5m
kubectl -n orion-platform rollout status deployment/litellm --timeout=10m
kubectl -n orion-platform rollout status deployment/orion-agent --timeout=5m
kubectl -n orion-platform rollout status deployment/orion-mcp --timeout=5m
kubectl -n orion-runtime rollout status deployment/orion-vision --timeout=5m

"$ROOT/scripts/readiness.sh" --core
"$ROOT/scripts/capture-component-lock.sh"
