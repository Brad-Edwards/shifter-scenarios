#!/usr/bin/env bash

set -Eeuo pipefail

readonly ROOT="${KEPLEROPS_V2_ROOT:-/opt/keplerops-v2}"
readonly IDENTITY_ENV="${BUSINESS_RELEASE_ENV:-${ROOT}/state/business-release.env}"
[[ -r ${IDENTITY_ENV} ]] || {
  printf 'active business model identity file is unavailable: %s\n' "${IDENTITY_ENV}" >&2
  exit 2
}
set -a
# shellcheck disable=SC1090
source "${IDENTITY_ENV}"
set +a
readonly ADAPTER_URL="${BUSINESS_ADAPTER_URL:-http://10.61.70.25:8080}"
readonly ADAPTER_TOKEN="${BUSINESS_ADAPTER_TOKEN:-KeplerV2-Training-Business-Adapter}"
readonly DECISION_KEY="${ORION_DECISION_SIGNING_KEY:-KeplerV2-Training-Orion-Decision-Signing}"
readonly RANGE_ID="${KEPLEROPS_RANGE_ID:-template}"
readonly RELEASE_RISK_RELEASE_ID="${ORION_RELEASE_RISK_RELEASE_ID:?missing release-risk release ID}"
readonly RELEASE_RISK_MODEL_DIGEST="${ORION_RELEASE_RISK_MODEL_DIGEST:?missing release-risk model digest}"
readonly RELEASE_RISK_IMAGE_DIGEST="${ORION_RELEASE_RISK_IMAGE_DIGEST:?missing release-risk image digest}"
readonly ASSISTANT_RELEASE_ID="${ORION_ASSISTANT_RELEASE_ID:?missing assistant release ID}"
readonly ASSISTANT_MODEL_DIGEST="${ORION_ASSISTANT_MODEL_DIGEST:?missing assistant model digest}"
readonly ASSISTANT_IMAGE_DIGEST="${ORION_ASSISTANT_IMAGE_DIGEST:?missing assistant image digest}"
readonly POLICY_DIGEST="${ORION_ACTIVE_POLICY_DIGEST:?missing active business policy digest}"
readonly UNLEASH_URL="${UNLEASH_URL:-http://10.61.70.23:4242}"
readonly UNLEASH_TOKEN="${UNLEASH_TOKEN:-*:*.range-admin}"
readonly ODOO_URL="${ODOO_URL:-http://10.61.70.20:8069}"
readonly GHOST_URL="${GHOST_URL:-https://status.keplerops.lab}"
readonly MAUTIC_URL="${MAUTIC_URL:-https://advisories.keplerops.lab}"
readonly MAUTIC_AUTH="${MAUTIC_AUTH:-range-admin:KeplerV2-Training-Mautic}"
readonly ZAMMAD_URL="${ZAMMAD_URL:-http://10.61.50.43:8080}"
readonly ZAMMAD_AUTH="${ZAMMAD_AUTH:-range-admin:KeplerV2-Training-Zammad-Admin}"
readonly QDRANT_URL="${QDRANT_URL:-http://10.61.50.62:6333}"
readonly LAKEFS_URL="${LAKEFS_URL:-http://10.61.50.61:8000}"
readonly LAKEFS_AUTH="${LAKEFS_AUTH:-KeplerLakeFSAccess:KeplerV2-Training-LakeFS-Object-Key}"
readonly NEXTCLOUD_URL="${NEXTCLOUD_URL:-http://10.61.50.42}"
readonly NEXTCLOUD_AUTH="${NEXTCLOUD_AUTH:-range-admin:KeplerV2-Training-Nextcloud}"
readonly REDMINE_URL="${REDMINE_URL:-http://10.61.30.22:3000}"
readonly REDMINE_AUTH="${REDMINE_AUTH:-range-admin:KeplerV2-Training-Redmine-Admin}"
readonly RABBITMQ_URL="${RABBITMQ_MANAGEMENT_URL:-http://10.61.50.12:15672}"
readonly RABBITMQ_AUTH="${RABBITMQ_AUTH:-kepler:KeplerV2-Training-Rabbit}"
readonly STALWART_IMAP_HOST="${STALWART_IMAP_HOST:-10.61.10.20}"
readonly STALWART_IMAP_PORT="${STALWART_IMAP_PORT:-993}"
readonly REVIEWER_MAIL_PASSWORD="${REVIEWER_PASSWORD:-KeplerV2-Training-Reviewer}"
readonly SYNTHETIC_MAIL_PASSWORD="${SYNTHETIC_BUSINESS_PASSWORD:-KeplerV2-Training-Synthetic-Business}"

