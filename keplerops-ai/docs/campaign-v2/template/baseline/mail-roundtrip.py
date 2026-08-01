#!/usr/bin/env python3
"""Prove a real cross-domain mail thread and attachment through Stalwart."""

from __future__ import annotations

import email
import imaplib
import os
import ssl
import smtplib
import time
import uuid
from email.message import EmailMessage


SMTP_HOST = os.getenv("SMTP_HOST", "10.61.10.20")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
IMAP_HOST = os.getenv("IMAP_HOST", "10.61.10.20")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
CINDER_USER = os.getenv("CINDER_MAIL_USER", "cinder.operator")
CINDER_PASSWORD = os.getenv("CINDER_MAIL_PASSWORD", "KeplerV2-Training-Cinder")
CINDER_ADDRESS = "cinder.operator@cinder.lab"
REVIEWER_USER = os.getenv("REVIEWER_MAIL_USER", "reviewer")
REVIEWER_PASSWORD = os.getenv("REVIEWER_MAIL_PASSWORD", "KeplerV2-Training-Reviewer")
REVIEWER_ADDRESS = "reviewer@keplerops.lab"


def tls_context() -> ssl.SSLContext:
    ca_file = os.getenv("MAIL_CA_FILE")
    if ca_file:
        return ssl.create_default_context(cafile=ca_file)
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def send(message: EmailMessage, user: str, password: str) -> None:
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as smtp:
        smtp.starttls(context=tls_context())
        smtp.login(user, password)
        smtp.send_message(message)


def wait_for_message(user: str, password: str, subject: str) -> bytes:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        with imaplib.IMAP4_SSL(
            IMAP_HOST, IMAP_PORT, ssl_context=tls_context(), timeout=10
        ) as mailbox:
            mailbox.login(user, password)
            mailbox.select("INBOX")
            status, ids = mailbox.search(None, "SUBJECT", f'"{subject}"')
            if status == "OK" and ids[0]:
                message_id = ids[0].split()[-1]
                status, payload = mailbox.fetch(message_id, "(RFC822)")
                if status == "OK":
                    return payload[0][1]
        time.sleep(2)
    raise TimeoutError(f"mail with subject {subject!r} did not arrive")


def main() -> None:
    correlation = f"baseline-{uuid.uuid4()}"
    subject = f"Orion partner review {correlation}"
    outbound = EmailMessage()
    outbound["From"] = CINDER_ADDRESS
    outbound["To"] = REVIEWER_ADDRESS
    outbound["Subject"] = subject
    outbound["Message-ID"] = f"<{correlation}@cinder.lab>"
    outbound["X-KeplerOps-Workflow"] = correlation
    outbound.set_content("Please confirm receipt of the attached benign review note.")
    outbound.add_attachment(
        b"clean-baseline attachment\n",
        maintype="text",
        subtype="plain",
        filename="review-note.txt",
    )
    send(outbound, CINDER_USER, CINDER_PASSWORD)
    print(f"submitted Cinder message: {correlation}", flush=True)

    received_bytes = wait_for_message(REVIEWER_USER, REVIEWER_PASSWORD, subject)
    received = email.message_from_bytes(received_bytes)
    if received.get("X-KeplerOps-Workflow") != correlation:
        raise RuntimeError("reviewer message lost its workflow correlation")
    filenames = [part.get_filename() for part in received.walk() if part.get_filename()]
    if filenames != ["review-note.txt"]:
        raise RuntimeError(f"unexpected attachment set: {filenames}")
    print("reviewer received the attachment", flush=True)

    reply = EmailMessage()
    reply["From"] = REVIEWER_ADDRESS
    reply["To"] = CINDER_ADDRESS
    reply["Subject"] = f"Re: {subject}"
    reply["In-Reply-To"] = outbound["Message-ID"]
    reply["References"] = outbound["Message-ID"]
    reply["X-KeplerOps-Workflow"] = correlation
    reply.set_content("Receipt confirmed. The attachment opened normally.")
    send(reply, REVIEWER_USER, REVIEWER_PASSWORD)
    print("reviewer submitted a threaded reply", flush=True)

    reply_bytes = wait_for_message(CINDER_USER, CINDER_PASSWORD, subject)
    reply_received = email.message_from_bytes(reply_bytes)
    if reply_received.get("X-KeplerOps-Workflow") != correlation:
        raise RuntimeError("reply lost its workflow correlation")
    if reply_received.get("In-Reply-To") != outbound["Message-ID"]:
        raise RuntimeError("reply did not preserve the original Message-ID")
    print(f"mail roundtrip passed: {correlation}")


if __name__ == "__main__":
    main()
