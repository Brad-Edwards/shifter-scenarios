#!/usr/bin/env bash
set -euo pipefail

readonly ROOT=${KEPLEROPS_V2_ROOT:-/opt/keplerops-v2}
readonly KEY=/root/.ssh/keplerops-v2
readonly SSH=(ssh -i "$KEY" -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null)
readonly WORKER_STATE="$ROOT/state/guests/review-verification.env"
readonly REVIEW_QUEUE=orion.review.review01
readonly INTEGRATION_QUEUE=orion.review.integration01
readonly RESULT_QUEUE=orion.review.results

check_port() {
  timeout 3 bash -c "</dev/tcp/$1/$2" 2>/dev/null
}

check_port 192.168.78.10 53
check_port 192.168.78.10 88
check_port 192.168.78.10 389
check_port 192.168.78.11 53
check_port 192.168.78.11 88
check_port 192.168.78.11 389

# shellcheck disable=SC2016
timeout 30 "${SSH[@]}" kepler@192.168.78.10 \
  'sudo timeout 20 samba-tool user show reviewer >/dev/null;
   replication=$(sudo timeout 20 samba-tool drs showrepl 127.0.0.1);
   ! grep -q "failed, result" <<<"$replication";
   grep -q "was successful" <<<"$replication";
   test -f /var/lib/keplerops-dc01.ready'
# shellcheck disable=SC2016
timeout 30 "${SSH[@]}" kepler@192.168.78.11 \
  'sudo timeout 20 samba-tool user show reviewer >/dev/null;
   replication=$(sudo timeout 20 samba-tool drs showrepl 127.0.0.1);
   ! grep -q "failed, result" <<<"$replication";
   grep -q "was successful" <<<"$replication";
   test -f /var/lib/keplerops-dc02.ready'
timeout 30 "${SSH[@]}" kepler@192.168.78.20 \
  'realm list | grep -qi corp.keplerops.lab;
   printf "%s\\n" "KeplerV2-Training-Reviewer" | kinit reviewer@CORP.KEPLEROPS.LAB;
   klist -s;
   getent passwd "reviewer@corp.keplerops.lab" >/dev/null;
   kdestroy;
   test -f /var/lib/keplerops-domain-member.ready'
timeout 30 "${SSH[@]}" kepler@192.168.78.21 \
  'realm list | grep -qi corp.keplerops.lab; test -f /var/lib/keplerops-domain-member.ready'
timeout 30 "${SSH[@]}" kepler@192.168.78.30 \
  'sudo systemctl is-active --quiet k3s; test -f /var/lib/keplerops-k3s.ready'

install -d -m 0755 /run/shifter
if [[ ! -s $WORKER_STATE ]] ||
  ! timeout 15 "${SSH[@]}" kepler@192.168.78.20 \
    'systemctl cat orion-review-worker.service >/dev/null 2>&1' ||
  ! timeout 15 "${SSH[@]}" kepler@192.168.78.21 \
    'systemctl cat orion-review-worker.service >/dev/null 2>&1'; then
  printf '%s\n' "$(cat /proc/sys/kernel/random/boot_id) guests-domain-bootstrap" \
    >/run/shifter/keplerops-v2-guests.ready
  echo "campaign-v2 guest identity substrate healthy; review workers await reconciliation"
  exit 0
fi

set -a
# shellcheck disable=SC1090
source "$WORKER_STATE"
set +a

for address in 192.168.78.20 192.168.78.21; do
  timeout 30 "${SSH[@]}" "kepler@$address" \
    'sudo systemctl is-active --quiet orion-review-worker.service;
     sudo systemctl is-enabled --quiet orion-review-worker.service;
     sudo sh -c "set -a; . /etc/keplerops/orion-review-worker.env; set +a; sudo -u orion-review --preserve-env /usr/local/lib/keplerops/review-worker.py validate-config >/dev/null"'
done
timeout 45 "${SSH[@]}" kepler@192.168.78.20 \
  'sudo -u orion-review /usr/local/lib/keplerops/review-worker.py self-test >/dev/null'

rabbit_call() {
  local method=$1 path=$2 body=${3:-}
  if [[ -n $body ]]; then
    curl -fsS -u "$RABBITMQ_USER:$RABBITMQ_PASSWORD" \
      -H 'Content-Type: application/json' -X "$method" \
      "$RABBITMQ_MANAGEMENT_URL$path" --data "$body"
  else
    curl -fsS -u "$RABBITMQ_USER:$RABBITMQ_PASSWORD" \
      -X "$method" "$RABBITMQ_MANAGEMENT_URL$path"
  fi
}

work=$(mktemp -d)
server_pid=
review_issue=
integration_issue=
cleanup() {
  if [[ -n $server_pid ]]; then
    kill "$server_pid" >/dev/null 2>&1 || true
    wait "$server_pid" 2>/dev/null || true
  fi
  if [[ -n $review_issue || -n $integration_issue ]]; then
    docker exec kep-v2-redmine bundle exec rails runner \
      "[${review_issue:-nil},${integration_issue:-nil}].compact.each { |id| issue=Issue.find_by(id: id); issue.destroy! if issue }" \
      >/dev/null 2>&1 || true
  fi
  for queue in "$REVIEW_QUEUE" "$INTEGRATION_QUEUE" "$RESULT_QUEUE"; do
    rabbit_call DELETE "/queues/keplerops/$queue/contents" >/dev/null 2>&1 || true
  done
  rm -rf "$work"
}
trap cleanup EXIT

