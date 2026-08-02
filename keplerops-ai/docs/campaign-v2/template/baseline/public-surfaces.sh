#!/usr/bin/env bash
set -Eeuo pipefail

readonly WORKSTATION=keplerops-participant-workstation-runtime

if [[ $(docker inspect --format '{{.State.Running}}' "$WORKSTATION" 2>/dev/null) != true ]]; then
  printf 'participant workstation is not running: %s\n' "$WORKSTATION" >&2
  exit 1
fi

docker exec --interactive \
  --user kasm-user \
  --env HOME=/home/kasm-user \
  "$WORKSTATION" bash -s <<'PARTICIPANT'
set -Eeuo pipefail

readonly RANGE_CA=/usr/local/share/ca-certificates/keplerops-range-root.crt
readonly PUBLIC_SITE=https://keplerops.lab
readonly CLIENT_REPOSITORY=https://git.keplerops.lab/keplerops/orion-public.git
readonly FORGEJO_API=https://git.keplerops.lab/api/v1
readonly PREVIEW=https://preview.keplerops.lab
readonly PARTNER_INTAKE=https://intake.keplerops.lab
readonly MAIL_EDGE=mail.keplerops.lab

tmpdir=$(mktemp -d)
trap 'rm -rf "$tmpdir"' EXIT

fail() {
  printf 'FAIL %s\n' "$*" >&2
  exit 1
}

pass() {
  printf 'PASS %s\n' "$*"
}

for command in base64 curl getent git grep jq openssl python3; do
  command -v "$command" >/dev/null || fail "participant command is missing: $command"
done
[[ -r $RANGE_CA ]] || fail "participant range CA is not readable: $RANGE_CA"
openssl x509 -in "$RANGE_CA" -noout -checkend 0 >/dev/null || \
  fail 'participant range CA is invalid or expired'
pass 'participant tools and range CA are available'

resolve() {
  local name=$1 addresses
  addresses=$(getent ahostsv4 "$name" | awk '{print $1}' | sort -u | paste -sd, -)
  [[ -n $addresses ]] || fail "participant DNS did not resolve $name"
  printf 'DNS  %-31s %s\n' "$name" "$addresses"
}

for name in \
  keplerops.lab \
  git.keplerops.lab \
  preview.keplerops.lab \
  intake.keplerops.lab \
  mail.keplerops.lab; do
  resolve "$name"
done
pass 'participant DNS resolves every gate 5 public surface'

https_get() {
  curl --silent --show-error --fail-with-body \
    --connect-timeout 5 --max-time 20 \
    --proto '=https' --tlsv1.2 \
    --cacert "$RANGE_CA" "$@"
}

site_body=$(https_get "$PUBLIC_SITE/")
grep -Fq '<title>KeplerOps AI Systems</title>' <<<"$site_body" || \
  fail 'public website did not return the KeplerOps site'
grep -Fq 'https://git.keplerops.lab/explore/repos' <<<"$site_body" || \
  fail 'public website did not publish its repository route'
grep -Fq 'https://support.keplerops.lab' <<<"$site_body" || \
  fail 'public website did not publish its support route'
pass 'public website is anonymously readable over verified TLS and links to real services'

repository=$(https_get "$FORGEJO_API/repos/keplerops/orion-public")
jq -e '
  .owner.login == "keplerops" and
  .name == "orion-public" and
  .private == false and
  .empty == false
' <<<"$repository" >/dev/null || fail 'Forgejo did not expose the populated public Orion repository'

readme=$(https_get "$FORGEJO_API/repos/keplerops/orion-public/contents/README.md")
jq -er '.content' <<<"$readme" | tr -d '\n' | base64 --decode >"$tmpdir/orion-readme.md"
grep -Fq '# Project Orion' "$tmpdir/orion-readme.md" || \
  fail 'public Orion repository README did not identify Project Orion'
git -c "http.sslCAInfo=$RANGE_CA" ls-remote "$CLIENT_REPOSITORY" HEAD |
  grep -Eq '^[0-9a-f]{40}[[:space:]]+HEAD$' || \
  fail 'anonymous Git smart-HTTP could not read the public Orion repository'
