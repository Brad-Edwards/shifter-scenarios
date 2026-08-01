#!/usr/bin/env bash

set -Eeuo pipefail

readonly FORGEJO_URL="${FORGEJO_URL:-http://10.61.40.20:3000}"
readonly FORGEJO_AUTH="${FORGEJO_AUTH:-range-admin:KeplerV2-Training-Forgejo-Admin}"
readonly FORGEJO_REPOSITORY="${FORGEJO_REPOSITORY:-keplerops/orion-build}"
readonly DEVPI_URL="${DEVPI_URL:-http://10.61.40.30:3141}"
readonly VERDACCIO_URL="${VERDACCIO_URL:-http://10.61.40.31:4873}"
readonly VERDACCIO_AUTH="${VERDACCIO_AUTH:-publisher:KeplerV2-Training-Npm-Publisher}"
readonly HARBOR_URL="${HARBOR_URL:-http://10.61.40.32:8080}"
readonly HARBOR_AUTH="${HARBOR_AUTH:-admin:KeplerV2-Training-Harbor}"

for command in curl jq grep; do
  command -v "${command}" >/dev/null || {
    printf 'missing required command: %s\n' "${command}" >&2
    exit 1
  }
done

branch="$(curl -fsS \
  -u "${FORGEJO_AUTH}" \
  "${FORGEJO_URL}/api/v1/repos/${FORGEJO_REPOSITORY}/branches/main")"
source_revision="$(jq -er '.commit.id' <<<"${branch}")"
short_revision="${source_revision:0:12}"

runs="$(curl -fsS \
  -u "${FORGEJO_AUTH}" \
  "${FORGEJO_URL}/api/v1/repos/${FORGEJO_REPOSITORY}/actions/tasks?limit=1")"
jq -e \
  --arg revision "${source_revision}" \
  '(.workflow_runs | max_by(.id))
   | .status == "success"
     and .head_branch == "main"
     and .head_sha == $revision
     and .workflow_id == "publish.yml"' \
  <<<"${runs}" >/dev/null
run_number="$(jq -er '.workflow_runs | max_by(.id).run_number' <<<"${runs}")"

curl -fsS \
  "${DEVPI_URL}/publisher/stable/+simple/keplerops-orion-release/" | \
  grep -q 'keplerops_orion_release-0.1.0-py3-none-any.whl'

node_metadata="$(curl -fsS \
  -u "${VERDACCIO_AUTH}" \
  "${VERDACCIO_URL}/%40keplerops%2Forion-build-metadata")"
jq -e '.versions["0.1.0"].name == "@keplerops/orion-build-metadata"' \
  <<<"${node_metadata}" >/dev/null

artifacts="$(curl -fsS \
  -u "${HARBOR_AUTH}" \
  "${HARBOR_URL}/api/v2.0/projects/orion-build/repositories/orion-release-metadata/artifacts?with_tag=true")"
artifact="$(jq -ec \
  --arg revision "ORION_BUILD_REVISION=${source_revision}" \
  --arg short "${short_revision}" \
  '[.[]
    | select(any((.tags // [])[]; .name == $short))
    | select(any((.tags // [])[]; .name == "clean-latest"))
    | select(any((.extra_attrs.config.Env // [])[]; . == $revision))]
   | if length == 1 then .[0] else error("expected one matching Harbor artifact") end' \
  <<<"${artifacts}")"
digest="$(jq -er '.digest' <<<"${artifact}")"

printf 'source publication passed: run=%s revision=%s python=0.1.0 node=0.1.0 image=%s@%s\n' \
  "${run_number}" "${source_revision}" \
  'registry.keplerops.lab/orion-build/orion-release-metadata' "${digest}"
