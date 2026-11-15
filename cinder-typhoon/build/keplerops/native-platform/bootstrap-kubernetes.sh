#!/usr/bin/env bash
set -euo pipefail
umask 077
ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
operator=${KEPLEROPS_OPERATOR_DIR:-./.operator}
docker compose up -d --no-deps --wait --wait-timeout 300 fieldlink-k3s
docker compose exec -T fieldlink-k3s /bin/kubectl wait --for=condition=Ready --timeout=120s node/fieldlink-k3s
docker compose exec -T fieldlink-k3s /bin/kubectl wait --for=condition=DiskPressure=False --timeout=360s node/fieldlink-k3s
client_image=docker.io/rancher/k3s:v1.37.2-k3s1
client_archive="$operator/native-platform/k3s-images/fieldlink-client.tar"
if [[ ! -s $client_archive ]]; then
  docker image save rancher/k3s:v1.37.2-k3s1 --output "$client_archive.part"
  mv "$client_archive.part" "$client_archive"
fi
if ! docker compose exec -T fieldlink-k3s /bin/crictl inspecti "$client_image" >/dev/null 2>&1; then
  # K3s watches this directory and owns native import/CRI pinning. Refresh an
  # existing archive's timestamp if an earlier cache was removed.
  touch "$client_archive"
  for ((attempt=0; attempt<60; attempt++)); do
    if docker compose exec -T fieldlink-k3s /bin/crictl inspecti "$client_image" >/dev/null 2>&1; then
      break
    fi
    sleep 2
  done
fi
docker compose exec -T fieldlink-k3s /bin/crictl inspecti "$client_image" >/dev/null
docker compose exec -T fieldlink-k3s /bin/kubectl apply -f - <native-platform/namespace.yaml
profile="$operator/native-platform/kubernetes/rowan.yaml"
identity="$operator/native-platform/kubernetes/cluster-identity"
current=$(docker compose exec -T fieldlink-k3s cat /var/lib/rancher/k3s/server/tls/server-ca.crt | sha256sum | cut -d ' ' -f1)
previous=$(cat "$identity" 2>/dev/null || true)
if [[ ! -e $profile || $previous != "$current" ]]; then
  token=$(docker compose exec -T fieldlink-k3s /bin/kubectl create token rowan-workspace --namespace fieldlink --duration=720h)
  ca=$(docker compose exec -T fieldlink-k3s cat /var/lib/rancher/k3s/server/tls/server-ca.crt | base64 -w0)
  temporary=$(mktemp "$profile.XXXXXX")
  trap 'rm -f -- "$temporary"' EXIT
  cat >"$temporary" <<YAML
apiVersion: v1
kind: Config
clusters:
  - name: fieldlink
    cluster:
      server: https://cloud-api.keplerops.test:6443
      certificate-authority-data: $ca
users:
  - name: rowan-workspace
    user:
      token: $token
contexts:
  - name: fieldlink
    context:
      cluster: fieldlink
      user: rowan-workspace
      namespace: fieldlink
current-context: fieldlink
YAML
  mv "$temporary" "$profile"
  printf '%s\n' "$current" >"$identity"
fi
echo 'Native namespace and scoped workspace configuration ready.'
