#!/usr/bin/env bash
set -Eeuo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MODULE_ROOT
TEMPLATE_ROOT="$(cd "${MODULE_ROOT}/../../.." && pwd)"
readonly TEMPLATE_ROOT
readonly OPERATION="${1:-all}"
readonly STATE_ROOT="${CAMPAIGN_STATE_ROOT:-${TEMPLATE_ROOT}/state/campaign-start}/m10"
readonly M09_ACCEPTED="${TEMPLATE_ROOT}/state/campaign-start/m09/accepted"
readonly BUSINESS_RELEASE="${TEMPLATE_ROOT}/state/business-release.env"
readonly K3S01_SSH_TARGET="${K3S01_SSH_TARGET:-kepler@192.168.78.30}"
readonly K3S01_SSH_KEY="${K3S01_SSH_KEY:-/root/.ssh/keplerops-v2}"
readonly REDMINE_URL="${REDMINE_URL:-http://10.61.50.41:3000}"
readonly REDMINE_AUTH="${REDMINE_AUTH:-range-admin:KeplerV2-Training-Redmine-Admin}"
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
    -f "${TEMPLATE_ROOT}/campaign-start/modules/m07/compose.overlay.yaml" \
    -f "${TEMPLATE_ROOT}/campaign-start/modules/m08/compose.overlay.yaml" \
    -f "${TEMPLATE_ROOT}/campaign-start/modules/m09/compose.overlay.yaml" \
    -f "${MODULE_ROOT}/compose.overlay.yaml" "$@"
}

verify_accepted_release() {
  local operation
  for operation in kep-m09-a kep-m09-b kep-m09-f kep-m09-g; do
    [[ -s ${M09_ACCEPTED}/${operation}.json ]] || die "accepted production release record is incomplete"
  done
  jq -e '.schema == "keplerops.registered-candidate/v2" and .model_family == "release-risk" and (.native_record | type == "object")' "${M09_ACCEPTED}/kep-m09-a.json" >/dev/null || die 'candidate is not the accepted v2 contract'
  jq -e '.schema == "keplerops.visible-evaluation-predicate/v2" and .model_family == "release-risk" and (.native_record | type == "object")' "${M09_ACCEPTED}/kep-m09-b.json" >/dev/null || die 'evaluation is not the accepted v2 contract'
  jq -e '.schema == "keplerops.signed-release/v2" and .model_family == "release-risk" and (.native_record | type == "object")' "${M09_ACCEPTED}/kep-m09-f.json" >/dev/null || die 'signed release is not the accepted v2 contract'
  jq -e --slurpfile candidate "${M09_ACCEPTED}/kep-m09-a.json" \
        --slurpfile signed "${M09_ACCEPTED}/kep-m09-f.json" '
    .schema == "keplerops.runtime-inventory/v2" and .model_family == "release-risk" and
    (.native_record | type == "object") and
    .application == "orion-canary" and .healthy == true and
    .release_id == $signed[0].release_id and .model_digest == $signed[0].model_digest and
    .image_digest == $signed[0].image_digest and .model_digest == $candidate[0].model_digest and
    .image_digest == $candidate[0].image_digest and .argo_revision == .gitops_commit and
    (.opa_admission.allow == true) and (.loaded_members == $candidate[0].model_members)
  ' "${M09_ACCEPTED}/kep-m09-g.json" >/dev/null || die 'accepted production runtime is not the signed candidate'

  [[ -s ${BUSINESS_RELEASE} ]] || die 'current business release identity was not published by production promotion'
  local release_id model_digest image_digest
  release_id="$(jq -er .release_id "${M09_ACCEPTED}/kep-m09-g.json")"
  model_digest="$(jq -er .model_digest "${M09_ACCEPTED}/kep-m09-g.json")"
  image_digest="$(jq -er .image_digest "${M09_ACCEPTED}/kep-m09-g.json")"
  grep -Fxq "ORION_RELEASE_RISK_RELEASE_ID=${release_id}" "${BUSINESS_RELEASE}" || die 'business release ID is stale'
  grep -Fxq "ORION_RELEASE_RISK_MODEL_DIGEST=${model_digest}" "${BUSINESS_RELEASE}" || die 'business model digest is stale'
  grep -Fxq "ORION_RELEASE_RISK_IMAGE_DIGEST=${image_digest}" "${BUSINESS_RELEASE}" || die 'business image digest is stale'
  grep -Eq '^ORION_ASSISTANT_RELEASE_ID=sha256:[0-9a-f]{64}$' "${BUSINESS_RELEASE}" || die 'assistant release identity is unavailable'
  grep -Eq '^ORION_ASSISTANT_MODEL_DIGEST=sha256:[0-9a-f]{64}$' "${BUSINESS_RELEASE}" || die 'assistant model identity is unavailable'
  grep -Eq '^ORION_ASSISTANT_IMAGE_DIGEST=sha256:[0-9a-f]{64}$' "${BUSINESS_RELEASE}" || die 'assistant image identity is unavailable'
}

