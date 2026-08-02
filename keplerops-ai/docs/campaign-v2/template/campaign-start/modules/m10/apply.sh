#!/usr/bin/env bash
set -Eeuo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MODULE_ROOT
TEMPLATE_ROOT="$(cd "${MODULE_ROOT}/../../.." && pwd)"
readonly TEMPLATE_ROOT
readonly OPERATION="${1:-all}"
readonly STATE_ROOT="${CAMPAIGN_STATE_ROOT:-${TEMPLATE_ROOT}/state/campaign-start}/m10"
readonly K3S01_SSH_TARGET="${K3S01_SSH_TARGET:-kepler@192.168.78.30}"
readonly K3S01_SSH_KEY="${K3S01_SSH_KEY:-/root/.ssh/keplerops-v2}"
readonly REDMINE_URL="${REDMINE_URL:-http://10.61.50.41:3000}"
readonly REDMINE_AUTH="${REDMINE_AUTH:-range-admin:KeplerV2-Training-Redmine-Admin}"
readonly FORGEJO_API_URL="${FORGEJO_API_URL:-http://10.61.40.20:3000/api/v1}"
readonly FORGEJO_AUTH="${FORGEJO_AUTH:-range-admin:KeplerV2-Training-Forgejo-Admin}"
readonly SSH=(ssh -i "${K3S01_SSH_KEY}" -o BatchMode=yes -o StrictHostKeyChecking=accept-new)