for command in curl docker grep jq mktemp python3; do
  command -v "${command}" >/dev/null || {
    printf 'missing required command: %s\n' "${command}" >&2
    exit 1
  }
done

workdir="$(mktemp -d)"
trap 'rm -rf "${workdir}"' EXIT
docker exec kep-v2-caddy cat /data/caddy/pki/authorities/local/root.crt \
  >"${workdir}/range-ca.crt"
readonly -a MAUTIC_CURL=(curl -fsS --cacert "${workdir}/range-ca.crt" \
  --resolve 'advisories.keplerops.lab:443:10.61.70.2')
readonly -a GHOST_CURL=(curl -sS --cacert "${workdir}/range-ca.crt" \
  --resolve 'status.keplerops.lab:443:10.61.70.2')
run_id="$(date -u +%Y%m%dT%H%M%SZ)"

sign() {
  local input=$1
  DECISION_KEY_VALUE="${DECISION_KEY}" python3 - "${input}" <<'PY'
import hashlib
import hmac
import json
import os
import sys

with open(sys.argv[1], encoding="utf-8") as source:
    value = json.load(source)
canonical = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
print(hmac.digest(os.environ["DECISION_KEY_VALUE"].encode(), canonical, hashlib.sha256).hex())
PY
}

make_envelope() {
  local destination=$1 workflow=$2 actor=$3 family=$4 action=$5 outcome=$6 range=$7 suffix=$8
  local release model image
  if [[ ${family} == release-risk ]]; then
    release=${RELEASE_RISK_RELEASE_ID}
    model=${RELEASE_RISK_MODEL_DIGEST}
    image=${RELEASE_RISK_IMAGE_DIGEST}
  else
    release=${ASSISTANT_RELEASE_ID}
    model=${ASSISTANT_MODEL_DIGEST}
    image=${ASSISTANT_IMAGE_DIGEST}
  fi
  jq -n \
    --arg schema 'keplerops.business-decision/v1' \
    --arg range "${range}" \
    --arg request "clean-${workflow}-${suffix}" \
    --arg trace "trace-${workflow}-${suffix}" \
    --arg idempotency "idempotency-${workflow}-${suffix}" \
    --arg actor "${actor}" \
    --arg release "${release}" \
    --arg model "${model}" \
    --arg image "${image}" \
    --arg policy "${POLICY_DIGEST}" \
    --arg family "${family}" \
    --arg workflow "${workflow}" \
    --arg action "${action}" \
    --arg outcome "${outcome}" \
    '{
      schema: $schema,
      range_id: $range,
      request_id: $request,
      trace_id: $trace,
      idempotency_key: $idempotency,
      actor: $actor,
      token_audience: "keplerops-business-adapter",
      input_digest: ("sha256:" + ("5" * 64)),
      extraction_digest: ("sha256:" + ("6" * 64)),
      preprocessing_digest: ("sha256:" + ("7" * 64)),
      prompt_tool_digest: ("sha256:" + ("8" * 64)),
      release: {
        release_id: $release,
        model_digest: $model,
        serving_image_digest: $image,
        policy_digest: $policy,
        model_family: $family,
        model_version: "clean-v1",
        signed: true
      },
      decision: {
        workflow: $workflow,
        action: $action,
        outcome: $outcome,
        confidence: 0.99,
        reason_codes: ["clean-control"]
      },
      clean_control_decision: "approved-clean-control"
    }' >"${destination}"
}

post_envelope() {
  local workflow=$1 envelope=$2 signature=$3 output=$4
  curl -fsS \
    -H "Authorization: Bearer ${ADAPTER_TOKEN}" \
    -H "X-Orion-Signature: ${signature}" \
    -H 'Content-Type: application/json' \
    --data-binary "@${envelope}" \
    "${ADAPTER_URL}/internal/v1/workflows/${workflow}/execute" >"${output}"
}

unleash_enabled() {
  curl -fsS -H "Authorization: ${UNLEASH_TOKEN}" \
    "${UNLEASH_URL}/api/admin/projects/default/features/orion-canary-assistant" |
    jq -er '.environments[] | select(.name == "development") | .enabled'
}