verify_clean_platform_release() {
  [[ -s ${BUSINESS_RELEASE} ]] || die 'clean business release identity is unavailable'
  local release_id model_digest image_digest assistant_release assistant_model assistant_image
  release_id="$(sed -n 's/^ORION_RELEASE_RISK_RELEASE_ID=//p' "${BUSINESS_RELEASE}")"
  model_digest="$(sed -n 's/^ORION_RELEASE_RISK_MODEL_DIGEST=//p' "${BUSINESS_RELEASE}")"
  image_digest="$(sed -n 's/^ORION_RELEASE_RISK_IMAGE_DIGEST=//p' "${BUSINESS_RELEASE}")"
  assistant_release="$(sed -n 's/^ORION_ASSISTANT_RELEASE_ID=//p' "${BUSINESS_RELEASE}")"
  assistant_model="$(sed -n 's/^ORION_ASSISTANT_MODEL_DIGEST=//p' "${BUSINESS_RELEASE}")"
  assistant_image="$(sed -n 's/^ORION_ASSISTANT_IMAGE_DIGEST=//p' "${BUSINESS_RELEASE}")"
  for value in "${release_id}" "${model_digest}" "${image_digest}" \
      "${assistant_release}" "${assistant_model}" "${assistant_image}"; do
    [[ ${value} =~ ^sha256:[0-9a-f]{64}$ ]] || die 'clean platform identity contains an invalid digest'
  done
  "${TEMPLATE_ROOT}/baseline/release-runtime-continuity.sh" >/dev/null || \
    die 'clean Release Risk identity is not joined to its promoted runtime'
  "${SSH[@]}" "${K3S01_SSH_TARGET}" sudo bash -s -- \
    "${release_id}" "${model_digest}" "${image_digest}" \
    "${assistant_release}" "${assistant_model}" "${assistant_image}" <<'REMOTE'
set -Eeuo pipefail
release_id=$1
model_digest=$2
image_digest=$3
assistant_release=$4
assistant_model=$5
assistant_image=$6
state=/var/lib/keplerops-platform
release_dir="$(readlink -f "${state}/current-release")"
assistant_dir="$(readlink -f "${state}/current-assistant-release")"
[[ ${release_dir} == "${state}"/releases/* && ${assistant_dir} == "${state}"/assistant-releases/* ]]
(
  cd "${release_dir}"
  sha256sum -c SHA256SUMS >/dev/null
  cosign verify-blob --insecure-ignore-tlog --key cosign.pub \
    --bundle release.sigstore.json release.intoto.json >/dev/null
)
(
  cd "${assistant_dir}"
  sha256sum -c SHA256SUMS >/dev/null
  cosign verify-blob --insecure-ignore-tlog --key cosign.pub \
    --bundle assistant-runtime.sigstore.json assistant-runtime.intoto.json >/dev/null
)
jq -e --arg release "${release_id}" --arg model "${model_digest}" --arg image "${image_digest}" '
  .schema == "keplerops.release/v2" and .model_family == "release-risk" and
  .release_id == $release and .model.onnx_digest == $model and
  .serving_image.image_digest == $image and
  (.serving_image.repository | contains("placeholder") | not)
' "${release_dir}/release.json" >/dev/null
jq -e --arg release "${assistant_release}" --arg model "${assistant_model}" --arg image "${assistant_image}" '
  .schema == "keplerops.assistant-runtime/v1" and .release_id == $release and
  .model_identity.digest == $model and .serving_images.digest == $image and
  .model_identity.provider == "google-vertex-ai" and
  .model_identity.model == "zai-org/glm-5-maas"
' "${assistant_dir}/assistant-runtime.json" >/dev/null
REMOTE
}

verify_release_owned_diagnostic() {
  [[ -r ${K3S01_SSH_KEY} ]] || die 'k3s verification identity is unavailable'
  local expected_commit assistant_release assistant_model assistant_image
  expected_commit="$(jq -er .gitops_commit "${M09_ACCEPTED}/kep-m09-g.json")"
  assistant_release="$(sed -n 's/^ORION_ASSISTANT_RELEASE_ID=//p' "${BUSINESS_RELEASE}")"
  assistant_model="$(sed -n 's/^ORION_ASSISTANT_MODEL_DIGEST=//p' "${BUSINESS_RELEASE}")"
  assistant_image="$(sed -n 's/^ORION_ASSISTANT_IMAGE_DIGEST=//p' "${BUSINESS_RELEASE}")"
  "${SSH[@]}" "${K3S01_SSH_TARGET}" sudo bash -s -- \
    "${expected_commit}" "${assistant_release}" "${assistant_model}" "${assistant_image}" <<'REMOTE'
set -Eeuo pipefail
expected=$1
assistant_release=$2
assistant_model=$3
assistant_image=$4
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
actual="$(k3s kubectl -n argocd get application/orion-canary -o jsonpath='{.status.sync.revision}')"
[[ ${actual} == "${expected}" ]]
pod="$(k3s kubectl -n orion-runtime get pods -l serving.kserve.io/inferenceservice=orion-release-risk -o json | jq -r '.items[] | select(any(.status.containerStatuses[]?; .ready == true)) | .metadata.name' | head -n1)"
[[ -n ${pod} ]]
mount="$(k3s kubectl -n orion-runtime get pod "${pod}" -o jsonpath='{.spec.containers[?(@.name=="kserve-container")].volumeMounts[?(@.name=="production-diagnostic")].mountPath}')"
readonly_mount="$(k3s kubectl -n orion-runtime get pod "${pod}" -o jsonpath='{.spec.containers[?(@.name=="kserve-container")].volumeMounts[?(@.name=="production-diagnostic")].readOnly}')"
[[ ${mount} == /var/run/secrets/keplerops/production && ${readonly_mount} == true ]]
secret_release="$(k3s kubectl -n orion-platform get secret orion-agent-runtime -o jsonpath='{.data.ORION_ASSISTANT_RELEASE_ID}' | base64 -d)"
secret_model="$(k3s kubectl -n orion-platform get secret orion-agent-runtime -o jsonpath='{.data.ORION_ASSISTANT_MODEL_DIGEST}' | base64 -d)"
[[ ${secret_release} == "${assistant_release}" && ${secret_model} == "${assistant_model}" ]]
agent_pod="$(k3s kubectl -n orion-platform get pods -l app.kubernetes.io/name=orion-agent -o json | jq -r '.items[] | select(any(.status.containerStatuses[]?; .ready == true)) | .metadata.name' | head -n1)"
[[ -n ${agent_pod} ]]
agent_image="$(k3s kubectl -n orion-platform get pod "${agent_pod}" -o jsonpath='{.status.containerStatuses[?(@.name=="agent")].imageID}')"
[[ ${agent_image} == *"${assistant_image#sha256:}"* ]]
REMOTE
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
    if [[ ! -s /cinder-state/orion-export.agekey ]]; then age-keygen -o /cinder-state/orion-export.agekey >/dev/null 2>&1; fi
    age-keygen -y /cinder-state/orion-export.agekey >/cinder-state/orion-export.recipient
  '
  install -d -m 0750 "${STATE_ROOT}"
  compose exec -T airflow-api cat /cinder-state/orion-export.recipient | tr -d '\r' >"${STATE_ROOT}/cinder-age-recipient.txt"
  grep -Eq '^age1[[:alnum:]]+$' "${STATE_ROOT}/cinder-age-recipient.txt" || die 'Cinder export recipient is invalid'
}

ensure_callback_token_reviewer() {
  install -d -m 0700 "${STATE_ROOT}/identity"
  "${SSH[@]}" "${K3S01_SSH_TARGET}" sudo bash -s <<'REMOTE' >"${STATE_ROOT}/identity/token-reviewer.bundle"
set -Eeuo pipefail
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
cat <<'YAML' | k3s kubectl apply -f - >/dev/null
apiVersion: v1
kind: ServiceAccount
metadata: {name: m10-callback-reviewer, namespace: orion-runtime}
---
apiVersion: v1
kind: Service
metadata: {name: kep-v2-m10-source-producer, namespace: orion-runtime}
spec:
  ports:
    - {name: http, port: 8080, targetPort: 18090}
---
apiVersion: v1
kind: Endpoints
metadata: {name: kep-v2-m10-source-producer, namespace: orion-runtime}
subsets:
  - addresses: [{ip: 192.168.78.1}]
    ports: [{name: http, port: 18090, protocol: TCP}]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata: {name: m10-callback-token-reviewer}
rules:
  - apiGroups: [authentication.k8s.io]
    resources: [tokenreviews]
    verbs: [create]
  - apiGroups: [""]
    resources: [pods]
    verbs: [get]
  - apiGroups: [""]
    resources: [pods/exec]
    verbs: [create]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata: {name: m10-callback-token-reviewer}
roleRef: {apiGroup: rbac.authorization.k8s.io, kind: ClusterRole, name: m10-callback-token-reviewer}
subjects:
  - {kind: ServiceAccount, name: m10-callback-reviewer, namespace: orion-runtime}
---
apiVersion: v1
kind: Secret
metadata:
  name: m10-callback-reviewer-token
  namespace: orion-runtime
  annotations: {kubernetes.io/service-account.name: m10-callback-reviewer}
type: kubernetes.io/service-account-token
YAML
for _ in $(seq 1 30); do
  token="$(k3s kubectl -n orion-runtime get secret m10-callback-reviewer-token -o jsonpath='{.data.token}' 2>/dev/null || true)"
  ca="$(k3s kubectl -n orion-runtime get secret m10-callback-reviewer-token -o jsonpath='{.data.ca\.crt}' 2>/dev/null || true)"
  [[ -n ${token} && -n ${ca} ]] && break
  sleep 1
done
[[ -n ${token:-} && -n ${ca:-} ]]
printf '%s\n%s\n' "${token}" "${ca}"
REMOTE
  sed -n '1p' "${STATE_ROOT}/identity/token-reviewer.bundle" | base64 -d >"${STATE_ROOT}/identity/token-reviewer.jwt"
  sed -n '2p' "${STATE_ROOT}/identity/token-reviewer.bundle" | base64 -d >"${STATE_ROOT}/identity/kubernetes-ca.crt"
  rm -f "${STATE_ROOT}/identity/token-reviewer.bundle"
  chmod 0600 "${STATE_ROOT}/identity/token-reviewer.jwt" "${STATE_ROOT}/identity/kubernetes-ca.crt"
}

ensure_airflow() {
  compose up -d cinder-forgejo cinder-forgejo-runner partner-contract-monitors >/dev/null
  compose up --no-build m10-storage-init >/dev/null
  compose up -d --force-recreate prometheus >/dev/null
  # Every M10 source, worker, and Airflow service shares the same module image.
  # Build it once before startup to avoid same-tag export races.
  compose build m10-source-producer >/dev/null
  compose run --rm --no-deps m10-state-init >/dev/null
  compose up -d --no-build --no-deps m10-source-producer m10-research-worker-1 m10-research-worker-2 \
    m10-feedback-worker-1 m10-feedback-worker-2 \
    airflow-api airflow-scheduler airflow-dag-processor airflow-triggerer airflow-worker >/dev/null
  local token=''
  for _ in $(seq 1 90); do
    token="$(curl -fsS -H 'Content-Type: application/json' -X POST \
      --data '{"username":"range-admin","password":"KeplerV2-Training-Airflow"}' \
      http://10.61.40.35:8080/auth/token 2>/dev/null | jq -r '.access_token // empty' || true)"
    [[ -n ${token} ]] && break
    sleep 2
  done
  [[ -n ${token} ]] || die 'Airflow API did not become ready'
  for _ in $(seq 1 90); do
    if curl -fsS -H "Authorization: Bearer ${token}" \
      http://10.61.40.35:8080/api/v2/dags/orion_production_continuity >/dev/null 2>&1 && \
      compose exec -T m10-source-producer python -c \
        "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/metrics', timeout=5).read()"; then
      return
    fi
    sleep 2
  done
  die 'Airflow did not discover the production audit and worker DAGs'
}

ensure_operations_edge() {
  local caddyfile="${TEMPLATE_ROOT}/config/caddy/Caddyfile"
  local fragment="${MODULE_ROOT}/runtime/Caddyfile.fragment"
  if ! grep -q 'campaign-m10-production-operations' "${caddyfile}"; then
    cat "${fragment}" >>"${caddyfile}"
  fi
  curl -fsS -H 'X-API-Key: KeplerV2-Training-PDNS' -H 'Content-Type: application/json' -X PATCH \
    --data '{"rrsets":[{"name":"operations.keplerops.lab.","type":"A","ttl":60,"changetype":"REPLACE","records":[{"content":"10.61.10.2","disabled":false}]}]}' \
    http://10.61.10.10:8081/api/v1/servers/localhost/zones/keplerops.lab. >/dev/null
  docker exec kep-v2-pdns-recursor rec_control wipe-cache 'keplerops.lab$' >/dev/null
  docker cp "${caddyfile}" kep-v2-caddy:/tmp/keplerops-campaign-Caddyfile
  docker exec kep-v2-caddy caddy reload --adapter caddyfile \
    --config /tmp/keplerops-campaign-Caddyfile >/dev/null
  for _ in $(seq 1 30); do
    if curl -kfsS --resolve operations.keplerops.lab:443:192.168.78.1 \
      https://operations.keplerops.lab/metrics >/dev/null 2>&1; then
      return
    fi
    sleep 1
  done
  die 'Orion production operations edge did not become reachable'
}

main() {
  local command
  for command in curl docker jq ssh; do command -v "${command}" >/dev/null || die "missing command: ${command}"; done
  [[ ${OPERATION} == all ]] || jq -e --arg id "${OPERATION}" 'any(.[]; .id == $id)' "${MODULE_ROOT}/operations.json" >/dev/null || die "unknown operation: ${OPERATION}"
  "${TEMPLATE_ROOT}/campaign-start/reconcile-airflow-dags.sh"
  if [[ ${OPERATION} == all ]]; then
    verify_clean_platform_release
  else
    verify_accepted_release
    verify_release_owned_diagnostic
  fi
  ensure_callback_token_reviewer
  ensure_airflow
  ensure_operations_edge
  ensure_age_identity
  ensure_runbook
  # Recreate release consumers so baseline apply reads the clean admitted
  # identities; operation apply reads the genuine later M09 promotion.
  compose build business-adapter >/dev/null
  compose up -d --no-build --force-recreate --no-deps business-opa business-adapter partner-contract-monitors >/dev/null
  install -d -m 0750 "${STATE_ROOT}/applied"
  if [[ ${OPERATION} == all ]]; then
    printf 'clean-platform-release\n' >"${STATE_ROOT}/baseline-ready"
    while IFS= read -r operation; do
      printf '%s\n' "${operation}" >"${STATE_ROOT}/applied/${operation}"
    done < <(jq -r '.[] | .id' "${MODULE_ROOT}/operations.json")
  else
    printf '%s\n' "${OPERATION}" >"${STATE_ROOT}/applied/${OPERATION}"
  fi
  log "reconciled ${OPERATION} without creating or promoting another release"
}

main "$@"
