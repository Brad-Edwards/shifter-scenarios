#!/bin/sh
set -eu

script_dir="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
opensearch_url="${OPENSEARCH_URL:-http://127.0.0.1:9200}"
"${script_dir}/health.sh"
curl --fail --silent --show-error \
  "${opensearch_url}/_index_template/keplerops-research-v1" >/dev/null
count="$(curl --fail --silent --show-error \
  "${opensearch_url}/keplerops-research/_count" | \
  sed -n 's/.*"count"[[:space:]]*:[[:space:]]*\([0-9][0-9]*\).*/\1/p')"
test "${count}" = "8"
"${script_dir}/corpus/company-readback.sh"