odoo_verify_move() {
  local move_id=$1 expected_type=$2
  ODOO_URL_VALUE="${ODOO_URL}" ODOO_MOVE_ID="${move_id}" ODOO_MOVE_TYPE="${expected_type}" \
    python3 <<'PY'
import os
import xmlrpc.client

url = os.environ["ODOO_URL_VALUE"]
common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate("business", "range-admin", "KeplerV2-Training-Odoo-Admin", {})
if not uid:
    raise SystemExit("Odoo authentication failed")
models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
move = models.execute_kw(
    "business", uid, "KeplerV2-Training-Odoo-Admin", "account.move", "read",
    [[int(os.environ["ODOO_MOVE_ID"])]],
    {"fields": ["state", "move_type", "amount_total", "line_ids"]},
)[0]
if move["state"] != "posted" or move["move_type"] != os.environ["ODOO_MOVE_TYPE"]:
    raise SystemExit(f"unexpected Odoo move state: {move}")
if float(move["amount_total"]) != 125.0 or len(move["line_ids"]) < 2:
    raise SystemExit(f"Odoo move is not a balanced EUR 125 adjustment: {move}")
PY
}

odoo_partner_balance() {
  ODOO_URL_VALUE="${ODOO_URL}" python3 <<'PY'
import json
import os
import xmlrpc.client

url = os.environ["ODOO_URL_VALUE"]
common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate("business", "range-admin", "KeplerV2-Training-Odoo-Admin", {})
if not uid:
    raise SystemExit("Odoo authentication failed")
models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
ids = models.execute_kw(
    "business", uid, "KeplerV2-Training-Odoo-Admin", "res.partner", "search",
    [[["ref", "=", "KAI-CUSTOMER-001"]]], {"limit": 2},
)
if len(ids) != 1:
    raise SystemExit(f"expected one synthetic customer, found {len(ids)}")
record = models.execute_kw(
    "business", uid, "KeplerV2-Training-Odoo-Admin", "res.partner", "read", [ids],
    {"fields": ["credit", "debit"]},
)[0]
print(json.dumps({"credit": float(record["credit"]), "debit": float(record["debit"])}, sort_keys=True))
PY
}

redmine_retention_done_ratio() {
  local issue_id
  issue_id="$(curl -fsS -u "${REDMINE_AUTH}" \
    "${REDMINE_URL}/issues.json?project_id=orion&status_id=*&limit=100" |
    jq -er '.issues[] | select(.subject == "Retention request: acme-labs expired export") | .id')"
  curl -fsS -u "${REDMINE_AUTH}" "${REDMINE_URL}/issues/${issue_id}.json" |
    jq -er '.issue.done_ratio'
}

mailbox_highwater() {
  local login=$1 password=$2
  MAIL_HOST="${STALWART_IMAP_HOST}" MAIL_PORT="${STALWART_IMAP_PORT}" \
    MAIL_LOGIN="${login}" MAIL_PASSWORD="${password}" python3 <<'PY'
import imaplib
import os
import ssl

context = ssl.create_default_context()
context.check_hostname = False
context.verify_mode = ssl.CERT_NONE
with imaplib.IMAP4_SSL(
    os.environ["MAIL_HOST"], int(os.environ["MAIL_PORT"]), ssl_context=context
) as client:
    client.login(os.environ["MAIL_LOGIN"], os.environ["MAIL_PASSWORD"])
    client.select("INBOX", readonly=True)
    status, data = client.uid("search", None, "ALL")
    if status != "OK":
        raise SystemExit("IMAP UID search failed")
    values = [int(value) for value in data[0].split()]
    print(max(values, default=0))
PY
}

wait_for_mail_since() {
  local login=$1 password=$2 highwater=$3 field=$4 expected=$5
  MAIL_HOST="${STALWART_IMAP_HOST}" MAIL_PORT="${STALWART_IMAP_PORT}" \
    MAIL_LOGIN="${login}" MAIL_PASSWORD="${password}" \
    MAIL_HIGHWATER="${highwater}" MAIL_FIELD="${field}" MAIL_EXPECTED="${expected}" \
    python3 <<'PY'
import email
import imaplib
import os
import ssl
import time

minimum_uid = int(os.environ["MAIL_HIGHWATER"]) + 1
field = os.environ["MAIL_FIELD"].lower()
expected = os.environ["MAIL_EXPECTED"]
context = ssl.create_default_context()
context.check_hostname = False
context.verify_mode = ssl.CERT_NONE
with imaplib.IMAP4_SSL(
    os.environ["MAIL_HOST"], int(os.environ["MAIL_PORT"]), ssl_context=context
) as client:
    client.login(os.environ["MAIL_LOGIN"], os.environ["MAIL_PASSWORD"])
    for _ in range(30):
        client.select("INBOX", readonly=True)
        status, data = client.uid("search", None, f"UID {minimum_uid}:*")
        if status != "OK":
            raise SystemExit("IMAP UID search failed")
        for uid in data[0].split():
            status, fetched = client.uid(
                "fetch", uid, "(BODY.PEEK[HEADER.FIELDS (SUBJECT MESSAGE-ID)])"
            )
            if status != "OK":
                continue
            payload = next(
                (part[1] for part in fetched if isinstance(part, tuple)), b""
            )
            message = email.message_from_bytes(payload)
            if str(message.get(field, "")) == expected:
                raise SystemExit(0)
        time.sleep(2)
raise SystemExit(
    f"new message with {field}={expected!r} did not arrive within 60 seconds"
)
PY
}

