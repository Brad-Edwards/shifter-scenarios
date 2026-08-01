#!/usr/bin/env bash
set -Eeuo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck source=../versions.env
source "$ROOT/versions.env"
STATE_DIR=${PLATFORM_STATE_DIR:-/var/lib/keplerops-platform}
export KUBECONFIG=${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}

install -d -m 0750 "$STATE_DIR"
helm_releases=$(helm list --all-namespaces -o json | jq \
  '[.[] | select(.namespace == "argocd" or .namespace == "cert-manager" or .namespace == "kserve") | {name,namespace,chart,app_version,status}]')
runtime_images=$(kubectl get pods --all-namespaces -o json | jq '
  [.items[]
    | select(.metadata.namespace == "argocd" or
             .metadata.namespace == "cert-manager" or
             .metadata.namespace == "kserve" or
             .metadata.namespace == "orion-platform" or
             .metadata.namespace == "orion-runtime")
    | (.status.initContainerStatuses[]?, .status.containerStatuses[]?)
    | {image, image_id:.imageID}]
  | unique_by(.image, .image_id)
  | sort_by(.image)')

jq -n -S \
  --arg schema "keplerops.component-lock/v1" \
  --arg captured_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg platform_bundle "$PLATFORM_BUNDLE_VERSION" \
  --arg k3s "$(kubectl get node k3s01 -o jsonpath='{.status.nodeInfo.kubeletVersion}')" \
  --arg helm "$HELM_VERSION" \
  --argjson helm_releases "$helm_releases" \
  --argjson runtime_images "$runtime_images" \
  '{schema:$schema,captured_at:$captured_at,platform_bundle:$platform_bundle,
    kubernetes:$k3s,helm:$helm,helm_releases:$helm_releases,runtime_images:$runtime_images}' \
  >"$STATE_DIR/component-lock.yaml"
chmod 0644 "$STATE_DIR/component-lock.yaml"
echo "Component lock: $STATE_DIR/component-lock.yaml"
