#!/usr/bin/env bash

set -Eeuo pipefail

STALWART_SMTP_HOST="${STALWART_SMTP_HOST:-10.61.10.20}"
STALWART_SMTP_PORT="${STALWART_SMTP_PORT:-587}"
STALWART_IMAP_HOST="${STALWART_IMAP_HOST:-10.61.10.20}"
STALWART_IMAP_PORT="${STALWART_IMAP_PORT:-993}"
CINDER_MAIL_USER="${CINDER_MAIL_USER:-cinder.operator}"
CINDER_MAIL_PASSWORD="${CINDER_MAIL_PASSWORD:-KeplerV2-Training-Cinder}"
ZAMMAD_URL="${ZAMMAD_URL:-http://10.61.50.43:8080}"
ZAMMAD_HOST="${ZAMMAD_HOST:-support.keplerops.lab}"
ZAMMAD_ADMIN_AUTH="${ZAMMAD_ADMIN_AUTH:-range-admin:KeplerV2-Training-Zammad-Admin}"
ZAMMAD_SUPPORT_AUTH="${ZAMMAD_SUPPORT_AUTH:-support.analyst:KeplerV2-Training-Support}"
REDMINE_URL="${REDMINE_URL:-http://10.61.50.41:3000}"
REDMINE_HOST="${REDMINE_HOST:-workhub.keplerops.lab}"
REDMINE_AUTH="${REDMINE_AUTH:-range-admin:KeplerV2-Training-Redmine-Admin}"
NEXTCLOUD_URL="${NEXTCLOUD_URL:-http://10.61.50.42}"
NEXTCLOUD_HOST="${NEXTCLOUD_HOST:-files.keplerops.lab}"
NEXTCLOUD_OWNER_AUTH="${NEXTCLOUD_OWNER_AUTH:-reviewer:KeplerV2-Training-Reviewer}"
KEYCLOAK_URL="${KEYCLOAK_URL:-http://10.61.50.20:8080}"
KEYCLOAK_REALM="${KEYCLOAK_REALM:-keplerops}"
KEYCLOAK_PARTNER_CLIENT_ID="${KEYCLOAK_PARTNER_CLIENT_ID:-orion-partner-intake}"
KEYCLOAK_PARTNER_CLIENT_SECRET="${KEYCLOAK_PARTNER_CLIENT_SECRET:-KeplerV2-Training-Partner-Intake-Keycloak}"
QDRANT_URL="${QDRANT_URL:-http://10.61.50.62:6333}"
WAIT_SECONDS="${WAIT_SECONDS:-420}"

for command in curl jq python3 sed sha256sum; do
  command -v "${command}" >/dev/null || {
    printf 'missing required command: %s\n' "${command}" >&2
    exit 1
  }
done

tmpdir="$(mktemp -d)"
ticket_id=''
cleanup() {
  find "${tmpdir}" -type f -delete
  rmdir "${tmpdir}"
}
trap cleanup EXIT

correlation="$(printf '%s:%s:%s' "$(date +%s%N)" "$$" "${RANDOM}" | sha256sum | cut -c1-12)"
subject='Cinder Labs Orion integration profile'
source_file="${tmpdir}/orion-integration-profile.txt"
cat >"${source_file}" <<'DOCUMENT'
Cinder Labs requests access to the Orion partner review workspace.

Organization: Cinder Labs
Contact: Avery Morgan <cinder.operator@cinder.lab>
Purpose: Review the Orion integration profile and coordinate compatibility findings.
Requested access: Partner files and the associated WorkHub project only.
DOCUMENT
source_sha="$(sha256sum "${source_file}" | awk '{print $1}')"

old_tickets="$(curl -fsS \
  -u "${ZAMMAD_ADMIN_AUTH}" \
  -H "Host: ${ZAMMAD_HOST}" \
  "${ZAMMAD_URL}/api/v1/tickets?per_page=100")"
while IFS= read -r old_ticket_id; do
  [[ -n ${old_ticket_id} ]] || continue
  curl -fsS -X DELETE \
    -u "${ZAMMAD_ADMIN_AUTH}" \
    -H "Host: ${ZAMMAD_HOST}" \
    "${ZAMMAD_URL}/api/v1/tickets/${old_ticket_id}" >/dev/null
done < <(jq -r --arg title "${subject}" \
  '.[] | select(.title == $title) | .id' <<<"${old_tickets}")