verify_native() {
  local workflow=$1 result=$2 request_id=$3 mail_highwater=${4:-}
  local target commit path point_id state_name email notification
  target="$(jq -er '.target_object_id' "${result}")"
  case "${workflow}" in
    feature-control)
      [[ "$(unleash_enabled)" == true ]]
      ;;
    accounting-credit)
      odoo_verify_move "${target}" out_refund
      jq -e '.native_response_ids[] | endswith("-credit-note.pdf")' "${result}" >/dev/null
      notification="$(jq -er '.notification_ids[0]' "${result}")"
      wait_for_mail_since billing.customer "${SYNTHETIC_MAIL_PASSWORD}" \
        "${mail_highwater}" message-id "${notification}"
      ;;
    incident-publication)
      "${GHOST_CURL[@]}" "${GHOST_URL}/orion-safety-update/" |
        grep -q 'Orion Safety Review Complete'
      ;;
    advisory-campaign)
      email="$("${MAUTIC_CURL[@]}" -u "${MAUTIC_AUTH}" \
        "${MAUTIC_URL}/api/emails?search=Orion%20Edge%20Safety%20Advisory&limit=10")"
      jq -e '[.emails[] | select(.name == "Orion Edge Safety Advisory" and .sentCount >= 1)] | length == 1' \
        <<<"${email}" >/dev/null
      "${MAUTIC_CURL[@]}" -u "${MAUTIC_AUTH}" \
        "${MAUTIC_URL}/api/campaigns?search=Orion%20Edge%20Safety%20Advisory%20Campaign&limit=10" |
        jq -e '[.campaigns[] | select(.name == "Orion Edge Safety Advisory Campaign" and .isPublished == true)] | length == 1' \
        >/dev/null
      wait_for_mail_since edge.operator "${SYNTHETIC_MAIL_PASSWORD}" \
        "${mail_highwater}" subject 'Orion Edge scheduled safety advisory'
      ;;
    support-triage)
      state_name="$(curl -fsS -u "${ZAMMAD_AUTH}" \
        "${ZAMMAD_URL}/api/v1/tickets/${target}" | jq -er '.state_id' | {
          read -r state_id
          curl -fsS -u "${ZAMMAD_AUTH}" "${ZAMMAD_URL}/api/v1/ticket_states/${state_id}" | jq -er '.name'
        })"
      [[ ${state_name} == closed ]]
      notification="$(jq -er '.notification_ids[0]' "${result}")"
      wait_for_mail_since reviewer "${REVIEWER_MAIL_PASSWORD}" \
        "${mail_highwater}" message-id "${notification}"
      ;;
    feedback-intake)
      point_id="$(jq -er '.native_response_ids[] | select(startswith("qdrant:")) | split(":")[2]' "${result}")"
      curl -fsS "${QDRANT_URL}/collections/orion_feedback/points/${point_id}" |
        jq -e --arg request "${request_id}" '.result.payload.request_id == $request' >/dev/null
      curl -fsS -u "${RABBITMQ_AUTH}" \
        "${RABBITMQ_URL}/api/queues/keplerops/orion.feedback" |
        jq -e '.messages_ready == 0' >/dev/null
      ;;
    feedback-maintenance)
      commit="${target%%:*}"
      path="${target#*:}"
      curl -fsS -u "${LAKEFS_AUTH}" \
        "${LAKEFS_URL}/api/v1/repositories/orion/refs/${commit}/objects?path=${path}" |
        jq -e --arg request "${request_id}" '.request_id == $request and .status == "valid"' >/dev/null
      ;;
    tenant-retention)
      [[ "$(curl -sS -o /dev/null -w '%{http_code}' -H 'Host: files.keplerops.lab' \
        -u "${NEXTCLOUD_AUTH}" \
        "${NEXTCLOUD_URL}/remote.php/dav/files/range-admin/Orion%20Review%20Room/Tenant%20Retention/acme-labs/expired.txt")" == 404 ]]
      [[ "$(curl -sS -o /dev/null -w '%{http_code}' -u "${LAKEFS_AUTH}" \
        "${LAKEFS_URL}/api/v1/repositories/orion/refs/retention/objects?path=tenants/acme-labs/expired/customer-export.json")" == 404 ]]
      [[ "$(redmine_retention_done_ratio)" == 100 ]]
      ;;
  esac
}

