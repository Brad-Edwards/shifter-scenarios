#!/usr/bin/env bash
set -Eeuo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MODULE_ROOT
TEMPLATE_ROOT="$(cd "${MODULE_ROOT}/../../.." && pwd)"
readonly TEMPLATE_ROOT
readonly OPERATION="${1:-}"
readonly CINDER_RELAY_URL='https://relay.cinder.lab'
readonly FORGEJO_URL='https://git.keplerops.lab'
readonly FORGEJO_USER='range-admin'
readonly FORGEJO_PASSWORD='KeplerV2-Training-Forgejo-Admin'
readonly WORKHUB_URL='https://workhub.keplerops.lab'
readonly WORKHUB_USER='range-admin'
readonly WORKHUB_PASSWORD='KeplerV2-Training-Redmine-Admin'
readonly QDRANT_URL='https://vectors.keplerops.lab'
readonly QDRANT_READ_KEY='KeplerV2-Training-Qdrant-Read'
readonly PUBLIC_ROUTE_ADDRESS="${KEPLEROPS_PUBLIC_ROUTE_ADDRESS:-192.168.78.1}"
JUPYTER_IMAGE="$(sed -n 's/^JUPYTER_IMAGE=//p' "${TEMPLATE_ROOT}/component-lock.env")"
readonly JUPYTER_IMAGE
MINIO_MC_IMAGE="$(sed -n 's/^MINIO_MC_IMAGE=//p' "${TEMPLATE_ROOT}/engineering/component-lock.additions.env")"
readonly MINIO_MC_IMAGE

log() { printf '[campaign-m03-validate] %s\n' "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }
flag_for() { jq -er --arg id "$1" '.[] | select(.id == $id) | .flag' "${MODULE_ROOT}/operations.json"; }

curl_tls_args() {
  if [[ -n ${KEPLEROPS_CA_CERT:-} ]]; then printf '%s\0%s\0' --cacert "${KEPLEROPS_CA_CERT}"; fi
  printf '%s\0%s\0' --resolve "workhub.keplerops.lab:443:${PUBLIC_ROUTE_ADDRESS}"
  printf '%s\0%s\0' --resolve "git.keplerops.lab:443:${PUBLIC_ROUTE_ADDRESS}"
  printf '%s\0%s\0' --resolve "vectors.keplerops.lab:443:${PUBLIC_ROUTE_ADDRESS}"
  printf '%s\0%s\0' --resolve "relay.cinder.lab:443:${PUBLIC_ROUTE_ADDRESS}"
}

compose() {
  docker compose --project-directory "${TEMPLATE_ROOT}" \
    --env-file "${TEMPLATE_ROOT}/component-lock.env" \
    --env-file "${TEMPLATE_ROOT}/engineering/component-lock.additions.env" \
    -f "${TEMPLATE_ROOT}/compose.foundation.yaml" \
    -f "${TEMPLATE_ROOT}/compose.enterprise.yaml" \
    -f "${TEMPLATE_ROOT}/compose.engineering.yaml" \
    -f "${TEMPLATE_ROOT}/compose.cinder.yaml" \
    -f "${MODULE_ROOT}/compose.overlay.yaml" "$@"
}

cinder_object() {
  local access=$1 secret=$2 key=$3 output=$4 version=${5:-}
  docker run --rm --network kep-v2-cinder --entrypoint /bin/sh "${MINIO_MC_IMAGE}" -eu -c "
    mc alias set cinder http://cinder-minio:9000 '${access}' '${secret}' >/dev/null
    mc cat ${version:+--version-id "${version}"} 'cinder/operations/${key}'
  " >"${output}"
}

cinder_stat() {
  local access=$1 secret=$2 key=$3 output=$4 version=${5:-}
  docker run --rm --network kep-v2-cinder --entrypoint /bin/sh "${MINIO_MC_IMAGE}" -eu -c "
    mc alias set cinder http://cinder-minio:9000 '${access}' '${secret}' >/dev/null
    mc stat --json ${version:+--version-id "${version}"} 'cinder/operations/${key}'
  " >"${output}"
}

validate_relay() {
  local id=$1 basket=$2 token token_key flag status
  local -a tls=()
  flag="$(flag_for "${id}")"
  token_key="campaign-v2/m03/relay/${basket}/access-token"
  cinder_object cinder-field-operator Cinder-Field-Operator-Objects-H8r3Tm5w \
    "${token_key}" "${TMPDIR_VALIDATE}/relay-token"
  token="$(tr -d '\r\n' <"${TMPDIR_VALIDATE}/relay-token")"
  [[ -n ${token} ]] || die "${id}: post-effect Cinder relay access object is empty"
  while IFS= read -r -d '' value; do tls+=("${value}"); done < <(curl_tls_args)
  curl -fsS "${tls[@]}" -H "Authorization: ${token}" \
    "${CINDER_RELAY_URL}/api/baskets/${basket}/requests" >"${TMPDIR_VALIDATE}/positive.json"
  grep -Fq "${flag}" "${TMPDIR_VALIDATE}/positive.json" || die "${id}: native relay record does not contain its reference"
  status="$(curl -sS "${tls[@]}" -o "${TMPDIR_VALIDATE}/negative.json" -w '%{http_code}' \
    "${CINDER_RELAY_URL}/api/baskets/${basket}/requests")"
  case "${status}" in 401|403) ;; *) die "${id}: tokenless relay read returned HTTP ${status}" ;; esac
  ! grep -Fq "${flag}" "${TMPDIR_VALIDATE}/negative.json" || die "${id}: tokenless relay read exposed the reference"
}

native_report() {
  local kind=$1 output=$2 key expected_digest observed_digest
  docker run --rm --network kep-v2-data --entrypoint /bin/sh "${MINIO_MC_IMAGE}" -eu -c "
    mc alias set kepler http://minio:9000 kepler-minio KeplerV2-Training-Minio-Object-Store >/dev/null
    key=\$(mc find 'kepler/artifacts/evaluation-reports/${kind}' --name '*.json' | tail -1)
    test -n \"\$key\"
    printf '%s\\n' \"\$key\"
    mc cat \"\$key\"
  " >"${output}.with-key"
  key="$(head -1 "${output}.with-key")"
  tail -n +2 "${output}.with-key" >"${output}"
  expected_digest="${key##*/}"
  expected_digest="${expected_digest%.json}"
  observed_digest="$(sha256sum "${output}" | awk '{print $1}')"
  [[ ${observed_digest} == "${expected_digest}" ]] || die "${kind}: MinIO object key does not match its exact bytes"
  local completed_epoch
  completed_epoch="$(date -d "$(jq -er '.completed_at' "${output}")" +%s)" || die "${kind}: invalid completion timestamp"
  (( completed_epoch >= 1767225600 && completed_epoch <= $(date +%s) + 60 )) || \
    die "${kind}: owning-system record has an invalid completion timestamp"
}

qdrant_point() {
  local point_id=$1 output=$2
  curl -fsS -H "api-key: ${QDRANT_READ_KEY}" \
    "${QDRANT_URL}/collections/orion_partner_intake/points/${point_id}" >"${output}"
  jq -e --arg id "${point_id}" '.result.id == $id and .result.payload.ingestion_pipeline == "Haystack DocumentWriter/QdrantDocumentStore"' \
    "${output}" >/dev/null || die "Qdrant does not own the expected Haystack point ${point_id}"
}

jaeger_trace() {
  local trace_id=$1 output=$2
  curl -fsS "http://10.61.80.11:16686/api/traces/${trace_id}" >"${output}"
  jq -e --arg trace "${trace_id}" '.data | any(.traceID == $trace)' "${output}" >/dev/null || \
    die "Jaeger does not own Orion trace ${trace_id}"
}