export CINDER_MAIL_PASSWORD CINDER_MAIL_USER STALWART_SMTP_HOST STALWART_SMTP_PORT
export STALWART_IMAP_HOST STALWART_IMAP_PORT
export CORRELATION="${correlation}" SOURCE_FILE="${source_file}" SUBJECT="${subject}"
python3 <<'PY'
from __future__ import annotations

import os
import imaplib
import smtplib
import ssl
from email.message import EmailMessage

message = EmailMessage()
message["From"] = "Avery Morgan <cinder.operator@cinder.lab>"
message["To"] = "partner-intake@keplerops.lab"
message["Subject"] = os.environ["SUBJECT"]
message["Message-ID"] = f"<{os.environ['CORRELATION']}@cinder.lab>"
message.set_content(
    "Please review the attached Orion integration profile and provision the "
    "approved collaboration access."
)
with open(os.environ["SOURCE_FILE"], "rb") as source:
    message.add_attachment(
        source.read(),
        maintype="text",
        subtype="plain",
        filename="orion-integration-profile.txt",
    )

context = ssl.create_default_context()
context.check_hostname = False
context.verify_mode = ssl.CERT_NONE
with imaplib.IMAP4_SSL(
    os.environ["STALWART_IMAP_HOST"],
    int(os.environ["STALWART_IMAP_PORT"]),
    ssl_context=context,
    timeout=30,
) as mailbox:
    mailbox.login(os.environ["CINDER_MAIL_USER"], os.environ["CINDER_MAIL_PASSWORD"])
    mailbox.select("INBOX")
    for old_subject in ("Update Your Account", "Cinder Labs Orion access approved"):
        status, ids = mailbox.search(None, "SUBJECT", f'"{old_subject}"')
        if status == "OK":
            for message_id in ids[0].split():
                mailbox.store(message_id, "+FLAGS", "\\Deleted")
    mailbox.expunge()

with smtplib.SMTP(
    os.environ["STALWART_SMTP_HOST"],
    int(os.environ["STALWART_SMTP_PORT"]),
    timeout=30,
) as smtp:
    smtp.starttls(context=context)
    smtp.login(os.environ["CINDER_MAIL_USER"], os.environ["CINDER_MAIL_PASSWORD"])
    smtp.send_message(message)
PY
printf 'submitted partner email through Stalwart SMTP\n'

deadline=$((SECONDS + WAIT_SECONDS))
ticket=''
while ((SECONDS < deadline)); do
  tickets="$(curl -fsS \
    -u "${ZAMMAD_ADMIN_AUTH}" \
    -H "Host: ${ZAMMAD_HOST}" \
    "${ZAMMAD_URL}/api/v1/tickets?per_page=100")"
  ticket="$(jq -c --arg title "${subject}" \
    '[.[] | select(.title == $title)] | last // empty' <<<"${tickets}")"
  [[ -n ${ticket} ]] && break
  sleep 3
done
[[ -n ${ticket} ]] || {
  printf 'timed out waiting for Zammad to import the partner mailbox message\n' >&2
  exit 1
}
ticket_id="$(jq -er '.id' <<<"${ticket}")"
ticket_number="$(jq -er '.number' <<<"${ticket}")"

articles="$(curl -fsS \
  -u "${ZAMMAD_ADMIN_AUTH}" \
  -H "Host: ${ZAMMAD_HOST}" \
  "${ZAMMAD_URL}/api/v1/ticket_articles/by_ticket/${ticket_id}")"
attachment_record="$(jq -c \
  '[.[] as $article | $article.attachments[]? |
    select(.filename == "orion-integration-profile.txt") |
    {article_id: $article.id, attachment_id: .id}] | last // empty' \
  <<<"${articles}")"
[[ -n ${attachment_record} ]] || {
  printf 'Zammad ticket does not contain the submitted attachment\n' >&2
  exit 1
}
article_id="$(jq -er '.article_id' <<<"${attachment_record}")"
attachment_id="$(jq -er '.attachment_id' <<<"${attachment_record}")"
zammad_copy="${tmpdir}/zammad-attachment.txt"
curl -fsS \
  -u "${ZAMMAD_ADMIN_AUTH}" \
  -H "Host: ${ZAMMAD_HOST}" \
  "${ZAMMAD_URL}/api/v1/ticket_attachment/${ticket_id}/${article_id}/${attachment_id}" \
  -o "${zammad_copy}"
[[ "$(sha256sum "${zammad_copy}" | awk '{print $1}')" == "${source_sha}" ]] || {
  printf 'Zammad attachment digest differs from the SMTP submission\n' >&2
  exit 1
}

