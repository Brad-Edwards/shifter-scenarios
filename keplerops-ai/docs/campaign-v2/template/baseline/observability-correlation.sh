#!/usr/bin/env bash

set -Eeuo pipefail

readonly CADDY_CONTAINER="${CADDY_CONTAINER:-kep-v2-caddy}"
readonly MODEL_HOST="${MODEL_HOST:-risk-model.keplerops.lab}"
readonly MODEL_EDGE="${MODEL_EDGE:-10.61.10.2}"
readonly JAEGER_URL="${JAEGER_URL:-http://10.61.80.11:16686}"
readonly PROMETHEUS_URL="${PROMETHEUS_URL:-http://10.61.80.12:9090}"
readonly ALERTMANAGER_URL="${ALERTMANAGER_URL:-http://10.61.80.15:9093}"
readonly OPENSEARCH_URL="${OPENSEARCH_URL:-http://10.61.80.14:9200}"
readonly OPENCOST_URL="${OPENCOST_URL:-http://192.168.78.30:30090}"
readonly TIMEOUT="${OBSERVABILITY_ACCEPTANCE_TIMEOUT:-180}"

for command in curl docker jq mktemp python3; do
  command -v "${command}" >/dev/null || {
    printf 'missing required command: %s\n' "${command}" >&2
    exit 1
  }
done

workdir="$(mktemp -d)"
trap 'rm -rf "${workdir}"' EXIT

docker exec "${CADDY_CONTAINER}" \
  cat /data/caddy/pki/authorities/local/root.crt >"${workdir}/range-ca.crt"

event_id="$(python3 - <<'PY'
import uuid
print(f"orion-{uuid.uuid4()}")
PY
)"
event_epoch="$(date +%s)"

cat >"${workdir}/request.json" <<'JSON'
{
  "instances": [
    {
      "text": "Pause deployment because the serving artifact is not signed."
    }
  ]
}
JSON

curl -fsS \
  --cacert "${workdir}/range-ca.crt" \
  --resolve "${MODEL_HOST}:443:${MODEL_EDGE}" \
  -H 'Content-Type: application/json' \
  -H "X-KeplerOps-Event-ID: ${event_id}" \
  --data-binary "@${workdir}/request.json" \
  "https://${MODEL_HOST}/v1/models/orion-release-risk:predict" \
  >"${workdir}/response.json"

jq -e '
  .model_name == "orion-release-risk"
  and (.predictions | length) == 1
  and (.predictions[0].probabilities | length) > 1' \
  "${workdir}/response.json" >/dev/null

deadline=$((SECONDS + TIMEOUT))
trace_id=""
while ((SECONDS < deadline)); do
  query="$(jq -cn --arg event_id "${event_id}" \
    '{size: 10, query: {term: {"event_id.keyword": $event_id}}}')"
  if curl -fsS \
    -H 'Content-Type: application/json' \
    -d "${query}" \
    "${OPENSEARCH_URL}/keplerops-audit-access/_search" \
    >"${workdir}/opensearch.json" 2>/dev/null; then
    trace_id="$(jq -r '.hits.hits[0]._source.trace_id // empty' \
      "${workdir}/opensearch.json")"
    [[ "${trace_id}" =~ ^[0-9a-f]{32}$ ]] && break
  fi
  sleep 2
done
[[ "${trace_id}" =~ ^[0-9a-f]{32}$ ]] || {
  echo "OpenSearch did not index the correlated Orion access log" >&2
  exit 2
}
jq -e --arg event_id "${event_id}" --arg trace_id "${trace_id}" '
  .hits.hits
  | any(._source.event_id == $event_id
        and ._source.trace_id == $trace_id
        and ._source.service == "orion-release-risk-edge"
        and (._source.response_code | tonumber) == 200)' \
  "${workdir}/opensearch.json" >/dev/null

deadline=$((SECONDS + TIMEOUT))
while ((SECONDS < deadline)); do
  if curl -fsS "${JAEGER_URL}/api/traces/${trace_id}" \
    >"${workdir}/jaeger.json" 2>/dev/null &&
    jq -e --arg trace_id "${trace_id}" --arg event_id "${event_id}" '
      .data
      | any(
          .traceID == $trace_id
          and any(.spans[];
            any(.tags[]?; .key == "keplerops.event_id" and .value == $event_id)
            and any(.tags[]?;
              .key == "keplerops.cost.allocation"
              and .value == "orion-runtime/orion-release-risk"))
        )' "${workdir}/jaeger.json" >/dev/null; then
    break
  fi
  sleep 2
