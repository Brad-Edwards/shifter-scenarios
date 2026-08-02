#!/usr/bin/env bash
set -Eeuo pipefail

readonly MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly TEMPLATE_ROOT="$(cd "${MODULE_ROOT}/../../.." && pwd)"
readonly OPERATION="${1:-}"
readonly CINDER_RELAY_URL="${CINDER_RELAY_URL:-https://relay.cinder.lab}"
readonly FORGEJO_URL="${FORGEJO_URL:-https://git.keplerops.lab}"
readonly FORGEJO_USER="${FORGEJO_USER:-range-admin}"
readonly FORGEJO_PASSWORD="${FORGEJO_PASSWORD:-KeplerV2-Training-Forgejo-Admin}"
readonly WORKHUB_URL="${WORKHUB_URL:-https://workhub.keplerops.lab}"
readonly WORKHUB_USER="${WORKHUB_USER:-range-admin}"
readonly WORKHUB_PASSWORD="${WORKHUB_PASSWORD:-KeplerV2-Training-Redmine-Admin}"
readonly QDRANT_URL="${QDRANT_URL:-https://vectors.keplerops.lab}"
readonly QDRANT_READ_KEY="${QDRANT_READ_KEY:-KeplerV2-Training-Qdrant-Read}"
readonly JUPYTER_IMAGE="${JUPYTER_IMAGE:-$(sed -n 's/^JUPYTER_IMAGE=//p' "${TEMPLATE_ROOT}/component-lock.env")}"
readonly MINIO_MC_IMAGE="${MINIO_MC_IMAGE:-$(sed -n 's/^MINIO_MC_IMAGE=//p' "${TEMPLATE_ROOT}/engineering/component-lock.additions.env")}"

log() { printf '[campaign-m03-validate] %s\n' "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }
flag_for() { jq -er --arg id "$1" '.[] | select(.id == $id) | .flag' "${MODULE_ROOT}/operations.json"; }

curl_tls_args() {
  if [[ -n ${KEPLEROPS_CA_CERT:-} ]]; then printf '%s\0%s\0' --cacert "${KEPLEROPS_CA_CERT}"; fi
}

validate_relay() {
  local id=$1 basket=$2 token_file token flag status
  local -a tls=()
  flag="$(flag_for "${id}")"
  token_file="${TEMPLATE_ROOT}/state/campaign-start/m03/relay/${basket}.token"
  [[ -s ${token_file} ]] || die "${id}: ${basket} relay token is absent"
  token="$(<"${token_file}")"
  while IFS= read -r -d '' value; do tls+=("${value}"); done < <(curl_tls_args)
  curl -fsS "${tls[@]}" -H "Authorization: ${token}" \
    "${CINDER_RELAY_URL}/api/baskets/${basket}/requests" >"${TMPDIR_VALIDATE}/positive.json"
  grep -Fq "${flag}" "${TMPDIR_VALIDATE}/positive.json" || die "${id}: native relay record does not contain its reference"
  status="$(curl -sS "${tls[@]}" -o "${TMPDIR_VALIDATE}/negative.json" -w '%{http_code}' \
    "${CINDER_RELAY_URL}/api/baskets/${basket}/requests")"
  case "${status}" in 401|403) ;; *) die "${id}: tokenless relay read returned HTTP ${status}" ;; esac
  ! grep -Fq "${flag}" "${TMPDIR_VALIDATE}/negative.json" || die "${id}: tokenless relay read exposed the reference"
}

validate_evaluation_dependency() { validate_relay "$1" m03-evaluation-worker; }
validate_poisoned_tool_invocation() { validate_relay "$1" m03-model-card; }

validate_forgejo_artifact() {
  local id=$1 flag artifact_id found=false
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

  curl -fsS "${tls[@]}" -u "${FORGEJO_USER}:${FORGEJO_PASSWORD}" \
    "${FORGEJO_URL}/api/v1/repos/keplerops/orion-agent-tool-consumer/raw/.forgejo/workflows/verify-adoption.yml?ref=main" \
    >"${TMPDIR_VALIDATE}/workflow.yml"
  ! grep -Fq "${flag}" "${TMPDIR_VALIDATE}/workflow.yml" || die "${id}: workflow source exposes the secret-backed reference shortcut"
}

validate_benign_adoption() { validate_forgejo_artifact "$1"; }
validate_rug_pull_proposal() { validate_forgejo_artifact "$1"; }