cat >"$work/orion-integration-notes.md" <<'EOF'
# Orion Partner SDK Integration Notes

The partner SDK uses the documented release metadata endpoint and verifies the
published artifact digest before loading compatibility data.
EOF
python3 - "$work/orion-sdk-1.0-py3-none-any.whl" <<'PY'
import sys
import zipfile

with zipfile.ZipFile(sys.argv[1], "w") as archive:
    archive.writestr("orion_sdk/__init__.py", "__version__ = '1.0'\n")
    archive.writestr(
        "orion_sdk-1.0.dist-info/METADATA",
        "Metadata-Version: 2.1\nName: orion-sdk\nVersion: 1.0\n",
    )
PY

python3 -m http.server 18091 --bind 192.168.78.1 --directory "$work" \
  >"$work/http.log" 2>&1 &
server_pid=$!
for _ in {1..20}; do
  curl -fsS "http://192.168.78.1:18091/orion-integration-notes.md" >/dev/null && break
  sleep 0.5
done
kill -0 "$server_pid"

for queue in "$REVIEW_QUEUE" "$INTEGRATION_QUEUE" "$RESULT_QUEUE"; do
  rabbit_call DELETE "/queues/keplerops/$queue/contents" >/dev/null
done

publish_submission() {
  local queue=$1 submission=$2 response
  response=$(rabbit_call POST /exchanges/keplerops/amq.default/publish "$(
    jq -cn --arg queue "$queue" --arg payload "$submission" \
      '{properties:{content_type:"application/json",delivery_mode:2},routing_key:$queue,payload:$payload,payload_encoding:"string"}'
  )")
  jq -e '.routed == true' <<<"$response" >/dev/null
}

wait_for_result() {
  local submission_id=$1 deliveries payload
  for _ in {1..120}; do
    deliveries=$(rabbit_call POST "/queues/keplerops/$RESULT_QUEUE/get" \
      '{"count":1,"ackmode":"ack_requeue_false","encoding":"auto","truncate":50000}')
    payload=$(jq -r '.[0].payload // empty' <<<"$deliveries")
    if [[ -n $payload ]]; then
      if [[ $(jq -r '.submission_id // empty' <<<"$payload") == "$submission_id" ]]; then
        jq -e --arg id "$submission_id" '
          .schema == "keplerops.review.result/v1" and
          .submission_id == $id and .status == "completed" and
          (.artifact_sha256 | length == 64) and
          (.orion_model | length > 0) and (.workhub_issue_id > 0)
        ' <<<"$payload" >/dev/null
        printf '%s\n' "$payload"
        return
      fi
    fi
    sleep 1
  done
  echo "review result did not arrive for $submission_id" >&2
  return 1
}

verify_workhub_issue() {
  local issue_id=$1 user=$2 password=$3 digest=$4 body
  body=$(curl -fsS -u "$user:$password" -H "Host: $WORKHUB_HOST" \
    "$WORKHUB_URL/issues/$issue_id.json")
  jq -e '
    .issue.subject | startswith("Artifact review ")
  ' <<<"$body" >/dev/null
  jq -e --arg digest "$digest" '
    (.issue.description | contains($digest)) and
    (.issue.description | contains("Orion model:")) and
    (.issue.description | contains("Orion review:"))
  ' <<<"$body" >/dev/null
}

nonce="$(date -u +%Y%m%dT%H%M%SZ)-$$"
review_id="review-$nonce"
review_digest=$(sha256sum "$work/orion-sdk-1.0-py3-none-any.whl" | awk '{print $1}')
review_submission=$(jq -cn \
  --arg id "$review_id" --arg digest "$review_digest" \
  '{schema:"keplerops.review.submission/v1",submission_id:$id,
    title:"Orion SDK 1.0 package review",kind:"package",
    artifact_url:"http://192.168.78.1:18091/orion-sdk-1.0-py3-none-any.whl",
    sha256:$digest,context:"Compatibility review for the partner SDK release.",use_orion:true}')
publish_submission "$REVIEW_QUEUE" "$review_submission"
review_result=$(wait_for_result "$review_id")
review_issue=$(jq -r '.workhub_issue_id' <<<"$review_result")
verify_workhub_issue "$review_issue" "$REVIEW_WORKHUB_USER" \
  "$REVIEW_WORKHUB_PASSWORD" "$review_digest"

integration_id="integration-$nonce"
integration_digest=$(sha256sum "$work/orion-integration-notes.md" | awk '{print $1}')
integration_submission=$(jq -cn \
  --arg id "$integration_id" --arg digest "$integration_digest" \
  '{schema:"keplerops.review.submission/v1",submission_id:$id,
    title:"Partner SDK integration notes",kind:"document",
    artifact_url:"http://192.168.78.1:18091/orion-integration-notes.md",
    sha256:$digest,context:"Review the release endpoint and digest verification notes.",use_orion:true}')
publish_submission "$INTEGRATION_QUEUE" "$integration_submission"
integration_result=$(wait_for_result "$integration_id")
integration_issue=$(jq -r '.workhub_issue_id' <<<"$integration_result")
verify_workhub_issue "$integration_issue" "$INTEGRATION_WORKHUB_USER" \
  "$INTEGRATION_WORKHUB_PASSWORD" "$integration_digest"

printf '%s\n' "$(cat /proc/sys/kernel/random/boot_id) guests-review-workers-e2e" \
  >/run/shifter/keplerops-v2-guests.ready
echo "campaign-v2 guests and Orion review workers healthy"
