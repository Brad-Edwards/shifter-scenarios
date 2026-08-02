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

die() { printf '[campaign-m07 reset] ERROR: %s\n' "$*" >&2; exit 1; }

accepted() {
  [[ ",${M07_ACCEPTED_OPERATIONS:-}," == *",$1,"* ]]
}

preserve_or_continue() {
  if accepted "$1"; then
    printf '%s: earned checkpoint preserved\n' "$1"
    return 1
  fi
  return 0
}

restore_labels() {
  [[ -s ${STATE_ROOT}/baseline-labels.json ]] || die 'clean label snapshot is missing'
  python3 - "${LABEL_STUDIO_URL}" "${TRAINER_TOKEN}" "${STATE_ROOT}/baseline-labels.json" <<'PY'
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

restore_holdout() {
  local clean current sha payload
  clean="$(curl -fsS --user "${FORGEJO_ADMIN_AUTH}" "${FORGEJO_API_URL}/repos/keplerops/orion-model-integrity/contents/evaluation/holdout.clean.json")"
  current="$(curl -fsS --user "${FORGEJO_ADMIN_AUTH}" "${FORGEJO_API_URL}/repos/keplerops/orion-model-integrity/contents/evaluation/holdout.json")"
  sha="$(jq -er '.sha' <<<"${current}")"
  payload="$(jq -cn --arg content "$(jq -r '.content' <<<"${clean}" | tr -d '\n')" --arg sha "${sha}" \
    '{content:$content,sha:$sha,message:"Restore clean holdout after failed evaluation",branch:"main"}')"
  curl -fsS --user "${FORGEJO_ADMIN_AUTH}" -H 'Content-Type: application/json' -X PUT --data "${payload}" \
    "${FORGEJO_API_URL}/repos/keplerops/orion-model-integrity/contents/evaluation/holdout.json" >/dev/null
}

delete_failed_mlflow_runs() {
  local operation=$1 experiments runs run_id status
  experiments="$(curl -fsS --user "${MLFLOW_AUTH}" -H 'Content-Type: application/json' -X POST \
    --data '{"max_results":100}' "${MLFLOW_URL}/api/2.0/mlflow/experiments/search")"
  while IFS= read -r experiment; do
    runs="$(curl -fsS --user "${MLFLOW_AUTH}" -H 'Content-Type: application/json' -X POST \
      --data "$(jq -cn --arg id "${experiment}" '{experiment_ids:[$id],max_results:1000}')" \
      "${MLFLOW_URL}/api/2.0/mlflow/runs/search")"
    while IFS=$'\t' read -r run_id status; do
      [[ ${status} == FAILED || ${status} == KILLED ]] || continue
      curl -fsS --user "${MLFLOW_AUTH}" -H 'Content-Type: application/json' -X POST \
        --data "$(jq -cn --arg id "${run_id}" '{run_id:$id}')" \
        "${MLFLOW_URL}/api/2.0/mlflow/runs/delete" >/dev/null
    done < <(jq -r --arg operation "${operation}" '.runs[]? | select(any(.data.tags[]?; .key == "operation" and .value == $operation)) | [.info.run_id,.info.status] | @tsv' <<<"${runs}")
  done < <(jq -r '.experiments[].experiment_id' <<<"${experiments}")
}

main() {
  local operation=${1:-}
  jq -e --arg id "${operation}" 'any(.[]; .id == $id)' "${MODULE_ROOT}/operations.json" >/dev/null || die 'usage: reset.sh <kep-m07-operation>'
  preserve_or_continue "${operation}" || return 0
  case "${operation}" in
    kep-m07-a) restore_labels ;;
    kep-m07-f) restore_holdout ;;
    kep-m07-b|kep-m07-c|kep-m07-d|kep-m07-e|kep-m07-g|kep-m07-h|kep-m07-i) : ;;
  esac
  delete_failed_mlflow_runs "${operation}"
  rm -f "${STATE_ROOT}/applied/${operation}"
  printf '%s: failed-attempt state reset; successful immutable artifacts were retained\n' "${operation}"
}

main "$@"
