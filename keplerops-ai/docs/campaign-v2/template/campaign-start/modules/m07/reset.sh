#!/usr/bin/env bash
set -Eeuo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MODULE_ROOT
TEMPLATE_ROOT="$(cd "${MODULE_ROOT}/../../.." && pwd)"
readonly TEMPLATE_ROOT
readonly STATE_ROOT="${CAMPAIGN_STATE_ROOT:-${TEMPLATE_ROOT}/state/campaign-start}/m07"
readonly LABEL_STUDIO_URL="${LABEL_STUDIO_URL:-http://10.61.40.34:8080}"
readonly TRAINER_TOKEN=KAI-Orion-Trainer-2b68d419a7f340ce
readonly FORGEJO_API_URL="${FORGEJO_API_URL:-http://10.61.40.20:3000/api/v1}"
readonly FORGEJO_ADMIN_AUTH="${FORGEJO_ADMIN_AUTH:-range-admin:KeplerV2-Training-Forgejo-Admin}"
readonly MLFLOW_URL="${MLFLOW_URL:-http://10.61.40.36:5000}"
readonly MLFLOW_AUTH="${MLFLOW_AUTH:-range-admin:KeplerV2-Training-MLflow-Admin}"
readonly LAKEFS_URL="${LAKEFS_URL:-http://10.61.40.31:8000}"
readonly LAKEFS_AUTH="${LAKEFS_AUTH:-KeplerLakeFSAccess:KeplerV2-Training-LakeFS-Object-Key}"
readonly HARBOR_API_URL="${HARBOR_API_URL:-http://10.61.40.32:8080/api/v2.0}"
readonly HARBOR_ADMIN_AUTH="${HARBOR_ADMIN_AUTH:-admin:KeplerV2-Training-Harbor}"

die() { printf '[orion integrity reset] ERROR: %s\n' "$*" >&2; exit 1; }

accepted() {
  local slot=${1##*-} path="${STATE_ROOT}/accepted/${1##*-}.json"
  [[ -s ${path} ]] || return 1
  python3 - "${path}" "${slot}" <<'PY'
import hashlib, hmac, json, sys
path, slot = sys.argv[1:]
record = json.load(open(path, encoding="utf-8"))
signature = str(record.pop("signature", ""))
body = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
valid = record.get("schema") == "keplerops.integrity-checkpoint/v1" and record.get("slot") == slot
valid = valid and hmac.compare_digest(signature, hmac.new(b"KeplerOps-Integrity-Handoff-2026", body, hashlib.sha256).hexdigest())
raise SystemExit(0 if valid else 1)
PY
}

restore_labels() {
  local snapshot=$1
  [[ -s ${snapshot} ]] || die "label snapshot is missing: ${snapshot}"
  python3 - "${LABEL_STUDIO_URL}" "${TRAINER_TOKEN}" "${snapshot}" <<'PY'
import json, sys
import requests

url, token, baseline_path = sys.argv[1:]
headers = {"Authorization": f"Token {token}", "Content-Type": "application/json"}
projects = requests.get(f"{url}/api/projects", params={"page_size": 100}, headers=headers, timeout=30)
projects.raise_for_status()
project = next(item for item in projects.json()["results"] if item["title"] == "Orion Release Risk Training Baseline")
tasks = requests.get(f"{url}/api/tasks", params={"project": project["id"], "page_size": 100}, headers=headers, timeout=30)
tasks.raise_for_status()
baseline = json.load(open(baseline_path, encoding="utf-8"))
for summary in tasks.json()["tasks"]:
    record = baseline[summary["data"]["record_id"]]
    task = requests.get(f"{url}/api/tasks/{summary['id']}", headers=headers, timeout=30)
    task.raise_for_status()
    task = task.json()
    for annotation in task.get("annotations", []):
        response = requests.delete(f"{url}/api/annotations/{annotation['id']}", headers=headers, timeout=30)
        if response.status_code not in (200, 204):
            response.raise_for_status()
    response = requests.patch(f"{url}/api/tasks/{summary['id']}", headers=headers,
        json={"data": {"record_id": summary["data"]["record_id"], "text": record["text"]}}, timeout=30)
    response.raise_for_status()
    response = requests.post(f"{url}/api/tasks/{summary['id']}/annotations/", headers=headers,
        json={"result": [{"from_name": "risk", "to_name": "text", "type": "choices", "value": {"choices": [record["label"]]}}]}, timeout=30)
    response.raise_for_status()
PY
}

delete_lakefs_branch() {
  local branch=$1
  curl -fsS --user "${LAKEFS_AUTH}" -X DELETE \
    "${LAKEFS_URL}/api/v1/repositories/orion/branches/${branch}" >/dev/null 2>&1 || true
}

delete_failed_attestations() {
  local attempt_scope=$1 repository=$2 artifact digest encoded
  repository="${repository#cinder-datasets/}"
  encoded="$(jq -rn --arg value "${repository}" '$value | @uri')"
  while IFS=$'\t' read -r digest artifact; do
    [[ -n ${digest} && ${artifact} == "attested-${attempt_scope}-"* ]] || continue
    curl -fsS --user "${HARBOR_ADMIN_AUTH}" -X DELETE \
      "${HARBOR_API_URL}/projects/cinder-datasets/repositories/${encoded}/artifacts/${digest}" >/dev/null
  done < <(curl -fsS --user "${HARBOR_ADMIN_AUTH}" \
    "${HARBOR_API_URL}/projects/cinder-datasets/repositories/${encoded}/artifacts?page_size=100&with_tag=true" |
    jq -r '.[] | .digest as $digest | .tags[]? | [$digest,.name] | @tsv')
}

delete_attempt_mlflow_runs() {
  local operation=$1 attempt_id=$2 review_kind experiments runs run_id
  case "${operation}" in
    kep-m07-b) review_kind='poisoned-training-lineage' ;;
    kep-m07-c) review_kind='targeted-poison-evaluation' ;;
    kep-m07-e) review_kind='participant-backdoor-evaluation' ;;
    kep-m07-f) review_kind='holdout-integrity-evaluation' ;;
    kep-m07-g) review_kind='computation-graph-integrity' ;;
    *) return 0 ;;
  esac
  experiments="$(curl -fsS --user "${MLFLOW_AUTH}" -H 'Content-Type: application/json' -X POST \
    --data '{"max_results":100}' "${MLFLOW_URL}/api/2.0/mlflow/experiments/search")"
  while IFS= read -r experiment; do
    runs="$(curl -fsS --user "${MLFLOW_AUTH}" -H 'Content-Type: application/json' -X POST \
      --data "$(jq -cn --arg id "${experiment}" '{experiment_ids:[$id],max_results:1000}')" \
      "${MLFLOW_URL}/api/2.0/mlflow/runs/search")"
    while IFS= read -r run_id; do
      curl -fsS --user "${MLFLOW_AUTH}" -H 'Content-Type: application/json' -X POST \
        --data "$(jq -cn --arg id "${run_id}" '{run_id:$id}')" \
        "${MLFLOW_URL}/api/2.0/mlflow/runs/delete" >/dev/null
    done < <(jq -r --arg kind "${review_kind}" --arg attempt "${attempt_id}" \
      '.runs[]? | select(
        any(.data.tags[]?; .key == "review.kind" and .value == $kind) and
        any(.data.tags[]?; .key == "attempt.id" and .value == $attempt)
      ) | .info.run_id' <<<"${runs}")
  done < <(jq -r '.experiments[].experiment_id' <<<"${experiments}")
}