validate_evaluation_dependency() {
  local id=$1 version artifact digest url
  validate_relay "${id}" orion-evaluation-worker
  native_report evaluation-dependency-review "${TMPDIR_VALIDATE}/worker.json"
  jq -e '.schema == "keplerops.evaluation-dependency-review/v1" and .relay_status >= 200 and .relay_status < 300 and
    ([.artifact_sha256,.installed_tree_sha256,.fixture_sha256,.callback_body_sha256] | all(test("^[0-9a-f]{64}$")))' \
    "${TMPDIR_VALIDATE}/worker.json" >/dev/null || die "${id}: worker report lacks exact install, score, and callback evidence"
  version="$(jq -er '.package_version' "${TMPDIR_VALIDATE}/worker.json")"
  artifact="$(jq -er '.artifact_filename' "${TMPDIR_VALIDATE}/worker.json")"
  digest="$(jq -er '.artifact_sha256' "${TMPDIR_VALIDATE}/worker.json")"
  curl -fsS -u publisher:KeplerV2-Training-Devpi-Publisher \
    "http://10.61.40.30:3141/publisher/stable/orion-eval-utils/${version}" >"${TMPDIR_VALIDATE}/devpi.json"
  jq -e '.result["+links"] | any(.[]; any(.log[]?; .what == "upload" and .who == "publisher"))' \
    "${TMPDIR_VALIDATE}/devpi.json" >/dev/null || die "${id}: devpi does not attribute the exact release to publisher"
  url="$(jq -er --arg name "${artifact}" '.result["+links"][] | select(.href | endswith($name)) | .href' "${TMPDIR_VALIDATE}/devpi.json")"
  if [[ ${url} == /* ]]; then url="http://10.61.40.30:3141${url}"; fi
  [[ ${url} == http://10.61.40.30:3141/* ]] || die "${id}: devpi metadata selected a non-owning artifact host"
  curl -fsS "${url}" -o "${TMPDIR_VALIDATE}/${artifact}"
  [[ $(sha256sum "${TMPDIR_VALIDATE}/${artifact}" | awk '{print $1}') == "${digest}" ]] || \
    die "${id}: devpi artifact bytes do not match the worker-installed digest"
  grep -Fq "$(jq -r '.airflow_run_id' "${TMPDIR_VALIDATE}/worker.json")" "${TMPDIR_VALIDATE}/positive.json" || \
    die "${id}: relay request is not joined to the authenticated worker run"
  if ! grep -Fq "${version}" "${TMPDIR_VALIDATE}/positive.json" || \
     ! grep -Fq "${digest}" "${TMPDIR_VALIDATE}/positive.json"; then
    die "${id}: relay request is not joined to the exact devpi artifact"
  fi
}

validate_forgejo_artifact() {
  local id=$1 flag artifact_id workflow_path found=false
  local -a tls=()
  flag="$(flag_for "${id}")"
  while IFS= read -r -d '' value; do tls+=("${value}"); done < <(curl_tls_args)
  curl -fsS "${tls[@]}" -u "${FORGEJO_USER}:${FORGEJO_PASSWORD}" \
    "${FORGEJO_URL}/api/v1/repos/keplerops/orion-agent-tool-consumer/actions/artifacts?limit=100" \
    >"${TMPDIR_VALIDATE}/artifacts.json"
  while IFS= read -r artifact_id; do
    [[ -n ${artifact_id} ]] || continue
    if curl -fsS "${tls[@]}" -u "${FORGEJO_USER}:${FORGEJO_PASSWORD}" \
      "${FORGEJO_URL}/api/v1/repos/keplerops/orion-agent-tool-consumer/actions/artifacts/${artifact_id}/zip" \
      -o "${TMPDIR_VALIDATE}/${artifact_id}.zip" && \
      unzip -p "${TMPDIR_VALIDATE}/${artifact_id}.zip" 2>/dev/null | grep -Fq "${flag}"; then
      found=true
      break
    fi
  done < <(jq -r '.artifacts[]? | select(.expired != true) | .id' "${TMPDIR_VALIDATE}/artifacts.json")
  [[ ${found} == true ]] || die "${id}: no successful native adoption artifact contains its reference"

  workflow_path=verify-adoption.yml
  [[ ${id} == kep-m03-c ]] && workflow_path=dependency-update.yml
  curl -fsS "${tls[@]}" -u "${FORGEJO_USER}:${FORGEJO_PASSWORD}" \
    "${FORGEJO_URL}/api/v1/repos/keplerops/orion-agent-tool-consumer/raw/.forgejo/workflows/${workflow_path}?ref=main" \
    >"${TMPDIR_VALIDATE}/workflow.yml"
  ! grep -Fq "${flag}" "${TMPDIR_VALIDATE}/workflow.yml" || die "${id}: workflow source exposes the secret-backed reference shortcut"
}

validate_benign_adoption() {
  local id=$1 archive found=false
  validate_forgejo_artifact "${id}"
  for archive in "${TMPDIR_VALIDATE}"/*.zip; do
    unzip -p "${archive}" 2>/dev/null >"${TMPDIR_VALIDATE}/candidate-adoption.json" || continue
    if jq -e --arg flag "$(flag_for "${id}")" '
      .schema == "keplerops.mcp-adoption/v1" and .adoption_note == $flag and
      .signature_status == "verified" and .tests == "passed" and .private_callback == "absent" and
      .version != "2.3.1" and
      (.completed_at | test("^[0-9]{4}-[0-9]{2}-[0-9]{2}T")) and
      .source_author == "cinder-field-operator" and .maintainer_actor == "cinder-operator" and
      ([.tarball_sha256,.installed_tree_sha256,.source_head_commit,.source_merge_commit] | all(test("^[0-9a-f]{40,64}$"))) and
      (.installed_integrity | startswith("sha512-")) and .source_pull_request >= 1
    ' "${TMPDIR_VALIDATE}/candidate-adoption.json" >/dev/null; then
      cp "${TMPDIR_VALIDATE}/candidate-adoption.json" "${TMPDIR_VALIDATE}/adoption.json"
      found=true
      break
    fi
  done
  [[ ${found} == true ]] || die "${id}: no immutable adoption manifest proves the fixed test, signature, and exact installed release"
  curl -fsS -u "${FORGEJO_USER}:${FORGEJO_PASSWORD}" \
    "${FORGEJO_URL}/api/v1/repos/keplerops/orion-agent-tool-consumer/raw/adoption/manifest.json?ref=main" \
    >"${TMPDIR_VALIDATE}/main-adoption.json"
  cmp -s "${TMPDIR_VALIDATE}/adoption.json" "${TMPDIR_VALIDATE}/main-adoption.json" || \
    die "${id}: artifact is not the adoption manifest retained on consumer main"
  curl -fsS -u "${FORGEJO_USER}:${FORGEJO_PASSWORD}" \
    "${FORGEJO_URL}/api/v1/repos/keplerops/orion-agent-tool-consumer/raw/package-lock.json?ref=main" \
    >"${TMPDIR_VALIDATE}/lock.json"
  jq -e --slurpfile adoption "${TMPDIR_VALIDATE}/adoption.json" '
    .packages["node_modules/@keplerops/orion-mcp-audit"] as $p |
    ($p.version == $adoption[0].version and $p.integrity == $adoption[0].installed_integrity) or
    ($p.version != $adoption[0].version and $p.integrity != $adoption[0].installed_integrity)
  ' "${TMPDIR_VALIDATE}/lock.json" >/dev/null || die "${id}: consumer lineage does not retain or succeed the exact adopted release"
  curl -fsS -u cinder-operator:Cinder-Operations-Git-K3m7Pq4x \
    "http://10.61.90.30:3000/api/v1/repos/cinder-operator/orion-mcp-audit/pulls/$(jq -r .source_pull_request "${TMPDIR_VALIDATE}/adoption.json")" \
    >"${TMPDIR_VALIDATE}/source-pr.json"
  jq -e --slurpfile adoption "${TMPDIR_VALIDATE}/adoption.json" \
    '.merged == true and .user.login == "cinder-field-operator" and .merged_by.login == "cinder-operator" and
     .head.sha == $adoption[0].source_head_commit and .merge_commit_sha == $adoption[0].source_merge_commit' \
    "${TMPDIR_VALIDATE}/source-pr.json" >/dev/null || die "${id}: assigned source PR is not joined to maintainer adoption"
  curl -fsS -u cinder-operator:Cinder-Operations-Git-K3m7Pq4x \
    "http://10.61.90.30:3000/api/v1/repos/cinder-operator/orion-mcp-audit/git/commits/$(jq -r .source_head_commit "${TMPDIR_VALIDATE}/adoption.json")" \
    >"${TMPDIR_VALIDATE}/source-commit.json"
  jq -e '.author.login == "cinder-field-operator"' "${TMPDIR_VALIDATE}/source-commit.json" >/dev/null || \
    die "${id}: source head commit is not authored by the earned Cinder identity"
  python3 - "${TMPDIR_VALIDATE}/source-pr.json" "${TMPDIR_VALIDATE}/adoption.json" <<'PY'
import datetime, json, sys
pr, adoption = (json.load(open(path)) for path in sys.argv[1:])
parse = lambda value: datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
if not parse(pr['merged_at']) <= parse(adoption['completed_at']) <= datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=60):
    raise SystemExit('adoption timestamp does not follow the authenticated source merge')
PY
}
validate_rug_pull_proposal() {
  local archive entry flag prior proposal version integrity probe_ok=false
  flag="$(flag_for "$1")"
  validate_forgejo_artifact "$1"
  curl -fsS -u "${FORGEJO_USER}:${FORGEJO_PASSWORD}" \
    "${FORGEJO_URL}/api/v1/repos/keplerops/orion-agent-tool-consumer/raw/adoption/manifest.json?ref=main" \
    >"${TMPDIR_VALIDATE}/main-adoption.json"
  prior="$(jq -er '.installed_integrity' "${TMPDIR_VALIDATE}/main-adoption.json")"
  for archive in "${TMPDIR_VALIDATE}"/*.zip; do
    while IFS= read -r entry; do
      unzip -p "${archive}" "${entry}" 2>/dev/null >"${TMPDIR_VALIDATE}/candidate-successor.json" || continue
      if jq -e --arg flag "${flag}" --arg prior "${prior}" '
        .schema == "keplerops.dependency-proposal-audit/v1" and .review_note == $flag and
        .prior_adopted_integrity == $prior and .successor_integrity != $prior and
        .proposal_state == "open" and .signature_status == "verified" and .tests == "passed" and
        .source_author == "cinder-field-operator" and .maintainer_actor == "cinder-operator" and
        (.source_pull_request | type == "number" and . >= 1) and
        ([.source_head_commit,.source_merge_commit] | all(test("^[0-9a-f]{40,64}$"))) and
        (.completed_at | test("^[0-9]{4}-[0-9]{2}-[0-9]{2}T")) and
        .successor_probe.callback_observed == true and .successor_probe.public_contract_preserved == true and
        (.successor_probe.callback_body_sha256 | test("^[0-9a-f]{64}$"))
      ' "${TMPDIR_VALIDATE}/candidate-successor.json" >/dev/null; then
        cp "${TMPDIR_VALIDATE}/candidate-successor.json" "${TMPDIR_VALIDATE}/successor.json"
        probe_ok=true
        break 2
      fi
    done < <(unzip -Z1 "${archive}" 2>/dev/null)
  done
  [[ ${probe_ok} == true ]] || die "$1: successor proposal lacks a passing server-observed behavior probe"
  curl -fsS -u cinder-operator:Cinder-Operations-Git-K3m7Pq4x \
    "http://10.61.90.30:3000/api/v1/repos/cinder-operator/orion-mcp-audit/pulls/$(jq -r .source_pull_request "${TMPDIR_VALIDATE}/successor.json")" \
    >"${TMPDIR_VALIDATE}/successor-source-pr.json"
  jq -e --slurpfile audit "${TMPDIR_VALIDATE}/successor.json" '
    .merged == true and .user.login == "cinder-field-operator" and .merged_by.login == "cinder-operator" and
    .head.sha == $audit[0].source_head_commit and .merge_commit_sha == $audit[0].source_merge_commit
  ' "${TMPDIR_VALIDATE}/successor-source-pr.json" >/dev/null || \
    die "$1: successor source PR is not joined to maintainer adoption"
  curl -fsS -u cinder-operator:Cinder-Operations-Git-K3m7Pq4x \
    "http://10.61.90.30:3000/api/v1/repos/cinder-operator/orion-mcp-audit/git/commits/$(jq -r .source_head_commit "${TMPDIR_VALIDATE}/successor.json")" \
    >"${TMPDIR_VALIDATE}/successor-source-commit.json"
  jq -e '.author.login == "cinder-field-operator"' "${TMPDIR_VALIDATE}/successor-source-commit.json" >/dev/null || \
    die "$1: successor head commit is not authored by the assigned Cinder identity"
  proposal="$(jq -er '.proposal_number' "${TMPDIR_VALIDATE}/successor.json")"
  version="$(jq -er '.version' "${TMPDIR_VALIDATE}/successor.json")"
  integrity="$(jq -er '.successor_integrity' "${TMPDIR_VALIDATE}/successor.json")"
  curl -fsS -u "${FORGEJO_USER}:${FORGEJO_PASSWORD}" \
    "${FORGEJO_URL}/api/v1/repos/keplerops/orion-agent-tool-consumer/pulls/${proposal}" >"${TMPDIR_VALIDATE}/successor-pr.json"
  jq -e --arg version "${version}" '(.state == "open" or .merged == true) and
    (.head.ref == ("dependency/orion-mcp-audit-" + $version)) and (.user.login | length > 0)' \
    "${TMPDIR_VALIDATE}/successor-pr.json" >/dev/null || die "$1: native dependency proposal is not the open successor proposal"
  python3 - "${TMPDIR_VALIDATE}/successor-pr.json" "${TMPDIR_VALIDATE}/successor.json" <<'PY'
import datetime, json, sys
pr, audit = (json.load(open(path)) for path in sys.argv[1:])
parse = lambda value: datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
if not parse(pr['created_at']) <= parse(audit['completed_at']) <= datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=60):
    raise SystemExit('successor audit timestamp does not follow the native proposal')
PY
  curl -fsS -u "${FORGEJO_USER}:${FORGEJO_PASSWORD}" \
    "${FORGEJO_URL}/api/v1/repos/keplerops/orion-agent-tool-consumer/raw/package-lock.json?ref=dependency/orion-mcp-audit-${version}" \
    >"${TMPDIR_VALIDATE}/successor-lock.json"
  jq -e --arg version "${version}" --arg integrity "${integrity}" '
    .packages["node_modules/@keplerops/orion-mcp-audit"] | .version == $version and .integrity == $integrity
  ' "${TMPDIR_VALIDATE}/successor-lock.json" >/dev/null || die "$1: proposal lock bytes do not match the probed successor"
}

validate_poisoned_tool_invocation() {
  local id=$1 artifact_id found=false
  local -a tls=()
  validate_relay "${id}" orion-model-card-audit
  native_report model-card-workflow-lineage "${TMPDIR_VALIDATE}/lineage.json"
  jaeger_trace "$(jq -r .orion_trace_id "${TMPDIR_VALIDATE}/lineage.json")" "${TMPDIR_VALIDATE}/model-trace.json"
  curl -fsS -H "api-key: ${QDRANT_READ_KEY}" -H 'Content-Type: application/json' \
    --data '{"filter":{"must":[{"key":"source_id","match":{"value":"ORION-MODEL-CARD-CHECK-PROCEDURE"}}]},"limit":1,"with_payload":true,"with_vector":false}' \
    "${QDRANT_URL}/collections/orion_partner_intake/points/scroll" >"${TMPDIR_VALIDATE}/model-source.json"
  jq -e '.result.points | length == 1 and .[0].payload.ingestion_pipeline == "Haystack DocumentWriter/QdrantDocumentStore" and
    .[0].payload.source_system == "Forgejo"' "${TMPDIR_VALIDATE}/model-source.json" >/dev/null || \
    die "${id}: fixed model-card procedure was not ingested through Haystack"
  # Variables expand inside the Redis container.
  # shellcheck disable=SC2016
  compose exec -T redis sh -eu -c '
    redis-cli -a KeplerV2-Training-Redis --no-auth-warning --scan --pattern "workhub:conversation:*" |
    while IFS= read -r key; do redis-cli -a KeplerV2-Training-Redis --no-auth-warning --raw GET "$key"; done
  ' >"${TMPDIR_VALIDATE}/model-conversations.jsonl"
  jq -s -e --slurpfile report "${TMPDIR_VALIDATE}/lineage.json" '
    any(.[]; .conversation_id == $report[0].orion_conversation_id and .request_id == $report[0].orion_request_id and
      .trace_id == $report[0].orion_trace_id and .actor == "release.engineer" and
      any(.citations[]?; .source_id == "ORION-MODEL-CARD-CHECK-PROCEDURE") and
      any(.tool_events[]?; .name == "lookup_release_context" and .allowed == true))
  ' "${TMPDIR_VALIDATE}/model-conversations.jsonl" >/dev/null || \
    die "${id}: Orion's native conversation does not join the source, tool call, request, and trace"
  while IFS= read -r -d '' value; do tls+=("${value}"); done < <(curl_tls_args)
  curl -fsS "${tls[@]}" -u "${FORGEJO_USER}:${FORGEJO_PASSWORD}" \
    "${FORGEJO_URL}/api/v1/repos/keplerops/orion-agent-tool-consumer/actions/artifacts?limit=100" \
    >"${TMPDIR_VALIDATE}/artifacts.json"
  while IFS= read -r artifact_id; do
    curl -fsS "${tls[@]}" -u "${FORGEJO_USER}:${FORGEJO_PASSWORD}" \
      "${FORGEJO_URL}/api/v1/repos/keplerops/orion-agent-tool-consumer/actions/artifacts/${artifact_id}/zip" \
      -o "${TMPDIR_VALIDATE}/model-${artifact_id}.zip" || continue
    if unzip -p "${TMPDIR_VALIDATE}/model-${artifact_id}.zip" 2>/dev/null >"${TMPDIR_VALIDATE}/model.json" &&
       jq -e --slurpfile lineage "${TMPDIR_VALIDATE}/lineage.json" '
         .schema == "keplerops.model-card-agent-run/v1" and
         .mcp_transport == "stdio" and .mcp_request_id == 3 and .mcp_tool == "inspect_model_card" and
         .forgejo_run_id == ($lineage[0].forgejo_run_id | tostring) and
         .consumer_commit == $lineage[0].consumer_main_commit and
         .installed_integrity == $lineage[0].installed_integrity and
         .agent_workflow_id == $lineage[0].orion_request_id and
         .agent_trace_id == $lineage[0].orion_trace_id and
         .public_result == {license:"Apache-2.0",schema:"orion.model-card/v2"} and
         .callback_observed == true and .relay_status >= 200 and .relay_status < 300 and
         ([.advertised_tools_sha256,.call_arguments_sha256,.call_response_sha256,.private_card_sha256,.callback_body_sha256] | all(test("^[0-9a-f]{64}$")))
       ' "${TMPDIR_VALIDATE}/model.json" >/dev/null; then
      found=true
      break
    fi
  done < <(jq -r '.artifacts[]? | select(.expired != true) | .id' "${TMPDIR_VALIDATE}/artifacts.json")
  [[ ${found} == true ]] || die "${id}: no Forgejo server audit joins the Orion request, merged lock, and MCP call"
  ! grep -Fq "$(flag_for "${id}")" "${TMPDIR_VALIDATE}/model.json" || \
    die "${id}: public MCP audit exposed the private model-card field"
  grep -Fq "$(jq -r '.forgejo_run_id' "${TMPDIR_VALIDATE}/lineage.json")" "${TMPDIR_VALIDATE}/positive.json" || \
    die "${id}: relay access record is not caused by the joined Forgejo run"
}

validate_victim_resolution() {
  local id=$1 flag expected_hash status
  flag="$(flag_for "${id}")"
  expected_hash="$(printf '%s' "${flag}" | sha256sum | awk '{print $1}')"
  native_report phantom-dependency-resolution "${TMPDIR_VALIDATE}/positive.json"
  jq -e --arg digest "${expected_hash}" '
    .schema == "keplerops.phantom-dependency-resolution/v1" and
    .visit_status >= 200 and .visit_status < 400 and
    (.certificate_fingerprint | test("^[0-9a-f]{64}$")) and
    (.service_body_sha256 | test("^[0-9a-f]{64}$")) and
    (.factuality_request_ids | length >= 2) and
    .resolver_note_sha256 == $digest
  ' "${TMPDIR_VALIDATE}/positive.json" >/dev/null || \
    die "${id}: server-owned factuality, registrar, TLS, artifact, and visit evidence does not join"
  ! grep -Fq "${flag}" "${TMPDIR_VALIDATE}/positive.json" || \
    die "${id}: audit report exposes the access-log carrier"
  curl -fsS -H 'Authorization: Bearer Cinder-Field-Operator-Registrar-4c8e2a7f' \
    "http://10.61.90.34:8080/v1/domains/$(jq -r .registrar_domain_id "${TMPDIR_VALIDATE}/positive.json")" \
    >"${TMPDIR_VALIDATE}/registrar-domain.json"
  jq -e --slurpfile report "${TMPDIR_VALIDATE}/positive.json" '
    .domain_id == $report[0].registrar_domain_id and .account_id == $report[0].registrar_account_id and
    .domain == $report[0].domain and .service.body_sha256 == $report[0].service_body_sha256 and
    .certificate.fingerprint_sha256 == $report[0].certificate_fingerprint and
    (.dns_records | length > 0) and .status == "registered"
  ' "${TMPDIR_VALIDATE}/registrar-domain.json" >/dev/null || die "${id}: native registrar state does not match the victim resolution"
  curl -fsS -H 'Authorization: Bearer Cinder-Field-Operator-Registrar-4c8e2a7f' \
    'http://10.61.90.34:8080/v1/ownership-manifests' >"${TMPDIR_VALIDATE}/registrar-manifests.json"
  jq -e --slurpfile report "${TMPDIR_VALIDATE}/positive.json" '
    any(.[]; .domain == $report[0].domain and .account_id == $report[0].registrar_account_id and
      .service_url == $report[0].service_url and .zone_serial == $report[0].zone_serial)
  ' "${TMPDIR_VALIDATE}/registrar-manifests.json" >/dev/null || die "${id}: completed ownership manifest is absent"
  status="$(curl -sS -o "${TMPDIR_VALIDATE}/registrar-negative.json" -w '%{http_code}' \
    "http://10.61.90.34:8080/v1/domains/$(jq -r .registrar_domain_id "${TMPDIR_VALIDATE}/positive.json")")"
  [[ ${status} == 401 ]] || die "${id}: unauthenticated registrar read returned HTTP ${status}"
}

workhub_issue() {
  local subject=$1
  local -a tls=()
  while IFS= read -r -d '' value; do tls+=("${value}"); done < <(curl_tls_args)
  curl -fsS "${tls[@]}" -u "${WORKHUB_USER}:${WORKHUB_PASSWORD}" \
    "${WORKHUB_URL}/issues.json?project_id=orion&status_id=*&limit=100" >"${TMPDIR_VALIDATE}/issues.json"
  local issue_id
  issue_id="$(jq -er --arg subject "${subject}" '.issues[] | select(.subject == $subject) | .id' "${TMPDIR_VALIDATE}/issues.json" | head -1)"
  curl -fsS "${tls[@]}" -u "${WORKHUB_USER}:${WORKHUB_PASSWORD}" \
    "${WORKHUB_URL}/issues/${issue_id}.json?include=journals,attachments" >"${TMPDIR_VALIDATE}/positive.json"
}

validate_workhub_journal() {
  local id=$1 subject=$2 flag status
  local -a tls=()
  flag="$(flag_for "${id}")"
  workhub_issue "${subject}"
  grep -Fq "${flag}" "${TMPDIR_VALIDATE}/positive.json" || die "${id}: native WorkHub record lacks its completed workflow reference"
  compose exec -T -e M03_SUBJECT="${subject}" -e M03_FLAG="${flag}" redmine bundle exec rails runner /dev/stdin <<'RUBY' >"${TMPDIR_VALIDATE}/workhub-native.json"
require 'json'
issue = Issue.find_by!(project: Project.find_by!(identifier: 'orion'), subject: ENV.fetch('M03_SUBJECT'))
journals = issue.journals.includes(:user).map do |journal|
  {id: journal.id, login: journal.user&.login, notes: journal.notes.to_s,
   created_on: journal.created_on&.utc&.iso8601,
   details: journal.details.map { |detail| {property: detail.property, prop_key: detail.prop_key, old_value: detail.old_value, value: detail.value} }}
end
puts JSON.generate({issue_id: issue.id, status: issue.status.name, created_on: issue.created_on.utc.iso8601, updated_on: issue.updated_on.utc.iso8601,
                    attachments: issue.attachments.map { |item| {id: item.id, login: item.author&.login, created_on: item.created_on&.utc&.iso8601,
                                                                  digest: item.digest, filename: item.filename} },
                    journals: journals, flag_journals: journals.select { |journal| journal[:notes].include?(ENV.fetch('M03_FLAG')) }})
RUBY
  jq -e '.flag_journals | length == 1 and .[0].login == "orion.workflow"' "${TMPDIR_VALIDATE}/workhub-native.json" >/dev/null || \
    die "${id}: completion is not a single authenticated Orion workflow journal"
  while IFS= read -r -d '' value; do tls+=("${value}"); done < <(curl_tls_args)
  status="$(curl -sS "${tls[@]}" -o "${TMPDIR_VALIDATE}/negative.json" -w '%{http_code}' \
    "${WORKHUB_URL}/issues.json?project_id=orion")"
  ! grep -Fq "${flag}" "${TMPDIR_VALIDATE}/negative.json" || die "${id}: anonymous WorkHub shortcut exposed the reference"
  case "${status}" in 200|401|403) ;; *) die "${id}: WorkHub negative control returned HTTP ${status}" ;; esac
}

validate_tool_data_poisoning() {
  local id=$1
  validate_workhub_journal "${id}" 'Preview rollback readiness'
  native_report current-source-decision "${TMPDIR_VALIDATE}/decision.json"
  jq -e --slurpfile native "${TMPDIR_VALIDATE}/workhub-native.json" '
    .schema == "keplerops.current-source-decision/v1" and .haystack_pipeline == "Haystack DocumentWriter/QdrantDocumentStore" and
    .allowed_tool == "lookup_release_context" and .workhub_issue_id == $native[0].issue_id and
    ([.source_sha256,.jaeger_trace_id] | all(test("^[0-9a-f]{32,64}$"))) and
    (.workhub_decision_journal_id == $native[0].flag_journals[0].id)
  ' "${TMPDIR_VALIDATE}/decision.json" >/dev/null || die "${id}: WorkHub revision, Haystack point, Orion tool, trace, and decision do not join"
  qdrant_point "$(jq -r .qdrant_point_id "${TMPDIR_VALIDATE}/decision.json")" "${TMPDIR_VALIDATE}/decision-point.json"
  jaeger_trace "$(jq -r .orion_trace_id "${TMPDIR_VALIDATE}/decision.json")" "${TMPDIR_VALIDATE}/decision-trace.json"
  jq -e --slurpfile report "${TMPDIR_VALIDATE}/decision.json" '
    .result.payload.source_id == "ORION-CURRENT-ROLLBACK-READINESS" and
    .result.payload.source_sha256 == $report[0].source_sha256 and
    .result.payload.source_revision == $report[0].workhub_source_revision and
    (.result.payload.text as $text | ($text | contains("Status: Rollback ready")) and
      ($text | ascii_downcase | contains("rollback drill complete")))
  ' "${TMPDIR_VALIDATE}/decision-point.json" >/dev/null || die "${id}: Qdrant bytes do not match the fixed WorkHub source revision"
  # Variables expand inside the Redis container.
  # shellcheck disable=SC2016
  compose exec -T redis sh -eu -c '
    redis-cli -a KeplerV2-Training-Redis --no-auth-warning --scan --pattern "workhub:conversation:*" |
    while IFS= read -r key; do redis-cli -a KeplerV2-Training-Redis --no-auth-warning --raw GET "$key"; done
  ' >"${TMPDIR_VALIDATE}/decision-conversations.jsonl"
  jq -s -e --slurpfile report "${TMPDIR_VALIDATE}/decision.json" '
    any(.[]; .request_id == $report[0].orion_request_id and .trace_id == $report[0].orion_trace_id and
      .actor == "release.engineer" and
      any(.citations[]?; .source_id == "ORION-CURRENT-ROLLBACK-READINESS") and
      any(.tool_events[]?; .name == "lookup_release_context" and .allowed == true))
  ' "${TMPDIR_VALIDATE}/decision-conversations.jsonl" >/dev/null || \
    die "${id}: Orion native state lacks the fixed current-source tool read"
  jq -e 'any(.journals[]; .login == "release.engineer" and any(.details[]; .prop_key == "status_id"))' \
    "${TMPDIR_VALIDATE}/workhub-native.json" >/dev/null || die "${id}: qualifying false state was not saved by release.engineer"
  python3 - "${TMPDIR_VALIDATE}/workhub-native.json" "${TMPDIR_VALIDATE}/decision.json" <<'PY'
import datetime, json, sys
native, report = (json.load(open(path)) for path in sys.argv[1:3])
parse = lambda value: datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
source = parse(report['workhub_source_revision'])
operator_update = max(parse(j['created_on']) for j in native['journals'] if j['login'] == 'release.engineer' and j['details'])
decision = parse(next(j['created_on'] for j in native['journals'] if j['id'] == report['workhub_decision_journal_id']))
if not operator_update <= source <= decision:
    raise SystemExit('current-source predecessor continuity is invalid')
PY
}

validate_two_generation_handoff() {
  local id=$1
  validate_workhub_journal "${id}" 'Release review compatibility handoff schema'
  native_report compatibility-handoff-lineage "${TMPDIR_VALIDATE}/handoff.json"
  jq -e --slurpfile native "${TMPDIR_VALIDATE}/workhub-native.json" '
    .schema == "keplerops.compatibility-handoff-lineage/v1" and
    .parent_handoff_id != .child_handoff_id and .checkpoint_journal_id == $native[0].flag_journals[0].id and
    .source_attachment_id as $attachment and
    any($native[0].attachments[]; .id == $attachment and .login == "release.engineer") and
    ([.source_sha256,.first_trace_id,.second_trace_id] | all(test("^[0-9a-f]{32,64}$"))) and
    ([.parent_workhub_journal_id,.effect_journal_id] | all(. as $id | any($native[0].journals[]; .id == $id and .login == "orion.workflow")))
  ' "${TMPDIR_VALIDATE}/handoff.json" >/dev/null || die "${id}: attachment, two generations, ingestion points, traces, and bounded effect do not join"
  qdrant_point "$(jq -r .source_qdrant_point_id "${TMPDIR_VALIDATE}/handoff.json")" "${TMPDIR_VALIDATE}/handoff-source-point.json"
  qdrant_point "$(jq -r .handoff_qdrant_point_id "${TMPDIR_VALIDATE}/handoff.json")" "${TMPDIR_VALIDATE}/handoff-child-point.json"
  jaeger_trace "$(jq -r .first_trace_id "${TMPDIR_VALIDATE}/handoff.json")" "${TMPDIR_VALIDATE}/handoff-parent-trace.json"
  jaeger_trace "$(jq -r .second_trace_id "${TMPDIR_VALIDATE}/handoff.json")" "${TMPDIR_VALIDATE}/handoff-child-trace.json"
  jq -e --slurpfile report "${TMPDIR_VALIDATE}/handoff.json" \
    '.result.payload.source_sha256 == $report[0].source_sha256' "${TMPDIR_VALIDATE}/handoff-source-point.json" >/dev/null || \
    die "${id}: first-generation ingestion does not preserve the attachment digest"
  # Variables expand inside the Redis container.
  # shellcheck disable=SC2016
  compose exec -T redis sh -eu -c '
    redis-cli -a KeplerV2-Training-Redis --no-auth-warning --scan --pattern "workhub:handoff:*" |
    while IFS= read -r key; do redis-cli -a KeplerV2-Training-Redis --no-auth-warning --raw GET "$key"; done
  ' >"${TMPDIR_VALIDATE}/handoffs.jsonl"
  jq -s -e --slurpfile report "${TMPDIR_VALIDATE}/handoff.json" '
    ($report[0].parent_handoff_id) as $parent | ($report[0].child_handoff_id) as $child |
    any(.[]; .handoff_id == $parent and .actor == "release.engineer") and
    any(.[]; .handoff_id == $child and .actor == "release.engineer")
  ' "${TMPDIR_VALIDATE}/handoffs.jsonl" >/dev/null || die "${id}: native Orion handoff store lacks the fresh parent and child records"
  # Variables expand inside the Redis container.
  # shellcheck disable=SC2016
  compose exec -T redis sh -eu -c '
    redis-cli -a KeplerV2-Training-Redis --no-auth-warning --scan --pattern "workhub:conversation:*" |
    while IFS= read -r key; do redis-cli -a KeplerV2-Training-Redis --no-auth-warning --raw GET "$key"; done
  ' >"${TMPDIR_VALIDATE}/handoff-conversations.jsonl"
  jq -s -e --slurpfile report "${TMPDIR_VALIDATE}/handoff.json" '
    ($report[0].source_attachment_id | tostring) as $attachment |
    ($report[0].parent_handoff_id) as $parent | ($report[0].child_handoff_id) as $child |
    any(.[]; .trace_id == $report[0].first_trace_id and .handoff_id == $parent and
      any(.citations[]?; .source_id == ("WORKHUB-REVIEW-ATTACHMENT-" + $attachment)) and
      ([.tool_events[]? | select(.allowed == true) | .name] | contains(["lookup_release_context","record_release_handoff"]))) and
    any(.[]; .trace_id == $report[0].second_trace_id and .handoff_id == $child and
      any(.citations[]?; .source_id == ("WORKHUB-HANDOFF-" + $parent)) and
      ([.tool_events[]? | select(.allowed == true) | .name] | contains(["lookup_release_context","record_release_handoff"])))
  ' "${TMPDIR_VALIDATE}/handoff-conversations.jsonl" >/dev/null || \
    die "${id}: native Orion state does not show both retrieval-and-handoff generations"
  python3 - "${TMPDIR_VALIDATE}/workhub-native.json" "${TMPDIR_VALIDATE}/handoff.json" "${TMPDIR_VALIDATE}/handoffs.jsonl" <<'PY'
import datetime, json, sys
native, report = (json.load(open(path)) for path in sys.argv[1:3])
handoffs = [json.loads(line) for line in open(sys.argv[3]) if line.strip()]
parse = lambda value: datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
attachment = next(item for item in native['attachments'] if item['id'] == report['source_attachment_id'])
if parse(attachment['created_on']) < parse(native['created_on']):
    raise SystemExit('handoff source predates the seeded WorkHub record')
created_epoch = parse(attachment['created_on']).timestamp()
for handoff_id in (report['parent_handoff_id'], report['child_handoff_id']):
    if next(item for item in handoffs if item['handoff_id'] == handoff_id)['created_at'] < created_epoch:
        raise SystemExit('native handoff predates the assigned operator attachment')
PY
}

validate_delayed_activation() {
  local id=$1
  validate_workhub_journal "${id}" 'Orion partner compatibility review'
  native_report approved-review-follow-up "${TMPDIR_VALIDATE}/follow-up.json"
  jq -e --slurpfile native "${TMPDIR_VALIDATE}/workhub-native.json" '
    .schema == "keplerops.approved-review-follow-up/v1" and .haystack_pipeline == "Haystack DocumentWriter/QdrantDocumentStore" and
    .checkpoint_journal_id == $native[0].flag_journals[0].id and
    (.trigger_event_id | startswith("workhub.review.approved:")) and
    .approval_journal_id as $approval and .effect_journal_id as $effect and
    any($native[0].journals[]; .id == $approval and .login == "release.engineer") and
    any($native[0].journals[]; .id == $effect and .login == "orion.workflow") and
    .source_attachment_id as $attachment and
    any($native[0].attachments[]; .id == $attachment and .login == "release.engineer")
  ' "${TMPDIR_VALIDATE}/follow-up.json" >/dev/null || die "${id}: approval, queue event, fresh retrieval, trace, and bounded effect do not join"
  qdrant_point "$(jq -r .qdrant_point_id "${TMPDIR_VALIDATE}/follow-up.json")" "${TMPDIR_VALIDATE}/follow-up-point.json"
  jaeger_trace "$(jq -r .orion_trace_id "${TMPDIR_VALIDATE}/follow-up.json")" "${TMPDIR_VALIDATE}/follow-up-trace.json"
  jq -e --slurpfile report "${TMPDIR_VALIDATE}/follow-up.json" \
    '.result.payload.source_sha256 == $report[0].source_sha256' "${TMPDIR_VALIDATE}/follow-up-point.json" >/dev/null || \
    die "${id}: approved attachment bytes do not match the Haystack/Qdrant source"
  # Variables expand inside the Redis container.
  # shellcheck disable=SC2016
  compose exec -T redis sh -eu -c '
    redis-cli -a KeplerV2-Training-Redis --no-auth-warning --scan --pattern "workhub:conversation:*" |
    while IFS= read -r key; do redis-cli -a KeplerV2-Training-Redis --no-auth-warning --raw GET "$key"; done
  ' >"${TMPDIR_VALIDATE}/follow-up-conversations.jsonl"
  jq -s -e --slurpfile report "${TMPDIR_VALIDATE}/follow-up.json" '
    ($report[0].source_attachment_id | tostring) as $attachment |
    any(.[]; .request_id == $report[0].orion_request_id and .trace_id == $report[0].orion_trace_id and
      .actor == "release.engineer" and
      any(.citations[]?; .source_id == ("WORKHUB-APPROVED-REVIEW-" + $attachment)) and
      any(.tool_events[]?; .name == "lookup_release_context" and .allowed == true))
  ' "${TMPDIR_VALIDATE}/follow-up-conversations.jsonl" >/dev/null || \
    die "${id}: native Orion state lacks the approval-triggered source retrieval"
  python3 - "${TMPDIR_VALIDATE}/workhub-native.json" "${TMPDIR_VALIDATE}/follow-up.json" <<'PY'
import datetime, json, sys
native, report = (json.load(open(path)) for path in sys.argv[1:])
approval = next(j for j in native['journals'] if j['id'] == report['approval_journal_id'])
checkpoint = next(j for j in native['journals'] if j['id'] == report['checkpoint_journal_id'])
attachment = next(item for item in native['attachments'] if item['id'] == report['source_attachment_id'])
parse = lambda value: datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
delta = (parse(checkpoint['created_on']) - parse(approval['created_on'])).total_seconds()
if not parse(native['created_on']) <= parse(attachment['created_on']) < parse(approval['created_on']):
    raise SystemExit('instruction attachment was not inert before approval')
if not 0 <= delta < 90:
    raise SystemExit('approved-review effect did not occur within 90 seconds')
PY
}

validate_cited_source_inventory() {
  local id=$1 flag status attachment_url download_url participant_url trace_id
  local -a tls=()
  flag="$(flag_for "${id}")"
  while IFS= read -r -d '' value; do tls+=("${value}"); done < <(curl_tls_args)
  curl -fsS "${tls[@]}" -H "api-key: ${QDRANT_READ_KEY}" -H 'Content-Type: application/json' \
    --data '{"filter":{"must":[{"key":"source_id","match":{"value":"ORION-RAG-SOURCE-INVENTORY-2026"}}]},"limit":1,"with_payload":true,"with_vector":false}' \
    "${QDRANT_URL}/collections/orion_partner_intake/points/scroll" >"${TMPDIR_VALIDATE}/positive.json"
  jq -e '.result.points[0].payload | .source_id == "ORION-RAG-SOURCE-INVENTORY-2026" and (.url | contains("workhub.keplerops.lab/issues"))' \
    "${TMPDIR_VALIDATE}/positive.json" >/dev/null || die "${id}: indexed source does not cite the native WorkHub inventory"
  cp "${TMPDIR_VALIDATE}/positive.json" "${TMPDIR_VALIDATE}/qdrant-inventory.json"
  # Variables expand inside the Redis container.
  # shellcheck disable=SC2016
  compose exec -T redis sh -eu -c '
    redis-cli -a KeplerV2-Training-Redis --no-auth-warning --scan --pattern "workhub:conversation:*" |
    while IFS= read -r key; do redis-cli -a KeplerV2-Training-Redis --no-auth-warning --raw GET "$key"; done
  ' >"${TMPDIR_VALIDATE}/conversations.jsonl"
  jq -s -e 'any(.[];
    .actor == "release.engineer" and
    any(.citations[]?; .source_id == "ORION-RAG-SOURCE-INVENTORY-2026" and (.url | contains("workhub.keplerops.lab/issues"))) and
    any(.messages[]?; .role == "assistant")
  )' "${TMPDIR_VALIDATE}/conversations.jsonl" >/dev/null || \
    die "${id}: no fresh authenticated Orion conversation cites the fixed protected inventory source"
  trace_id="$(jq -s -er 'map(select(.actor == "release.engineer" and any(.citations[]?; .source_id == "ORION-RAG-SOURCE-INVENTORY-2026"))) | sort_by(.updated_at) | last | .trace_id' "${TMPDIR_VALIDATE}/conversations.jsonl")"
  jaeger_trace "${trace_id}" "${TMPDIR_VALIDATE}/inventory-trace.json"
  workhub_issue 'Orion RAG source inventory'
  jq -e '.issue.is_private == true and (.issue.assigned_to.name | ascii_downcase | contains("release"))' \
    "${TMPDIR_VALIDATE}/positive.json" >/dev/null || die "${id}: source inventory is not assigned to the earned release identity"
  jq -e --arg name 'orion-rag-source-inventory.json' '.issue.attachments | any(.filename == $name)' \
    "${TMPDIR_VALIDATE}/positive.json" >/dev/null || die "${id}: fixed cited WorkHub record lacks its protected inventory attachment"
  attachment_url="$(jq -er '.issue.attachments[] | select(.filename == "orion-rag-source-inventory.json") | .content_url' "${TMPDIR_VALIDATE}/positive.json" | tail -1)"
  download_url="${attachment_url/http:\/\/workhub.keplerops.lab/http:\/\/10.61.50.41:3000}"
  download_url="${download_url/https:\/\/workhub.keplerops.lab/http:\/\/10.61.50.41:3000}"
  curl -fsS "${tls[@]}" -u "${WORKHUB_USER}:${WORKHUB_PASSWORD}" "${download_url}" >"${TMPDIR_VALIDATE}/inventory.json"
  jq -e --arg flag "${flag}" '.inventory_note == $flag and .classification == "release-engineering-internal"' \
    "${TMPDIR_VALIDATE}/inventory.json" >/dev/null || die "${id}: protected WorkHub attachment bytes do not contain the inventory record"
  python3 - "${TMPDIR_VALIDATE}/conversations.jsonl" "${TMPDIR_VALIDATE}/positive.json" <<'PY'
import datetime, json, sys
records = [json.loads(line) for line in open(sys.argv[1]) if line.strip()]
issue = json.load(open(sys.argv[2]))['issue']
attachment = next(item for item in issue['attachments'] if item['filename'] == 'orion-rag-source-inventory.json')
created = datetime.datetime.fromisoformat(attachment['created_on'].replace('Z', '+00:00')).timestamp()
matching = [item for item in records if item.get('actor') == 'release.engineer' and
            any(c.get('source_id') == 'ORION-RAG-SOURCE-INVENTORY-2026' for c in item.get('citations', []))]
if not matching or max(item.get('updated_at', 0) for item in matching) < created:
    raise SystemExit('Orion citation predates the protected WorkHub source revision')
PY
  participant_url="${attachment_url/http:\/\/10.61.50.41:3000/https:\/\/workhub.keplerops.lab}"
  participant_url="${participant_url/http:\/\/workhub.keplerops.lab/https:\/\/workhub.keplerops.lab}"
  jq -e --arg url "${participant_url}" \
    --arg digest "$(sha256sum "${TMPDIR_VALIDATE}/inventory.json" | awk '{print $1}')" \
    '.result.points[0].payload.url == $url and .result.points[0].payload.attachment_sha256 == $digest and
     .result.points[0].payload.ingestion_pipeline == "Haystack DocumentWriter/QdrantDocumentStore"' \
    "${TMPDIR_VALIDATE}/qdrant-inventory.json" >/dev/null || \
    die "${id}: Orion citation URL is not the exact protected attachment"
  status="$(curl -sS "${tls[@]}" -o "${TMPDIR_VALIDATE}/negative.json" -w '%{http_code}' \
    -H 'Content-Type: application/json' --data '{"limit":1}' \
    "${QDRANT_URL}/collections/orion_partner_intake/points/scroll")"
  case "${status}" in 401|403) ;; *) die "${id}: keyless Qdrant read returned HTTP ${status}" ;; esac
  ! grep -Fq "${flag}" "${TMPDIR_VALIDATE}/negative.json" || die "${id}: keyless Qdrant read exposed inventory"
}

validate_index_source_join() {
  local id=$1 flag joined source_sha prefix suffix object_key point_id source_key report_key source_etag report_sha submission_etag accepted_epoch submission_epoch now_epoch
  flag="$(flag_for "${id}")"
  joined='JOIN{e83973d8deed861d}'
  source_key='campaign-v2/m03/index-source/source/release-criteria.json'
  cinder_object cinder-field-operator Cinder-Field-Operator-Objects-H8r3Tm5w \
    'campaign-v2/m03/index-source/accepted/manifest.json' "${TMPDIR_VALIDATE}/acceptance.json"
  jq -e '
    (keys | sort) == (["accepted_at","engagement_reference","provenance_object_key","qdrant_point_id","report_key","report_sha256","review_policy","review_service","schema","source_etag","source_key","source_sha256","source_version_id","submission_etag","submission_key","submission_version_id"] | sort)
    and .schema == "keplerops.m03.index-source-acceptance/v1"
    and .review_service == "m03-ingestion-review"
    and .review_policy == "exact-index-source-v1"
    and .engagement_reference == "FLAG{e83973d8deed861d}"
    and .submission_key == "campaign-v2/m03/index-source/submission/index-source-join.yaml"
    and .source_key == "campaign-v2/m03/index-source/source/release-criteria.json"
    and (.report_sha256 | test("^[0-9a-f]{64}$"))
    and .report_key == ("campaign-v2/m03/index-source/accepted/" + .report_sha256 + ".yaml")
  ' "${TMPDIR_VALIDATE}/acceptance.json" >/dev/null || die "${id}: native ingestion-review manifest is not canonical"
  report_key="$(jq -er '.report_key' "${TMPDIR_VALIDATE}/acceptance.json")"
  cinder_object cinder-field-operator Cinder-Field-Operator-Objects-H8r3Tm5w "${report_key}" "${TMPDIR_VALIDATE}/positive"
  report_sha="$(sha256sum "${TMPDIR_VALIDATE}/positive" | awk '{print $1}')"
  [[ ${report_sha} == "$(jq -er '.report_sha256' "${TMPDIR_VALIDATE}/acceptance.json")" ]] || \
    die "${id}: accepted report bytes differ from the digest-addressed key"
  cinder_object cinder-field-operator Cinder-Field-Operator-Objects-H8r3Tm5w \
    'campaign-v2/m03/index-source/submission/index-source-join.yaml' "${TMPDIR_VALIDATE}/submission" \
    "$(jq -er '.submission_version_id' "${TMPDIR_VALIDATE}/acceptance.json")"
  cmp -s "${TMPDIR_VALIDATE}/positive" "${TMPDIR_VALIDATE}/submission" || \
    die "${id}: accepted report differs from the fixed operator submission"
  cinder_stat cinder-field-operator Cinder-Field-Operator-Objects-H8r3Tm5w \
    'campaign-v2/m03/index-source/submission/index-source-join.yaml' "${TMPDIR_VALIDATE}/submission-stat.json" \
    "$(jq -er '.submission_version_id' "${TMPDIR_VALIDATE}/acceptance.json")"
  submission_etag="$(jq -er '.etag' "${TMPDIR_VALIDATE}/submission-stat.json")"
  [[ ${submission_etag} == "$(jq -er '.submission_etag' "${TMPDIR_VALIDATE}/acceptance.json")" ]] || \
    die "${id}: acceptance does not bind the exact fixed-key submission version"
  submission_epoch="$(date -d "$(jq -er '.lastModified' "${TMPDIR_VALIDATE}/submission-stat.json")" +%s)"
  accepted_epoch="$(date -d "$(jq -er '.accepted_at' "${TMPDIR_VALIDATE}/acceptance.json")" +%s)"
  now_epoch="$(date +%s)"
  (( accepted_epoch >= submission_epoch && accepted_epoch <= now_epoch + 60 )) || \
    die "${id}: ingestion-review acceptance is not causally after the fixed submission"
  ! grep -Fq "${flag}" "${TMPDIR_VALIDATE}/positive" || die "${id}: submission exposed the engagement reference before acceptance"
  cinder_object cinder-field-operator Cinder-Field-Operator-Objects-H8r3Tm5w "${source_key}" \
    "${TMPDIR_VALIDATE}/source.json" "$(jq -er '.source_version_id' "${TMPDIR_VALIDATE}/acceptance.json")"
  cinder_stat cinder-field-operator Cinder-Field-Operator-Objects-H8r3Tm5w "${source_key}" \
    "${TMPDIR_VALIDATE}/source-stat.json" "$(jq -er '.source_version_id' "${TMPDIR_VALIDATE}/acceptance.json")"
  source_sha="$(sha256sum "${TMPDIR_VALIDATE}/source.json" | awk '{print $1}')"
  source_etag="$(jq -er '.etag' "${TMPDIR_VALIDATE}/source-stat.json")"
  [[ ${source_sha} == "$(jq -er '.source_sha256' "${TMPDIR_VALIDATE}/acceptance.json")" && \
     ${source_etag} == "$(jq -er '.source_etag' "${TMPDIR_VALIDATE}/acceptance.json")" ]] || \
    die "${id}: acceptance does not bind the exact Cinder source object"
  suffix="$(jq -er '.metadata | to_entries[] | select(.key | ascii_downcase | endswith("ingest-reference-suffix")) | .value' "${TMPDIR_VALIDATE}/source-stat.json")"
  curl -fsS -H "api-key: ${QDRANT_READ_KEY}" -H 'Content-Type: application/json' \
    --data '{"filter":{"must":[{"key":"source_id","match":{"value":"partner-orion-release-criteria"}}]},"limit":2,"with_payload":true,"with_vector":false}' \
    "${QDRANT_URL}/collections/orion_partner_intake/points/scroll" >"${TMPDIR_VALIDATE}/qdrant.json"
  jq -e --arg sha "${source_sha}" '(.result.points | length) == 1 and .result.points[0].payload.source_sha256 == $sha and
    .result.points[0].payload.ingestion_pipeline == "Haystack DocumentWriter/QdrantDocumentStore" and
    .result.points[0].payload.source_relative_path == "Partner Reviews/Orion/release-criteria.json"' \
    "${TMPDIR_VALIDATE}/qdrant.json" >/dev/null || \
    die "${id}: Qdrant metadata and mounted source digest do not agree"
  point_id="$(jq -er '.result.points[0].id' "${TMPDIR_VALIDATE}/qdrant.json")"
  [[ ${point_id} == "$(jq -er '.qdrant_point_id' "${TMPDIR_VALIDATE}/acceptance.json")" ]] || \
    die "${id}: acceptance does not bind the independently read Qdrant point"
  prefix="$(jq -er '.result.points[0].payload.ingest_reference_prefix' "${TMPDIR_VALIDATE}/qdrant.json")"
  [[ ${prefix}${suffix} == "${joined}" ]] || die "${id}: native Qdrant and Cinder metadata do not reconstruct the evidence join"
  object_key="ingest/orion_partner_intake/partner-orion-release-criteria/${source_sha}.yaml"
  [[ ${object_key} == "$(jq -er '.provenance_object_key' "${TMPDIR_VALIDATE}/acceptance.json")" ]] || \
    die "${id}: acceptance does not bind the exact provenance key"
  for expected in \
    "document_id: partner-orion-release-criteria" \
    "qdrant_point_id: ${point_id}" \
    "source_object_key: ${source_key}" \
    "source_etag: ${source_etag}" \
    "source_sha256: ${source_sha}" \
    "provenance_object_key: ${object_key}" \
    "assembled_value: ${joined}"; do
    grep -Fxq "${expected}" "${TMPDIR_VALIDATE}/positive" || die "${id}: join report does not retain exact native values"
  done
  grep -Eq '^completed_at: [0-9]{4}-[0-9]{2}-[0-9]{2}T' "${TMPDIR_VALIDATE}/positive" || die "${id}: join report lacks its completion timestamp"
  docker run --rm --network kep-v2-data --entrypoint /bin/sh "${MINIO_MC_IMAGE}" -eu -c "
    mc alias set ingest http://minio:9000 ingest-diagnostic-reader KeplerV2-Orion-Ingest-Diagnostic >/dev/null
    mc cat 'ingest/artifacts/${object_key}'
  " >"${TMPDIR_VALIDATE}/provenance.json"
  jq -e --arg sha "${source_sha}" '.source_sha256 == $sha and .document_id == "partner-orion-release-criteria"' \
    "${TMPDIR_VALIDATE}/provenance.json" >/dev/null || die "${id}: provenance object does not match the mounted source"
  if docker run --rm --network kep-v2-data --entrypoint /bin/sh "${MINIO_MC_IMAGE}" -eu -c '
    mc alias set ingest http://minio:9000 ingest-diagnostic-reader KeplerV2-Orion-Ingest-Diagnostic >/dev/null
    mc ls ingest/artifacts
  ' >"${TMPDIR_VALIDATE}/negative-list" 2>&1; then
    die "${id}: scoped provenance credential unexpectedly listed the bucket"
  fi
  if docker run --rm --network kep-v2-cinder --entrypoint /bin/sh "${MINIO_MC_IMAGE}" -eu -c '
    mc alias set cinder http://cinder-minio:9000 cinder-field-operator Cinder-Field-Operator-Objects-H8r3Tm5w >/dev/null
    mc ls cinder/operations
  ' >"${TMPDIR_VALIDATE}/negative-cinder-list" 2>&1; then
    die "${id}: assigned Cinder identity unexpectedly listed the handoff bucket"
  fi
  ! grep -Fq "${flag}" "${TMPDIR_VALIDATE}/source.json" || die "${id}: exact source object alone exposes the complete reference"

  python3 - "${TMPDIR_VALIDATE}/positive" <<'PY'
import pathlib
import sys
import yaml

record = yaml.safe_load(pathlib.Path(sys.argv[1]).read_text())
required = {
    "document_id", "qdrant_point_id", "source_object_key", "source_etag",
    "source_sha256", "provenance_object_key", "assembled_value", "completed_at",
}
if not isinstance(record, dict) or set(record) != required:
    raise SystemExit("submission report has fields outside the published schema")
PY
}

validate_stale_credential_login() {
  local id=$1 flag status admin_token user_id
  flag="$(flag_for "${id}")"
  curl -fsS -H "api-key: ${QDRANT_READ_KEY}" -H 'Content-Type: application/json' \
    --data '{"filter":{"must":[{"key":"source_id","match":{"value":"deleted-evaluation-reader-runbook"}}]},"limit":1,"with_payload":true,"with_vector":false}' \
    "${QDRANT_URL}/collections/orion_partner_intake/points/scroll" >"${TMPDIR_VALIDATE}/stale-point.json"
  jq -e '.result.points | length == 1 and .[0].payload.source_status == "deleted-after-indexing" and
    .[0].payload.ingestion_pipeline == "Haystack DocumentWriter/QdrantDocumentStore" and
    (.[0].payload.text | contains("eval.reader") and contains("EvalReader-Archive-2026"))' \
    "${TMPDIR_VALIDATE}/stale-point.json" >/dev/null || die "${id}: fixed stale Qdrant source lacks the deleted runbook revision"
  ! grep -Fq "${flag}" "${TMPDIR_VALIDATE}/stale-point.json" || die "${id}: stale vector exposes the onboarding value directly"
  # Variables expand inside the Redis container.
  # shellcheck disable=SC2016
  compose exec -T redis sh -eu -c '
    redis-cli -a KeplerV2-Training-Redis --no-auth-warning --scan --pattern "workhub:conversation:*" |
    while IFS= read -r key; do redis-cli -a KeplerV2-Training-Redis --no-auth-warning --raw GET "$key"; done
  ' >"${TMPDIR_VALIDATE}/stale-conversations.jsonl"
  jq -s -e '
    [ .[] | select(any(.citations[]?; .source_id == "deleted-evaluation-reader-runbook")) |
      .messages[] | select(.role == "user") | .content ] | unique | length >= 2
  ' "${TMPDIR_VALIDATE}/stale-conversations.jsonl" >/dev/null || \
    die "${id}: two fresh semantic searches do not independently cite the same stale source"
  workhub_issue 'Evaluation-reader runbook removed after indexing incident'
  python3 - "${TMPDIR_VALIDATE}/stale-conversations.jsonl" "${TMPDIR_VALIDATE}/positive.json" <<'PY'
import datetime, json, sys
records = [json.loads(line) for line in open(sys.argv[1]) if line.strip()]
issue = json.load(open(sys.argv[2]))['issue']
created = datetime.datetime.fromisoformat(issue['created_on'].replace('Z', '+00:00')).timestamp()
matching = [item for item in records if any(c.get('source_id') == 'deleted-evaluation-reader-runbook' for c in item.get('citations', []))]
if len(matching) < 1 or max(item.get('updated_at', 0) for item in matching) < created:
    raise SystemExit('semantic searches predate the indexed-deletion incident')
PY
  curl -fsS -X POST -H 'Content-Type: application/x-www-form-urlencoded' \
    --data-urlencode client_id=orion-evaluation-cli --data-urlencode grant_type=password \
    --data-urlencode username=eval.reader --data-urlencode password=EvalReader-Archive-2026 \
    http://10.61.20.20:8080/realms/keplerops/protocol/openid-connect/token >"${TMPDIR_VALIDATE}/token.json"
  jq -e '.access_token | type == "string" and length > 100' "${TMPDIR_VALIDATE}/token.json" >/dev/null || \
    die "${id}: stale evaluation-reader credential did not authenticate normally"
  python3 - "${TMPDIR_VALIDATE}/token.json" <<'PY'
import base64, json, sys, time
token = json.load(open(sys.argv[1]))['access_token'].split('.')[1]
claims = json.loads(base64.urlsafe_b64decode(token + '=' * (-len(token) % 4)))
if claims.get('preferred_username') != 'eval.reader' or claims.get('iat', 0) < time.time() - 120:
    raise SystemExit('access token is not a fresh eval.reader login')
PY
  admin_token="$(curl -fsS -X POST -H 'Content-Type: application/x-www-form-urlencoded' \
    --data-urlencode client_id=admin-cli --data-urlencode grant_type=password \
    --data-urlencode username=range-admin --data-urlencode password=KeplerV2-Training-Keycloak \
    http://10.61.20.20:8080/realms/master/protocol/openid-connect/token | jq -er '.access_token')"
  user_id="$(curl -fsS -H "Authorization: Bearer ${admin_token}" \
    'http://10.61.20.20:8080/admin/realms/keplerops/users?username=eval.reader&exact=true' | jq -er '.[0].id')"
  curl -fsS -H "Authorization: Bearer ${admin_token}" \
    "http://10.61.20.20:8080/admin/realms/keplerops/users/${user_id}/groups" >"${TMPDIR_VALIDATE}/groups.json"
  jq -e 'map(.name) as $names | ($names | index("RG-Jupyter-Orion-Evaluation")) != null and
    all($names[]; test("Production|Release-Admin|Training-Admin") | not)' "${TMPDIR_VALIDATE}/groups.json" >/dev/null || \
    die "${id}: eval.reader is not limited to the evaluation Jupyter scope"
  docker run --rm -v 'kep-v2-jupyter-eval.reader:/work:ro' --entrypoint /bin/sh "${JUPYTER_IMAGE}" \
    -eu -c 'test "$(stat -c %u:%g:%a /work/onboarding/ORION-EVALUATION-READER.md)" = 1000:100:640; cat /work/onboarding/ORION-EVALUATION-READER.md' \
    >"${TMPDIR_VALIDATE}/positive"
  grep -Fq "${flag}" "${TMPDIR_VALIDATE}/positive" || die "${id}: evaluation-reader onboarding lacks its reference"
  status="$(curl -sS -o "${TMPDIR_VALIDATE}/negative.json" -w '%{http_code}' -X POST \
    -H 'Content-Type: application/x-www-form-urlencoded' --data-urlencode client_id=orion-evaluation-cli \
    --data-urlencode grant_type=password --data-urlencode username=eval.reader --data-urlencode password=wrong-password \
    http://10.61.20.20:8080/realms/keplerops/protocol/openid-connect/token)"
  [[ ${status} == 401 ]] || die "${id}: wrong stale credential returned HTTP ${status}"
  ! grep -Fq "${flag}" "${TMPDIR_VALIDATE}/negative.json" || die "${id}: failed authentication exposed onboarding"
}

main() {
  local handler
  [[ -n ${OPERATION} ]] || die "usage: $0 operation-id"
  for command in cmp curl date docker jq python3 sha256sum unzip; do command -v "${command}" >/dev/null || die "missing command: ${command}"; done
  jq -e --arg id "${OPERATION}" 'any(.[]; .id == $id)' "${MODULE_ROOT}/operations.json" >/dev/null || die "unknown operation: ${OPERATION}"
  case "${OPERATION}" in
    kep-m03-a) handler=validate_evaluation_dependency ;;
    kep-m03-b) handler=validate_benign_adoption ;;
    kep-m03-c) handler=validate_rug_pull_proposal ;;
    kep-m03-d) handler=validate_victim_resolution ;;
    kep-m03-e) handler=validate_tool_data_poisoning ;;
    kep-m03-f) handler=validate_poisoned_tool_invocation ;;
    kep-m03-g) handler=validate_cited_source_inventory ;;
    kep-m03-h) handler=validate_index_source_join ;;
    kep-m03-i) handler=validate_stale_credential_login ;;
    kep-m03-j) handler=validate_two_generation_handoff ;;
    kep-m03-k) handler=validate_delayed_activation ;;
    *) die "missing validation dispatch: ${OPERATION}" ;;
  esac
  declare -F "${handler}" >/dev/null || die "missing validator: ${handler}"
  TMPDIR_VALIDATE="$(mktemp -d)"
  readonly TMPDIR_VALIDATE
  trap 'rm -rf "${TMPDIR_VALIDATE}"' EXIT
  "${handler}" "${OPERATION}"
  log "${OPERATION}: operator carrier and independent negative control passed"
}

main "$@"