verify_compensation() {
  local workflow=$1 result=$2 request_id=$3 business_before=${4:-}
  local target state_name report_count email
  target="$(jq -er '.target_object_id' "${result}")"
  case "${workflow}" in
    feature-control)
      [[ "$(unleash_enabled)" == false ]]
      ;;
    accounting-credit)
      ODOO_URL_VALUE="${ODOO_URL}" CREDIT_MOVE_ID="${target}" python3 <<'PY'
import os
import xmlrpc.client

url = os.environ["ODOO_URL_VALUE"]
common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate("business", "range-admin", "KeplerV2-Training-Odoo-Admin", {})
models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
ids = models.execute_kw(
    "business", uid, "KeplerV2-Training-Odoo-Admin", "account.move", "search",
    [[["ref", "=", f"Reversal for credit move {os.environ['CREDIT_MOVE_ID']}"]]],
)
if len(ids) != 1:
    raise SystemExit("Odoo compensation did not create exactly one reversing move")
move = models.execute_kw(
    "business", uid, "KeplerV2-Training-Odoo-Admin", "account.move", "read", [ids],
    {"fields": ["state", "move_type", "amount_total"]},
)[0]
if move["state"] != "posted" or move["move_type"] != "out_invoice" or float(move["amount_total"]) != 125.0:
    raise SystemExit(f"invalid Odoo reversing move: {move}")
PY
      [[ "$(odoo_partner_balance)" == "${business_before}" ]]
      ;;
    incident-publication)
      [[ "$("${GHOST_CURL[@]}" -o /dev/null -w '%{http_code}' \
        "${GHOST_URL}/orion-safety-update/")" == 404 ]]
      ;;
    advisory-campaign)
      email="$("${MAUTIC_CURL[@]}" -u "${MAUTIC_AUTH}" \
        "${MAUTIC_URL}/api/emails?search=Orion%20Edge%20Safety%20Advisory&limit=10")"
      jq -e '[.emails[] | select(.name == "Orion Edge Safety Advisory" and .isPublished == false)] | length == 1' \
        <<<"${email}" >/dev/null
      "${MAUTIC_CURL[@]}" -u "${MAUTIC_AUTH}" \
        "${MAUTIC_URL}/api/campaigns?search=Orion%20Edge%20Safety%20Advisory%20Campaign&limit=10" |
        jq -e '[.campaigns[] | select(.name == "Orion Edge Safety Advisory Campaign" and .isPublished == false)] | length == 1' \
        >/dev/null
      ;;
    support-triage)
      state_name="$(curl -fsS -u "${ZAMMAD_AUTH}" \
        "${ZAMMAD_URL}/api/v1/tickets/${target}" | jq -er '.state_id' | {
          read -r state_id
          curl -fsS -u "${ZAMMAD_AUTH}" "${ZAMMAD_URL}/api/v1/ticket_states/${state_id}" | jq -er '.name'
        })"
      [[ ${state_name} == open ]]
      ;;
    feedback-intake)
      local point_id
      point_id="$(jq -er '.native_response_ids[] | select(startswith("qdrant:")) | split(":")[2]' "${result}")"
      [[ "$(curl -sS -o /dev/null -w '%{http_code}' \
        "${QDRANT_URL}/collections/orion_feedback/points/${point_id}")" == 404 ]]
      ;;
    feedback-maintenance)
      report_count="$(curl -fsS -u "${LAKEFS_AUTH}" \
        "${LAKEFS_URL}/api/v1/repositories/orion/refs/feedback-maintenance/objects/ls?prefix=feedback/maintenance/${request_id}.json" |
        jq -er '.results | length')"
      [[ ${report_count} == 0 ]]
      ;;
    tenant-retention)
      curl -fsS -H 'Host: files.keplerops.lab' -u "${NEXTCLOUD_AUTH}" \
        "${NEXTCLOUD_URL}/remote.php/dav/files/range-admin/Orion%20Review%20Room/Tenant%20Retention/acme-labs/expired.txt" \
        | grep -q 'Synthetic Acme Labs'
      curl -fsS -u "${LAKEFS_AUTH}" \
        "${LAKEFS_URL}/api/v1/repositories/orion/refs/retention/objects?path=tenants/acme-labs/expired/customer-export.json" |
        jq -e '.tenant == "acme-labs" and .retention_status == "expired"' >/dev/null
      [[ "$(redmine_retention_done_ratio)" == 0 ]]
      ;;
  esac
}

