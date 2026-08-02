#!/usr/bin/env bash
set -Eeuo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
WORKSTATION=keplerops-participant-workstation-runtime
basket=""
token=""
readonly FORGEJO_AUTH=cinder-operator:Cinder-Operations-Git-K3m7Pq4x

ws() {
  docker exec --user kasm-user --env HOME=/home/kasm-user "$WORKSTATION" "$@"
}

cinder_api() {
  local method=$1
  local path=$2
  shift 2
  ws curl --silent --show-error --fail-with-body \
    --user "$FORGEJO_AUTH" --request "$method" "$@" \
    "https://git.cinder.lab/api/v1${path}"
}

cleanup() {
  if [[ -n $basket && -n $token ]]; then
    ws curl -fsS -X DELETE -H "Authorization: $token" \
      "https://relay.cinder.lab/api/baskets/$basket" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

for container in \
  "$WORKSTATION" \
  kep-v2-cinder-forgejo \
  kep-v2-cinder-forgejo-runner \
  kep-v2-cinder-minio \
  kep-v2-cinder-jupyter; do
  [[ $(docker inspect --format '{{.State.Running}}' "$container") == true ]]
done
[[ $(docker inspect --format '{{.State.Status}} {{.State.ExitCode}}' \
  kep-v2-cinder-forgejo-bootstrap) == "exited 0" ]]
echo "PASS Cinder containers running"

for command in apktool chromium curl ffmpeg git identify jq labgrid-client mc \
  mitmproxy nmap opencode python3 s3cmd swaks unzip; do
  ws sh -lc "command -v '$command' >/dev/null"
done
echo "PASS participant tools installed"

for url in \
  https://git.cinder.lab/ \
  https://objects.cinder.lab/ \
  https://notebook.cinder.lab/ \
  https://webmail.cinder.lab/ \
  https://relay.cinder.lab/; do
  ws curl -fsSL -o /dev/null "$url"
done
echo "PASS participant TLS application routes"

ws curl -fsS \
  -H 'Authorization: token Cinder-Operations-Notebook-R5w8Nx2k' \
  https://notebook.cinder.lab/api >/dev/null
echo "PASS Cinder notebook authentication"

forgejo_user=$(ws curl -fsS --user "$FORGEJO_AUTH" \
  https://git.cinder.lab/api/v1/user)
jq -e '.login == "cinder-operator" and .is_admin == true' \
  <<<"$forgejo_user" >/dev/null
echo "PASS Cinder source-control identity"

if ! cinder_api GET /repos/cinder-operator/workbench-readiness >/dev/null 2>&1; then
  cinder_api POST /user/repos \
    --header 'Content-Type: application/json' \
    --data '{"name":"workbench-readiness","private":true,"auto_init":true,"default_branch":"main"}' \
    >/dev/null
fi
workflow=$(cat <<'YAML'
name: Cinder Workbench Readiness
on:
  workflow_dispatch:
jobs:
  readiness:
    runs-on: cinder-linux
    steps:
      - name: Verify the isolated host workspace
        run: |
          workspace="$(pwd -P)"
          case "$workspace" in
            /var/lib/keplerops-v2/cinder-forgejo-runner/workspace/*) ;;
            *) echo "unexpected runner workspace: $workspace" >&2; exit 2 ;;
          esac
          printf 'cinder-actions-ready\n' >runner-readiness.txt
          grep -Fx cinder-actions-ready runner-readiness.txt
YAML
)
workflow_path=.forgejo/workflows/readiness.yml
encoded=$(printf '%s\n' "$workflow" | base64 -w0)
existing=$(cinder_api GET "/repos/cinder-operator/workbench-readiness/contents/$workflow_path" \
  2>/dev/null || true)
if sha=$(jq -er '.sha' <<<"$existing" 2>/dev/null); then
  payload=$(jq -cn --arg content "$encoded" --arg sha "$sha" \
    '{content:$content,sha:$sha,message:"Reconcile workbench readiness"}')
  cinder_api PUT "/repos/cinder-operator/workbench-readiness/contents/$workflow_path" \
    --header 'Content-Type: application/json' --data "$payload" >/dev/null
else
  payload=$(jq -cn --arg content "$encoded" \
    '{content:$content,message:"Add workbench readiness"}')
  cinder_api POST "/repos/cinder-operator/workbench-readiness/contents/$workflow_path" \
    --header 'Content-Type: application/json' --data "$payload" >/dev/null
fi
revision=$(cinder_api GET /repos/cinder-operator/workbench-readiness/branches/main |
  jq -er '.commit.id')
cinder_api POST \
  /repos/cinder-operator/workbench-readiness/actions/workflows/readiness.yml/dispatches \
  --header 'Content-Type: application/json' \
  --data '{"ref":"main","inputs":{}}' >/dev/null
run=''
for _ in $(seq 1 90); do
  run=$(cinder_api GET /repos/cinder-operator/workbench-readiness/actions/tasks?limit=20 |
    jq -c --arg revision "$revision" '
      [.workflow_runs[] | select(.workflow_id == "readiness.yml" and .head_sha == $revision)]
      | max_by(.id) // empty')
  [[ -n $run ]] || { sleep 2; continue; }
  status=$(jq -er '.status' <<<"$run")
  [[ $status == success ]] && break
  if [[ $status == failure || $status == cancelled || $status == skipped ]]; then
    echo "Cinder Actions readiness ended with status $status" >&2
    exit 1
  fi
  sleep 2
done
jq -e '.status == "success"' <<<"$run" >/dev/null
echo "PASS Cinder participant-owned Forgejo Actions runner"

model_response=$(ws curl -fsS https://model.cinder.lab/v1/chat/completions \
  -H 'Content-Type: application/json' \
  --data '{"model":"zai-org/glm-5-maas","messages":[{"role":"user","content":"Reply with the word ready."}],"max_tokens":128}')
jq -e '.choices[0].message | ((.content // "") + (.reasoning_content // "")) | length > 0' \
  <<<"$model_response" >/dev/null
echo "PASS direct GLM completion"

ws timeout 180 opencode run --format json \
  'Reply with CINDER-OPENCODE-READY only.' | grep -Fq CINDER-OPENCODE-READY
echo "PASS OpenCode completion through GLM"

ws mc --config-dir /tmp/keplerops-mc alias set cinder \
  http://10.61.90.31:9000 cinder-operator Cinder-Operations-ObjectStore-T7v2Lm9q >/dev/null
ws mc --config-dir /tmp/keplerops-mc ls cinder/operations >/dev/null
echo "PASS Cinder object-store access"

workspace_probe="/home/jovyan/work/.keplerops-persistence-probe"
probe_value="workspace-$(date -u +%s)"
docker exec --user jovyan kep-v2-cinder-jupyter \
  sh -c "printf '%s\\n' '$probe_value' >'$workspace_probe'"
docker restart kep-v2-cinder-jupyter >/dev/null
for _ in $(seq 1 60); do
  docker exec kep-v2-cinder-jupyter curl -fsS \
    -H 'Authorization: token Cinder-Operations-Notebook-R5w8Nx2k' \
    http://127.0.0.1:8888/api >/dev/null 2>&1 && break
  sleep 2
done
[[ $(docker exec --user jovyan kep-v2-cinder-jupyter cat "$workspace_probe") == "$probe_value" ]]
docker exec --user jovyan kep-v2-cinder-jupyter sh -c "rm -f '$workspace_probe'"
echo "PASS Cinder notebook workspace persists across restart"

basket="baseline-$(date -u +%Y%m%d%H%M%S)"
token=$(ws curl -fsS -X POST -H 'Content-Type: application/json' \
  --data '{"capacity":10}' \
  "https://relay.cinder.lab/api/baskets/$basket" | jq -er '.token')
ws curl -fsS -H 'Content-Type: application/json' \
  --data '{"event":"cinder-baseline-callback"}' \
  "https://relay.cinder.lab/$basket" >/dev/null
requests=$(ws curl -fsS -H "Authorization: $token" \
  "https://relay.cinder.lab/api/baskets/$basket/requests")
jq -e '.requests | length == 1' <<<"$requests" >/dev/null
echo "PASS Cinder Knative callback substrate"

"$ROOT/baseline/mail-roundtrip.py"
echo "Cinder participant surfaces passed"
