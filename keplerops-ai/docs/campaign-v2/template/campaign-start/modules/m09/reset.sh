#!/usr/bin/env bash
set -Eeuo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MODULE_ROOT
TEMPLATE_ROOT="$(cd "${MODULE_ROOT}/../../.." && pwd)"
readonly TEMPLATE_ROOT
readonly OPERATION="${1:-}"
readonly STATE_ROOT="${CAMPAIGN_STATE_ROOT:-${TEMPLATE_ROOT}/state/campaign-start}/m09"
readonly FORGEJO_API="${FORGEJO_API_URL:-http://10.61.40.20:3000/api/v1}"
readonly CINDER_FORGEJO_API="${CINDER_FORGEJO_API_URL:-http://10.61.90.30:3000/api/v1}"
readonly HARBOR_API="${HARBOR_API_URL:-http://10.61.40.32:8080/api/v2.0}"
readonly MLFLOW_API="${MLFLOW_URL:-http://10.61.40.36:5000}"
readonly OPA_URL="${OPA_URL:-http://192.168.78.30:30082}"
readonly RABBITMQ_AMQP_URL="${M09_RESET_RABBITMQ_URL:-amqp://svc-review-verification:KeplerV2-Worker-Verification-Rabbit@10.61.50.12:5672/keplerops}"
readonly DRAIN_IMAGE="${M09_RESET_DRAIN_IMAGE:-keplerops/orion-import-review:campaign-v2-m09}"
readonly DRAIN_NETWORK="${M09_RESET_DRAIN_NETWORK:-kep-v2-data}"
readonly K3S01_SSH_TARGET="${K3S01_SSH_TARGET:-kepler@192.168.78.30}"
readonly K3S01_SSH_KEY="${K3S01_SSH_KEY:-/root/.ssh/keplerops-v2}"
readonly SSH=(ssh -i "${K3S01_SSH_KEY}" -o BatchMode=yes -o StrictHostKeyChecking=accept-new)

log() { printf '[campaign-m09 reset] %s\n' "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }
uri() { jq -rn --arg value "$1" '$value | @uri'; }

mlflow_post() {
  curl -fsS --user 'svc-orion-training:KeplerV2-Training-MLflow-Service' \
    -H 'Content-Type: application/json' -X POST --data "$2" "${MLFLOW_API}$1" >/dev/null
}

cleanup_mlflow() {
  local kind=$1 resource=$2
  case "${kind}" in
    run)
      mlflow_post /api/2.0/mlflow/runs/delete "$(jq -cn --arg run_id "$(jq -r '.run_id' <<<"${resource}")" '{run_id:$run_id}')"
      ;;
    model-version)
      mlflow_post /api/2.0/mlflow/model-versions/delete "$(jq -cn \
        --arg name "$(jq -r '.name' <<<"${resource}")" --arg version "$(jq -r '.version' <<<"${resource}")" \
        '{name:$name,version:$version}')"
      ;;
    alias)
      mlflow_post /api/2.0/mlflow/registered-models/alias "$(jq -cn \
        --arg name "$(jq -r '.name' <<<"${resource}")" --arg alias "$(jq -r '.alias' <<<"${resource}")" \
        --arg version "$(jq -r '.restore_version' <<<"${resource}")" \
        '{name:$name,alias:$alias,version:$version}')"
      ;;
    *) die "unsupported MLflow reset resource: ${kind}" ;;
  esac
}

harbor_label_id() {
  curl -fsS --user 'admin:KeplerV2-Training-Harbor' "${HARBOR_API}/labels?scope=g&page_size=100" | \
    jq -er --arg name "$1" '.[] | select(.name == $name) | .id'
}

harbor_artifact_path() {
  local repository=$1 digest=$2 project name
  project=${repository%%/*}; name=${repository#*/}
  printf '%s/projects/%s/repositories/%s/artifacts/%s' \
    "${HARBOR_API}" "$(uri "${project}")" "$(uri "${name}")" "$(uri "${digest}")"
}

