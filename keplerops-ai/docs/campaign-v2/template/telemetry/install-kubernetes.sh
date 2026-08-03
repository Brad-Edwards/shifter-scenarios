#!/usr/bin/env bash

set -Eeuo pipefail

readonly ROOT="${KEPLEROPS_V2_ROOT:-/opt/keplerops-v2}"
readonly KEY="${KEPLEROPS_K3S_SSH_KEY:-/root/.ssh/keplerops-v2}"
readonly TARGET="${KEPLEROPS_K3S_TARGET:-kepler@192.168.78.30}"
readonly LOCK="${ROOT}/telemetry/component-lock.env"
readonly MANIFEST="${ROOT}/telemetry/kubernetes.yaml"
readonly SSH=(ssh -i "${KEY}" -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null)

for command in envsubst ssh; do
  command -v "${command}" >/dev/null || {
    printf 'missing required command: %s\n' "${command}" >&2
    exit 1
  }
done

[[ -r "${LOCK}" && -r "${MANIFEST}" ]] || {
  echo "telemetry component lock or Kubernetes manifest is missing" >&2
  exit 1
}

set -a
# The lock contains only pinned component identifiers used by this template.
# shellcheck source=/dev/null
source "${LOCK}"
set +a

: "${OPENCOST_IMAGE:?missing OPENCOST_IMAGE}"
: "${KUBE_STATE_METRICS_IMAGE:?missing KUBE_STATE_METRICS_IMAGE}"
: "${CADVISOR_IMAGE:?missing CADVISOR_IMAGE}"

envsubst "\${OPENCOST_IMAGE} \${KUBE_STATE_METRICS_IMAGE} \${CADVISOR_IMAGE}" \
  <"${MANIFEST}" | "${SSH[@]}" "${TARGET}" sudo kubectl apply -f -

for workload in deployment/kube-state-metrics daemonset/cadvisor deployment/opencost; do
  "${SSH[@]}" "${TARGET}" sudo kubectl \
    -n keplerops-observe rollout status "${workload}" --timeout=5m
done

printf 'OpenCost telemetry workloads reconciled on %s\n' "${TARGET}"