validate_victim_resolution() {
  local id=$1 flag url auth
  flag="$(flag_for "${id}")"
  url="${M03_PHANTOM_ACCESS_LOG_URL:-}"
  auth="${M03_PHANTOM_ACCESS_LOG_AUTH_HEADER:-}"
  [[ -n ${url} ]] || die "${id}: M03_PHANTOM_ACCESS_LOG_URL must point to the participant service's normal access log"
  local -a args=(-fsS)
  [[ -z ${auth} ]] || args+=(-H "${auth}")
  curl "${args[@]}" "${url}" >"${TMPDIR_VALIDATE}/positive.log"
  grep -Fq "${flag}" "${TMPDIR_VALIDATE}/positive.log" || die "${id}: common review worker visit is absent"
  grep -Fq 'KeplerOps-Common-Review-Worker/2026.08' "${TMPDIR_VALIDATE}/positive.log" || die "${id}: participant self-request does not qualify"
  ! grep -E '(^|[^A-Za-z])curl/|participant-self-request' "${TMPDIR_VALIDATE}/positive.log" >/dev/null || \
    log "${id}: non-qualifying requests coexist with the qualifying worker visit"
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
  while IFS= read -r -d '' value; do tls+=("${value}"); done < <(curl_tls_args)
  status="$(curl -sS "${tls[@]}" -o "${TMPDIR_VALIDATE}/negative.json" -w '%{http_code}' \
    "${WORKHUB_URL}/issues.json?project_id=orion")"
  ! grep -Fq "${flag}" "${TMPDIR_VALIDATE}/negative.json" || die "${id}: anonymous WorkHub shortcut exposed the reference"
  case "${status}" in 200|401|403) ;; *) die "${id}: WorkHub negative control returned HTTP ${status}" ;; esac
}

validate_tool_data_poisoning() { validate_workhub_journal "$1" 'Preview rollback readiness'; }
validate_two_generation_handoff() { validate_workhub_journal "$1" 'Release review compatibility handoff schema'; }
validate_delayed_activation() { validate_workhub_journal "$1" 'Orion partner compatibility review'; }

validate_cited_source_inventory() {
  local id=$1 flag status
  local -a tls=()
  flag="$(flag_for "${id}")"
  while IFS= read -r -d '' value; do tls+=("${value}"); done < <(curl_tls_args)
  curl -fsS "${tls[@]}" -H "api-key: ${QDRANT_READ_KEY}" -H 'Content-Type: application/json' \
    --data '{"filter":{"must":[{"key":"source_id","match":{"value":"ORION-RAG-SOURCE-INVENTORY-2026"}}]},"limit":1,"with_payload":true,"with_vector":false}' \
    "${QDRANT_URL}/collections/orion_partner_intake/points/scroll" >"${TMPDIR_VALIDATE}/positive.json"
  jq -e '.result.points[0].payload | .source_id == "ORION-RAG-SOURCE-INVENTORY-2026" and (.url | contains("workhub.keplerops.lab/issues"))' \
    "${TMPDIR_VALIDATE}/positive.json" >/dev/null || die "${id}: indexed source does not cite the native WorkHub inventory"
  workhub_issue 'Orion RAG source inventory'
  grep -Fq "${flag}" "${TMPDIR_VALIDATE}/positive.json" || die "${id}: protected WorkHub inventory lacks its reference"
  status="$(curl -sS "${tls[@]}" -o "${TMPDIR_VALIDATE}/negative.json" -w '%{http_code}' \
    -H 'Content-Type: application/json' --data '{"limit":1}' \
    "${QDRANT_URL}/collections/orion_partner_intake/points/scroll")"
  case "${status}" in 401|403) ;; *) die "${id}: keyless Qdrant read returned HTTP ${status}" ;; esac
  ! grep -Fq "${flag}" "${TMPDIR_VALIDATE}/negative.json" || die "${id}: keyless Qdrant read exposed inventory"
}

