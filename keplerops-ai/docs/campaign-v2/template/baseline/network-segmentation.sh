#!/usr/bin/env bash
set -Eeuo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
POLICY=${COMPOSE_NETWORK_POLICY:-$ROOT/network/apply-compose-policy.sh}
PROBE=keplerops-network-probe
K3S_TARGET=${K3S01_SSH_TARGET:-kepler@192.168.78.30}
K3S_KEY=${K3S01_SSH_KEY:-/root/.ssh/keplerops-v2}
SSH=(ssh -i "$K3S_KEY" -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null)

pass() { printf 'PASS  %s\n' "$*"; }
fail() { printf 'FAIL  %s\n' "$*" >&2; exit 1; }

for command in docker iptables jq nsenter ssh sysctl timeout; do
  command -v "$command" >/dev/null 2>&1 || fail "required command $command"
done
[[ $EUID -eq 0 ]] || fail "network segmentation baseline requires root"
[[ -r $K3S_KEY ]] || fail "k3s SSH key is not readable: $K3S_KEY"

container_pid() {
  local container=$1
  docker inspect "$container" --format '{{.State.Pid}}' 2>/dev/null
}

target_ip() {
  local source=$1 destination=$2 source_networks destination_networks
  source_networks=$(docker inspect "$source" --format '{{json .NetworkSettings.Networks}}')
  destination_networks=$(docker inspect "$destination" --format '{{json .NetworkSettings.Networks}}')
  jq -nr --argjson source "$source_networks" --argjson destination "$destination_networks" '
    first(
      $source | to_entries[] |
      select(.key | startswith("kep-v2-")) |
      .key as $network |
      $destination[$network].IPAddress? |
      select(length > 0)
    ) // first(
      $destination | to_entries[] |
      select(.key | startswith("kep-v2-")) |
      .value.IPAddress |
      select(length > 0)
    )
  '
}

connects() {
  local source=$1 destination=$2 port=$3 pid address
  pid=$(container_pid "$source")
  [[ $pid =~ ^[1-9][0-9]*$ ]] || fail "source container is not running: $source"
  address=$(target_ip "$source" "$destination")
  [[ -n $address ]] || fail "destination has no managed address: $destination"
  # Expansion is intentionally performed by the shell inside the source netns.
  # shellcheck disable=SC2016
  nsenter --target "$pid" --net timeout 3 bash -c \
    'exec 3<>"/dev/tcp/$1/$2"' _ "$address" "$port" >/dev/null 2>&1
}

expect_allowed() {
  connects "$1" "$2" "$3" || fail "declared flow $1 -> $2:$3"
  pass "declared flow $1 -> $2:$3"
}

expect_denied() {
  if connects "$1" "$2" "$3"; then
    fail "adjacent undeclared flow was reachable: $1 -> $2:$3"
  fi
  pass "adjacent flow denied $1 -> $2:$3"
}

[[ $(sysctl -n net.bridge.bridge-nf-call-iptables) == 1 ]] || \
  fail "br_netfilter is not enforcing bridged IPv4 traffic"
"$POLICY" status >/dev/null || fail "Compose network policy is not installed"
iptables -w -S KEP-V2-SEGMENT | grep -q 'deny-undeclared-lateral' || \
  fail "Compose lateral default deny is absent"
iptables -w -S KEP-V2-SEGMENT | grep -q 'deny-undeclared-egress' || \
  fail "Compose egress default deny is absent"
iptables -w -S KEP-V2-SEGMENT | grep -q -- \
  '-s 192\.168\.78\.0/24 .*deny-undeclared-guest-ingress' || \
  fail "nested guest subnet default deny is absent"
pass "Compose default-deny chains installed"

expect_allowed kep-v2-caddy kep-v2-public-site 80
expect_allowed kep-v2-keycloak kep-v2-postgres 5432
expect_allowed kep-v2-roundcube kep-v2-stalwart 143
expect_allowed kep-v2-business-adapter kep-v2-business-opa 8181
expect_allowed kep-v2-airflow-worker kep-v2-rabbitmq 5672
expect_allowed kep-v2-hayhooks kep-v2-tika 9998

