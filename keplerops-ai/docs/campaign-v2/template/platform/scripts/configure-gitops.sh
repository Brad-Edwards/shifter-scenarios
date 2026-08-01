#!/usr/bin/env bash
set -Eeuo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
export KUBECONFIG=${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}
GITOPS_REPO_PATH=${GITOPS_REPO_PATH:-keplerops-ai/docs/campaign-v2/template/platform/gitops/orion-canary}

: "${GITOPS_REPO_URL:?Set GITOPS_REPO_URL to the Forgejo repository clone URL}"
: "${GITOPS_REVISION:?Set GITOPS_REVISION to an immutable Forgejo commit}"

if [[ ! $GITOPS_REVISION =~ ^[a-fA-F0-9]{40}([a-fA-F0-9]{24})?$ ]] && \
   [[ ${ALLOW_MUTABLE_GITOPS_REVISION:-0} != 1 ]]; then
  echo "GITOPS_REVISION must be a 40- or 64-hex immutable commit" >&2
  exit 2
fi

if [[ -n ${ARGO_REPO_USERNAME:-} || -n ${ARGO_REPO_TOKEN:-} ]]; then
  : "${ARGO_REPO_USERNAME:?Set both ARGO_REPO_USERNAME and ARGO_REPO_TOKEN}"
  : "${ARGO_REPO_TOKEN:?Set both ARGO_REPO_USERNAME and ARGO_REPO_TOKEN}"
  kubectl -n argocd create secret generic orion-forgejo-repository \
    --from-literal=type=git \
    --from-literal=url="$GITOPS_REPO_URL" \
    --from-literal=username="$ARGO_REPO_USERNAME" \
    --from-literal=password="$ARGO_REPO_TOKEN" \
    --dry-run=client -o yaml | \
    kubectl label --local -f - argocd.argoproj.io/secret-type=repository -o yaml | \
    kubectl apply -f - >/dev/null
fi

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
escape_sed() { printf '%s' "$1" | sed 's/[|&]/\\&/g'; }
repo=$(escape_sed "$GITOPS_REPO_URL")
revision=$(escape_sed "$GITOPS_REVISION")
path=$(escape_sed "$GITOPS_REPO_PATH")

sed "s|__REPO_URL__|$repo|g" "$ROOT/argocd/project.yaml" >"$tmp/project.yaml"
sed -e "s|__REPO_URL__|$repo|g" \
    -e "s|__REVISION__|$revision|g" \
    -e "s|__REPO_PATH__|$path|g" \
    "$ROOT/argocd/application.yaml" >"$tmp/application.yaml"

kubectl apply -f "$tmp/project.yaml"
kubectl apply -f "$tmp/application.yaml"
kubectl -n argocd annotate application/orion-canary \
  keplerops.lab/configured-revision="$GITOPS_REVISION" --overwrite >/dev/null

echo "Argo CD application configured at immutable revision $GITOPS_REVISION"