cleanup_harbor() {
  local kind=$1 resource=$2 repository digest label label_id attempted restore
  case "${kind}" in
    artifact)
      [[ $(jq -r '.participant_owned' <<<"${resource}") == true ]] || return
      repository="$(jq -r '.repository' <<<"${resource}")"; digest="$(jq -r '.digest' <<<"${resource}")"
      curl -fsS --user 'admin:KeplerV2-Training-Harbor' -X DELETE \
        "$(harbor_artifact_path "${repository}" "${digest}")" >/dev/null 2>&1 || true
      ;;
    label-binding)
      label="$(jq -r '.label' <<<"${resource}")"; label_id="$(harbor_label_id "${label}")"
      attempted="$(harbor_artifact_path "$(jq -r '.attempted_repository' <<<"${resource}")" "$(jq -r '.attempted_digest' <<<"${resource}")")"
      restore="$(harbor_artifact_path "$(jq -r '.restore_repository' <<<"${resource}")" "$(jq -r '.restore_digest' <<<"${resource}")")"
      curl -fsS --user 'admin:KeplerV2-Training-Harbor' -X DELETE "${attempted}/labels/${label_id}" >/dev/null 2>&1 || true
      curl -fsS --user 'admin:KeplerV2-Training-Harbor' -H 'Content-Type: application/json' -X POST \
        --data "$(jq -cn --argjson id "${label_id}" '{id:$id}')" "${restore}/labels" >/dev/null
      ;;
    *) die "unsupported Harbor reset resource: ${kind}" ;;
  esac
}

cleanup_minio() {
  local bucket=$1 key=$2
  [[ ${bucket} == artifacts && ${key} =~ ^(release|model-mirror|model-review)/[A-Za-z0-9._:/-]+$ ]] || \
    die "unsafe MinIO reset target: ${bucket}/${key}"
  docker run --rm --network kep-v2-data minio/mc:RELEASE.2025-07-21T05-28-08Z sh -ec \
    "mc alias set kepler http://minio:9000 svc-orion-training KeplerV2-Training-Minio-Orion-Training >/dev/null; mc rm --force 'kepler/${bucket}/${key}' >/dev/null 2>&1 || true"
}

cleanup_opa() {
  local path=$1
  [[ ${path} =~ ^keplerops/m09/[A-Za-z0-9._:/-]+$ ]] || die "unsafe OPA reset target: ${path}"
  curl -fsS -X DELETE "${OPA_URL}/v1/data/${path}" >/dev/null 2>&1 || true
}

cleanup_kubernetes() {
  local kind=$1 resource=$2 namespace name restore
  namespace="$(jq -r '.namespace // empty' <<<"${resource}")"; name="$(jq -r '.name // empty' <<<"${resource}")"
  [[ ${namespace} =~ ^(orion-(evaluation|runtime)|argocd)$ && ${name} =~ ^[a-z0-9][a-z0-9-]{2,62}$ ]] || \
    die "unsafe Kubernetes reset target: ${namespace}/${name}"
  [[ ${kind} =~ ^(job|secret|application|inferenceservice|configmap|serviceaccount)$ ]] || die "unsafe Kubernetes reset kind: ${kind}"
  restore="$(jq -r '.restore_base64 // empty' <<<"${resource}")"
  if [[ -n ${restore} ]]; then
    printf '%s' "${restore}" | base64 -d | "${SSH[@]}" "${K3S01_SSH_TARGET}" \
      sudo k3s kubectl apply -f - >/dev/null
  else
    "${SSH[@]}" "${K3S01_SSH_TARGET}" sudo k3s kubectl -n "${namespace}" delete "${kind}/${name}" --ignore-not-found >/dev/null
  fi
  [[ ${kind} != job ]] || "${SSH[@]}" "${K3S01_SSH_TARGET}" sudo k3s kubectl -n "${namespace}" \
    delete "networkpolicy/${name}-deny" --ignore-not-found >/dev/null
}

cleanup_local() {
  local kind=$1 resource=$2 path restore existed
  path="$(jq -r '.path' <<<"${resource}")"
  case "${kind}" in
    promotion-capability)
      [[ ${path} =~ ^promotion-capabilities/[0-9a-f]{64}\.json$ ]] || die "unsafe capability marker: ${path}"
      rm -f -- "${STATE_ROOT}/${path}"
      ;;
    range-state-file)
      [[ ${path} == business-release.env ]] || \
        die "unsafe range-state reset target: ${path}"
      existed="$(jq -r '.existed' <<<"${resource}")"; restore="$(jq -r '.restore_base64' <<<"${resource}")"
      if [[ ${existed} == true ]]; then printf '%s' "${restore}" | base64 -d >"${TEMPLATE_ROOT}/state/${path}"; else rm -f -- "${TEMPLATE_ROOT}/state/${path}"; fi
      ;;
    *) die "unsupported local reset resource: ${kind}" ;;
  esac
}

