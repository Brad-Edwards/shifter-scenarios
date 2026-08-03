#!/usr/bin/env bash
set -Eeuo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck source=../versions.env
source "$ROOT/versions.env"

if [[ $EUID -ne 0 ]]; then
  echo "install-knative.sh must run as root on k3s01" >&2
  exit 2
fi

export KUBECONFIG=${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}

kubectl apply -f \
  "https://github.com/knative/serving/releases/download/knative-v${KNATIVE_VERSION}/serving-crds.yaml"
kubectl wait --for=condition=Established --all customresourcedefinitions --timeout=5m
kubectl apply -f \
  "https://github.com/knative/serving/releases/download/knative-v${KNATIVE_VERSION}/serving-core.yaml"
kubectl apply -f \
  "https://github.com/knative-extensions/net-kourier/releases/download/knative-v${KOURIER_VERSION}/kourier.yaml"

kubectl -n knative-serving patch configmap config-network --type merge \
  -p '{"data":{"ingress-class":"kourier.ingress.networking.knative.dev"}}' >/dev/null
kubectl -n knative-serving patch configmap config-domain --type merge \
  -p '{"data":{"cinder.lab":""}}' >/dev/null
kubectl -n kourier-system patch service kourier --type json -p '[
  {"op":"replace","path":"/spec/type","value":"NodePort"},
  {"op":"add","path":"/spec/ports/0/nodePort","value":31080},
  {"op":"add","path":"/spec/ports/1/nodePort","value":31443}
]' >/dev/null

kubectl -n knative-serving rollout status deployment/controller --timeout=5m
kubectl -n knative-serving rollout status deployment/autoscaler --timeout=5m
kubectl -n knative-serving rollout status deployment/webhook --timeout=5m
kubectl -n kourier-system rollout status deployment/3scale-kourier-gateway --timeout=5m
