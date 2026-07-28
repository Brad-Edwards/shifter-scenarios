#!/bin/sh
set -eu

alias_name=${1:?alias required}
bucket=${2:?bucket required}
seed_root=/opt/keplerops/company-state
owner=keplerops-company-state
owner_prefix=company-state/v1/.ownership
readback_root=$(mktemp -d)
trap 'rm -rf "$readback_root"' EXIT

while IFS="$(printf '\t')" read -r object_id source_file object_key expected_digest media_type; do
  marker_key="${owner_prefix}/${object_id}"
  if mc stat --insecure "${alias_name}/${bucket}/${object_key}" >/dev/null 2>&1; then
    actual_owner=$(mc cat --insecure "${alias_name}/${bucket}/${marker_key}" 2>/dev/null || true)
    if [ "$actual_owner" != "$owner" ]; then
      printf 'ownership collision: MinIO object %s\n' "$object_key" >&2
      exit 1
    fi
  elif mc stat --insecure "${alias_name}/${bucket}/${marker_key}" >/dev/null 2>&1; then
    actual_owner=$(mc cat --insecure "${alias_name}/${bucket}/${marker_key}" 2>/dev/null || true)
    if [ "$actual_owner" != "$owner" ]; then
      printf 'ownership collision: MinIO marker %s\n' "$marker_key" >&2
      exit 1
    fi
  fi
  printf '%s\n' "$owner" >"${readback_root}/owner"
  mc cp --insecure "${readback_root}/owner" \
    "${alias_name}/${bucket}/${marker_key}" >/dev/null
  mc cp --insecure --attr "Content-Type=${media_type}" \
    "${seed_root}/objects/${source_file}" \
    "${alias_name}/${bucket}/${object_key}" >/dev/null
  mc cat --insecure "${alias_name}/${bucket}/${object_key}" \
    >"${readback_root}/${object_id}"
  actual_digest="sha256:$(sha256sum "${readback_root}/${object_id}" | cut -d ' ' -f 1)"
  if [ "$actual_digest" != "$expected_digest" ]; then
    printf 'company artifact native readback digest mismatch: %s\n' "$object_id" >&2
    exit 1
  fi
done <"${seed_root}/objects.tsv"

mc cp --insecure "${seed_root}/plan.json" \
  "${alias_name}/${bucket}/company-state/v1/readback-plan.json" >/dev/null
