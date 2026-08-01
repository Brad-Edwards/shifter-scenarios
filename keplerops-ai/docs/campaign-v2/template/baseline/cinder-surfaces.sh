#!/usr/bin/env bash
set -Eeuo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
WORKSTATION=keplerops-participant-workstation-runtime
basket=""
token=""

ws() {
  docker exec --user kasm-user --env HOME=/home/kasm-user "$WORKSTATION" "$@"
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
  kep-v2-cinder-minio \
  kep-v2-cinder-jupyter; do
  [[ $(docker inspect --format '{{.State.Running}}' "$container") == true ]]
done
echo "PASS Cinder containers running"

for command in chromium curl git jq mc opencode python3 s3cmd swaks; do
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
  http://10.61.90.31:9000 cinder-operator CinderV2-Training-ObjectStore >/dev/null
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
echo "PASS participant-created callback relay"

"$ROOT/baseline/mail-roundtrip.py"
echo "Cinder participant surfaces passed"
