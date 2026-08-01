#!/usr/bin/env bash
set -Eeuo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck source=../versions.env
source "$ROOT/versions.env"
ONLINE=0
BUILD_IMAGES=0
for option in "$@"; do
  case "$option" in
    --online) ONLINE=1 ;;
    --build-images) BUILD_IMAGES=1 ;;
    *) echo "Unknown option: $option" >&2; exit 2 ;;
  esac
done

for command in bash jq python3 yq; do
  command -v "$command" >/dev/null || { echo "Missing validator: $command" >&2; exit 3; }
done

while IFS= read -r script; do
  bash -n "$script"
done < <(find "$ROOT/scripts" -type f -name '*.sh' -print | sort)
echo "PASS shell syntax"

if command -v shellcheck >/dev/null 2>&1; then
  shellcheck -x --source-path=SCRIPTDIR "$ROOT"/scripts/*.sh
  echo "PASS shellcheck"
else
  echo "SKIP shellcheck (not installed)"
fi

while IFS= read -r yaml; do
  yq eval-all '.' "$yaml" >/dev/null
done < <(find "$ROOT" -type f \( -name '*.yaml' -o -name '*.yml' \) -print | sort)
echo "PASS YAML parse"

kubectl kustomize "$ROOT/gitops/orion-canary" >/dev/null
echo "PASS Kustomize render"

if command -v kubeconform >/dev/null 2>&1; then
  kubeconform -strict -ignore-missing-schemas \
    "$ROOT"/manifests/*.yaml "$ROOT"/argocd/*.yaml \
    <(kubectl kustomize "$ROOT/gitops/orion-canary")
  echo "PASS Kubernetes schema validation"
else
  echo "SKIP kubeconform (not installed)"
fi

python3 - "$ROOT" <<'PY'
import ast
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
for path in sorted(root.glob("images/**/*.py")):
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
print("PASS Python syntax")
PY

embedded_policy=$(yq -r \
  'select(.kind == "ConfigMap" and .metadata.name == "release-policy") | .data."release.rego"' \
  "$ROOT/manifests/opa.yaml")
[[ $(<"$ROOT/policies/release.rego") == "$embedded_policy" ]]
echo "PASS OPA policy source matches ConfigMap"

grep -Fq "image: $OPA_IMAGE" "$ROOT/manifests/opa.yaml"
grep -Fq "image: $LITELLM_IMAGE" "$ROOT/manifests/litellm.yaml"
grep -Fq "image: $ORION_PLACEHOLDER_IMAGE" "$ROOT/gitops/orion-canary/inferenceservice.yaml"
grep -Fq "image: $ORION_AGENT_IMAGE" "$ROOT/manifests/orion-agent.yaml"
grep -Fq "image: $REQUEST_BASKETS_IMAGE" "$ROOT/manifests/cinder-relay.yaml"
grep -Fq "FROM $PYTHON_BASE_IMAGE" "$ROOT/images/orion-placeholder/Dockerfile"
grep -Fq "FROM $PYTHON_BASE_IMAGE" "$ROOT/images/orion-agent/Dockerfile"
echo "PASS version-lock references"

if (( ONLINE )); then
  command -v helm >/dev/null || { echo "Missing validator: helm" >&2; exit 3; }
  tmp=$(mktemp -d)
  trap 'rm -rf "$tmp"' EXIT
  helm template argocd argo-cd --repo https://argoproj.github.io/argo-helm \
    --version "$ARGOCD_CHART_VERSION" --namespace argocd \
    --values "$ROOT/helm/argocd-values.yaml" >"$tmp/argocd.yaml"
  helm template cert-manager cert-manager --repo https://charts.jetstack.io \
    --version "$CERT_MANAGER_CHART_VERSION" --namespace cert-manager \
    --values "$ROOT/helm/cert-manager-values.yaml" >"$tmp/cert-manager.yaml"
  helm template kserve-crd oci://ghcr.io/kserve/charts/kserve-crd \
    --version "$KSERVE_CHART_VERSION" --namespace kserve >"$tmp/kserve-crd.yaml"
  helm template kserve oci://ghcr.io/kserve/charts/kserve \
    --version "$KSERVE_CHART_VERSION" --namespace kserve \
    --values "$ROOT/helm/kserve-values.yaml" >"$tmp/kserve.yaml"
  yq eval-all '.' "$tmp"/*.yaml >/dev/null
  echo "PASS pinned Helm chart render"

  if command -v docker >/dev/null 2>&1; then
    docker run --rm -v "$ROOT/policies:/policies:ro" "$OPA_IMAGE" \
      check --strict /policies/release.rego
    echo "PASS OPA policy check"
  fi
fi

if (( BUILD_IMAGES )); then
  command -v docker >/dev/null || { echo "Missing validator: docker" >&2; exit 3; }
  docker build -t "$ORION_PLACEHOLDER_IMAGE" "$ROOT/images/orion-placeholder"
  docker build -t "$ORION_AGENT_IMAGE" "$ROOT/images/orion-agent"
  docker run --rm "$ORION_PLACEHOLDER_IMAGE" \
    python -c 'import onnx; onnx.checker.check_model(onnx.load("/models/orion-placeholder.onnx"))'
  docker run --rm "$ORION_AGENT_IMAGE" \
    python -c 'import agent_service, mcp_service; assert agent_service.graph; assert mcp_service.mcp'
  container=$(docker run --rm -d -p 127.0.0.1::8080 "$ORION_PLACEHOLDER_IMAGE")
  trap 'docker rm -f "$container" >/dev/null 2>&1 || true' EXIT
  port=$(docker port "$container" 8080/tcp | awk -F: '{print $NF}')
  for _ in $(seq 1 20); do
    curl -fsS "http://127.0.0.1:$port/health/ready" >/dev/null 2>&1 && break
    sleep 1
  done
  prediction=$(curl -fsS -H 'Content-Type: application/json' \
    --data '{"instances":[[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]]}' \
    "http://127.0.0.1:$port/v1/models/orion-release-risk:predict")
  [[ $(jq '.predictions[0].probabilities | length' <<<"$prediction") == 8 ]]
  docker rm -f "$container" >/dev/null
  trap - EXIT
  echo "PASS local image builds, imports, and ONNX HTTP prediction"
fi

echo "Platform bundle validation passed"
