"""Participant-equivalent protocol check for the KeplerOps mail boundary."""

from __future__ import annotations

from email.message import EmailMessage
import imaplib
import json
import os
import smtplib
import ssl
import time
import urllib.request
import uuid

from company_state_mail import load_manifest, readback_messages


CA_FILE = os.environ.get("MAIL_CA_FILE", "/etc/keplerops/pki/ca.crt")
MAIL_HOST = os.environ.get("MAIL_HOST", "stalwart")
WEBMAIL_URL = os.environ.get("WEBMAIL_URL", "http://roundcube:8000/")  # NOSONAR
SENDER = "generation@keplerops.test"
SENDER_PASSWORD = os.environ.get(  # NOSONAR - committed synthetic range credential
    "MAIL_SENDER_PASSWORD", "Generation-Mail-2026!"
)
RECIPIENT = "researcher@keplerops.test"
RECIPIENT_PASSWORD = os.environ.get(  # NOSONAR - committed synthetic range credential
    "MAIL_RECIPIENT_PASSWORD", "Researcher-Mail-2026!"
)


def check_webmail() -> None:
    with urllib.request.urlopen(WEBMAIL_URL, timeout=10) as response:
        body = response.read(256 * 1024).lower()
        if response.status != 200 or b"roundcube" not in body:
            raise RuntimeError("Roundcube login page did not render")


def check_mail_flow() -> str:
    message_id = f"<{uuid.uuid4()}@readiness.keplerops.test>"
    subject = f"KeplerOps mail readiness {uuid.uuid4()}"
    message = EmailMessage()
    message["From"] = SENDER
    message["To"] = RECIPIENT
    message["Subject"] = subject
    message["Message-ID"] = message_id
    message.set_content("KeplerOps internal mail protocol readiness check.")

    tls = ssl.create_default_context(cafile=CA_FILE)
    tls.minimum_version = ssl.TLSVersion.TLSv1_2
    with smtplib.SMTP(MAIL_HOST, 587, timeout=15) as smtp:
        smtp.ehlo()
        smtp.starttls(context=tls)
        smtp.ehlo()
        smtp.login(SENDER, SENDER_PASSWORD)
        smtp.send_message(message)

    deadline = time.monotonic() + 30
    with imaplib.IMAP4_SSL(MAIL_HOST, 993, ssl_context=tls, timeout=15) as imap:
        imap.login(RECIPIENT, RECIPIENT_PASSWORD)
        status, _ = imap.select("INBOX")
        if status != "OK":
            raise RuntimeError("recipient inbox could not be selected")
        while time.monotonic() < deadline:
            status, matches = imap.search(None, "ALL")
            if status == "OK" and matches:
                for sequence_number in matches[0].split()[-100:]:
                    fetch_status, response = imap.fetch(
                        sequence_number, "(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID)])"
                    )
                    if fetch_status == "OK" and message_id.encode() in b"".join(
                        item[1] for item in response if isinstance(item, tuple)
                    ):
                        return message_id
            time.sleep(1)
    raise RuntimeError("SMTP submission was not observable over IMAP")


def main() -> None:
    check_webmail()
    message_id = check_mail_flow()
    company_state = readback_messages(load_manifest())
    print(
        json.dumps(
            {
                "ready": True,
                "message_id": message_id,
                "company_mail_state": {
                    "item_count": len(company_state["items"]),
                    "canonical_digest": company_state["canonical_digest"],
                },
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
