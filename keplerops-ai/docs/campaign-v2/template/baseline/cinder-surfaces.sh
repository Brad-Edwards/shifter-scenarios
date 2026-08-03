#!/usr/bin/env bash
set -Eeuo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
WORKSTATION=keplerops-participant-workstation-runtime
basket=""
token=""
readonly FORGEJO_AUTH=cinder-field-operator:Cinder-Field-Operator-Git-V6n4Qs8p

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

for command in apktool chromium curl fdroidcl ffmpeg git identify jarsigner jq keytool \
  labgrid-client mc mitmproxy nmap opencode python3 s3cmd swaks unzip; do
  ws sh -lc "command -v '$command' >/dev/null"
done
perl -MIO::Socket::SSL -MNet::SSLeay -e 1 || fail 'swaks TLS dependencies unavailable'
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

docker exec -i --user kasm-user --env HOME=/home/kasm-user "$WORKSTATION" \
  python3 - <"$ROOT/baseline/jupyterhub-roundtrip.py"

forgejo_user=$(ws curl -fsS --user "$FORGEJO_AUTH" \
  https://git.cinder.lab/api/v1/user)
jq -e '.login == "cinder-field-operator" and .is_admin == false and .has_actions == true' \
  <<<"$forgejo_user" >/dev/null
echo "PASS Cinder source-control identity"

if ! cinder_api GET /repos/cinder-field-operator/workbench-readiness >/dev/null 2>&1; then
  cinder_api POST /user/repos \
    --header 'Content-Type: application/json' \
    --data '{"name":"workbench-readiness","private":true,"auto_init":true,"default_branch":"main"}' \
    >/dev/null
fi
workflow=$(cat <<'YAML'
name: Cinder Workbench Readiness
on:
  push:
    branches: [main]
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
existing=$(cinder_api GET "/repos/cinder-field-operator/workbench-readiness/contents/$workflow_path" \
  2>/dev/null || true)
if sha=$(jq -er '.sha' <<<"$existing" 2>/dev/null); then
  payload=$(jq -cn --arg content "$encoded" --arg sha "$sha" \
    '{content:$content,sha:$sha,message:"Reconcile workbench readiness"}')
  cinder_api PUT "/repos/cinder-field-operator/workbench-readiness/contents/$workflow_path" \
    --header 'Content-Type: application/json' --data "$payload" >/dev/null
else
  payload=$(jq -cn --arg content "$encoded" \
    '{content:$content,message:"Add workbench readiness"}')
  cinder_api POST "/repos/cinder-field-operator/workbench-readiness/contents/$workflow_path" \
    --header 'Content-Type: application/json' --data "$payload" >/dev/null
fi
trigger_path=.forgejo/readiness-trigger.txt
trigger_content="readiness-$(date -u +%s)"
trigger_encoded=$(printf '%s\n' "$trigger_content" | base64 -w0)
trigger_existing=$(cinder_api GET "/repos/cinder-field-operator/workbench-readiness/contents/$trigger_path" \
  2>/dev/null || true)
if trigger_sha=$(jq -er '.sha' <<<"$trigger_existing" 2>/dev/null); then
  trigger_payload=$(jq -cn --arg content "$trigger_encoded" --arg sha "$trigger_sha" \
    '{content:$content,sha:$sha,message:"Run workbench readiness"}')
  cinder_api PUT "/repos/cinder-field-operator/workbench-readiness/contents/$trigger_path" \
    --header 'Content-Type: application/json' --data "$trigger_payload" >/dev/null
else
  trigger_payload=$(jq -cn --arg content "$trigger_encoded" \
    '{content:$content,message:"Run workbench readiness"}')
  cinder_api POST "/repos/cinder-field-operator/workbench-readiness/contents/$trigger_path" \
    --header 'Content-Type: application/json' --data "$trigger_payload" >/dev/null
fi
revision=$(cinder_api GET /repos/cinder-field-operator/workbench-readiness/branches/main |
  jq -er '.commit.id')
run=''
for _ in $(seq 1 90); do
  run=$(cinder_api GET /repos/cinder-field-operator/workbench-readiness/actions/tasks?limit=20 |
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
echo "PASS Cinder field operator-owned Forgejo Actions runner"

model_response=$(ws curl -fsS --max-time 120 https://model.cinder.lab/v1/chat/completions \
  -H 'Authorization: Bearer Cinder-Field-Operator-GLM-6f2a9d8c' \
  -H 'Content-Type: application/json' \
  --data '{"model":"glm-5.2","messages":[{"role":"user","content":"Reply with the word ready."}],"max_tokens":128}')
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
echo "Cinder field operator surfaces passed"
