#!/bin/sh
set -eu

script_dir="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
opensearch_url="${OPENSEARCH_URL:-http://127.0.0.1:9200}"
index_name="keplerops-research-v1-000001"
company_index_name="keplerops-company-v1-000001"
company_template_name="keplerops-company-v1"
company_alias="keplerops-company"
company_owner="keplerops-company-state"
http_code_format='%{http_code}'
json_content_type='Content-Type: application/json'

"${script_dir}/health.sh"
curl --fail --silent --show-error \
  -H "${json_content_type}" \
  -X PUT "${opensearch_url}/_index_template/keplerops-research-v1" \
  --data-binary "@${script_dir}/index-template.json" >/dev/null

delete_status="$(curl --silent --show-error -o /dev/null -w "${http_code_format}" \
  -X DELETE "${opensearch_url}/${index_name}")"
case "${delete_status}" in
  200|404) ;;
  *)
    printf 'unexpected OpenSearch delete status: %s\n' "${delete_status}" >&2
    exit 1
    ;;
esac

curl --fail --silent --show-error \
  -H "${json_content_type}" \
  -X PUT "${opensearch_url}/${index_name}" >/dev/null
bulk_response="$(curl --fail --silent --show-error \
  -H 'Content-Type: application/x-ndjson' \
  -X POST "${opensearch_url}/_bulk?refresh=wait_for" \
  --data-binary "@${script_dir}/corpus/research-corpus.ndjson")"
printf '%s' "${bulk_response}" | grep -Eq '"errors"[[:space:]]*:[[:space:]]*false'

template_status="$(curl --silent --show-error -o /tmp/company-template.json -w "${http_code_format}" \
  "${opensearch_url}/_index_template/${company_template_name}")"
case "${template_status}" in
  200)
    grep -Fq "\"owner\":\"${company_owner}\"" /tmp/company-template.json ||
      {
        printf 'ownership collision: OpenSearch template %s\n' "${company_template_name}" >&2
        exit 1
      }
    ;;
  404) ;;
  *)
    printf 'unexpected OpenSearch template status: %s\n' "${template_status}" >&2
    exit 1
    ;;
esac

company_status="$(curl --silent --show-error -o /tmp/company-index-mapping.json -w "${http_code_format}" \
  "${opensearch_url}/${company_index_name}/_mapping?filter_path=*.mappings._meta")"
case "${company_status}" in
  200)
    grep -Fq "\"owner\":\"${company_owner}\"" \
      /tmp/company-index-mapping.json ||
      {
        printf 'ownership collision: OpenSearch index %s\n' "${company_index_name}" >&2
        exit 1
      }
    ;;
  404) ;;
  *)
    printf 'unexpected OpenSearch company index status: %s\n' "${company_status}" >&2
    exit 1
    ;;
esac

alias_status="$(curl --silent --show-error -o /tmp/company-alias.json -w "${http_code_format}" \
  "${opensearch_url}/_cat/aliases/${company_alias}?format=json&h=alias,index")"
case "${alias_status}" in
  200)
    if grep -Eq '^\[\]$' /tmp/company-alias.json; then
      :
    elif test "${company_status}" != 200 ||
      ! grep -Eq "^\\[\\{\"alias\":\"${company_alias}\",\"index\":\"${company_index_name}\"\\}\\]$" \
        /tmp/company-alias.json; then
      printf 'ownership collision: OpenSearch alias %s\n' "${company_alias}" >&2
      exit 1
    fi
    ;;
  404) ;;
  *)
    printf 'unexpected OpenSearch company alias status: %s\n' "${alias_status}" >&2
    exit 1
    ;;
esac

curl --fail --silent --show-error \
  -H "${json_content_type}" \
  -X PUT "${opensearch_url}/_index_template/${company_template_name}" \
  --data-binary "@${script_dir}/corpus/company-index-template.json" >/dev/null

if test "${company_status}" = 200; then
  curl --fail --silent --show-error \
    -X DELETE "${opensearch_url}/${company_index_name}" >/dev/null
fi
curl --fail --silent --show-error \
  -H "${json_content_type}" \
  -X PUT "${opensearch_url}/${company_index_name}" \
  --data-binary "@${script_dir}/corpus/company-index.json" >/dev/null
company_bulk_response="$(curl --fail --silent --show-error \
  -H 'Content-Type: application/x-ndjson' \
  -X POST "${opensearch_url}/_bulk?refresh=wait_for" \
  --data-binary "@${script_dir}/corpus/company-corpus.ndjson")"
printf '%s' "${company_bulk_response}" |
  grep -Eq '"errors"[[:space:]]*:[[:space:]]*false'

"${script_dir}/readiness.sh"