done
jq -e --arg trace_id "${trace_id}" --arg event_id "${event_id}" '
  .data
  | any(
      .traceID == $trace_id
      and any(.spans[];
        any(.tags[]?; .key == "keplerops.event_id" and .value == $event_id)
        and any(.tags[]?;
          .key == "keplerops.cost.allocation"
          and .value == "orion-runtime/orion-release-risk"))
    )' "${workdir}/jaeger.json" >/dev/null || {
  echo "Jaeger did not retain the correlated Orion trace" >&2
  exit 3
}

metric_query="orion_calls_total{service_name=\"orion-release-risk-edge\",keplerops_event_id=\"${event_id}\"}"
deadline=$((SECONDS + TIMEOUT))
while ((SECONDS < deadline)); do
  if curl -fsS -G --data-urlencode "query=${metric_query}" \
    "${PROMETHEUS_URL}/api/v1/query" >"${workdir}/prometheus.json" &&
    jq -e '.status == "success" and any(.data.result[]; (.["value"][1] | tonumber) >= 1)' \
      "${workdir}/prometheus.json" >/dev/null; then
    break
  fi
  sleep 2
done
jq -e '.status == "success" and any(.data.result[]; (.["value"][1] | tonumber) >= 1)' \
  "${workdir}/prometheus.json" >/dev/null || {
  echo "Prometheus did not receive the span-derived Orion metric" >&2
  exit 4
}

deadline=$((SECONDS + TIMEOUT))
while ((SECONDS < deadline)); do
  if curl -fsS "${ALERTMANAGER_URL}/api/v2/alerts" \
    >"${workdir}/alerts.json" &&
    jq -e --arg event_id "${event_id}" '
      any(.[];
        .labels.alertname == "OrionCorrelatedInferenceObserved"
        and .labels.keplerops_event_id == $event_id
        and .status.state == "active")' "${workdir}/alerts.json" >/dev/null; then
    break
  fi
  sleep 2
done
jq -e --arg event_id "${event_id}" '
  any(.[];
    .labels.alertname == "OrionCorrelatedInferenceObserved"
    and .labels.keplerops_event_id == $event_id
    and .status.state == "active")' "${workdir}/alerts.json" >/dev/null || {
  echo "Alertmanager did not receive the correlated Orion alert" >&2
  exit 5
}

deadline=$((SECONDS + TIMEOUT))
while ((SECONDS < deadline)); do
  if curl -fsS -G \
    --data-urlencode 'window=30m' \
    --data-urlencode 'resolution=1m' \
    --data-urlencode 'aggregate=namespace,controller' \
    "${OPENCOST_URL}/allocation/compute" >"${workdir}/opencost.json" &&
    jq -e '
      .code == 200
      and any(.data[] | to_entries[];
        (.key | contains("orion-runtime"))
        and (.key | contains("orion-release-risk"))
        and (.value.totalCost // 0) > 0)' "${workdir}/opencost.json" >/dev/null; then
    break
  fi
  sleep 5
done
jq -e '
  .code == 200
  and any(.data[] | to_entries[];
    (.key | contains("orion-runtime"))
    and (.key | contains("orion-release-risk"))
    and (.value.totalCost // 0) > 0)' "${workdir}/opencost.json" >/dev/null || {
  echo "OpenCost did not produce a release-risk workload allocation" >&2
  exit 6
}

cost="$(jq -r '
  [.data[] | to_entries[]
   | select((.key | contains("orion-runtime"))
            and (.key | contains("orion-release-risk")))
   | .value.totalCost]
  | add' "${workdir}/opencost.json")"

printf 'observability correlation passed: event=%s epoch=%s trace=%s metric=orion_calls_total alert=OrionCorrelatedInferenceObserved cost=%s\n' \
  "${event_id}" "${event_epoch}" "${trace_id}" "${cost}"