curl -fsS \
  -u "${ZAMMAD_SUPPORT_AUTH}" \
  -H "Host: ${ZAMMAD_HOST}" \
  -H 'Content-Type: application/json' \
  -d "$(jq -cn --argjson id "${ticket_id}" \
    '{object: "Ticket", o_id: $id, item: "partner-review-accepted"}')" \
  "${ZAMMAD_URL}/api/v1/tags/add" >/dev/null
printf 'support accepted ticket %s through its native triage state\n' "${ticket_number}"

completion=''
while ((SECONDS < deadline)); do
  articles="$(curl -fsS \
    -u "${ZAMMAD_ADMIN_AUTH}" \
    -H "Host: ${ZAMMAD_HOST}" \
    "${ZAMMAD_URL}/api/v1/ticket_articles/by_ticket/${ticket_id}")"
  completion="$(jq -r \
    '[.[] | select(.subject == "Orion intake processing complete") | .body] |
     last // empty' <<<"${articles}")"
  [[ -n ${completion} ]] && break
  sleep 3
done
[[ -n ${completion} ]] || {
  printf 'timed out waiting for automatic intake processing\n' >&2
  exit 1
}

issue_id="$(sed -n 's/.*issue #\([0-9][0-9]*\).*/\1/p' <<<"${completion}")"
project_id="$(sed -n 's/.*WorkHub project \([^ ]*\).*/\1/p' <<<"${completion}")"
citation="zammad://tickets/${ticket_number}/articles/${article_id}/attachments/${attachment_id}"
[[ -n ${issue_id} && ${project_id} == partner-cinder-labs ]] || {
  printf 'completion note lacks the expected WorkHub access records\n' >&2
  exit 1
}
[[ ${completion} == *"${citation}"* && ${completion} == *"${source_sha}"* ]] || {
  printf 'completion note lost its source citation or attachment digest\n' >&2
  exit 1
}

point_id="$(python3 -c 'import sys; print(int(sys.argv[1][:15], 16))' "${source_sha}")"
point="$(curl -fsS \
  "${QDRANT_URL}/collections/orion_partner_intake/points/${point_id}")"
jq -e \
  --arg sha "${source_sha}" \
  --arg ticket "${ticket_number}" \
  --arg citation "${citation}" \
  '.result.payload.sha256 == $sha
   and .result.payload.ticket_number == $ticket
   and .result.payload.source_uri == $citation
   and .result.payload.citation.source == $citation
   and .result.payload.citation.sha256 == $sha
   and (.result.payload.text | contains("Cinder Labs requests access"))' \
  <<<"${point}" >/dev/null

review_file="${tmpdir}/nextcloud-attachment.txt"
curl -fsS \
  -u "${NEXTCLOUD_OWNER_AUTH}" \
  -H "Host: ${NEXTCLOUD_HOST}" \
  "${NEXTCLOUD_URL}/remote.php/dav/files/reviewer/Partner%20Rooms/Cinder%20Labs/orion-integration-profile.txt" \
  -o "${review_file}"
[[ "$(sha256sum "${review_file}" | awk '{print $1}')" == "${source_sha}" ]] || {
  printf 'Nextcloud partner-room document digest differs from the submitted attachment\n' >&2
  exit 1
}

shares="$(curl -fsS -G \
  -u "${NEXTCLOUD_OWNER_AUTH}" \
  -H "Host: ${NEXTCLOUD_HOST}" \
  -H 'OCS-APIRequest: true' \
  --data 'format=json' \
  --data 'reshares=true' \
  "${NEXTCLOUD_URL}/ocs/v2.php/apps/files_sharing/api/v1/shares")"
jq -e \
  '[.ocs.data[] |
    select((.share_type | tonumber) == 0 and .share_with == "cinder.operator")] as $shares |
   ($shares | length) == 1
   and $shares[0].path == "/Partner Rooms/Cinder Labs"
   and ($shares[0].permissions | tonumber) == 15' <<<"${shares}" >/dev/null

issue="$(curl -fsS \
  -u "${REDMINE_AUTH}" \
  -H "Host: ${REDMINE_HOST}" \
  "${REDMINE_URL}/issues/${issue_id}.json")"
jq -e \
  --arg sha "${source_sha}" \
  --arg citation "${citation}" \
  '.issue.project.name == "Cinder Labs Partner Review"
   and .issue.tracker.name == "Support"
   and (.issue.description | contains($sha))
   and (.issue.description | contains($citation))' <<<"${issue}" >/dev/null

