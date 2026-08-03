#!/usr/bin/env bash
set -Eeuo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly MODULE_ROOT
readonly WORKHUB_URL="${M01_WORKHUB_INTERNAL_URL:-http://10.61.30.22:3000}"
readonly WORKHUB_USER=svc-orion-agent
readonly WORKHUB_PASSWORD=KAI-M01-WorkHub-Agent-f1468d2a
readonly FORGEJO_URL="${M01_FORGEJO_INTERNAL_URL:-http://10.61.40.20:3000}"
readonly FORGEJO_REPOSITORY=svc-orion-agent/release-runbook-validation

FAILED_ISSUE_JSON=""
die() { printf '[m01 reset] ERROR: %s\n' "$*" >&2; exit 1; }
known_operation() { jq -e --arg id "$1" 'any(.[]; .id == $id)' "${MODULE_ROOT}/operations.json" >/dev/null; }
flag_for() { jq -er --arg id "$1" '.[] | select(.id == $id) | .flag' "${MODULE_ROOT}/operations.json"; }
issue_text() { jq -r '[.issue.subject,.issue.description,(.issue.journals[]?.notes // "")] | join("\n")' "$1"; }
cleanup() { [[ -z ${FAILED_ISSUE_JSON} ]] || rm -f "${FAILED_ISSUE_JSON}"; }
trap cleanup EXIT