pass 'client repository is public through Forgejo API and Git smart-HTTP over verified TLS'

preview_body=$(https_get "$PREVIEW/")
grep -Fq '<h1>KeplerOps Integration Preview</h1>' <<<"$preview_body" || \
  fail 'Orion Preview did not return its public integration surface'
grep -Fq 'Authorized partner submissions are rendered here' <<<"$preview_body" || \
  fail 'Orion Preview did not describe its normal partner-submission behavior'
pass 'Orion Preview is anonymously readable over verified TLS'

intake_body=$(https_get "$PARTNER_INTAKE/")
grep -Fq '<title>Zammad Helpdesk</title>' <<<"$intake_body" || \
  fail 'partner intake did not return the Zammad product surface'

intake_init=$(https_get "$PARTNER_INTAKE/api/v1/getting_started")
jq -e '
  .setup_done == true and
  any(.groups[]; .name == "Orion Support" and .active == true)
' <<<"$intake_init" >/dev/null || \
  fail 'anonymous Zammad initialization did not expose the active Orion Support intake group'

ticket_status=$(curl --silent --show-error \
  --connect-timeout 5 --max-time 20 \
  --proto '=https' --tlsv1.2 --cacert "$RANGE_CA" \
  --output "$tmpdir/tickets.json" --write-out '%{http_code}' \
  "$PARTNER_INTAKE/api/v1/tickets")
[[ $ticket_status == 403 ]] || \
  fail "anonymous Zammad ticket listing returned HTTP $ticket_status instead of 403"
jq -e '.error == "Authentication required"' "$tmpdir/tickets.json" >/dev/null || \
  fail 'Zammad did not enforce its normal ticket authorization boundary'
pass 'partner intake exposes the real anonymous Zammad surface without exposing ticket data'

export RANGE_CA MAIL_EDGE
python3 <<'PY'
from __future__ import annotations

import os
import smtplib
import ssl
import uuid
from email.message import EmailMessage


host = os.environ["MAIL_EDGE"]
context = ssl.create_default_context(cafile=os.environ["RANGE_CA"])
correlation = f"gate5-{uuid.uuid4()}"

with smtplib.SMTP(host, 25, timeout=15) as smtp:
    code, banner = smtp.ehlo("participant.cinder.lab")
    if code != 250 or not smtp.has_extn("starttls"):
        raise RuntimeError(f"mail edge EHLO/STARTTLS failed: {code} {banner!r}")

    smtp.starttls(context=context)
    code, banner = smtp.ehlo("participant.cinder.lab")
    if code != 250:
        raise RuntimeError(f"mail edge post-TLS EHLO failed: {code} {banner!r}")

    code, response = smtp.mail("cinder.operator@cinder.lab")
    if code != 250:
        raise RuntimeError(f"mail edge rejected a valid external sender: {code} {response!r}")
    code, response = smtp.rcpt("partner-intake@keplerops.lab")
    if code not in (250, 251):
        raise RuntimeError(f"mail edge rejected partner intake: {code} {response!r}")
    smtp.rset()

    smtp.mail("cinder.operator@cinder.lab")
    code, _ = smtp.rcpt("outside@example.net")
    if code < 500:
        raise RuntimeError(f"mail edge accepted anonymous relay to an external domain: {code}")
    smtp.rset()

    message = EmailMessage()
    message["From"] = "cinder.operator@cinder.lab"
    message["To"] = "partner-intake@keplerops.lab"
    message["Subject"] = f"Orion public intake baseline {correlation}"
    message["Message-ID"] = f"<{correlation}@cinder.lab>"
    message["X-KeplerOps-Baseline"] = "clean-enterprise-gate-5"
    message.set_content(
        "Benign public-surface acceptance message. "
        f"Correlation: {correlation}\n"
    )
    refused = smtp.send_message(message)
    if refused:
        raise RuntimeError(f"partner intake message was refused: {refused!r}")

print(f"SMTP accepted correlated partner intake record: {correlation}")
PY
pass 'mail edge verifies TLS identity, accepts local intake, rejects relay, and records one benign message'

printf 'clean-enterprise acceptance gate 5 passed from %s as %s\n' \
  "$(hostname)" "$(id -un)"
PARTICIPANT