users="$(curl -fsS -G \
  -u "${REDMINE_AUTH}" \
  -H "Host: ${REDMINE_HOST}" \
  --data-urlencode 'name=cinder.operator@cinder.lab' \
  --data 'status=' \
  "${REDMINE_URL}/users.json")"
redmine_user_id="$(jq -er \
  '.users[] | select(.mail == "cinder.operator@cinder.lab") | .id' <<<"${users}")"
user_detail="$(curl -fsS -G \
  -u "${REDMINE_AUTH}" \
  -H "Host: ${REDMINE_HOST}" \
  --data 'include=memberships' \
  "${REDMINE_URL}/users/${redmine_user_id}.json")"
jq -e \
  '(.user.memberships | length) == 1
   and .user.memberships[0].project.name == "Cinder Labs Partner Review"
   and [.user.memberships[0].roles[].name] == ["Reporter"]' \
  <<<"${user_detail}" >/dev/null

keycloak_token="$(curl -fsS \
  -d grant_type=client_credentials \
  --data-urlencode "client_id=${KEYCLOAK_PARTNER_CLIENT_ID}" \
  --data-urlencode "client_secret=${KEYCLOAK_PARTNER_CLIENT_SECRET}" \
  "${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}/protocol/openid-connect/token" |
  jq -er '.access_token')"
keycloak_users="$(curl -fsS -G \
  -H "Authorization: Bearer ${keycloak_token}" \
  --data-urlencode 'username=cinder.operator' \
  --data 'exact=true' \
  "${KEYCLOAK_URL}/admin/realms/${KEYCLOAK_REALM}/users")"
keycloak_user_id="$(jq -er '.[0].id' <<<"${keycloak_users}")"
jq -e \
  '.[0].email == "cinder.operator@cinder.lab"
   and .[0].enabled == true
   and ([.[0].requiredActions[]] |
        sort == ["UPDATE_PASSWORD", "VERIFY_EMAIL"])' \
  <<<"${keycloak_users}" >/dev/null
keycloak_groups="$(curl -fsS \
  -H "Authorization: Bearer ${keycloak_token}" \
  "${KEYCLOAK_URL}/admin/realms/${KEYCLOAK_REALM}/users/${keycloak_user_id}/groups")"
jq -e \
  '[.[].name] | sort == ["RG-Nextcloud-Orion-Partner", "RG-WorkHub-Orion-Partner"]' \
  <<<"${keycloak_groups}" >/dev/null

export CINDER_MAIL_PASSWORD CINDER_MAIL_USER STALWART_IMAP_HOST STALWART_IMAP_PORT
python3 <<'PY'
from __future__ import annotations

import email
import imaplib
import os
import ssl
import time

context = ssl.create_default_context()
context.check_hostname = False
context.verify_mode = ssl.CERT_NONE
deadline = time.monotonic() + 120
matched: list[bytes] = []
while time.monotonic() < deadline:
    with imaplib.IMAP4_SSL(
        os.environ["STALWART_IMAP_HOST"],
        int(os.environ["STALWART_IMAP_PORT"]),
        ssl_context=context,
        timeout=30,
    ) as mailbox:
        mailbox.login(os.environ["CINDER_MAIL_USER"], os.environ["CINDER_MAIL_PASSWORD"])
        mailbox.select("INBOX")
        status, ids = mailbox.search(None, "ALL")
        if status != "OK":
            raise RuntimeError("could not search the Cinder partner mailbox")
        invitation = False
        welcome = False
        matched = []
        for message_id in ids[0].split():
            status, payload = mailbox.fetch(message_id, "(RFC822)")
            if status != "OK":
                continue
            message = email.message_from_bytes(payload[0][1])
            subject = message.get("Subject", "")
            body = "".join(
                part.get_payload(decode=True).decode(errors="replace")
                for part in message.walk()
                if part.get_content_type() == "text/plain"
                and part.get_payload(decode=True)
            )
            if "login-actions/action-token" in body:
                invitation = True
                matched.append(message_id)
            if subject == "Cinder Labs Orion access approved":
                if "partner-cinder-labs" not in body or "Temporary WorkHub password" not in body:
                    raise RuntimeError("partner welcome mail lacks its scoped access details")
                welcome = True
                matched.append(message_id)
        if invitation and welcome:
            break
    time.sleep(3)
else:
    raise TimeoutError("Keycloak invitation and partner access mail did not arrive")
PY

printf 'partner intake passed: ticket=%s project=%s issue=%s point=%s sha256=%s\n' \
  "${ticket_number}" "${project_id}" "${issue_id}" "${point_id}" "${source_sha}"
