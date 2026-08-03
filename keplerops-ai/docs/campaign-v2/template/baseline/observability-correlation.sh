#!/usr/bin/env bash

set -Eeuo pipefail

readonly ROOT="${KEPLEROPS_V2_ROOT:-/opt/keplerops-v2}"
readonly DRIVER="${ROOT}/observability/review-workflow-correlation.py"
readonly CADDY_CONTAINER="${CADDY_CONTAINER:-kep-v2-caddy}"
readonly JAEGER_URL="${JAEGER_URL:-http://10.61.80.11:16686}"
readonly PROMETHEUS_URL="${PROMETHEUS_URL:-http://10.61.80.12:9090}"
readonly OPENSEARCH_URL="${OPENSEARCH_URL:-http://10.61.80.14:9200}"
readonly K3S_KEY="${KEPLEROPS_K3S_SSH_KEY:-/root/.ssh/keplerops-v2}"
readonly K3S_TARGET="${KEPLEROPS_K3S_TARGET:-kepler@192.168.78.30}"
readonly WORKER_STATE="${ROOT}/state/guests/review-verification.env"
readonly TIMEOUT="${OBSERVABILITY_ACCEPTANCE_TIMEOUT:-240}"
readonly SSH=(ssh -i "${K3S_KEY}" -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null)

for command in curl docker jq mktemp python3 sha256sum ssh; do
  command -v "${command}" >/dev/null || {
    printf 'missing required command: %s\n' "${command}" >&2
    exit 1
  }
done

[[ -r "${DRIVER}" ]] || {
  printf 'missing correlation driver: %s\n' "${DRIVER}" >&2
  exit 1
}
[[ -r "${WORKER_STATE}" ]] || {
  printf 'review workers have not been reconciled: %s\n' "${WORKER_STATE}" >&2
  exit 1
}

workdir="$(mktemp -d)"
server_pid=''
cleanup() {
  if [[ -n ${server_pid} ]]; then
    kill "${server_pid}" >/dev/null 2>&1 || true
    wait "${server_pid}" 2>/dev/null || true
  fi
  rm -rf "${workdir}"
}
trap cleanup EXIT

docker exec "${CADDY_CONTAINER}" \
  cat /data/caddy/pki/authorities/local/root.crt >"${workdir}/enterprise-ca.crt"

# shellcheck disable=SC2016
"${SSH[@]}" "${K3S_TARGET}" \
  'sudo sh -c '\''release=$(readlink -f /var/lib/keplerops-platform/current-assistant-release); cd "$release"; sha256sum -c SHA256SUMS >/dev/null; COSIGN_PASSWORD=$(cat /var/lib/keplerops-platform/signing/cosign-password) cosign verify-blob --insecure-ignore-tlog --key cosign.pub --bundle assistant-runtime.sigstore.json assistant-runtime.intoto.json >/dev/null; cat assistant-runtime.json'\''' \
  >"${workdir}/assistant-runtime.json"

jq -e '
  (.release_id | test("^sha256:[0-9a-f]{64}$")) and
  (.model_identity.digest | test("^sha256:[0-9a-f]{64}$"))
' "${workdir}/assistant-runtime.json" >/dev/null

cat >"${workdir}/partner-sdk-notes.md" <<'EOF'
# Orion Partner SDK Compatibility Notes

The partner SDK reads the published release manifest before loading a model
adapter. Integrations must verify the artifact SHA-256 and reject an adapter
whose declared release identity differs from the active Orion release.
EOF
artifact_digest="$(sha256sum "${workdir}/partner-sdk-notes.md" | awk '{print $1}')"
python3 -m http.server 18094 --bind 192.168.78.1 --directory "${workdir}" \
  >"${workdir}/artifact-server.log" 2>&1 &
server_pid=$!
for _ in {1..20}; do
  curl -fsS http://192.168.78.1:18094/partner-sdk-notes.md >/dev/null && break
  sleep 0.5
done
kill -0 "${server_pid}"

set -a
# This file contains only synthetic identities created by reconcile-guests.sh.
# shellcheck source=/dev/null
source "${WORKER_STATE}"
set +a

export CADDY_CA_FILE="${workdir}/enterprise-ca.crt"
export ASSISTANT_RELEASE_FILE="${workdir}/assistant-runtime.json"
export ARTIFACT_URL='http://192.168.78.1:18094/partner-sdk-notes.md'
export ARTIFACT_SHA256="${artifact_digest}"
export CORRELATION_OUTPUT="${workdir}/correlation.json"
export OPENSEARCH_URL JAEGER_URL PROMETHEUS_URL TIMEOUT
export ORION_AGENT_API_KEY="${ORION_AGENT_API_KEY:-KAI-Orion-Agent-Runtime-8f4c1a7d29e6b053}"
export KEPLEROPS_K3S_SSH_KEY="${K3S_KEY}"
export KEPLEROPS_K3S_TARGET="${K3S_TARGET}"