cleanup_dispatcher() {
  local resource=$1 path issue
  path="$(jq -r '.path' <<<"${resource}")"; issue="$(jq -r '.issue' <<<"${resource}")"
  [[ ${issue} =~ ^[1-9][0-9]*$ && ${path} == "review-dispatch/${issue}.json" ]] || \
    die "unsafe dispatcher marker: ${path}"
  rm -f -- "${STATE_ROOT}/${path}"
}

restore_forgejo_file() {
  local resource=$1 cinder base auth owner repository path commit detail parent current parent_file payload
  cinder="$(jq -r '.cinder // false' <<<"${resource}")"
  if [[ ${cinder} == true ]]; then base=${CINDER_FORGEJO_API}; auth='cinder-operator:Cinder-Operations-Git-K3m7Pq4x'; else base=${FORGEJO_API}; auth='range-admin:KeplerV2-Training-Forgejo-Admin'; fi
  owner="$(jq -r '.owner' <<<"${resource}")"; repository="$(jq -r '.repository' <<<"${resource}")"
  path="$(jq -r '.path' <<<"${resource}")"; commit="$(jq -r '.commit' <<<"${resource}")"
  [[ ${owner}/${repository}/${path} =~ ^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+/[A-Za-z0-9._/-]+$ && ${commit} =~ ^[0-9a-f]{40}([0-9a-f]{24})?$ ]] || \
    die "unsafe Forgejo reset target"
  detail="$(curl -fsS --user "${auth}" "${base}/repos/${owner}/${repository}/git/commits/${commit}")"
  parent="$(jq -er '.parents[0].sha' <<<"${detail}")"
  current="$(curl -fsS --user "${auth}" "${base}/repos/${owner}/${repository}/contents/${path}")"
  if parent_file="$(curl -fsS --user "${auth}" "${base}/repos/${owner}/${repository}/contents/${path}?ref=${parent}" 2>/dev/null)"; then
    payload="$(jq -cn --arg content "$(jq -r '.content | gsub("\\n"; "")' <<<"${parent_file}")" \
      --arg sha "$(jq -r '.sha' <<<"${current}")" --arg message "Restore failed release attempt for ${path}" \
      '{content:$content,sha:$sha,message:$message,branch:"main"}')"
    curl -fsS --user "${auth}" -H 'Content-Type: application/json' -X PUT --data "${payload}" \
      "${base}/repos/${owner}/${repository}/contents/${path}" >/dev/null
  else
    payload="$(jq -cn --arg sha "$(jq -r '.sha' <<<"${current}")" --arg message "Remove failed release attempt for ${path}" \
      '{sha:$sha,message:$message,branch:"main"}')"
    curl -fsS --user "${auth}" -H 'Content-Type: application/json' -X DELETE --data "${payload}" \
      "${base}/repos/${owner}/${repository}/contents/${path}" >/dev/null
  fi
}

# Read-only Python drain that removes ONLY the failed attempt's own messages
# (matched by exact request id or the review-issue request prefix) from the
# shared review queues, requeuing every unrelated message.  This never purges
# unrelated or accepted attempts' evidence.
readonly DRAIN_SCRIPT='
import json, os
import pika
url = os.environ["RABBITMQ_URL"]
queues = [q for q in os.environ.get("DRAIN_QUEUES", "").split(",") if q]
exact = {v for v in os.environ.get("DRAIN_IDS", "").split("\n") if v}
prefixes = [f"forgejo-review-{i}-" for i in os.environ.get("DRAIN_ISSUES", "").split("\n") if i]
def owned(body, corr):
    rid = corr or ""
    try:
        rid = json.loads(body).get("request_id") or rid
    except Exception:
        pass
    return rid in exact or any(rid.startswith(p) for p in prefixes)
conn = pika.BlockingConnection(pika.URLParameters(url))
ch = conn.channel()
for queue in queues:
    try:
        ch.queue_declare(queue=queue, durable=True, passive=True)
    except Exception:
        ch = conn.channel()
        continue
    keep, seen = [], 0
    while seen < 20000:
        method, props, body = ch.basic_get(queue=queue, auto_ack=False)
        if not method:
            break
        seen += 1
        if not owned(body, getattr(props, "correlation_id", None)):
            keep.append((body, props))
        ch.basic_ack(method.delivery_tag)
    for body, props in keep:
        ch.basic_publish(exchange="", routing_key=queue, body=body, properties=props)
conn.close()
'