expect_denied kep-v2-public-site kep-v2-postgres 5432
expect_denied kep-v2-forgejo kep-v2-redis 6379
expect_denied kep-v2-redmine kep-v2-qdrant-edge 6333
expect_denied kep-v2-business-opa kep-v2-ghost 2368
expect_allowed kep-v2-grafana kep-v2-jaeger 16686
expect_allowed kep-v2-grafana kep-v2-opensearch 9200
expect_denied kep-v2-preview kep-v2-forgejo 3000

for guest in 192.168.78.20 192.168.78.21; do
  "${SSH[@]}" "kepler@$guest" bash -s <<'WORKER_GUEST_PROOF'
set -Eeuo pipefail

host_connect() {
  # Expansion is intentionally performed by the remote guest shell.
  # shellcheck disable=SC2016
  timeout 3 bash -c 'exec 3<>"/dev/tcp/$1/$2"' _ "$1" "$2" >/dev/null 2>&1
}

host_connect 192.168.78.1 15673
host_connect 192.168.78.1 13000
host_connect 10.61.80.10 4318
! host_connect 192.168.78.1 15672
! host_connect 192.168.78.1 15674
! host_connect 192.168.78.1 12999
! host_connect 192.168.78.1 13001
! host_connect 192.168.78.1 16333
! host_connect 192.168.78.1 16379
! host_connect 10.61.50.12 5672
! host_connect 10.61.50.41 3000
! host_connect 10.61.80.10 4317
WORKER_GUEST_PROOF
done
pass "review workers restricted to RabbitMQ, WorkHub, and OTLP publications"

"${SSH[@]}" "$K3S_TARGET" sudo bash -s -- "$PROBE" <<'KUBERNETES_PROOF'
set -Eeuo pipefail
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
probe=$1

host_connect() {
  # Expansion is intentionally performed by the remote guest shell.
  # shellcheck disable=SC2016
  timeout 3 bash -c 'exec 3<>"/dev/tcp/$1/$2"' _ "$1" "$2" >/dev/null 2>&1
}

host_connect 192.168.78.1 16333
host_connect 192.168.78.1 16379
host_connect 192.168.78.1 3000
host_connect 192.168.78.1 4318
! host_connect 192.168.78.1 16332
! host_connect 192.168.78.1 16380
! host_connect 192.168.78.1 15673
! host_connect 192.168.78.1 13000
! host_connect 10.61.50.62 6333
! host_connect 10.61.50.11 6379
! host_connect 10.61.50.40 3000
! host_connect 10.61.50.10 5432
! host_connect 10.61.50.60 9000

cleanup() {
  kubectl -n orion-platform delete pod "$probe" --ignore-not-found --wait=false >/dev/null 2>&1 || true
}
trap cleanup EXIT

for namespace in orion-platform orion-runtime cinder; do
  kubectl -n "$namespace" get networkpolicy default-deny >/dev/null 2>&1
  types=$(kubectl -n "$namespace" get networkpolicy default-deny \
    -o jsonpath='{.spec.policyTypes[*]}')
  [[ $types == *Ingress* && $types == *Egress* ]]
done

kubectl -n orion-platform delete pod "$probe" --ignore-not-found --wait=true >/dev/null
kubectl -n orion-platform run "$probe" \
  --image=keplerops/orion-agent:0.1.0 \
  --labels=app.kubernetes.io/name=orion-agent,app.kubernetes.io/part-of=keplerops-platform \
  --restart=Never --command -- python -c 'import time; time.sleep(300)' >/dev/null
kubectl -n orion-platform wait --for=condition=Ready "pod/$probe" --timeout=90s >/dev/null

kube_connect() {
  kubectl -n orion-platform exec "$probe" -- python -c \
    'import socket,sys; s=socket.create_connection((sys.argv[1],int(sys.argv[2])),2); s.close()' \
    "$1" "$2" >/dev/null 2>&1
}

for endpoint in \
  litellm.orion-platform.svc:4000 \
  opa.orion-platform.svc:8181 \
  orion-mcp.orion-platform.svc:8081 \
  192.168.78.1:4318; do
  host=${endpoint%:*}
  port=${endpoint##*:}
  kube_connect "$host" "$port"
done

! kube_connect vertex-openai-proxy.orion-platform.svc 8082
! kube_connect kubernetes.default.svc 443
! kube_connect 192.168.78.1 4317
KUBERNETES_PROOF
pass "Kubernetes namespace defaults and workload flow boundaries"

echo "KeplerOps clean-enterprise network segmentation passed"