python3 "${DRIVER}"

target_request="$(jq -er '.target.request_id' "${workdir}/correlation.json")"
target_trace="$(jq -er '.target.trace_id' "${workdir}/correlation.json")"
adjacent_request="$(jq -er '.adjacent.request_id' "${workdir}/correlation.json")"
adjacent_trace="$(jq -er '.adjacent.trace_id' "${workdir}/correlation.json")"
release_id="$(jq -er '.target.model_release_id' "${workdir}/correlation.json")"
model_digest="$(jq -er '.target.model_identity_digest' "${workdir}/correlation.json")"

[[ ${target_request} != "${adjacent_request}" && ${target_trace} != "${adjacent_trace}" ]]

query_audit() {
  local request_id=$1 output=$2 query
  query="$(jq -cn --arg request_id "${request_id}" \
    '{size:20,query:{term:{"request_id.keyword":$request_id}}}')"
  curl -fsS -H 'Content-Type: application/json' --data "${query}" \
    "${OPENSEARCH_URL}/keplerops-audit-access/_search" >"${output}"
}

query_audit "${target_request}" "${workdir}/target-audit.json"
query_audit "${adjacent_request}" "${workdir}/adjacent-audit.json"

for identity in target adjacent; do
  request_var="${identity}_request"
  trace_var="${identity}_trace"
  request_id="${!request_var}"
  trace_id="${!trace_var}"
  jq -e --arg request_id "${request_id}" --arg trace_id "${trace_id}" \
    --arg release_id "${release_id}" '
      [.hits.hits[]._source] as $events |
      ($events | length) >= 2 and
      ([$events[].service] | unique | index("orion-agent")) != null and
      ([$events[].service] | unique | index("orion-review-worker")) != null and
      all($events[];
        .request_id == $request_id and .trace_id == $trace_id and
        .model_release_id == $release_id)
    ' "${workdir}/${identity}-audit.json" >/dev/null
done

jq -e --arg adjacent "${adjacent_request}" '
  all(.hits.hits[]._source; .request_id != $adjacent)
' "${workdir}/target-audit.json" >/dev/null
jq -e --arg target "${target_request}" '
  all(.hits.hits[]._source; .request_id != $target)
' "${workdir}/adjacent-audit.json" >/dev/null

verify_trace() {
  local request_id=$1 trace_id=$2 output=$3
  local deadline=$((SECONDS + TIMEOUT))
  while ((SECONDS < deadline)); do
    if curl -fsS "${JAEGER_URL}/api/traces/${trace_id}" >"${output}" 2>/dev/null &&
      jq -e --arg trace_id "${trace_id}" --arg request_id "${request_id}" \
        --arg release_id "${release_id}" '
          .data | any(
            .traceID == $trace_id and
            ([.processes[].serviceName] | index("orion-agent")) != null and
            ([.processes[].serviceName] | index("orion-review-worker")) != null and
            ([.spans[] | select(any(.tags[]?; .key == "keplerops.request_id" and .value == $request_id))] | length) >= 2
          )
        ' "${output}" >/dev/null; then
      return 0
    fi
    sleep 2
  done
  printf 'Jaeger did not reconstruct review trace %s\n' "${trace_id}" >&2
  return 1
}

verify_trace "${target_request}" "${target_trace}" "${workdir}/target-jaeger.json"
verify_trace "${adjacent_request}" "${adjacent_trace}" "${workdir}/adjacent-jaeger.json"

verify_metric() {
  local request_id=$1 output=$2
  local query="sum(orion_calls_total{keplerops_event_id=\"${request_id}\"})"
  local deadline=$((SECONDS + TIMEOUT))
  while ((SECONDS < deadline)); do
    if curl -fsS -G --data-urlencode "query=${query}" \
      "${PROMETHEUS_URL}/api/v1/query" >"${output}" &&
      jq -e '.status == "success" and ([.data.result[]["value"][1] | tonumber] | add) >= 2' \
        "${output}" >/dev/null; then
      return 0
    fi
    sleep 2
  done
  printf 'Prometheus did not expose the complete review trace for %s\n' "${request_id}" >&2
  return 1
}

verify_metric "${target_request}" "${workdir}/target-prometheus.json"
verify_metric "${adjacent_request}" "${workdir}/adjacent-prometheus.json"

printf 'observability correlation passed: request=%s trace=%s adjacent_request=%s adjacent_trace=%s release=%s model=%s\n' \
  "${target_request}" "${target_trace}" "${adjacent_request}" "${adjacent_trace}" \
  "${release_id}" "${model_digest}"