load_failed_issue() {
  local operation=$1 issue_id=${M01_RESET_WORKHUB_ISSUE_ID:-} status flag evidence
  [[ -n ${issue_id} ]] || return 1
  [[ ${issue_id} =~ ^[0-9]+$ ]] || die 'M01_RESET_WORKHUB_ISSUE_ID must be numeric'
  FAILED_ISSUE_JSON="$(mktemp)"
  curl -fsS -u "${WORKHUB_USER}:${WORKHUB_PASSWORD}" -H 'Host: workhub.keplerops.lab' \
    "${WORKHUB_URL}/issues/${issue_id}.json?include=journals,relations,attachments" > "${FAILED_ISSUE_JSON}"
  status="$(jq -er '.issue.status.name' "${FAILED_ISSUE_JSON}")"
  [[ ${status} == New || ${status} == Queued || ${status} == Running || ${status} == Rejected ]] || \
    die "WorkHub issue ${issue_id} is successful/immutable (${status}); reset refused"
  flag="$(flag_for "${operation}")"
  ! grep -Fq "${flag}" < <(issue_text "${FAILED_ISSUE_JSON}") || \
    die 'flag-bearing WorkHub state is immutable; reset refused'
  evidence="$(jq -ce --arg operation "${operation}" --argjson issue_id "${issue_id}" '
    [.issue.description, (.issue.journals[]?.notes // "")]
    | map(fromjson?)
    | map(if (.attempt|type) == "object" then .attempt else . end)
    | map(select(
        .schema == "keplerops.m01.operation-attempt/v1"
        and .operation == $operation
        and (.attempt_id|test("^m01-attempt-[0-9a-f]{32}$"))
        and (.tool_invocation_id|test("^m01-[a-z]+-[0-9a-f]{32}$"))
        and (.request_sha256|test("^[0-9a-f]{64}$"))
        and ((.workhub_issue_id // .workhub_attempt_issue) == $issue_id)
        and (.result == "started" or .result == "prepared" or .result == "queued" or .result == "rejected")
      ))
    | select(length >= 1)
    | last' "${FAILED_ISSUE_JSON}")" || \
    die 'WorkHub issue is not bound to an exact server-owned failed operation attempt'
  [[ -n ${evidence} ]] || die 'failed attempt evidence is empty'
}

delete_bound_review_source() {
  local digest=${M01_RESET_SOURCE_SHA256:-} path=${M01_RESET_NEXTCLOUD_PATH:-} point source_uri encoded
  [[ -n ${digest} || -n ${path} ]] || return 0
  [[ -n ${FAILED_ISSUE_JSON} && -n ${digest} && -n ${path} ]] || \
    die 'source cleanup requires one failed WorkHub issue, digest, and Nextcloud path'
  [[ ${digest} =~ ^[0-9a-f]{64}$ ]] || die 'source digest is invalid'
  [[ ${path} == 'Partner Rooms/Cinder Labs/Policy Exceptions/'* && ${path} != *'..'* ]] || \
    die 'Nextcloud reset path is outside the writable review directory'
  grep -Fq "${digest}" < <(issue_text "${FAILED_ISSUE_JSON}") || \
    die 'failed WorkHub issue does not bind the requested source digest'
  point="$(curl -fsS -X POST -H 'api-key: KeplerV2-Training-Qdrant-Write' -H 'Content-Type: application/json' \
    --data "$(jq -cn --arg digest "${digest}" '{filter:{must:[{key:"sha256",match:{value:$digest}}]},limit:2,with_payload:true,with_vector:false}')" \
    'http://10.61.50.72:6333/collections/orion_partner_intake/points/scroll')"
  jq -e --arg digest "${digest}" '.result.points | length == 1 and .[0].payload.sha256 == $digest and (.[0].payload.source_uri|type == "string")' \
    <<<"${point}" >/dev/null || die 'indexed source is not one exact server-owned object'
  source_uri="$(jq -er '.result.points[0].payload.source_uri' <<<"${point}")"
  { [[ ${source_uri} == *"${path}"* ]] || [[ ${source_uri} == *"$(printf '%s' "${path}" | sed 's/ /%20/g')"* ]]; } || \
    die 'indexed source URI does not bind the requested Nextcloud path'
  grep -Fq "${source_uri}" < <(issue_text "${FAILED_ISSUE_JSON}") || \
    die 'failed WorkHub issue does not bind the indexed source URI'
  curl -fsS -X POST -H 'api-key: KeplerV2-Training-Qdrant-Write' -H 'Content-Type: application/json' \
    --data "$(jq -cn --arg digest "${digest}" '{filter:{must:[{key:"sha256",match:{value:$digest}}]}}')" \
    'http://10.61.50.72:6333/collections/orion_partner_intake/points/delete?wait=true' >/dev/null
  encoded="$(python3 -c 'import sys,urllib.parse; print(urllib.parse.quote(sys.argv[1], safe="/"))' "${path}")"
  curl -fsS -X DELETE -u 'reviewer:KeplerV2-Training-Reviewer' -H 'Host: files.keplerops.lab' \
    "http://10.61.30.23/remote.php/dav/files/reviewer/${encoded}" >/dev/null
}

delete_bound_failed_mail() {
  local uid=${M01_RESET_MESSAGE_UID:-} cleanup_mail=${M01_RESET_MAILBOX_CLEANUP:-} evidence
  [[ -n ${uid} || ${cleanup_mail} == 1 ]] || return 0
  [[ -n ${FAILED_ISSUE_JSON} ]] || die 'mail cleanup requires one failed WorkHub issue'
  [[ -z ${uid} || ${uid} =~ ^[0-9]+$ ]] || die 'M01_RESET_MESSAGE_UID must be numeric'
  : "${M01_RESET_IMAP_USER:?set M01_RESET_IMAP_USER}"
  : "${M01_RESET_IMAP_PASSWORD:?set M01_RESET_IMAP_PASSWORD}"
  evidence="$(jq -ce --arg uid "${uid}" '
    [.issue.description, (.issue.journals[]?.notes // "")]
    | map(fromjson?)
    | map(select(
        .schema == "keplerops.m01.operation-attempt/v1"
        and .operation == "kep-m01-f"
        and .tool == "send_external_review_bundle"
        and (.smtp_message_id|type == "string")
        and (.bundle_sha256|test("^[0-9a-f]{64}$"))
        and (.source_sha256|test("^[0-9a-f]{64}$"))
        and (.destination|endswith(".cinder.lab"))
        and ($uid == "" or (.mailbox_uid|tostring) == $uid or .mailbox_uid == null)
      ))
    | group_by([.attempt_id,.smtp_message_id,.bundle_sha256,.source_sha256,.destination])
    | select(length == 1)
    | .[0]
    | select(([.[] | .mailbox_uid | select(. != null)] | unique | length) <= 1)
    | sort_by(.mailbox_uid != null)
    | last' "${FAILED_ISSUE_JSON}")" || \
    die 'failed WorkHub record does not bind one exact external message'
  export M01_RESET_MAIL_EVIDENCE="${evidence}" M01_RESET_EXPECTED_UID="${uid}"
  python3 - <<'PY'
import email, hashlib, imaplib, json, os

evidence=json.loads(os.environ["M01_RESET_MAIL_EVIDENCE"])
client=imaplib.IMAP4(os.getenv("M01_RESET_IMAP_HOST", "10.61.90.20"), int(os.getenv("M01_RESET_IMAP_PORT", "143")))
client.login(os.environ["M01_RESET_IMAP_USER"], os.environ["M01_RESET_IMAP_PASSWORD"])
client.select("INBOX")
status, values=client.uid("search", None, "HEADER", "Message-ID", f'"{evidence["smtp_message_id"]}"')
if status != "OK":
    raise SystemExit("failed-message Message-ID search failed")
uids=[value for value in (values[0].decode().split() if values and values[0] else []) if value.isdigit()]
if not uids:
    client.logout()
    raise SystemExit("no exact failed message is visible yet; preserve the attempt and retry mailbox cleanup")
if len(uids) != 1:
    raise SystemExit("failed record does not resolve to one exact mailbox UID")
uid=uids[0]
expected_uid=os.environ.get("M01_RESET_EXPECTED_UID", "")
if expected_uid and uid != expected_uid:
    raise SystemExit("discovered mailbox UID differs from M01_RESET_MESSAGE_UID")
if evidence.get("mailbox_uid") not in (None, "", uid, int(uid)):
    raise SystemExit("discovered mailbox UID differs from failed WorkHub evidence")
status, parts=client.uid("fetch", uid, "(RFC822)")
if status != "OK" or not parts or not isinstance(parts[0], tuple):
    raise SystemExit("bound failed message is not readable")
message=email.message_from_bytes(parts[0][1])
attachments=[part.get_payload(decode=True) for part in message.walk() if part.get_filename()=="orion-edge-2026.08.md"]
if message.get("Message-ID") != evidence["smtp_message_id"]:
    raise SystemExit("mailbox UID has a different Message-ID")
if "".join(str(message.get("X-Orion-Bundle-SHA256", "")).split()) != evidence["bundle_sha256"]:
    raise SystemExit("mailbox UID has a different declared bundle digest")
if len(attachments) != 1 or hashlib.sha256(attachments[0]).hexdigest() != evidence["bundle_sha256"]:
    raise SystemExit("mailbox UID has different attachment bytes")
if evidence["destination"].lower() not in str(message.get("To", "")).lower():
    raise SystemExit("mailbox UID has a different destination")
if "".join(str(message.get("X-Orion-Source-SHA256", "")).split()) != evidence["source_sha256"]:
    raise SystemExit("mailbox UID has a different source digest")
if message.get("X-Orion-Attempt-ID") != evidence["attempt_id"]:
    raise SystemExit("mailbox UID has a different operation attempt")
client.uid("store", uid, "+FLAGS.SILENT", "(\\Deleted)")
status, _=client.uid("expunge", uid)
if status != "OK":
    raise SystemExit("server did not UID-expunge the exact failed message")
client.logout()
PY
  unset M01_RESET_MAIL_EVIDENCE M01_RESET_EXPECTED_UID
}

delete_failed_forgejo_run() {
  local run_id=${M01_RESET_FORGEJO_RUN_ID:-} token=${M01_FORGEJO_TOKEN:-} run conversation requested actor record
  [[ -n ${run_id} ]] || return 0
  [[ ${run_id} =~ ^[0-9]+$ && -n ${token} ]] || die 'failed Forgejo run reset requires run ID and scoped read token'
  run="$(curl -fsS -H "Authorization: token ${token}" \
    "${FORGEJO_URL}/api/v1/repos/${FORGEJO_REPOSITORY}/actions/runs/${run_id}")"
  [[ $(jq -r '.conclusion // .status' <<<"${run}") != success ]] || die 'successful validation run is immutable'
  conversation="$(jq -r '.event_payload.inputs.orion_conversation_id // .inputs.orion_conversation_id // empty' <<<"${run}")"
  requested=${M01_RESET_CONVERSATION_ID:-}
  if [[ -n ${requested} ]]; then
    [[ -n ${conversation} && ${requested} == "${conversation}" ]] || \
      die 'Forgejo failed run does not bind the requested conversation'
    [[ ${requested} =~ ^[A-Za-z0-9._:-]{3,128}$ ]] || die 'conversation ID is invalid'
    record="$(docker exec kep-v2-redis redis-cli -a KeplerV2-Training-Redis --raw GET "workhub:conversation:${requested}")"
    actor=${M01_RESET_ACTOR:-}
    [[ -n ${actor} && $(jq -r '.actor' <<<"${record}") == "${actor}" ]] || \
      die 'conversation owner does not match M01_RESET_ACTOR'
    docker exec kep-v2-redis redis-cli -a KeplerV2-Training-Redis DEL "workhub:conversation:${requested}" >/dev/null
  fi
  curl -fsS -X DELETE -H "Authorization: token ${token}" \
    "${FORGEJO_URL}/api/v1/repos/${FORGEJO_REPOSITORY}/actions/runs/${run_id}" >/dev/null
}

delete_failed_issue() {
  [[ -n ${FAILED_ISSUE_JSON} ]] || return 0
  local issue_id
  issue_id="$(jq -er '.issue.id' "${FAILED_ISSUE_JSON}")"
  curl -fsS -u "${WORKHUB_USER}:${WORKHUB_PASSWORD}" -H 'Host: workhub.keplerops.lab' \
    -X DELETE "${WORKHUB_URL}/issues/${issue_id}.json" >/dev/null
}

reset_one() {
  local operation=$1 changed=false
  known_operation "${operation}" || die "unknown operation: ${operation}"
  if load_failed_issue "${operation}"; then changed=true; fi
  case "${operation}" in
    kep-m01-c)
      delete_failed_forgejo_run
      if [[ -n ${M01_RESET_FORGEJO_RUN_ID:-} ]]; then changed=true; fi
      ;;
    kep-m01-e|kep-m01-f)
      delete_bound_review_source
      if [[ -n ${M01_RESET_SOURCE_SHA256:-} ]]; then changed=true; fi
      if [[ ${operation} == kep-m01-f ]]; then
        delete_bound_failed_mail
        if [[ -n ${M01_RESET_MESSAGE_UID:-} || ${M01_RESET_MAILBOX_CLEANUP:-} == 1 ]]; then changed=true; fi
      fi
      ;;
    kep-m01-h)
      [[ -z ${M01_RESET_PACKAGE_VERSION:-} ]] || die 'package releases are predecessor/earned registry state and are never unpublished by M01 reset'
      ;;
    kep-m01-i)
      [[ -z ${M01_RESET_LANGFLOW_JOB_ID:-} ]] || \
        die 'Langflow exposes no attempt-owned deletion ABI; the failed temporary-flow job is retained until native expiry'
      ;;
  esac
  delete_failed_issue
  if [[ ${changed} == true ]]; then
    printf '%s\n' "${operation}: removed only failed native records bound to the supplied attempt identifiers"
  else
    printf '%s\n' "${operation}: no failed attempt identifiers supplied; no state changed"
  fi
}

[[ $# -eq 1 ]] || die 'usage: reset.sh <operation-id>'
reset_one "$1"