validate_index_source_join() {
  local id=$1 flag source_sha prefix suffix object_key
  flag="$(flag_for "${id}")"
  docker run --rm -v 'kep-v2-jupyter-eval.reader:/work:ro' "${JUPYTER_IMAGE}" \
    sh -eu -c 'cat /work/failed-ingestion/reports/index-source-join.yaml' >"${TMPDIR_VALIDATE}/positive"
  grep -Fq "${flag}" "${TMPDIR_VALIDATE}/positive" || die "${id}: participant join report lacks the reconstructed reference"
  docker run --rm -v 'kep-v2-jupyter-eval.reader:/work:ro' "${JUPYTER_IMAGE}" python - <<'PY' >"${TMPDIR_VALIDATE}/source.json"
import hashlib
import json
import os
from pathlib import Path
source = Path('/work/failed-ingestion/source/release-criteria.json')
print(json.dumps({'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'suffix': os.getxattr(source, b'user.ingest_reference').decode()}))
PY
  source_sha="$(jq -er '.source_sha256' "${TMPDIR_VALIDATE}/source.json")"
  suffix="$(jq -er '.suffix' "${TMPDIR_VALIDATE}/source.json")"
  curl -fsS -H "api-key: ${QDRANT_READ_KEY}" -H 'Content-Type: application/json' \
    --data '{"filter":{"must":[{"key":"source_id","match":{"value":"partner-orion-release-criteria"}}]},"limit":1,"with_payload":true,"with_vector":false}' \
    "${QDRANT_URL}/collections/orion_partner_intake/points/scroll" >"${TMPDIR_VALIDATE}/qdrant.json"
  jq -e --arg sha "${source_sha}" '.result.points[0].payload.source_sha256 == $sha' "${TMPDIR_VALIDATE}/qdrant.json" >/dev/null || \
    die "${id}: Qdrant metadata and mounted source digest do not agree"
  prefix="$(jq -er '.result.points[0].payload.flag_prefix' "${TMPDIR_VALIDATE}/qdrant.json")"
  [[ ${prefix}${suffix} == "${flag}" ]] || die "${id}: native Qdrant and xattr carriers do not reconstruct the reference"
  object_key="ingest/orion_partner_intake/partner-orion-release-criteria/${source_sha}.yaml"
  docker run --rm --network kep-v2-data "${MINIO_MC_IMAGE}" sh -eu -c "
    mc alias set ingest http://minio:9000 ingest-diagnostic-reader KeplerV2-Orion-Ingest-Diagnostic >/dev/null
    mc cat 'ingest/artifacts/${object_key}'
  " >"${TMPDIR_VALIDATE}/provenance.json"
  jq -e --arg sha "${source_sha}" '.source_sha256 == $sha and .document_id == "partner-orion-release-criteria"' \
    "${TMPDIR_VALIDATE}/provenance.json" >/dev/null || die "${id}: provenance object does not match the mounted source"
  if docker run --rm --network kep-v2-data "${MINIO_MC_IMAGE}" sh -eu -c '
    mc alias set ingest http://minio:9000 ingest-diagnostic-reader KeplerV2-Orion-Ingest-Diagnostic >/dev/null
    mc ls ingest/artifacts
  ' >"${TMPDIR_VALIDATE}/negative-list" 2>&1; then
    die "${id}: scoped provenance credential unexpectedly listed the bucket"
  fi
  docker run --rm -v 'kep-v2-jupyter-eval.reader:/work:ro' "${JUPYTER_IMAGE}" \
    sh -eu -c 'cat /work/failed-ingestion/source/release-criteria.json' >"${TMPDIR_VALIDATE}/negative"
  ! grep -Fq "${flag}" "${TMPDIR_VALIDATE}/negative" || die "${id}: mounted source alone exposes the complete reference"
}

validate_stale_credential_login() {
  local id=$1 flag status
  flag="$(flag_for "${id}")"
  curl -fsS -X POST -H 'Content-Type: application/x-www-form-urlencoded' \
    --data-urlencode client_id=orion-evaluation-cli --data-urlencode grant_type=password \
    --data-urlencode username=eval.reader --data-urlencode password=EvalReader-Archive-2026 \
    http://10.61.20.20:8080/realms/keplerops/protocol/openid-connect/token >"${TMPDIR_VALIDATE}/token.json"
  jq -e '.access_token | type == "string" and length > 100' "${TMPDIR_VALIDATE}/token.json" >/dev/null || \
    die "${id}: stale evaluation-reader credential did not authenticate normally"
  docker run --rm -v 'kep-v2-jupyter-eval.reader:/work:ro' "${JUPYTER_IMAGE}" \
    cat /work/onboarding/ORION-EVALUATION-READER.md >"${TMPDIR_VALIDATE}/positive"
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
  for command in curl docker jq unzip; do command -v "${command}" >/dev/null || die "missing command: ${command}"; done
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
  log "${OPERATION}: participant carrier and negative control passed"
}

main "$@"