log() { printf '[campaign-m10] %s\n' "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }

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

ensure_runbook() {
  local existing issue_id description
  existing="$(curl -fsS --user "${REDMINE_AUTH}" -H 'Host: workhub.keplerops.lab' \
    "${REDMINE_URL}/issues.json?project_id=orion&status_id=*&limit=100" | \
    jq -c '.issues[] | select(.subject == "Orion production operations runbook")' | head -n1 || true)"
  description="$(<"${MODULE_ROOT}/payloads/production-runbook.md")"
  if [[ -n ${existing} ]]; then
    issue_id="$(jq -er .id <<<"${existing}")"
    curl -fsS --user "${REDMINE_AUTH}" -H 'Host: workhub.keplerops.lab' -H 'Content-Type: application/json' \
      -X PUT --data "$(jq -cn --arg description "${description}" '{issue:{description:$description}}')" \
      "${REDMINE_URL}/issues/${issue_id}.json" >/dev/null
  else
    curl -fsS --user "${REDMINE_AUTH}" -H 'Host: workhub.keplerops.lab' -H 'Content-Type: application/json' \
      -X POST --data "$(jq -cn --arg description "${description}" \
      '{issue:{project_id:"orion",tracker_id:2,priority_id:2,subject:"Orion production operations runbook",description:$description}}')" \
      "${REDMINE_URL}/issues.json" >/dev/null
  fi
}

ensure_age_identity() {
  compose exec -T --user airflow airflow-api bash -ec '
    umask 077
    if [[ ! -s /cinder-state/orion-export.agekey ]]; then
      age-keygen -o /cinder-state/orion-export.agekey >/tmp/age-keygen.log 2>&1
    fi
    age-keygen -y /cinder-state/orion-export.agekey >/cinder-state/orion-export.recipient
  '
  local recipient
  recipient="$(compose exec -T airflow-api cat /cinder-state/orion-export.recipient | tr -d '\r\n')"
  [[ ${recipient} == age1* ]] || die 'Cinder age recipient was not created'
  install -d -m 0750 "${STATE_ROOT}"
  printf '%s\n' "${recipient}" >"${STATE_ROOT}/cinder-age-recipient.txt"
  chmod 0640 "${STATE_ROOT}/cinder-age-recipient.txt"
}

ensure_cinder_runbook() {
  local api='http://10.61.90.30:3000/api/v1'
  local auth='cinder-operator:Cinder-Operations-Git-K3m7Pq4x'
  local repo='orion-operations'
  local recipient current sha content payload
  recipient="$(<"${STATE_ROOT}/cinder-age-recipient.txt")"
  if ! curl -fsS --user "${auth}" "${api}/repos/cinder-operator/${repo}" >/dev/null 2>&1; then
    curl -fsS --user "${auth}" -H 'Content-Type: application/json' -X POST \
      --data '{"name":"orion-operations","description":"Cinder Orion acquisition and offline execution runbooks","private":true,"auto_init":true,"default_branch":"main"}' \
      "${api}/user/repos" >/dev/null
  fi
  content="$(printf '# Orion acquisition\n\nKeplerOps support exports must use this age recipient:\n\n`%s`\n\nPreserve archive and detached-manifest bytes. Replication completion is valid only after Cinder decrypts and compares the full member inventory. Airflow and native workflow task results return the object-store bucket/key or business record ID that owns each completion record.\n' "${recipient}" | base64 -w0)"
  current="$(curl -fsS --user "${auth}" "${api}/repos/cinder-operator/${repo}/contents/model-acquisition.md" 2>/dev/null || true)"
  sha="$(jq -r '.sha // empty' <<<"${current:-{}}")"
  payload="$(jq -cn --arg content "${content}" --arg sha "${sha}" \
    '{content:$content,message:"Reconcile Orion acquisition runbook"} + (if $sha == "" then {} else {sha:$sha} end)')"
  local method=POST
  [[ -z ${sha} ]] || method=PUT
  curl -fsS --user "${auth}" -H 'Content-Type: application/json' -X "${method}" --data "${payload}" \
    "${api}/repos/cinder-operator/${repo}/contents/model-acquisition.md" >/dev/null
}

forgejo_put_file() {
  local path=$1 source=$2 message=$3 current sha method payload desired_content current_content
  current="$(curl -fsS --user "${FORGEJO_AUTH}" \
    "${FORGEJO_API_URL}/repos/keplerops/orion-platform/contents/${path}" 2>/dev/null || true)"
  sha="$(jq -r '.sha // empty' <<<"${current:-{}}")"
  desired_content="$(base64 -w0 "${source}")"
  current_content="$(jq -r '.content // empty | gsub("\\n"; "")' <<<"${current:-{}}")"
  [[ -z ${sha} || ${current_content} != "${desired_content}" ]] || return
  method=POST
  [[ -z ${sha} ]] || method=PUT
  payload="$(jq -cn --arg content "${desired_content}" --arg message "${message}" --arg sha "${sha}" \
    '{content:$content,message:$message,branch:"main"} + (if $sha == "" then {} else {sha:$sha} end)')"
  curl -fsS --user "${FORGEJO_AUTH}" -H 'Content-Type: application/json' -X "${method}" --data "${payload}" \
    "${FORGEJO_API_URL}/repos/keplerops/orion-platform/contents/${path}" >/dev/null
}

ensure_gitops_diagnostic_projection() {
  local directory='gitops/orion-canary'
  local current decoded updated commit
  decoded="$(mktemp)"
  updated="$(mktemp)"

  forgejo_put_file "${directory}/production-diagnostic-patch.yaml" \
    "${MODULE_ROOT}/payloads/production-diagnostic-patch.yaml" \
    'Project the Orion production diagnostic into the serving revision'

  current="$(curl -fsS --user "${FORGEJO_AUTH}" \
    "${FORGEJO_API_URL}/repos/keplerops/orion-platform/contents/${directory}/kustomization.yaml")"
  jq -er '.content | gsub("\\n"; "") | @base64d' <<<"${current}" >"${decoded}"
  yq -e '.kind == "Kustomization"' "${decoded}" >/dev/null || die 'Orion canary GitOps path is not a Kustomization'
  yq '.patches = ((.patches // []) | map(select(.path != "production-diagnostic-patch.yaml"))) + [{"path":"production-diagnostic-patch.yaml","target":{"group":"serving.kserve.io","version":"v1beta1","kind":"InferenceService","name":"orion-release-risk"}}]' \
    "${decoded}" >"${updated}"
  forgejo_put_file "${directory}/kustomization.yaml" "${updated}" \
    'Keep the production diagnostic projection on promoted Orion revisions'
  commit="$(curl -fsS --user "${FORGEJO_AUTH}" \
    "${FORGEJO_API_URL}/repos/keplerops/orion-platform/branches/main" | jq -er '.commit.id')"
  [[ ${commit} =~ ^[0-9a-f]{40}([0-9a-f]{24})?$ ]] || die 'Forgejo did not return an immutable Orion GitOps revision'
  rm -f "${decoded}" "${updated}"
  printf '%s\n' "${commit}"
}

verify_release_continuity() {
  local required=${1:-false}
  local root="${TEMPLATE_ROOT}/state/campaign-start/m09/accepted"
  local report="${root}/kep-m09-b.json" candidate="${root}/kep-m09-a.json" runtime="${root}/kep-m09-g.json"
  local present=0 file
  for file in "${report}" "${candidate}" "${runtime}"; do [[ ! -s ${file} ]] || present=$((present + 1)); done
  if (( present == 0 )) && [[ ${required} != true ]]; then
    return
  fi
  (( present == 3 )) || die 'm09 release continuity records are incomplete'
  jq -e --slurpfile report "${report}" --slurpfile candidate "${candidate}" '
    .schema == "keplerops.runtime-inventory/v1" and
    .application == "orion-canary" and .kserve_service == "orion-release-risk" and .healthy == true and
    .model_digest == $report[0].model_digest and
    .model_digest == $candidate[0].model_digest and
    .image_digest == $candidate[0].image_digest and
    (.gitops_commit | test("^[0-9a-f]{40}([0-9a-f]{24})?$"))' "${runtime}" >/dev/null || \
    die 'the active m09 release is not the accepted m09-b candidate'
}

ensure_pod_diagnostic() {
  local require_release=${1:-false} commit service_account
  [[ -r ${K3S01_SSH_KEY} ]] || die "k3s SSH key is unavailable: ${K3S01_SSH_KEY}"
  verify_release_continuity "${require_release}"
  cat <<'YAML' | "${SSH[@]}" "${K3S01_SSH_TARGET}" sudo k3s kubectl apply -f - >/dev/null
apiVersion: v1
kind: Secret
metadata: {name: orion-production-diagnostic, namespace: orion-runtime}
type: Opaque
stringData: {engagement-reference: "FLAG{4a39ce8085989606}"}
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata: {name: read-production-diagnostic, namespace: orion-runtime}
rules:
  - apiGroups: [""]
    resources: ["secrets"]
    resourceNames: ["orion-production-diagnostic"]
    verbs: ["get"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata: {name: orion-runtime-production-diagnostic, namespace: orion-runtime}
subjects:
  - {kind: ServiceAccount, name: default, namespace: orion-runtime}
roleRef: {apiGroup: rbac.authorization.k8s.io, kind: Role, name: read-production-diagnostic}
YAML
  commit="$(ensure_gitops_diagnostic_projection)"
  "${SSH[@]}" "${K3S01_SSH_TARGET}" sudo env \
    GITOPS_REPO_URL=http://192.168.78.1:3000/keplerops/orion-platform.git \
    GITOPS_REVISION="${commit}" GITOPS_REPO_PATH=gitops/orion-canary ARGO_APPLICATION=orion-canary \
    /opt/keplerops-platform/scripts/configure-gitops.sh >/dev/null
  "${SSH[@]}" "${K3S01_SSH_TARGET}" sudo bash -s -- "${commit}" <<'REMOTE'
set -Eeuo pipefail
commit=$1
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
for _ in $(seq 1 150); do
  revision="$(k3s kubectl -n argocd get application/orion-canary -o jsonpath='{.status.sync.revision}' 2>/dev/null || true)"
  sync="$(k3s kubectl -n argocd get application/orion-canary -o jsonpath='{.status.sync.status}' 2>/dev/null || true)"
  [[ ${revision} == "${commit}" && ${sync} == Synced ]] && break
  sleep 2
done
[[ ${revision:-} == "${commit}" && ${sync:-} == Synced ]]
k3s kubectl -n orion-runtime wait --for=condition=Ready inferenceservice/orion-release-risk --timeout=5m >/dev/null
pod=''
for _ in $(seq 1 150); do
  pod="$(k3s kubectl -n orion-runtime get pod -l serving.kserve.io/inferenceservice=orion-release-risk -o json | \
    jq -r '.items[] | select(.status.phase == "Running") |
      select(any(.spec.volumes[]?; .name == "orion-production-diagnostic")) | .metadata.name' | head -n1)"
  [[ -n ${pod} ]] && break
  sleep 2
done
[[ -n ${pod} ]]
k3s kubectl -n orion-runtime wait --for=condition=Ready "pod/${pod}" --timeout=5m >/dev/null
k3s kubectl -n orion-runtime exec "${pod}" -c kserve-container -- \
  test -r /var/run/secrets/keplerops/production/engagement-reference
actual="$(k3s kubectl -n orion-runtime get "pod/${pod}" -o jsonpath='{.spec.containers[?(@.name=="kserve-container")].volumeMounts[?(@.name=="orion-production-diagnostic")].mountPath}')"
[[ ${actual} == /var/run/secrets/keplerops/production ]]
REMOTE
  service_account="$("${SSH[@]}" "${K3S01_SSH_TARGET}" sudo k3s kubectl -n orion-runtime get \
    inferenceservice/orion-release-risk -o jsonpath='{.spec.predictor.serviceAccountName}' || true)"
  service_account="${service_account:-default}"
  "${SSH[@]}" "${K3S01_SSH_TARGET}" sudo k3s kubectl -n orion-runtime patch rolebinding \
    orion-runtime-production-diagnostic --type=merge \
    -p "$(jq -cn --arg name "${service_account}" \
      '{subjects:[{kind:"ServiceAccount",name:$name,namespace:"orion-runtime"}]}')" >/dev/null
}

ensure_airflow() {
  compose up -d cinder-forgejo cinder-forgejo-runner >/dev/null
  compose up --no-build m10-storage-init >/dev/null
  compose up -d --build airflow-api airflow-scheduler airflow-dag-processor airflow-triggerer airflow-worker >/dev/null
  local token
  token="$(curl -fsS -H 'Content-Type: application/json' -X POST \
    --data '{"username":"range-admin","password":"KeplerV2-Training-Airflow"}' \
    http://10.61.40.35:8080/auth/token | jq -er .access_token)"
  for _ in $(seq 1 90); do
    if curl -fsS -H "Authorization: Bearer ${token}" \
        http://10.61.40.35:8080/api/v2/dags/orion_production_continuity >/dev/null 2>&1; then
      return
    fi
    sleep 2
  done
  die 'Airflow did not discover the Orion production jobs'
}

ensure_opencost() {
  "${TEMPLATE_ROOT}/telemetry/install-kubernetes.sh"
  for _ in $(seq 1 60); do
    if curl -fsS --connect-timeout 5 --max-time 20 \
        'http://192.168.78.30:30090/allocation/compute?window=10m&aggregate=namespace&resolution=1m&includeIdle=false' \
        >"${STATE_ROOT}/opencost-allocation.json" 2>/dev/null &&
        jq -e '.code == 200 and (.data | type == "array")' \
          "${STATE_ROOT}/opencost-allocation.json" >/dev/null; then
      return
    fi
    sleep 5
  done
  die 'OpenCost allocation API did not become ready'
}

main() {
  local command
  for command in base64 curl docker jq ssh yq; do command -v "${command}" >/dev/null || die "missing command: ${command}"; done
  if [[ ${OPERATION} != all ]]; then
    jq -e --arg id "${OPERATION}" 'any(.[]; .id == $id)' "${MODULE_ROOT}/operations.json" >/dev/null || die "unknown operation: ${OPERATION}"
  fi
  install -d -m 0750 "${STATE_ROOT}/applied"
  if [[ ${OPERATION} == all || ${OPERATION} == kep-m10-i ]]; then
    ensure_opencost
  fi
  ensure_airflow
  ensure_age_identity
  ensure_cinder_runbook
  ensure_runbook
  ensure_pod_diagnostic "$([[ ${OPERATION} == kep-m10-c ]] && printf true || printf false)"
  if [[ ${OPERATION} == all ]]; then
    jq -r '.[].id' "${MODULE_ROOT}/operations.json" | while read -r id; do printf '%s\n' "${id}" >"${STATE_ROOT}/applied/${id}"; done
  else
    printf '%s\n' "${OPERATION}" >"${STATE_ROOT}/applied/${OPERATION}"
  fi
  log "reconciled ${OPERATION} campaign start state"
}

main "$@"
