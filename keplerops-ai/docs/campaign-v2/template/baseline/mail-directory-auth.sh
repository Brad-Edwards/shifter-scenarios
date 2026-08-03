#!/usr/bin/env bash

set -Eeuo pipefail

readonly MAIL_HOST=${STALWART_MAIL_HOST:-10.61.10.20}
readonly SMTP_PORT=${STALWART_SMTP_PORT:-587}
readonly IMAP_PORT=${STALWART_IMAP_PORT:-993}
readonly EMPLOYEE_USER=${MAIL_EMPLOYEE_USER:-reviewer}
readonly EMPLOYEE_PASSWORD=${MAIL_EMPLOYEE_PASSWORD:-KeplerV2-Training-Reviewer}
readonly RECIPIENT_USER=${MAIL_RECIPIENT_USER:-ml.engineer}
readonly RECIPIENT_PASSWORD=${MAIL_RECIPIENT_PASSWORD:-KeplerV2-Training-MLEngineer}
readonly DISABLED_USER=${MAIL_DISABLED_USER:-former.contractor}
readonly DISABLED_PASSWORD=${MAIL_DISABLED_PASSWORD:-KeplerV2-Training-Former-Contractor}
readonly SERVICE_USER=${MAIL_SERVICE_USER:-partner-intake}
readonly SERVICE_PASSWORD=${MAIL_SERVICE_PASSWORD:-KeplerV2-Training-Partner}

command -v python3 >/dev/null 2>&1 || {
  echo 'python3 is required for the mail directory baseline' >&2
  exit 2
}

export MAIL_HOST SMTP_PORT IMAP_PORT EMPLOYEE_USER EMPLOYEE_PASSWORD
export RECIPIENT_USER RECIPIENT_PASSWORD DISABLED_USER DISABLED_PASSWORD
export SERVICE_USER SERVICE_PASSWORD

python3 <<'PY'
from __future__ import annotations

import email
import imaplib
import os
import smtplib
import ssl
import time
import uuid
from email.message import EmailMessage


MAIL_HOST = os.environ["MAIL_HOST"]
SMTP_PORT = int(os.environ["SMTP_PORT"])
IMAP_PORT = int(os.environ["IMAP_PORT"])
EMPLOYEE_USER = os.environ["EMPLOYEE_USER"]
EMPLOYEE_PASSWORD = os.environ["EMPLOYEE_PASSWORD"]
RECIPIENT_USER = os.environ["RECIPIENT_USER"]
RECIPIENT_PASSWORD = os.environ["RECIPIENT_PASSWORD"]
DISABLED_USER = os.environ["DISABLED_USER"]
DISABLED_PASSWORD = os.environ["DISABLED_PASSWORD"]
SERVICE_USER = os.environ["SERVICE_USER"]
SERVICE_PASSWORD = os.environ["SERVICE_PASSWORD"]


def tls_context() -> ssl.SSLContext:
    ca_file = os.getenv("MAIL_CA_FILE")
    if ca_file:
        return ssl.create_default_context(cafile=ca_file)
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def login(user: str, password: str) -> None:
    with imaplib.IMAP4_SSL(
        MAIL_HOST, IMAP_PORT, ssl_context=tls_context(), timeout=15
    ) as mailbox:
        mailbox.login(user, password)


def expect_rejected(user: str, password: str) -> None:
    try:
        login(user, password)
    except imaplib.IMAP4.error:
        return
    raise RuntimeError(f"mail authentication unexpectedly accepted {user!r}")


login(EMPLOYEE_USER, EMPLOYEE_PASSWORD)
login(SERVICE_USER, SERVICE_PASSWORD)
expect_rejected(DISABLED_USER, DISABLED_PASSWORD)
expect_rejected("unknown.employee", "not-a-directory-password")

correlation = uuid.uuid4().hex
subject = f"Orion evaluation handoff {correlation}"
message = EmailMessage()
message["From"] = f"{EMPLOYEE_USER}@keplerops.lab"
message["To"] = f"{RECIPIENT_USER}@keplerops.lab"
message["Subject"] = subject
message["Message-ID"] = f"<{correlation}@keplerops.lab>"
message.set_content(
    "The Orion evaluation summary is ready for the engineering review meeting."
)

with smtplib.SMTP(MAIL_HOST, SMTP_PORT, timeout=15) as smtp:
    smtp.starttls(context=tls_context())
    smtp.login(EMPLOYEE_USER, EMPLOYEE_PASSWORD)
    smtp.send_message(message)

deadline = time.monotonic() + 60
while time.monotonic() < deadline:
    with imaplib.IMAP4_SSL(
        MAIL_HOST, IMAP_PORT, ssl_context=tls_context(), timeout=15
    ) as mailbox:
        mailbox.login(RECIPIENT_USER, RECIPIENT_PASSWORD)
        mailbox.select("INBOX", readonly=True)
        status, ids = mailbox.search(None, "SUBJECT", f'"{subject}"')
        if status == "OK" and ids[0]:
            status, payload = mailbox.fetch(ids[0].split()[-1], "(RFC822)")
            if status != "OK":
                raise RuntimeError("mail delivery fetch failed")
            received = email.message_from_bytes(payload[0][1])
            if received.get("Message-ID") != message["Message-ID"]:
                raise RuntimeError("delivered message lost its identity")
            print(
                "mail directory baseline passed: employee and service authentication, "
                "disabled and invalid rejection, and employee delivery"
            )
            raise SystemExit(0)
    time.sleep(2)

raise TimeoutError("directory-authenticated employee mail did not arrive")
PY