scoped_drain_queues() {
  local ids=$1 issues=$2
  command -v docker >/dev/null || { log "docker unavailable; skipping scoped queue drain"; return; }
  docker run --rm --network "${DRAIN_NETWORK}" \
    -e "RABBITMQ_URL=${RABBITMQ_AMQP_URL}" \
    -e "DRAIN_QUEUES=orion.review.m09-import,orion.review.m09-results,orion.review.m09-review-results" \
    -e "DRAIN_IDS=${ids}" -e "DRAIN_ISSUES=${issues}" \
    --entrypoint python "${DRAIN_IMAGE}" -c "${DRAIN_SCRIPT}" >/dev/null 2>&1 \
    || log "scoped queue drain reported no attempt-owned messages or was unavailable"
}

# Relay callback baskets are shared and captured requests are retained as audit
# history (like the Forgejo review issues); a failed attempt never rotates the
# basket token or clears unrelated or accepted callback captures.
retain_relay() {
  local basket=$1
  [[ -s ${STATE_ROOT}/relay/${basket}.token ]] || return
  log "relay basket ${basket}: captured callbacks retained as audit history; token preserved"
}

cleanup_resource() {
  local resource=$1 owner kind
  owner="$(jq -r '.owner' <<<"${resource}")"; kind="$(jq -r '.kind' <<<"${resource}")"
  case "${owner}" in
    mlflow) cleanup_mlflow "${kind}" "${resource}" ;;
    harbor) cleanup_harbor "${kind}" "${resource}" ;;
    minio) cleanup_minio "$(jq -r '.bucket' <<<"${resource}")" "$(jq -r '.key' <<<"${resource}")" ;;
    opa) cleanup_opa "$(jq -r '.path' <<<"${resource}")" ;;
    kubernetes) cleanup_kubernetes "${kind}" "${resource}" ;;
    forgejo) restore_forgejo_file "${resource}" ;;
    local) cleanup_local "${kind}" "${resource}" ;;
    dispatcher) cleanup_dispatcher "${resource}" ;;
    rabbitmq) : ;;
    *) die "reset manifest contains unsupported owner: ${owner}" ;;
  esac
}

main() {
  [[ -n ${OPERATION} ]] || die "usage: $0 <kep-m09-operation>"
  jq -e --arg id "${OPERATION}" 'any(.[]; .id == $id)' "${MODULE_ROOT}/operations.json" >/dev/null || die "unknown operation: ${OPERATION}"
  jq -e --arg id "${OPERATION}" '.operations[$id] and .successful_state' "${MODULE_ROOT}/reset-manifest.json" >/dev/null || \
    die "reset manifest has no declaration for ${OPERATION}"
  if [[ -s ${STATE_ROOT}/accepted/${OPERATION}.json ]]; then
    log "${OPERATION}: accepted owning-system checkpoint preserved"
    return
  fi
  local failed_root="${STATE_ROOT}/failed/${OPERATION}" manifest encoded drain_ids drain_issues
  if [[ -d ${failed_root} ]]; then
    while IFS= read -r manifest; do
      while IFS= read -r encoded; do cleanup_resource "$(base64 -d <<<"${encoded}")"; done \
        < <(jq -r '.resources | reverse[]? | @base64' "${manifest}")
    done < <(find "${failed_root}" -mindepth 1 -maxdepth 1 -type f -name '*.json' -print)
  fi
  # Collect this failed operation's own message identities so the queue drain
  # removes only attempt-owned messages, never unrelated or accepted evidence.
  drain_ids=""; drain_issues=""
  if [[ -d ${failed_root} ]]; then
    drain_ids="$(jq -rs '[.[].resources[]? | select(.owner=="rabbitmq") | .correlation_id // empty] | unique | .[]' \
      "${failed_root}"/*.json 2>/dev/null || true)"
    drain_issues="$(jq -rs '[.[].resources[]? | select(.owner=="dispatcher") | .issue // empty] | unique | .[]' \
      "${failed_root}"/*.json 2>/dev/null || true)"
  fi
  case "${OPERATION}" in
    kep-m09-i) scoped_drain_queues "${drain_ids}" "${drain_issues}"; retain_relay m09-import-exceptions ;;
    kep-m09-k) scoped_drain_queues "${drain_ids}" "${drain_issues}"; retain_relay m09-mirror-review ;;
  esac
  find "${STATE_ROOT}/attempts/${OPERATION}" -mindepth 1 -delete 2>/dev/null || true
  find "${failed_root}" -mindepth 1 -delete 2>/dev/null || true
  log "${OPERATION}: failed attempt resources cleaned from their owning systems; ancestors preserved"
}

main
