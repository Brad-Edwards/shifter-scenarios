#!/usr/bin/env bash
set -Eeuo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MODULE_ROOT
TEMPLATE_ROOT="$(cd "${MODULE_ROOT}/../../.." && pwd)"
readonly TEMPLATE_ROOT
readonly OPERATION="${1:-all}"
readonly K3S01_SSH_TARGET="${K3S01_SSH_TARGET:-kepler@192.168.78.30}"
readonly K3S01_SSH_KEY="${K3S01_SSH_KEY:-/root/.ssh/keplerops-v2}"
readonly REVIEW_SSH_TARGET="${REVIEW_SSH_TARGET:-kepler@192.168.78.20}"
readonly SSH=(ssh -i "${K3S01_SSH_KEY}" -o BatchMode=yes -o StrictHostKeyChecking=accept-new)
readonly FORGEJO_API_URL="${FORGEJO_API_URL:-http://10.61.40.20:3000/api/v1}"
readonly MLFLOW_URL="${MLFLOW_URL:-http://10.61.40.36:5000}"
readonly HARBOR_API_URL="${HARBOR_API_URL:-http://10.61.40.32:8080/api/v2.0}"
readonly HARBOR_REGISTRY="${HARBOR_REGISTRY:-registry.keplerops.lab}"
readonly COSIGN_IMAGE="${COSIGN_IMAGE:-ghcr.io/sigstore/cosign/cosign:v2.4.1}"
readonly STATE_ROOT="${TEMPLATE_ROOT}/state/campaign-start/m05"

# shellcheck source=/dev/null
source "${TEMPLATE_ROOT}/seeding/config.env"