main() {
  local operation=${1:-} attempt_id=${2:-${M07_ATTEMPT_ID:-}} manifest attempt_scope
  jq -e --arg id "${operation}" 'any(.[]; .id == $id)' "${MODULE_ROOT}/operations.json" >/dev/null || die 'usage: reset.sh <kep-m07-operation>'
  [[ ${attempt_id} =~ ^[A-Za-z0-9][A-Za-z0-9._-]{7,95}$ ]] || \
    die 'usage: reset.sh <kep-m07-operation> <attempt-id>'
  attempt_scope="$(printf %s "${attempt_id}" | sha256sum | awk '{print substr($1,1,24)}')"
  if [[ ${operation} == kep-m07-i ]]; then
    manifest="${STATE_ROOT}/attempts/kep-m07-i/${attempt_id}.json"
  else
    manifest="${STATE_ROOT}/attempts/${operation}/${attempt_id}.json"
  fi
  [[ -s ${manifest} ]] || die 'attempt manifest does not exist for this operation and attempt ID'
  if jq -e '.status == "succeeded"' "${manifest}" >/dev/null; then
    printf '%s: successful attempt and immutable native records preserved\n' "${operation}"
    return 0
  fi
  case "${operation}" in
    kep-m07-a)
      if accepted kep-m07-a && [[ -s ${STATE_ROOT}/accepted-labels.json ]]; then
        restore_labels "${STATE_ROOT}/accepted-labels.json"
      else
        restore_labels "${STATE_ROOT}/baseline-labels.json"
      fi
      delete_lakefs_branch "m07-a-${attempt_scope}"
      ;;
    kep-m07-e) restore_labels "${STATE_ROOT}/accepted-labels.json" ;;
    kep-m07-d) delete_lakefs_branch "m07-d-${attempt_scope}" ;;
    kep-m07-f) delete_lakefs_branch "m07-f-${attempt_scope}" ;;
    kep-m07-h)
      delete_failed_attestations "${attempt_scope}" \
        "$(jq -r '.cleanup.harbor_repository // "cinder-datasets/orion-poisoned-dataset"' "${manifest}")"
      ;;
    kep-m07-b|kep-m07-c|kep-m07-g|kep-m07-i) : ;;
  esac
  delete_attempt_mlflow_runs "${operation}" "${attempt_id}"
  rm -f "${manifest}"
  printf '%s: mutable failed-attempt state reset; native audit history and immutable content-addressed records retained\n' "${operation}"
}

main "$@"