run_workflow() {
  local workflow=$1 actor=$2 family=$3 action=$4 outcome=$5
  local envelope signature result replay workflow_id request_id compensation
  local mail_highwater='' business_before=''
  envelope="${workdir}/${workflow}.json"
  result="${workdir}/${workflow}-result.json"
  replay="${workdir}/${workflow}-replay.json"
  compensation="${workdir}/${workflow}-compensation.json"
  make_envelope "${envelope}" "${workflow}" "${actor}" "${family}" "${action}" \
    "${outcome}" "${RANGE_ID}" "${run_id}"
  case "${workflow}" in
    accounting-credit)
      mail_highwater="$(mailbox_highwater billing.customer "${SYNTHETIC_MAIL_PASSWORD}")"
      business_before="$(odoo_partner_balance)"
      ;;
    advisory-campaign)
      mail_highwater="$(mailbox_highwater edge.operator "${SYNTHETIC_MAIL_PASSWORD}")"
      ;;
    support-triage)
      mail_highwater="$(mailbox_highwater reviewer "${REVIEWER_MAIL_PASSWORD}")"
      ;;
  esac
  signature="$(sign "${envelope}")"
  post_envelope "${workflow}" "${envelope}" "${signature}" "${result}"
  jq -e '.status == "succeeded" and .idempotent_replay == false' "${result}" >/dev/null
  request_id="$(jq -er '.request_id' "${envelope}")"
  verify_native "${workflow}" "${result}" "${request_id}" "${mail_highwater}"

  post_envelope "${workflow}" "${envelope}" "${signature}" "${replay}"
  jq -e --slurp '.[1].idempotent_replay == true and .[0].workflow_id == .[1].workflow_id' \
    "${result}" "${replay}" >/dev/null

  workflow_id="$(jq -er '.workflow_id' "${result}")"
  curl -fsS -X POST -H "Authorization: Bearer ${ADAPTER_TOKEN}" \
    "${ADAPTER_URL}/internal/v1/workflows/${workflow_id}/compensate" >"${compensation}"
  jq -e '.compensation_state == "completed"' "${compensation}" >/dev/null
  verify_compensation "${workflow}" "${result}" "${request_id}" "${business_before}"
  printf 'PASS %-24s workflow=%s\n' "${workflow}" "${workflow_id}"
}

"${ROOT}/seeding/seed.sh" business-workflows

denied="${workdir}/cross-range.json"
make_envelope "${denied}" feature-control svc-orion-canary assistant unleash:set \
  enable-canary other-range "${run_id}-denied"
denied_status="$(curl -sS -o /dev/null -w '%{http_code}' \
  -H "Authorization: Bearer ${ADAPTER_TOKEN}" \
  -H "X-Orion-Signature: $(sign "${denied}")" \
  -H 'Content-Type: application/json' --data-binary "@${denied}" \
  "${ADAPTER_URL}/internal/v1/workflows/feature-control/execute")"
[[ ${denied_status} == 403 ]] || {
  printf 'cross-range decision returned HTTP %s instead of 403\n' "${denied_status}" >&2
  exit 1
}

run_workflow feature-control svc-orion-canary assistant unleash:set enable-canary
run_workflow accounting-credit svc-orion-canary release-risk odoo:credit-note approve-adjustment
run_workflow incident-publication svc-orion-release assistant ghost:publish approve-publication
run_workflow advisory-campaign svc-orion-canary release-risk mautic:send cohort-orion-edge
run_workflow support-triage svc-orion-canary release-risk zammad:close routine-low-risk
run_workflow feedback-intake svc-orion-ingest release-risk feedback:ingest accepted-signal
run_workflow feedback-maintenance svc-orion-trainer release-risk lakefs:validate-partition partition-valid
run_workflow tenant-retention svc-data-steward assistant retention:delete retention-approved

printf 'bounded Orion business workflows passed with native effects, idempotency, range denial, and compensation\n'