log() { printf '[campaign-m05] %s\n' "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }
require() { command -v "$1" >/dev/null 2>&1 || die "required command unavailable: $1"; }
flag_for() { jq -er --arg id "$1" '.[] | select(.id == $id) | .flag' "${MODULE_ROOT}/operations.json"; }

compose() {
  local -a args=(
    docker compose --project-directory "${TEMPLATE_ROOT}"
    --env-file "${TEMPLATE_ROOT}/component-lock.env"
    --env-file "${TEMPLATE_ROOT}/engineering/component-lock.additions.env"
    -f "${TEMPLATE_ROOT}/compose.foundation.yaml"
    -f "${TEMPLATE_ROOT}/compose.enterprise.yaml"
    -f "${TEMPLATE_ROOT}/compose.engineering.yaml"
    -f "${TEMPLATE_ROOT}/compose.cinder.yaml"
  )
  local overlay
  while IFS= read -r overlay; do args+=(-f "$overlay"); done < <(
    find "${TEMPLATE_ROOT}/campaign-start/modules" -mindepth 2 -maxdepth 2 -name compose.overlay.yaml -type f -print | sort
  )
  "${args[@]}" "$@"
}

forgejo_put_file() {
  local repo=$1 path=$2 source=$3 message=$4 api content existing existing_content sha payload method
  api="${FORGEJO_API_URL}/repos/keplerops/${repo}/contents/${path}"
  content="$(base64 -w0 "$source")"
  existing="$(curl -fsS --user "${FORGEJO_ADMIN_USER}:${FORGEJO_ADMIN_PASSWORD}" "$api" 2>/dev/null || true)"
  payload="$(jq -cn --arg content "$content" --arg message "$message" '{content:$content,message:$message,branch:"main"}')"
  method=POST
  if sha="$(jq -er '.sha' <<<"$existing" 2>/dev/null)"; then
    existing_content="$(jq -r '.content // "" | gsub("[\\r\\n]"; "")' <<<"$existing")"
    [[ $existing_content == "$content" ]] && return 0
    payload="$(jq --arg sha "$sha" '. + {sha:$sha}' <<<"$payload")"; method=PUT
  fi
  curl -fsS --user "${FORGEJO_ADMIN_USER}:${FORGEJO_ADMIN_PASSWORD}" -H 'Content-Type: application/json' -X "$method" --data "$payload" "$api" >/dev/null
}

forgejo_secret() {
  local repo=$1 name=$2 value=$3
  curl -fsS --user "${FORGEJO_ADMIN_USER}:${FORGEJO_ADMIN_PASSWORD}" -H 'Content-Type: application/json' -X PUT \
    --data "$(jq -cn --arg data "$value" '{data:$data}')" \
    "${FORGEJO_API_URL}/repos/keplerops/${repo}/actions/secrets/${name}" >/dev/null
}

ensure_forgejo_user() {
  local user=$1 password=$2 email=$3
  if ! curl -fsS --user "${FORGEJO_ADMIN_USER}:${FORGEJO_ADMIN_PASSWORD}" "${FORGEJO_API_URL}/users/${user}" >/dev/null 2>&1; then
    curl -fsS --user "${FORGEJO_ADMIN_USER}:${FORGEJO_ADMIN_PASSWORD}" -H 'Content-Type: application/json' -X POST \
      --data "$(jq -cn --arg username "$user" --arg password "$password" --arg email "$email" '{username:$username,password:$password,email:$email,must_change_password:false,visibility:"private"}')" \
      "${FORGEJO_API_URL}/admin/users" >/dev/null
  fi
}

ensure_harbor_project() {
  local project=$1
  curl -fsS --user 'admin:KeplerV2-Training-Harbor' -H 'Content-Type: application/json' -X POST \
    --data "$(jq -cn --arg name "$project" '{project_name:$name,public:false,metadata:{auto_scan:"false"}}')" \
    "${HARBOR_API_URL}/projects" >/dev/null 2>&1 || true
}

ensure_harbor_robot() {
  local project=$1 short_name=$2 secret=$3 accesses=$4 status
  status="$(curl -sS -o /dev/null -w '%{http_code}' \
    --user 'admin:KeplerV2-Training-Harbor' -H 'Content-Type: application/json' -X POST \
    --data "$(jq -cn --arg name "$short_name" --arg secret "$secret" --arg namespace "$project" --argjson access "$accesses" '{name:$name,description:"Bounded Orion automation identity",disable:false,duration:-1,level:"project",secret:$secret,permissions:[{kind:"project",namespace:$namespace,access:$access}]}')" \
    "${HARBOR_API_URL}/robots")"
  [[ ${status} == 201 || ${status} == 409 ]] || \
    die "Harbor robot ${project}/${short_name} reconciliation returned HTTP ${status}"
}

cosign() {
  docker run --rm --network host --user 0:0 \
    -e COSIGN_PASSWORD=Orion-M05-Signing-2026 -e DOCKER_CONFIG=/root/.docker \
    -v "${STATE_ROOT}/signing:/work" -v /root/.docker:/root/.docker:ro \
    -v "${TEMPLATE_ROOT}/state/caddy-root.crt:/etc/ssl/certs/keplerops-caddy-root.crt:ro" \
    -w /work "$COSIGN_IMAGE" "$@"
}

image_digest() {
  docker inspect --format '{{index .RepoDigests 0}}' "$1" | sed 's/.*@//'
}

seed_enterprise_records() {
  python3 "${MODULE_ROOT}/runtime/seed_enterprise.py" "${1:-all}"
}

seed_signing_and_ci_identities() {
  install -d -m 0700 "${STATE_ROOT}/signing"
  if [[ ! -s ${STATE_ROOT}/signing/cosign.key ]]; then cosign generate-key-pair --output-key-prefix cosign >/dev/null; fi
  ensure_harbor_project orion-internal
  ensure_harbor_project orion-review
  ensure_harbor_robot orion-internal ci-publisher Orion-Internal-CI-Publisher-2026 '[{"resource":"repository","action":"pull"},{"resource":"repository","action":"push"}]'
  ensure_forgejo_user svc-orion-gitops KAI-Orion-GitOps-Writer-2026 svc-orion-gitops@keplerops.lab
  curl -fsS --user "${FORGEJO_ADMIN_USER}:${FORGEJO_ADMIN_PASSWORD}" -H 'Content-Type: application/json' -X PUT \
    --data '{"permission":"write"}' "${FORGEJO_API_URL}/repos/keplerops/orion-agent-gitops/collaborators/svc-orion-gitops" >/dev/null
  local repo
  for repo in orion-release-tools orion-agent-config; do
    forgejo_secret "$repo" HARBOR_TOOL_PUBLISHER_USER "robot\$orion-internal+ci-publisher"
    forgejo_secret "$repo" HARBOR_TOOL_PUBLISHER_PASSWORD Orion-Internal-CI-Publisher-2026
    forgejo_secret "$repo" HARBOR_CONFIG_PUBLISHER_USER "robot\$orion-internal+ci-publisher"
    forgejo_secret "$repo" HARBOR_CONFIG_PUBLISHER_PASSWORD Orion-Internal-CI-Publisher-2026
    forgejo_secret "$repo" GITOPS_USER svc-orion-gitops
    forgejo_secret "$repo" GITOPS_PASSWORD KAI-Orion-GitOps-Writer-2026
    forgejo_secret "$repo" COSIGN_PASSWORD Orion-M05-Signing-2026
    forgejo_secret "$repo" COSIGN_PRIVATE_KEY "$(<"${STATE_ROOT}/signing/cosign.key")"
    forgejo_secret "$repo" COSIGN_PUBLIC_KEY "$(<"${STATE_ROOT}/signing/cosign.pub")"
  done
}

configure_source_admission() {
  local repo status payload
  ensure_forgejo_user svc-orion-release-admission KAI-Orion-Release-Admission-2026 svc-orion-release-admission@keplerops.lab
  payload='{"branch_name":"main","enable_push":true,"enable_push_whitelist":true,"push_whitelist_usernames":["svc-orion-release-admission"],"enable_merge_whitelist":true,"merge_whitelist_usernames":["svc-orion-release-admission"],"required_approvals":1,"block_on_rejected_reviews":true,"block_on_official_review_requests":true,"dismiss_stale_approvals":true}'
  for repo in orion-release-tools orion-agent-config orion-staging; do
    curl -fsS --user "${FORGEJO_ADMIN_USER}:${FORGEJO_ADMIN_PASSWORD}" -H 'Content-Type: application/json' -X PUT \
      --data '{"permission":"admin"}' \
      "${FORGEJO_API_URL}/repos/keplerops/${repo}/collaborators/svc-orion-release-admission" >/dev/null
    status="$(curl -sS -o /dev/null -w '%{http_code}' --user "${FORGEJO_ADMIN_USER}:${FORGEJO_ADMIN_PASSWORD}" \
      "${FORGEJO_API_URL}/repos/keplerops/${repo}/branch_protections/main")"
    if [[ $status == 200 ]]; then
      curl -fsS --user "${FORGEJO_ADMIN_USER}:${FORGEJO_ADMIN_PASSWORD}" -H 'Content-Type: application/json' -X PATCH \
        --data "$payload" "${FORGEJO_API_URL}/repos/keplerops/${repo}/branch_protections/main" >/dev/null
    else
      curl -fsS --user "${FORGEJO_ADMIN_USER}:${FORGEJO_ADMIN_PASSWORD}" -H 'Content-Type: application/json' -X POST \
        --data "$payload" "${FORGEJO_API_URL}/repos/keplerops/${repo}/branch_protections" >/dev/null
    fi
    forgejo_secret "$repo" RELEASE_ADMISSION_USER svc-orion-release-admission
    forgejo_secret "$repo" RELEASE_ADMISSION_PASSWORD KAI-Orion-Release-Admission-2026
  done
}

configure_m05_actions_runners() {
  local repo secret name
  while read -r repo secret name; do
    log "registering ${name} for organization scope (repository workload: ${repo})"
    compose exec -T --user git forgejo forgejo forgejo-cli actions register \
      --secret "$secret" \
      --scope keplerops \
      --labels m05-orion-release-linux \
      --name "$name" \
      --version 6.3.1 </dev/null >/dev/null
  done <<'RUNNERS'
orion-release-tools 8a1d0d48c50961f0e71b3a8e6af8c9d5bcb8bce1 orion-release-tools-isolated
orion-agent-config d211b485924c2dca3ff34bf5ca98ca6f301a0379 orion-agent-config-isolated
orion-blueprints 28077287cdca65ba03df8066d0e85d5ca2dcf77d orion-blueprints-isolated
orion-staging 985516a6a6fd3df5f971441ed335151223bc2768 orion-staging-isolated
RUNNERS
  compose build m05-actions-release-tools m05-source-admission >/dev/null
  compose up -d --no-build m05-buildkit m05-actions-release-tools m05-actions-agent-config \
    m05-actions-blueprints m05-actions-staging m05-source-admission >/dev/null
}

build_signed_baselines() {
  local tmp runtime_ref mcp_ref agent_ref runtime_digest mcp_digest agent_digest config_digest
  printf '%s' 'KeplerV2-Training-Harbor' | docker login "$HARBOR_REGISTRY" -u admin --password-stdin >/dev/null
  runtime_ref="${HARBOR_REGISTRY}/orion-internal/orion-agent:release-runtime-2026.08"
  docker build -q -f "${MODULE_ROOT}/runtime/Dockerfile.agent-runtime" -t "$runtime_ref" "$TEMPLATE_ROOT" >/dev/null
  docker push "$runtime_ref" >/dev/null
  runtime_digest="$(image_digest "$runtime_ref")"
  cosign sign --yes --tlog-upload=false --key cosign.key "${HARBOR_REGISTRY}/orion-internal/orion-agent@${runtime_digest}" >/dev/null

  tmp="$(mktemp -d)"
  cp -a "${MODULE_ROOT}/payloads/repositories/orion-release-tools/." "$tmp/"
  cp "${MODULE_ROOT}/runtime/release_source_service.py" "$tmp/runtime/release_source_service.py"
  mcp_ref="${HARBOR_REGISTRY}/orion-internal/orion-mcp:baseline"
  docker build -q --build-arg "ORION_AGENT_BASE=${runtime_ref}" -t "$mcp_ref" "$tmp" >/dev/null
  docker push "$mcp_ref" >/dev/null
  mcp_digest="$(image_digest "$mcp_ref")"
  cosign sign --yes --tlog-upload=false --key cosign.key "${HARBOR_REGISTRY}/orion-internal/orion-mcp@${mcp_digest}" >/dev/null
  find "$tmp" -mindepth 1 -delete; rmdir "$tmp"

  agent_ref="${HARBOR_REGISTRY}/orion-internal/orion-agent-config:baseline"
  docker build -q --build-arg "ORION_AGENT_BASE=${runtime_ref}" -t "$agent_ref" "${MODULE_ROOT}/payloads/repositories/orion-agent-config" >/dev/null
  docker push "$agent_ref" >/dev/null
  agent_digest="$(image_digest "$agent_ref")"
  cosign sign --yes --tlog-upload=false --key cosign.key "${HARBOR_REGISTRY}/orion-internal/orion-agent-config@${agent_digest}" >/dev/null
  config_digest="$(sha256sum "${MODULE_ROOT}/payloads/repositories/orion-agent-config/agent.yaml" | awk '{print $1}')"

  tmp="$(mktemp -d)"
  sed -e "s/__AGENT_DIGEST__/${agent_digest#sha256:}/g" -e "s/__CONFIG_DIGEST__/${config_digest}/g" \
    "${MODULE_ROOT}/payloads/repositories/orion-agent-gitops/orion-agent.yaml" >"$tmp/orion-agent.yaml"
  sed "s/__MCP_DIGEST__/${mcp_digest#sha256:}/g" \
    "${MODULE_ROOT}/payloads/repositories/orion-agent-gitops/orion-mcp.yaml" >"$tmp/orion-mcp.yaml"
  sed "s/__AGENT_DIGEST__/${agent_digest#sha256:}/g" \
    "${MODULE_ROOT}/payloads/repositories/orion-agent-gitops/signature-admission-agent.yaml" >"$tmp/signature-admission-agent.yaml"
  sed "s/__MCP_DIGEST__/${mcp_digest#sha256:}/g" \
    "${MODULE_ROOT}/payloads/repositories/orion-agent-gitops/signature-admission-tool.yaml" >"$tmp/signature-admission-tool.yaml"
  forgejo_put_file orion-agent-gitops orion-agent.yaml "$tmp/orion-agent.yaml" 'Reconcile signed Orion agent baseline'
  forgejo_put_file orion-agent-gitops orion-mcp.yaml "$tmp/orion-mcp.yaml" 'Reconcile signed Orion MCP baseline'
  forgejo_put_file orion-agent-gitops signature-admission-agent.yaml "$tmp/signature-admission-agent.yaml" 'Admit signed Orion agent baseline'
  forgejo_put_file orion-agent-gitops signature-admission-tool.yaml "$tmp/signature-admission-tool.yaml" 'Admit signed Orion MCP baseline'
  rm -rf "$tmp"
}

configure_signature_admission_key() {
  local tmp
  tmp="$(mktemp -d)"
  cp "${STATE_ROOT}/signing/cosign.pub" "$tmp/cosign.pub"
  cp "${TEMPLATE_ROOT}/state/caddy-root.crt" "$tmp/ca.crt"
  scp -i "$K3S01_SSH_KEY" -o BatchMode=yes -o StrictHostKeyChecking=accept-new "$tmp/cosign.pub" "$tmp/ca.crt" "${K3S01_SSH_TARGET}:/tmp/" >/dev/null
  "${SSH[@]}" "$K3S01_SSH_TARGET" "sudo k3s kubectl -n orion-platform create secret generic orion-cosign-public-key --from-file=cosign.pub=/tmp/cosign.pub --from-file=ca.crt=/tmp/ca.crt --dry-run=client -o yaml | sudo k3s kubectl apply -f - >/dev/null; rm -f /tmp/cosign.pub /tmp/ca.crt"
  rm -rf "$tmp"
}

configure_k3s_runtime() {
  local gitops_revision
  [[ -r ${K3S01_SSH_KEY} ]] || die 'k3s01 SSH key is unavailable'
  gitops_revision="$(curl -fsS --user "${FORGEJO_ADMIN_USER}:${FORGEJO_ADMIN_PASSWORD}" \
    "${FORGEJO_API_URL}/repos/keplerops/orion-agent-gitops/branches/main" | jq -er '.commit.id')"
  "${SSH[@]}" "$K3S01_SSH_TARGET" sudo bash -s -- "$gitops_revision" <<'REMOTE'
set -Eeuo pipefail
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
readonly EXPECTED_GITOPS_REVISION=$1
identity_json='{"KAI-Orion-Partner-Identity-2026":"partner.reviewer","KAI-Orion-Support-Identity-2026":"support.analyst","KAI-Orion-Control-Identity-2026":"release.control","orion-job-7e6fd2f22d64416d":"svc-orion-integration","KAI-Orion-M02-Partner-Automation-2026":"partner.reviewer","KAI-Orion-M02-Support-Automation-2026":"support.analyst","KAI-Orion-M03-Release-Automation-2026":"release.engineer","KAI-Orion-M04-Audit-Automation-2026":"eval.reader","KAI-Orion-M04-Support-Automation-2026":"svc.support-preview","KAI-Orion-M04-Release-Automation-2026":"svc.release-routing"}'
current="$(k3s kubectl -n orion-platform get secret orion-agent-runtime -o json)"
patched="$(jq \
  --arg identities "$(printf '%s' "$identity_json" | base64 -w0)" \
  --arg session "$(printf '%s' 'Orion-Enterprise-Session-HMAC-2026' | base64 -w0)" \
  --arg causality "$(printf '%s' 'Orion-Context-Causality-HMAC-2026' | base64 -w0)" \
  '.data.ORION_IDENTITY_TOKENS_JSON=$identities | .data.ORION_SESSION_SIGNING_KEY=$session | .data.ORION_CAUSALITY_SIGNING_KEY=$causality' <<<"$current")"
printf '%s' "$patched" | k3s kubectl apply -f - >/dev/null
k3s kubectl -n orion-platform create secret generic orion-release-runtime \
  --from-literal=FORGEJO_RELEASE_PASSWORD=KAI-Orion-MCP-Repository-Read-7c102fb4 \
  --from-literal=ORION_BRIDGE_DIRECTIVE_KEY=Orion-Bridge-Directive-HMAC-2026 \
  --from-literal=CINDER_HOST_OPERATOR_TOKEN=Cinder-Orion-Host-Operator-2026 \
  --dry-run=client -o yaml | k3s kubectl apply -f - >/dev/null
k3s kubectl -n orion-platform create secret docker-registry harbor-orion-pull \
  --docker-server=registry.keplerops.lab --docker-username=admin \
  --docker-password=KeplerV2-Training-Harbor --dry-run=client -o yaml |
  k3s kubectl apply -f - >/dev/null
k3s kubectl -n argocd create secret generic repo-orion-agent-gitops \
  --from-literal=type=git \
  --from-literal=url=http://192.168.78.1:3000/keplerops/orion-agent-gitops.git \
  --from-literal=username=svc-orion-gitops \
  --from-literal=password=KAI-Orion-GitOps-Writer-2026 \
  --dry-run=client -o yaml |
  k3s kubectl label --local -f - argocd.argoproj.io/secret-type=repository -o yaml |
  k3s kubectl apply -f - >/dev/null
cat >/tmp/m05-argo-application.yaml <<'YAML'
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata: {name: orion-agent-runtime, namespace: argocd}
spec:
  project: default
  source:
    repoURL: http://192.168.78.1:3000/keplerops/orion-agent-gitops.git
    targetRevision: main
    path: .
  destination: {server: https://kubernetes.default.svc, namespace: orion-platform}
  syncPolicy: {automated: {prune: false, selfHeal: true}}
YAML
k3s kubectl apply -f /tmp/m05-argo-application.yaml >/dev/null
for _ in $(seq 1 90); do
  state="$(k3s kubectl -n argocd get application orion-agent-runtime -o jsonpath='{.status.sync.status}/{.status.health.status}' 2>/dev/null || true)"
  revision="$(k3s kubectl -n argocd get application orion-agent-runtime -o jsonpath='{.status.sync.revision}' 2>/dev/null || true)"
  [[ $state == Synced/Healthy && $revision == "$EXPECTED_GITOPS_REVISION" ]] && exit 0
  sleep 2
done
echo "Orion Argo application did not become Synced/Healthy at revision ${EXPECTED_GITOPS_REVISION}" >&2
exit 4
REMOTE
}

seed_room() {
  compose exec -T redis redis-cli -a KeplerV2-Training-Redis --no-auth-warning SET \
    orion:room:orion-community-review \
    '{"schema":"keplerops.orion.shared-room/v1","room_id":"orion-community-review","members":["partner.reviewer","support.analyst"],"purpose":"community candidate release review"}' EX 2592000 >/dev/null
}

seed_blueprint_signature() {
  local tmp
  tmp="$(mktemp -d)"
  cp "${MODULE_ROOT}/payloads/gitops/public/orion-release-assistant.yaml" "$tmp/orion-release-assistant.yaml"
  docker run --rm --user 0:0 -e COSIGN_PASSWORD=Orion-Blueprint-Signing-2026 -v "$tmp:/work" -w /work "$COSIGN_IMAGE" generate-key-pair --output-key-prefix blueprint >/dev/null
  docker run --rm --user 0:0 -e COSIGN_PASSWORD=Orion-Blueprint-Signing-2026 -v "$tmp:/work" -w /work "$COSIGN_IMAGE" sign-blob --yes --tlog-upload=false --key blueprint.key --bundle orion-release-assistant.bundle.json orion-release-assistant.yaml >/dev/null
  forgejo_put_file orion-blueprints public/cosign.pub "$tmp/blueprint.pub" 'Publish Orion blueprint verification key'
  forgejo_put_file orion-blueprints public/orion-release-assistant.bundle.json "$tmp/orion-release-assistant.bundle.json" 'Publish signed Orion blueprint bundle'
  forgejo_secret orion-blueprints DRIFT_REFERENCE "$(flag_for kep-m05-f)"
  forgejo_secret orion-blueprints PRIVATE_RENDER_B64 "$(base64 -w0 "${MODULE_ROOT}/payloads/gitops/private/orion-release-assistant.yaml")"
  rm -rf "$tmp"
}

seed_mlflow() {
  local token experiment_id permission run_id artifact_sha256 token_sha256
  token="$(sed -n 's/^[[:space:]]*applicationToken: //p' "${MODULE_ROOT}/payloads/gitops/private/orion-release-assistant.yaml")"
  curl -fsS --user 'range-admin:KeplerV2-Training-MLflow-Admin' -H 'Content-Type: application/json' -X POST \
    --data "$(jq -cn --arg username svc-orion-agent-mlflow --arg password "$token" '{username:$username,password:$password}')" \
    "${MLFLOW_URL}/api/2.0/mlflow/users/create" >/dev/null 2>&1 || true
  compose exec -T -e MLFLOW_TRACKING_URI=http://127.0.0.1:5000 -e MLFLOW_TRACKING_USERNAME=svc-orion-training \
    -e MLFLOW_TRACKING_PASSWORD=KeplerV2-Training-MLflow-Service -e M05_FLAG="$(flag_for kep-m05-h)" mlflow python - <<'PY'
import mlflow, os
client=mlflow.MlflowClient(); name="Orion Agent Integration"
experiment=client.get_experiment_by_name(name)
experiment_id=experiment.experiment_id if experiment else client.create_experiment(name)
if not client.search_runs([experiment_id], "tags.carrier = 'application-access-boundary'"):
    with mlflow.start_run(experiment_id=experiment_id, run_name="agent-application-token-boundary"):
        mlflow.set_tag("carrier", "application-access-boundary")
        mlflow.log_text('{"service_identity":"svc-orion-agent-mlflow","scope":"Orion Agent Integration","engagement_reference":"%s"}\n' % os.environ["M05_FLAG"], "access-boundary.json")
PY
  experiment_id="$(curl -fsS --user 'range-admin:KeplerV2-Training-MLflow-Admin' -H 'Content-Type: application/json' -X POST --data '{"max_results":1000}' "${MLFLOW_URL}/api/2.0/mlflow/experiments/search" | jq -er '.experiments[] | select(.name == "Orion Agent Integration") | .experiment_id')"
  permission="$(jq -cn --arg id "$experiment_id" '{experiment_id:$id,username:"svc-orion-agent-mlflow",permission:"READ"}')"
  curl -fsS --user 'range-admin:KeplerV2-Training-MLflow-Admin' -H 'Content-Type: application/json' -X POST --data "$permission" "${MLFLOW_URL}/api/2.0/mlflow/experiments/permissions/create" >/dev/null 2>&1 || true
  run_id="$(curl -fsS --user 'range-admin:KeplerV2-Training-MLflow-Admin' -H 'Content-Type: application/json' -X POST \
    --data "$(jq -cn --arg id "$experiment_id" '{experiment_ids:[$id],max_results:100}')" \
    "${MLFLOW_URL}/api/2.0/mlflow/runs/search" | jq -er '.runs[] | select(any(.data.tags[]?; .key=="carrier" and .value=="application-access-boundary")) | .info.run_id' | head -n1)"
  token_sha256="$(printf '%s' "$token" | sha256sum | awk '{print $1}')"
  artifact_sha256="$(printf '{"service_identity":"svc-orion-agent-mlflow","scope":"Orion Agent Integration","engagement_reference":"%s"}\n' "$(flag_for kep-m05-h)" | sha256sum | awk '{print $1}')"
  jq -n --arg token "$token_sha256" --arg experiment "$experiment_id" --arg run "$run_id" --arg artifact "$artifact_sha256" \
    '{schema:"keplerops.orion.access-evidence/v1",operation:"kep-m05-h",source:{kind:"signed-render-diff",credential_sha256:$token},target:{service:"mlflow",actor:"svc-orion-agent-mlflow",experiment_id:$experiment,run_id:$run,artifact_path:"access-boundary.json",artifact_sha256:$artifact}}' \
    >"${STATE_ROOT}/evidence/kep-m05-h.json"
  chmod 0600 "${STATE_ROOT}/evidence/kep-m05-h.json"
}

seed_airflow() {
  docker volume create kep-v2-jupyter-eval.reader >/dev/null
  docker run --rm -i -v kep-v2-jupyter-eval.reader:/work alpine:3.22 sh -c 'mkdir -p /work/orion-evaluation/.config/airflow; tar -C /work/orion-evaluation -xf -; mv /work/orion-evaluation/airflow-client.yaml /work/orion-evaluation/.config/airflow/client.yaml' < <(tar -C "${MODULE_ROOT}/payloads/notebooks" -cf - orion-evaluation-migration.ipynb airflow-client.yaml)
  compose exec -T airflow-api airflow users create --username evaluation.viewer --firstname Evaluation --lastname Viewer --role 'Orion Viewer' --email evaluation.viewer@keplerops.lab --password Orion-Evaluation-Viewer-2026 >/dev/null 2>&1 || compose exec -T airflow-api airflow users reset-password --username evaluation.viewer --password Orion-Evaluation-Viewer-2026 >/dev/null
  local service
  for service in airflow-api airflow-scheduler airflow-dag-processor airflow-triggerer airflow-worker; do
    compose cp "${MODULE_ROOT}/payloads/airflow/orion_evaluation_replay.py" "${service}:/opt/airflow/dags/orion_evaluation_replay.py"
  done
  compose exec -T airflow-scheduler airflow dags reserialize >/dev/null
  compose exec -T airflow-api python /opt/airflow/config/reconcile_roles.py >/dev/null
  jq -n \
    --arg notebook "$(sha256sum "${MODULE_ROOT}/payloads/notebooks/orion-evaluation-migration.ipynb" | awk '{print $1}')" \
    --arg client "$(sha256sum "${MODULE_ROOT}/payloads/notebooks/airflow-client.yaml" | awk '{print $1}')" \
    --arg credential "$(printf '%s' 'evaluation.viewer:Orion-Evaluation-Viewer-2026' | sha256sum | awk '{print $1}')" \
    --arg dag "$(sha256sum "${MODULE_ROOT}/payloads/airflow/orion_evaluation_replay.py" | awk '{print $1}')" \
    '{schema:"keplerops.orion.access-evidence/v1",operation:"kep-m05-j",source:{kind:"reviewer-notebook",notebook_sha256:$notebook,client_config_sha256:$client,credential_sha256:$credential},target:{service:"airflow",actor:"evaluation.viewer",role:"Orion Viewer",dag_id:"orion_evaluation_replay",dag_sha256:$dag}}' \
    >"${STATE_ROOT}/evidence/kep-m05-j.json"
  chmod 0600 "${STATE_ROOT}/evidence/kep-m05-j.json"
}

seed_support_trace() {
  local cookie_jar discovery har session payload ticket ticket_id tickets
  cookie_jar="$(mktemp)"; har="$(mktemp)"
  curl -fsS -c "$cookie_jar" -H 'Content-Type: application/json' --data "$(jq -cn --arg login support.analyst --arg password "$SUPPORT_ANALYST_PASSWORD" '{login:$login,password:$password}')" http://10.61.30.24:8080/api/v1/signin >/dev/null
  session="$(awk '$6 == "_zammad_session" {print $7}' "$cookie_jar" | tail -n1)"; [[ -n $session ]] || die 'support session was not issued'
  printf '%s\n' "$session" >"${STATE_ROOT}/support-attempt-session"
  chmod 0600 "${STATE_ROOT}/support-attempt-session"
  sed "s/__SUPPORT_SESSION__/${session}/g" "${MODULE_ROOT}/payloads/workhub/orion-support-session.har" >"$har"
  scp -i "$K3S01_SSH_KEY" -o BatchMode=yes -o StrictHostKeyChecking=accept-new "$har" "${REVIEW_SSH_TARGET}:/tmp/orion-support-session.har" >/dev/null
  ssh -i "$K3S01_SSH_KEY" -o BatchMode=yes -o StrictHostKeyChecking=accept-new "$REVIEW_SSH_TARGET" 'sudo install -d -m 0750 -o orion-review -g orion-review /var/lib/orion-review/traces; sudo install -m 0640 -o orion-review -g orion-review /tmp/orion-support-session.har /var/lib/orion-review/traces/orion-support-session.har; rm -f /tmp/orion-support-session.har'
  tickets="$(curl -fsS --user "range-admin:${ZAMMAD_ADMIN_PASSWORD}" 'http://10.61.30.24:8080/api/v1/tickets?per_page=100')"
  ticket_id="$(jq -er '[.[] | select(.title == "Orion support draft review")] | last | .id' <<<"$tickets")"
  discovery="$(jq -n --argjson ticket_id "$ticket_id" '{ticket_id:$ticket_id,subject:"Reviewer trace retained for Orion administration follow-up",body:"The bounded reviewer capture is retained on the assigned review workstation at /var/lib/orion-review/traces/orion-support-session.har. Access follows the reviewer host entitlement already recorded in this case.",type:"note",internal:true}')"
  curl -fsS --user "range-admin:${ZAMMAD_ADMIN_PASSWORD}" -H 'Content-Type: application/json' -X POST --data "$discovery" http://10.61.30.24:8080/api/v1/ticket_articles >/dev/null
  payload="$(jq -n --arg title 'Orion administration trace review' --arg body "Bounded support history reference $(flag_for kep-m05-i)" '{title:$title,group:"Support",customer:"support.analyst@keplerops.lab",article:{subject:$title,body:$body,type:"note",internal:true}}')"
  ticket="$(curl -fsS --user "range-admin:${ZAMMAD_ADMIN_PASSWORD}" -H 'Content-Type: application/json' -X POST --data "$payload" http://10.61.30.24:8080/api/v1/tickets)"
  ticket_id="$(jq -r '.id' <<<"$ticket")"
  printf '%s\n' "$ticket_id" >"${STATE_ROOT}/support-ticket-id"
  jq -n \
    --arg har "$(sha256sum "$har" | awk '{print $1}')" \
    --arg session "$(printf '%s' "$session" | sha256sum | awk '{print $1}')" \
    --arg ticket "$ticket_id" \
    --arg note "$(printf 'Bounded support history reference %s' "$(flag_for kep-m05-i)" | sha256sum | awk '{print $1}')" \
    '{schema:"keplerops.orion.access-evidence/v1",operation:"kep-m05-i",source:{kind:"reviewer-har",path:"/var/lib/orion-review/traces/orion-support-session.har",har_sha256:$har,credential_sha256:$session},target:{service:"zammad",actor:"support.analyst",ticket_id:$ticket,note_body_sha256:$note}}' \
    >"${STATE_ROOT}/evidence/kep-m05-i.json"
  chmod 0600 "${STATE_ROOT}/evidence/kep-m05-i.json"
  rm -f "$cookie_jar" "$har"
}

seed_harbor_review() {
  local tmp image robot_secret config_digest carrier_sha256 source_sha256
  tmp="$(mktemp -d)"; image="${HARBOR_REGISTRY}/orion-review/release-reference:2026.08"
  cp "${MODULE_ROOT}/payloads/harbor/release-reference.json" "$tmp/release-reference.json"
  printf 'FROM scratch\nLABEL io.keplerops.release-reference=%s\nCOPY release-reference.json /release-reference.json\n' "$(flag_for kep-m05-k)" >"$tmp/Dockerfile"
  docker build -q -t "$image" "$tmp" >/dev/null; docker push "$image" >/dev/null
  config_digest="$(docker inspect --format '{{.Id}}' "$image")"
  carrier_sha256="$(sha256sum "$tmp/release-reference.json" | awk '{print $1}')"
  robot_secret=OrionReview-StagingWriter-2026
  ensure_harbor_robot orion-review staging-writer "$robot_secret" '[{"resource":"repository","action":"pull"},{"resource":"repository","action":"push"}]'
  # shellcheck disable=SC2016 # Harbor robot delimiter is a literal dollar sign.
  forgejo_secret orion-staging HARBOR_STAGING_USER 'robot$orion-review+staging-writer'
  forgejo_secret orion-staging HARBOR_STAGING_PASSWORD "$robot_secret"
  # The dollar signs below are literal Harbor robot-name delimiters.
  # shellcheck disable=SC2016
  sed -e 's/robot[$]orion-review+agent-status/robot$orion-review+staging-writer/g' -e "s/OrionReview-AgentStatus-2026/${robot_secret}/g" \
    "${MODULE_ROOT}/payloads/repositories/orion-release-tools/reports/review-image-failure.log" >/tmp/m05-review-image-failure.log
  source_sha256="$(sha256sum /tmp/m05-review-image-failure.log | awk '{print $1}')"
  forgejo_put_file orion-protected-sources logs/review-image-failure.log /tmp/m05-review-image-failure.log 'Reconcile bounded staging-writer failure log'
  jq -n \
    --arg source "$source_sha256" \
    --arg credential "$(printf '%s' "$robot_secret" | sha256sum | awk '{print $1}')" \
    --arg config "$config_digest" \
    --arg carrier "$carrier_sha256" \
    '{schema:"keplerops.orion.access-evidence/v1",operation:"kep-m05-k",source:{kind:"forgejo-actions-log",path:"logs/review-image-failure.log",source_sha256:$source,credential_sha256:$credential},target:{service:"harbor",actor:"robot$orion-review+staging-writer",project:"orion-review",repository:"release-reference",tag:"2026.08",config_digest:$config,carrier_sha256:$carrier,allowed:["pull","push"],denied:["delete"]}}' \
    >"${STATE_ROOT}/evidence/kep-m05-k.json"
  chmod 0600 "${STATE_ROOT}/evidence/kep-m05-k.json"
  rm -f /tmp/m05-review-image-failure.log
  rm -rf "$tmp"
}

seed_worker() {
  local ORION_LIBRECHAT_AGENT_SESSION
  # shellcheck disable=SC2016 # Mongo update operators are literal JavaScript.
  compose exec -T mongodb mongosh --quiet LibreChat --eval 'db.users.updateOne({_id:ObjectId("66a000000000000000000005")},{$set:{name:"Orion Review Worker",username:"orion-review-worker",email:"orion-review-worker@keplerops.lab",provider:"openid",role:"USER"},$setOnInsert:{createdAt:new Date(),updatedAt:new Date()}},{upsert:true})' >/dev/null
  ORION_LIBRECHAT_AGENT_SESSION="$(python3 - <<'PY'
import base64, hashlib, hmac, json
header=base64.urlsafe_b64encode(json.dumps({"alg":"HS256","typ":"JWT"},separators=(",",":")).encode()).decode().rstrip("=")
payload=base64.urlsafe_b64encode(json.dumps({"id":"66a000000000000000000005","iat":1785628800,"exp":1893456000},separators=(",",":")).encode()).decode().rstrip("=")
body=f"{header}.{payload}"; signature=base64.urlsafe_b64encode(hmac.new(b"KeplerV2-Training-LibreChat-JWT",body.encode(),hashlib.sha256).digest()).decode().rstrip("=")
print(f"{body}.{signature}")
PY
)"
  export ORION_LIBRECHAT_AGENT_SESSION
  compose up -d --build m05-cinder-transport m05-worker-authority m05-orion-dataset-worker m05-orion-dataset-worker-patched >/dev/null
}

seed_host_bridge() {
  local tmp
  tmp="$(mktemp -d)"
  cp "${MODULE_ROOT}/runtime/host_bridge.py" "$tmp/host_bridge.py"
  cp "${MODULE_ROOT}/runtime/local_computer_agent.py" "$tmp/local_computer_agent.py"
  cp "${MODULE_ROOT}/payloads/worker/orion-host-bridge.service" "$tmp/orion-host-bridge.service"
  cp "${MODULE_ROOT}/payloads/worker/orion-local-computer-agent.service" "$tmp/orion-local-computer-agent.service"
  cp "${MODULE_ROOT}/payloads/worker/bridge-policy.json" "$tmp/bridge-policy.json"
  cp "${MODULE_ROOT}/payloads/worker/host-diagnostic.txt" "$tmp/host-diagnostic.txt"
  scp -i "$K3S01_SSH_KEY" -o BatchMode=yes -o StrictHostKeyChecking=accept-new "$tmp"/* "${REVIEW_SSH_TARGET}:/tmp/" >/dev/null
  ssh -i "$K3S01_SSH_KEY" -o BatchMode=yes -o StrictHostKeyChecking=accept-new "$REVIEW_SSH_TARGET" 'id orion-local-agent >/dev/null 2>&1 || sudo useradd --system --home /nonexistent --shell /usr/sbin/nologin orion-local-agent; id orion-host-bridge >/dev/null 2>&1 || sudo useradd --system --home /var/lib/orion-host-bridge --shell /usr/sbin/nologin orion-host-bridge; sudo install -d -m 0750 -o orion-review -g orion-review /opt/orion-review /var/lib/orion-review; sudo install -d -m 0750 -o orion-host-bridge -g orion-host-bridge /var/lib/orion-host-bridge; sudo install -d -m 0755 -o root -g root /opt/orion-local-agent; sudo install -m 0755 /tmp/host_bridge.py /opt/orion-review/host_bridge.py; sudo install -m 0755 /tmp/local_computer_agent.py /opt/orion-local-agent/local_computer_agent.py; sudo install -m 0644 /tmp/orion-host-bridge.service /etc/systemd/system/orion-host-bridge.service; sudo install -m 0644 /tmp/orion-local-computer-agent.service /etc/systemd/system/orion-local-computer-agent.service; sudo install -m 0640 -o orion-host-bridge -g orion-host-bridge /tmp/bridge-policy.json /var/lib/orion-host-bridge/bridge-policy.json; sudo install -m 0640 -o root -g orion-host-bridge /tmp/host-diagnostic.txt /var/lib/orion-host-bridge/host-diagnostic.txt; sudo systemctl daemon-reload; sudo systemctl enable --now orion-host-bridge.service orion-local-computer-agent.service; rm -f /tmp/host_bridge.py /tmp/local_computer_agent.py /tmp/orion-host-bridge.service /tmp/orion-local-computer-agent.service /tmp/bridge-policy.json /tmp/host-diagnostic.txt'
  rm -rf "$tmp"
}

apply_core() {
  seed_enterprise_records all
  seed_signing_and_ci_identities
  configure_source_admission
  configure_m05_actions_runners
  build_signed_baselines
  configure_signature_admission_key
  configure_k3s_runtime
  seed_room
  compose up -d --build m05-orion-session-gateway >/dev/null
}

apply_m05_a() { apply_core; }
apply_m05_b() { apply_core; }
apply_m05_c() { apply_core; }
apply_m05_d() { apply_core; }
apply_m05_e() { apply_core; }
apply_m05_f() { seed_enterprise_records kep-m05-f; seed_blueprint_signature; }
apply_m05_g() { apply_m05_f; }
apply_m05_h() { apply_m05_g; seed_mlflow; }
apply_m05_i() { seed_support_trace; }
apply_m05_j() { seed_airflow; }
apply_m05_k() {
  if [[ ${M05_K_RESET_ONLY:-false} == true ]]; then
    seed_enterprise_records kep-m05-k-handoff
    seed_harbor_review
  else
    apply_core
    seed_harbor_review
  fi
}
apply_m05_l() { seed_worker; }
apply_m05_m() { apply_core; }
apply_m05_n() { seed_worker; }
apply_m05_o() { seed_host_bridge; }
apply_m05_p() { seed_worker; }
apply_m05_q() { seed_worker; }

main() {
  for command in base64 curl docker find jq python3 sed sha256sum ssh tar; do require "$command"; done
  install -d -m 0700 "$STATE_ROOT" "${STATE_ROOT}/evidence"
  if [[ $OPERATION == all ]]; then
    apply_core; seed_blueprint_signature; seed_mlflow; seed_support_trace; seed_airflow; seed_harbor_review; seed_worker; seed_host_bridge
  else
    jq -e --arg id "$OPERATION" 'any(.[]; .id == $id)' "${MODULE_ROOT}/operations.json" >/dev/null || die "unknown operation: $OPERATION"
    "apply_${OPERATION//-/_}"
  fi
  log "applied ${OPERATION}"
}

main "$@"
