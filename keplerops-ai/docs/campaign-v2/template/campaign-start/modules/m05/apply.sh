#!/usr/bin/env bash
set -Eeuo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MODULE_ROOT
TEMPLATE_ROOT="$(cd "${MODULE_ROOT}/../../.." && pwd)"
readonly TEMPLATE_ROOT
readonly OPERATION="${1:-all}"
readonly K3S01_SSH_TARGET="${K3S01_SSH_TARGET:-kepler@192.168.78.30}"
readonly K3S01_SSH_KEY="${K3S01_SSH_KEY:-/root/.ssh/keplerops-v2}"
readonly SSH=(ssh -i "${K3S01_SSH_KEY}" -o BatchMode=yes -o StrictHostKeyChecking=accept-new)
readonly FORGEJO_API_URL="${FORGEJO_API_URL:-http://10.61.40.20:3000/api/v1}"
readonly MLFLOW_URL="${MLFLOW_URL:-http://10.61.40.36:5000}"
readonly HARBOR_API_URL="${HARBOR_API_URL:-http://10.61.40.32:8080/api/v2.0}"

# shellcheck source=/dev/null
source "${TEMPLATE_ROOT}/seeding/config.env"

log() { printf '[campaign-m05] %s\n' "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }
require() { command -v "$1" >/dev/null 2>&1 || die "required command unavailable: $1"; }

compose() {
  docker compose --project-directory "${TEMPLATE_ROOT}" \
    --env-file "${TEMPLATE_ROOT}/component-lock.env" \
    --env-file "${TEMPLATE_ROOT}/engineering/component-lock.additions.env" \
    -f "${TEMPLATE_ROOT}/compose.foundation.yaml" \
    -f "${TEMPLATE_ROOT}/compose.enterprise.yaml" \
    -f "${TEMPLATE_ROOT}/compose.engineering.yaml" "$@"
}

flag_for() { jq -er --arg id "$1" '.[] | select(.id == $id) | .flag' "${MODULE_ROOT}/operations.json"; }

seed_records() {
  python3 "${MODULE_ROOT}/runtime/seed_enterprise.py" "$1"
}

forgejo_put_file() {
  local repo=$1 path=$2 source=$3 message=$4 api existing sha payload method
  api="${FORGEJO_API_URL}/repos/keplerops/${repo}/contents/${path}"
  existing="$(curl -fsS --user "${FORGEJO_ADMIN_USER}:${FORGEJO_ADMIN_PASSWORD}" "$api" 2>/dev/null || true)"
  payload="$(jq -cn --arg content "$(base64 -w0 "$source")" --arg message "$message" '{content:$content,message:$message}')"
  method=POST
  if sha="$(jq -er '.sha' <<<"$existing" 2>/dev/null)"; then
    payload="$(jq --arg sha "$sha" '. + {sha:$sha}' <<<"$payload")"
    method=PUT
  fi
  curl -fsS --user "${FORGEJO_ADMIN_USER}:${FORGEJO_ADMIN_PASSWORD}" \
    -H 'Content-Type: application/json' -X "$method" --data "$payload" "$api" >/dev/null
}

seed_blueprint_signature() {
  local work
  work="$(mktemp -d)"
  trap 'find "$work" -mindepth 1 -delete; rmdir "$work"' RETURN
  cp "${MODULE_ROOT}/payloads/gitops/public/orion-release-assistant.yaml" "$work/orion-release-assistant.yaml"
  docker run --rm -e COSIGN_PASSWORD=KeplerOps-Orion-Blueprint-Signing \
    -v "$work:/work" -w /work gcr.io/projectsigstore/cosign:v2.4.1 \
    generate-key-pair --output-key-prefix cosign >/dev/null
  docker run --rm -e COSIGN_PASSWORD=KeplerOps-Orion-Blueprint-Signing \
    -v "$work:/work" -w /work gcr.io/projectsigstore/cosign:v2.4.1 \
    sign-blob --yes --tlog-upload=false --key cosign.key \
    --bundle orion-release-assistant.bundle.json orion-release-assistant.yaml >/dev/null
  forgejo_put_file orion-blueprints public/cosign.pub "$work/cosign.pub" 'Publish Orion blueprint verification key'
  forgejo_put_file orion-blueprints public/orion-release-assistant.bundle.json \
    "$work/orion-release-assistant.bundle.json" 'Publish signed Orion blueprint bundle'
  curl -fsS --user "${FORGEJO_ADMIN_USER}:${FORGEJO_ADMIN_PASSWORD}" \
    -H 'Content-Type: application/json' -X PUT \
    --data "$(jq -cn --arg data "$(flag_for kep-m05-f)" '{data:$data}')" \
    "${FORGEJO_API_URL}/repos/keplerops/orion-blueprints/actions/secrets/DRIFT_REFERENCE" >/dev/null
}

deploy_agent_extension() {
  [[ -r ${K3S01_SSH_KEY} ]] || die "k3s01 SSH key is unavailable"
  for proxy in forgejo:13000:10.61.40.20:3000 harbor:13082:10.61.40.32:8080; do
    local name listen target
    IFS=: read -r name listen target <<<"$proxy"
    docker rm -f "kep-v2-m05-${name}-proxy" >/dev/null 2>&1 || true
    docker run -d --name "kep-v2-m05-${name}-proxy" --restart unless-stopped \
      --network host alpine/socat:1.8.0.3-r0 \
      "TCP-LISTEN:${listen},fork,reuseaddr" "TCP:${target}" >/dev/null
  done
  tar -C "${MODULE_ROOT}/runtime" -cf - agent_campaign.py mcp_campaign.py | \
    "${SSH[@]}" "${K3S01_SSH_TARGET}" \
      "sudo install -d -m 0755 /opt/keplerops-campaign/m05/runtime && sudo tar -C /opt/keplerops-campaign/m05/runtime -xf -"
  "${SSH[@]}" "${K3S01_SSH_TARGET}" sudo bash -s <<'REMOTE'
set -Eeuo pipefail
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
runtime=/opt/keplerops-campaign/m05/runtime
k3s kubectl -n orion-platform create configmap m05-agent-extension \
  --from-file="$runtime/agent_campaign.py" \
  --from-file="$runtime/mcp_campaign.py" \
  --dry-run=client -o yaml | k3s kubectl apply -f - >/dev/null
k3s kubectl -n orion-platform patch deployment orion-agent --type=strategic -p '
spec:
  template:
    spec:
      containers:
        - name: agent
          command: ["uvicorn", "agent_campaign:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
          env:
            - {name: PYTHONPATH, value: "/campaign:/app"}
          volumeMounts:
            - {name: m05-agent-extension, mountPath: /campaign, readOnly: true}
      volumes:
        - name: m05-agent-extension
          configMap: {name: m05-agent-extension}
' >/dev/null
k3s kubectl -n orion-platform patch deployment orion-mcp --type=strategic -p '
spec:
  template:
    spec:
      containers:
        - name: mcp
          command: ["python", "/campaign/mcp_campaign.py"]
          env:
            - {name: PYTHONPATH, value: "/campaign:/app"}
            - {name: FORGEJO_URL, value: "http://192.168.78.1:13000"}
            - {name: FORGEJO_M05_USER, value: "svc-orion-mcp"}
            - {name: FORGEJO_M05_PASSWORD, value: "KAI-Orion-MCP-Repository-Read-7c102fb4"}
            - {name: HARBOR_URL, value: "http://192.168.78.1:13082"}
          volumeMounts:
            - {name: m05-agent-extension, mountPath: /campaign, readOnly: true}
      volumes:
        - name: m05-agent-extension
          configMap: {name: m05-agent-extension}
' >/dev/null
k3s kubectl -n orion-platform get configmap release-policy -o json |
  jq -r '.data["release.rego"]' >/tmp/release.rego
if ! grep -q 'campaign-m05-tool-policy' /tmp/release.rego; then
  cat >>/tmp/release.rego <<'REGO'

# campaign-m05-tool-policy
allow := {"allow": true, "reason": "scoped Forgejo status lookup"} if {
  valid_context
  input.tool.name == "forgejo_ci_status"
  input.tool.arguments.repository in {"orion-release-tools", "orion-agent-config"}
  is_string(input.tool.arguments.ref)
}

allow := {"allow": true, "reason": "allow-listed release source"} if {
  valid_context
  input.tool.name == "inspect_release_source"
  is_string(input.tool.arguments.reference)
}

allow := {"allow": true, "reason": "bounded review registry status"} if {
  valid_context
  input.tool.name == "review_registry_status"
  input.tool.arguments.project == "orion-review"
}
REGO
  k3s kubectl -n orion-platform create configmap release-policy \
    --from-file=release.rego=/tmp/release.rego --dry-run=client -o yaml |
    k3s kubectl apply -f - >/dev/null
  k3s kubectl -n orion-platform rollout restart deployment/opa >/dev/null
  k3s kubectl -n orion-platform rollout status deployment/opa --timeout=5m >/dev/null
fi
k3s kubectl -n orion-platform rollout status deployment/orion-agent --timeout=5m >/dev/null
k3s kubectl -n orion-platform rollout status deployment/orion-mcp --timeout=5m >/dev/null
REMOTE
}

seed_mlflow_token_and_artifact() {
  local token
  token="$(sed -n 's/^[[:space:]]*applicationToken: //p' "${MODULE_ROOT}/payloads/gitops/private/orion-release-assistant.yaml")"
  local api=(curl -fsS --user "range-admin:KeplerV2-Training-MLflow-Admin" -H 'Content-Type: application/json')
  local user_payload
  user_payload="$(jq -cn --arg username svc-orion-agent-mlflow --arg password "$token" '{username:$username,password:$password}')"
  if ! "${api[@]}" "${MLFLOW_URL}/api/2.0/mlflow/users/get?username=svc-orion-agent-mlflow" >/dev/null 2>&1; then
    "${api[@]}" -X POST --data "$user_payload" "${MLFLOW_URL}/api/2.0/mlflow/users/create" >/dev/null
  else
    "${api[@]}" -X PATCH --data "$user_payload" "${MLFLOW_URL}/api/2.0/mlflow/users/update-password" >/dev/null
  fi
  compose exec -T \
    -e MLFLOW_TRACKING_URI=http://127.0.0.1:5000 \
    -e MLFLOW_TRACKING_USERNAME=svc-orion-training \
    -e MLFLOW_TRACKING_PASSWORD=KeplerV2-Training-MLflow-Service \
    -e M05_FLAG="$(flag_for kep-m05-h)" mlflow python - <<'PY'
import mlflow, os
name = "Orion Agent Integration"
client = mlflow.MlflowClient()
try:
    experiment_id = client.create_experiment(name)
except mlflow.exceptions.MlflowException:
    experiment_id = client.get_experiment_by_name(name).experiment_id
runs = client.search_runs([experiment_id], "tags.m05_operation = 'kep-m05-h'")
if not runs:
    with mlflow.start_run(experiment_id=experiment_id, run_name="agent-application-token-boundary"):
        mlflow.set_tag("m05_operation", "kep-m05-h")
        mlflow.set_tag("service_identity", "svc-orion-agent-mlflow")
        mlflow.log_text(
            '{"service_identity":"svc-orion-agent-mlflow","scope":"Orion Agent Integration","engagement_reference":"%s"}\n' % os.environ["M05_FLAG"],
            "access-boundary.json",
        )
PY
  local experiment_id
  experiment_id="$(curl -fsS --user 'range-admin:KeplerV2-Training-MLflow-Admin' \
    -H 'Content-Type: application/json' -X POST --data '{"max_results":1000}' \
    "${MLFLOW_URL}/api/2.0/mlflow/experiments/search" | jq -er '.experiments[] | select(.name == "Orion Agent Integration") | .experiment_id')"
  local permission
  permission="$(jq -cn --arg id "$experiment_id" '{experiment_id:$id,username:"svc-orion-agent-mlflow",permission:"READ"}')"
  if ! "${api[@]}" "${MLFLOW_URL}/api/2.0/mlflow/experiments/permissions/get?experiment_id=${experiment_id}&username=svc-orion-agent-mlflow" >/dev/null 2>&1; then
    "${api[@]}" -X POST --data "$permission" "${MLFLOW_URL}/api/2.0/mlflow/experiments/permissions/create" >/dev/null
  fi
}

seed_support_trace() {
  local cookie_jar har
  cookie_jar="$(mktemp)"; har="$(mktemp)"
  trap 'rm -f "$cookie_jar" "$har"' RETURN
  curl -fsS -c "$cookie_jar" -H 'Content-Type: application/json' \
    --data "$(jq -cn --arg login support.analyst --arg password "$SUPPORT_ANALYST_PASSWORD" '{login:$login,password:$password}')" \
    http://10.61.30.24:8080/api/v1/signin >/dev/null
  local session
  session="$(awk '$6 == "_zammad_session" {print $7}' "$cookie_jar" | tail -n1)"
  [[ -n $session ]] || die "Zammad did not issue the bounded support session"
  sed "s/__M05_SUPPORT_SESSION__/${session}/g" \
    "${MODULE_ROOT}/payloads/workhub/orion-support-session.har" >"$har"
  local payload
  payload="$(jq -n \
    --arg title 'Orion administration trace review' \
    --arg body "Bounded support history reference $(flag_for kep-m05-i)" \
    --arg filename orion-support-session.har \
    --arg data "$(base64 -w0 "$har")" \
    '{title:$title,group:"Support",customer:"support.analyst@keplerops.lab",article:{subject:$title,body:$body,type:"note",internal:true,attachments:[{filename:$filename,data:$data,"mime-type":"application/json"}]}}')"
  curl -fsS --user "range-admin:${ZAMMAD_ADMIN_PASSWORD}" -H 'Content-Type: application/json' \
    -X POST --data "$payload" http://10.61.30.24:8080/api/v1/tickets >/dev/null
}

seed_notebook_and_airflow() {
  docker volume create kep-v2-jupyter-reviewer >/dev/null
  docker run --rm -i -v kep-v2-jupyter-reviewer:/work alpine:3.22 sh -c \
    'mkdir -p /work/orion-evaluation/.config/airflow; tar -C /work/orion-evaluation -xf -; mv /work/orion-evaluation/airflow-client.yaml /work/orion-evaluation/.config/airflow/client.yaml' < <(
      tar -C "${MODULE_ROOT}/payloads/notebooks" -cf - \
        orion-evaluation-migration.ipynb airflow-client.yaml
    )
  compose exec -T airflow-api airflow users create \
    --username evaluation.viewer --firstname Evaluation --lastname Viewer \
    --role 'Orion Viewer' --email evaluation.viewer@keplerops.lab \
    --password Orion-Evaluation-Viewer-2026 >/dev/null 2>&1 || \
  compose exec -T airflow-api airflow users reset-password \
    --username evaluation.viewer --password Orion-Evaluation-Viewer-2026 >/dev/null
  install -m 0644 "${MODULE_ROOT}/payloads/airflow/orion_evaluation_replay.py" \
    "${TEMPLATE_ROOT}/engineering/airflow/dags/orion_evaluation_replay.py"
}

seed_harbor_review() {
  local project
  project="$(jq -cn '{project_name:"orion-review",public:false,metadata:{auto_scan:"false"}}')"
  curl -fsS --user 'admin:KeplerV2-Training-Harbor' -H 'Content-Type: application/json' \
    -X POST --data "$project" "${HARBOR_API_URL}/projects" >/dev/null 2>&1 || true
  local context image
  context="$(mktemp -d)"; image="registry.keplerops.lab/orion-review/release-reference:2026.08"
  trap 'rm -rf "$context"' RETURN
  cp "${MODULE_ROOT}/payloads/harbor/release-reference.json" "$context/release-reference.json"
  printf 'FROM scratch\nLABEL io.keplerops.release-reference=%s\nCOPY release-reference.json /release-reference.json\n' \
    "$(flag_for kep-m05-k)" >"$context/Dockerfile"
  docker build -q -t "$image" "$context" >/dev/null
  printf '%s' 'KeplerV2-Training-Harbor' | docker login registry.keplerops.lab -u admin --password-stdin >/dev/null
  docker push "$image" >/dev/null

  local robot_name='robot$orion-review+agent-status'
  local robot_secret='OrionReview-AgentStatus-2026'
  local robots robot_id
  robots="$(curl -fsS --user 'admin:KeplerV2-Training-Harbor' \
    "${HARBOR_API_URL}/robots?page=1&page_size=100")"
  robot_id="$(jq -r --arg name "$robot_name" '.[] | select(.name == $name) | .id' \
    <<<"$robots" | head -n1)"
  if [[ -n $robot_id ]] && ! curl -fsS --user "${robot_name}:${robot_secret}" \
      'http://10.61.40.32:8080/service/token?service=harbor-registry&scope=repository%3Aorion-review%2Frelease-reference%3Apull' \
      >/dev/null 2>&1; then
    curl -fsS --user 'admin:KeplerV2-Training-Harbor' -X DELETE \
      "${HARBOR_API_URL}/robots/${robot_id}" >/dev/null
    robot_id=
  fi
  if [[ -z $robot_id ]]; then
    curl -fsS --user 'admin:KeplerV2-Training-Harbor' \
      -H 'Content-Type: application/json' -X POST \
      --data "$(jq -cn --arg secret "$robot_secret" '{
        name:"agent-status",
        description:"Read-only Orion review-image status automation",
        disable:false,
        duration:-1,
        level:"project",
        secret:$secret,
        permissions:[{
          kind:"project",
          namespace:"orion-review",
          access:[{resource:"repository",action:"pull"}]
        }]
      }')" "${HARBOR_API_URL}/robots" >/dev/null
  fi
}

seed_dataset_worker() {
  docker build -q -f "${MODULE_ROOT}/runtime/Dockerfile.dataset-worker" \
    -t keplerops/orion-dataset-worker:2.8.1 "${MODULE_ROOT}/runtime" >/dev/null
  docker rm -f kep-v2-orion-dataset-worker >/dev/null 2>&1 || true
  docker volume create kep-v2-orion-dataset-worker >/dev/null
  docker run -d --name kep-v2-orion-dataset-worker --restart unless-stopped \
    --network kep-v2-engineering -p 18088:8088 \
    -e ORION_TRAINER_TOKEN=KAI-Orion-Trainer-2b68d419a7f340ce \
    -e MLFLOW_TRACKING_URI=http://mlflow:5000 \
    -e MLFLOW_TRACKING_USERNAME=svc-orion-training \
    -e MLFLOW_TRACKING_PASSWORD=KeplerV2-Training-MLflow-Service \
    -v kep-v2-orion-dataset-worker:/var/lib/orion-dataset-worker \
    -v "${MODULE_ROOT}/payloads/worker/training-contributor.json:/opt/keplerops/training-contributor.json:ro" \
    -v "${MODULE_ROOT}/payloads/worker/rogue-tool-response.json:/opt/keplerops/rogue-tool-response.json:ro" \
    -v "${MODULE_ROOT}/payloads/worker/release-reconciliation-window.json:/opt/keplerops/release-reconciliation-window.json:ro" \
    -v "${MODULE_ROOT}/payloads/worker/pending-review-export.json:/opt/keplerops/pending-review-export.json:ro" \
    -e SERVICE_TOKEN=KAI-Orion-Trainer-2b68d419a7f340ce \
    keplerops/orion-dataset-worker:2.8.1 serve >/dev/null
}

seed_host_bridge() {
  local review_host="${REVIEW_WORKSTATION_HOST:-192.168.78.20}"
  scp -i "${K3S01_SSH_KEY}" -o BatchMode=yes -o StrictHostKeyChecking=accept-new \
    "${MODULE_ROOT}/payloads/worker/host-diagnostic.txt" "kepler@${review_host}:/tmp/orion-host-diagnostic.txt" >/dev/null
  ssh -i "${K3S01_SSH_KEY}" -o BatchMode=yes -o StrictHostKeyChecking=accept-new \
    "kepler@${review_host}" 'sudo install -d -m 0750 -o root -g orion-review /var/lib/orion-review; sudo install -m 0640 -o root -g orion-review /tmp/orion-host-diagnostic.txt /var/lib/orion-review/host-diagnostic.txt && rm /tmp/orion-host-diagnostic.txt'
}

apply_m05_a() { deploy_agent_extension; seed_records kep-m05-a; }
apply_m05_b() { apply_m05_a; seed_records kep-m05-b; }
apply_m05_c() { apply_m05_a; seed_records kep-m05-c; }
apply_m05_d() { apply_m05_a; seed_records kep-m05-d; }
apply_m05_e() { deploy_agent_extension; seed_records kep-m05-e; }
apply_m05_f() { seed_records kep-m05-f; seed_blueprint_signature; }
apply_m05_g() { apply_m05_f; }
apply_m05_h() { apply_m05_g; seed_mlflow_token_and_artifact; }
apply_m05_i() { seed_support_trace; }
apply_m05_j() { seed_notebook_and_airflow; }
apply_m05_k() { deploy_agent_extension; seed_records kep-m05-k; seed_harbor_review; }
apply_m05_l() { seed_dataset_worker; }
apply_m05_m() { deploy_agent_extension; seed_records kep-m05-m; }
apply_m05_n() { seed_dataset_worker; }
apply_m05_o() { seed_host_bridge; }
apply_m05_p() { seed_dataset_worker; }
apply_m05_q() { seed_dataset_worker; }

main() {
  for command in curl docker jq python3 ssh tar; do require "$command"; done
  if [[ $OPERATION == all ]]; then
    deploy_agent_extension
    seed_records all
    seed_blueprint_signature
    seed_mlflow_token_and_artifact
    seed_support_trace
    seed_notebook_and_airflow
    seed_harbor_review
    seed_dataset_worker
    seed_host_bridge
  else
    jq -e --arg id "$OPERATION" 'any(.[]; .id == $id)' "${MODULE_ROOT}/operations.json" >/dev/null || die "unknown operation: $OPERATION"
    "apply_${OPERATION//-/_}"
  fi
  log "applied ${OPERATION}"
}

main "$@"
