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
  local master_key base_url api_key upstream_model
  install -d -m 0700 "$STATE_DIR"
  if [[ ! -s $STATE_DIR/litellm-master-key ]]; then
    umask 077
    printf 'sk-%s\n' "$(openssl rand -hex 32)" >"$STATE_DIR/litellm-master-key"
  fi
  master_key=$(<"$STATE_DIR/litellm-master-key")
  base_url=${ORION_ASSISTANT_BASE_URL:-$(existing_secret_value ORION_ASSISTANT_BASE_URL)}
  api_key=${ORION_ASSISTANT_API_KEY:-$(existing_secret_value ORION_ASSISTANT_API_KEY)}
  upstream_model=${ORION_ASSISTANT_UPSTREAM_MODEL:-$(existing_secret_value ORION_ASSISTANT_UPSTREAM_MODEL)}
  [[ $base_url != http://127.0.0.1:9/v1 ]] || base_url=""
  [[ $api_key != not-configured ]] || api_key=""
  [[ $upstream_model != hosted_vllm/Qwen/Qwen2.5-7B-Instruct ]] || upstream_model=""
  base_url=${base_url:-http://vertex-openai-proxy.orion-platform.svc:8082/v1}
  api_key=${api_key:-keplerops-internal-vertex-proxy}
  upstream_model=${upstream_model:-openai/zai-org/glm-5-maas}

  kubectl -n orion-platform create secret generic litellm-runtime \
    --from-literal=LITELLM_MASTER_KEY="$master_key" \
    --from-literal=ORION_ASSISTANT_BASE_URL="$base_url" \
    --from-literal=ORION_ASSISTANT_API_KEY="$api_key" \
    --from-literal=ORION_ASSISTANT_UPSTREAM_MODEL="$upstream_model" \
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

configure_litellm_secret
kubectl apply -f "$ROOT/manifests/opa.yaml"
kubectl apply -f "$ROOT/manifests/litellm.yaml"
kubectl apply -f "$ROOT/manifests/orion-agent.yaml"
kubectl apply -f "$ROOT/manifests/network-policies.yaml"

kubectl wait --for=condition=Established \
  customresourcedefinition/inferenceservices.serving.kserve.io --timeout=5m
kubectl apply -k "$ROOT/gitops/orion-canary"

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

"$ROOT/scripts/readiness.sh" --core
"$ROOT/scripts/capture-component-lock.sh"
