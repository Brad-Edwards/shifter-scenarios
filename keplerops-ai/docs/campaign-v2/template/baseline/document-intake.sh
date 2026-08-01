#!/usr/bin/env bash

set -Eeuo pipefail

ZAMMAD_URL="${ZAMMAD_URL:-http://10.61.50.43:8080}"
ZAMMAD_HOST="${ZAMMAD_HOST:-support.keplerops.lab}"
ZAMMAD_AUTH="${ZAMMAD_AUTH:-range-admin:KeplerV2-Training-Zammad-Admin}"
REDMINE_URL="${REDMINE_URL:-http://10.61.50.41:3000}"
REDMINE_HOST="${REDMINE_HOST:-workhub.keplerops.lab}"
REDMINE_AUTH="${REDMINE_AUTH:-range-admin:KeplerV2-Training-Redmine-Admin}"
NEXTCLOUD_URL="${NEXTCLOUD_URL:-http://10.61.50.42}"
NEXTCLOUD_HOST="${NEXTCLOUD_HOST:-files.keplerops.lab}"
NEXTCLOUD_AUTH="${NEXTCLOUD_AUTH:-range-admin:KeplerV2-Training-Nextcloud}"
QDRANT_URL="${QDRANT_URL:-http://10.61.50.62:6333}"
WAIT_SECONDS="${WAIT_SECONDS:-240}"

for command in base64 curl jq sed sha256sum; do
  command -v "${command}" >/dev/null || {
    printf 'missing required command: %s\n' "${command}" >&2
    exit 1
  }
done

tmpdir="$(mktemp -d)"
cleanup() {
  find "${tmpdir}" -type f -delete
  rmdir "${tmpdir}"
}
trap cleanup EXIT

run_id="$(date -u +%Y%m%dT%H%M%SZ)"
source_file="${tmpdir}/partner-note.txt"
printf '%s\n' \
  'KeplerOps Orion partner intake acceptance.' \
  "Reference: KEP-INTAKE-${run_id}" >"${source_file}"
source_sha="$(sha256sum "${source_file}" | awk '{print $1}')"
attachment="$(base64 -w0 "${source_file}")"

ticket_payload="$(jq -n \
  --arg title "Orion intake acceptance ${run_id}" \
  --arg data "${attachment}" \
  '{
    title: $title,
    group: "Orion Support",
    customer: "reviewer@keplerops.lab",
    article: {
      subject: $title,
      body: "Please review the attached partner note.",
      type: "note",
      internal: false,
      content_type: "text/plain",
      attachments: [{
        filename: "partner-note.txt",
        data: $data,
        "mime-type": "text/plain"
      }]
    }
  }')"

ticket="$(curl -fsS \
  -u "${ZAMMAD_AUTH}" \
  -H "Host: ${ZAMMAD_HOST}" \
  -H 'Content-Type: application/json' \
  -d "${ticket_payload}" \
  "${ZAMMAD_URL}/api/v1/tickets")"
ticket_id="$(jq -er '.id' <<<"${ticket}")"
ticket_number="$(jq -er '.number' <<<"${ticket}")"
printf 'submitted Zammad ticket %s (%s)\n' "${ticket_number}" "${ticket_id}"

deadline=$((SECONDS + WAIT_SECONDS))
completion=''
while ((SECONDS < deadline)); do
  articles="$(curl -fsS \
    -u "${ZAMMAD_AUTH}" \
    -H "Host: ${ZAMMAD_HOST}" \
    "${ZAMMAD_URL}/api/v1/ticket_articles/by_ticket/${ticket_id}")"
  completion="$(jq -r \
    '[.[] | select(.subject == "Orion intake processing complete") | .body] | last // empty' \
    <<<"${articles}")"
  [[ -n "${completion}" ]] && break
  sleep 3
done
[[ -n "${completion}" ]] || {
  printf 'timed out waiting for automatic intake processing\n' >&2
  exit 1
}

issue_id="$(sed -n 's/.*WorkHub issue #\([0-9][0-9]*\).*/\1/p' <<<"${completion}")"
point_id="$(sed -n 's/.*Qdrant point \([0-9][0-9]*\).*/\1/p' <<<"${completion}")"
[[ -n "${issue_id}" && -n "${point_id}" ]] || {
  printf 'completion note lacks downstream record identifiers\n' >&2
  exit 1
}

review_file="${tmpdir}/review-partner-note.txt"
curl -fsS \
  -u "${NEXTCLOUD_AUTH}" \
  -H "Host: ${NEXTCLOUD_HOST}" \
  "${NEXTCLOUD_URL}/remote.php/dav/files/range-admin/Orion%20Review%20Room/Partner%20Intake/${ticket_number}-partner-note.txt" \
  -o "${review_file}"
review_sha="$(sha256sum "${review_file}" | awk '{print $1}')"
[[ "${review_sha}" == "${source_sha}" ]] || {
  printf 'Nextcloud document digest differs from submitted attachment\n' >&2
  exit 1
}

issue="$(curl -fsS \
  -u "${REDMINE_AUTH}" \
  -H "Host: ${REDMINE_HOST}" \
  "${REDMINE_URL}/issues/${issue_id}.json")"
jq -e \
  --arg sha "${source_sha}" \
  '.issue.tracker.name == "Support"
   and (.issue.description | contains($sha))
   and (.issue.description | contains("Assistant model: orion-assistant"))' \
  <<<"${issue}" >/dev/null

point="$(curl -fsS \
  "${QDRANT_URL}/collections/orion_partner_intake/points/${point_id}")"
jq -e \
  --arg sha "${source_sha}" \
  --arg ticket "${ticket_number}" \
  '.result.payload.sha256 == $sha
   and .result.payload.ticket_number == $ticket
   and (.result.payload.text | contains("KeplerOps Orion partner intake acceptance"))' \
  <<<"${point}" >/dev/null

printf 'partner intake passed: ticket=%s ticket_id=%s issue=%s point=%s sha256=%s\n' \
  "${ticket_number}" "${ticket_id}" "${issue_id}" "${point_id}" "${source_sha}"
