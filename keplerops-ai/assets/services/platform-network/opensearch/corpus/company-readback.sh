#!/bin/sh
set -eu

script_dir="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
opensearch_url="${OPENSEARCH_URL:-http://127.0.0.1:9200}"
manifest="${script_dir}/company-readback-manifest.json"
digests="${script_dir}/company-readback-digests.txt"
sources="${script_dir}/company-readback-sources.ndjson"
index_name="keplerops-company-v1-000001"
owner="keplerops-company-state"

expected_count="$(
  sed -n 's/^[[:space:]]*"object_count":[[:space:]]*\([0-9][0-9]*\),*$/\1/p' \
    "${manifest}"
)"
expected_digest="$(
  sed -n 's/^[[:space:]]*"canonical_digest":[[:space:]]*"\(sha256:[0-9a-f]\{64\}\)",*$/\1/p' \
    "${manifest}"
)"
test -n "${expected_count}"
test -n "${expected_digest}"

count="$(
  curl --fail --silent --show-error \
    "${opensearch_url}/${index_name}/_count" |
    sed -n 's/.*"count"[[:space:]]*:[[:space:]]*\([0-9][0-9]*\).*/\1/p'
)"
test "${count}" = "${expected_count}"

mapping="$(
  curl --fail --silent --show-error \
    "${opensearch_url}/${index_name}/_mapping?filter_path=*.mappings._meta"
)"
printf '%s' "${mapping}" | grep -Fq "\"owner\":\"${owner}\""
printf '%s' "${mapping}" |
  grep -Fq "\"canonical_digest\":\"${expected_digest}\""

line_number=1
while read -r document_id source_digest; do
  test -n "${document_id}"
  test -n "${source_digest}"
  document="$(
    curl --fail --silent --show-error \
      "${opensearch_url}/${index_name}/_doc/${document_id}?_source_includes=source_digest,company_state_owner"
  )"
  printf '%s' "${document}" |
    grep -Fq "\"source_digest\":\"${source_digest}\""
  printf '%s' "${document}" |
    grep -Fq "\"company_state_owner\":\"${owner}\""
  expected_source="$(sed -n "${line_number}p" "${sources}")"
  actual_source="$(
    curl --fail --silent --show-error \
      "${opensearch_url}/${index_name}/_source/${document_id}"
  )"
  test "${actual_source}" = "${expected_source}"
  line_number=$((line_number + 1))
done <"${digests}"
test "$((line_number - 1))" = "${expected_count}"
