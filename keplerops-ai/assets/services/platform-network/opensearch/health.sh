#!/bin/sh
set -eu

opensearch_url="${OPENSEARCH_URL:-http://127.0.0.1:9200}"
response="$(curl --fail --silent --show-error \
  "${opensearch_url}/_cluster/health?wait_for_status=yellow&timeout=30s")"
printf '%s' "${response}" | grep -Eq '"status"[[:space:]]*:[[:space:]]*"(green|yellow)"'
