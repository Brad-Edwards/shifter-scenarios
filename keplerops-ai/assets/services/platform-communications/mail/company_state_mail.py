"""Materialize and read back the authored company mail through SMTP and IMAP."""

from __future__ import annotations

import argparse
import hashlib
import imaplib
import json
import os
import smtplib
import socket
import ssl
import subprocess
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import format_datetime, getaddresses, parsedate_to_datetime
from pathlib import Path
from typing import Any

import yaml

COMPANY_STATE_PATH = Path(
    os.environ.get("COMPANY_STATE_PATH", "/opt/keplerops/company-state.yaml")
)
CA_FILE = os.environ.get("MAIL_CA_FILE", "/etc/keplerops/pki/ca.crt")
CONNECT_HOST = os.environ.get("COMPANY_MAIL_CONNECT_HOST", "mail-server-01.keplerops.lab")
TLS_NAME = os.environ.get("COMPANY_MAIL_TLS_NAME", "mail-server-01.keplerops.lab")
SMTP_PORT = int(os.environ.get("COMPANY_MAIL_SMTP_PORT", "587"))
IMAP_PORT = int(os.environ.get("COMPANY_MAIL_IMAP_PORT", "993"))
DOMAIN = "keplerops.test"
OWNER = "org-keplerops/company-mail-state"
READBACK_PATH = Path(
    os.environ.get(
        "COMPANY_MAIL_READBACK_PATH",
        "/var/lib/stalwart/company-mail-readback.json",
    )
)
DELIVERY_TIMEOUT_SECONDS = 30

# These are committed synthetic service credentials. Existing challenge mailboxes
# are validated and never rewritten by this materializer.
EXISTING_MAILBOXES = {
    "generation": {
        "password": "Generation-Mail-2026!",  # NOSONAR
        "description": "Generation service mailbox",
    },
    "operations": {
        "password": "Operations-Mail-2026!",  # NOSONAR
        "description": "Operations mailbox",
    },
}
OWNED_CREDENTIAL_SEED = b"KeplerOps-company-mail-v1"  # NOSONAR
TYPE_KEY = "@type"


class CompanyMailError(RuntimeError):
    """Raised when native mail state conflicts with the authored slice."""


class _NamedIMAP4SSL(imaplib.IMAP4_SSL):
    """Connect to an explicit address while verifying the declared TLS name."""

    def _create_socket(self, timeout: float | None):
        raw_socket = socket.create_connection(
            (self.host, self.port),
            timeout,
        )
        return self.ssl_context.wrap_socket(raw_socket, server_hostname=TLS_NAME)


def load_manifest(path: Path = COMPANY_STATE_PATH) -> dict[str, Any]:
    # Stalwart's image entrypoint supplies this immutable content path.
    value = yaml.safe_load(path.read_text(encoding="utf-8"))  # NOSONAR
    if not isinstance(value, dict):
        raise CompanyMailError("company-state manifest must be a mapping")
    for section in ("organization", "people", "service_identities", "messages"):
        if section not in value:
            raise CompanyMailError(f"company-state manifest omits {section}")
    if value["organization"].get("id") != "org-keplerops":
        raise CompanyMailError("company-state organization is not KeplerOps")
    for section in ("people", "service_identities"):
        for row in value[section]:
            if not row.get("account_ref"):
                raise CompanyMailError(
                    f"company-state identity {row.get('id', '<unknown>')} omits account_ref"
                )
    return value


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def canonical_digest(items: list[dict[str, Any]]) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(items)).hexdigest()


def stable_message_id(message_id: str) -> str:
    return f"<{message_id}.company-state@{DOMAIN}>"


def _identity_addresses(manifest: dict[str, Any]) -> dict[str, str]:
    addresses = {
        row["id"]: row["email"]
        for row in manifest["people"]
    }
    addresses.update(
        {
            row["id"]: f"{row['username']}@{DOMAIN}"
            for row in manifest["service_identities"]
        }
    )
    return addresses


def _identity_usernames(manifest: dict[str, Any]) -> dict[str, str]:
    return {
        row["id"]: row["username"]
        for section in ("people", "service_identities")
        for row in manifest[section]
    }


def expected_message_item(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "sender_ref": row["sender_ref"],
        "recipient_refs": list(row["recipient_refs"]),
        "sent_at": row["sent_at"],
        "subject": row["subject"],
        "body": row["body"],
        "ticket_refs": list(row["ticket_refs"]),
        "commit_refs": list(row["commit_refs"]),
        "model_refs": list(row["model_refs"]),
        "message_id": stable_message_id(row["id"]),
    }


def build_message(manifest: dict[str, Any], row: dict[str, Any]) -> EmailMessage:
    addresses = _identity_addresses(manifest)
    message = EmailMessage()
    message["From"] = addresses[row["sender_ref"]]
    message["To"] = ", ".join(addresses[ref] for ref in row["recipient_refs"])
    message["Subject"] = row["subject"]
    message["Date"] = format_datetime(
        datetime.fromisoformat(row["sent_at"].replace("Z", "+00:00"))
    )
    message["Message-ID"] = stable_message_id(row["id"])
    message["X-KeplerOps-State-ID"] = row["id"]
    message["X-KeplerOps-State-Owner"] = OWNER
    message["X-KeplerOps-Sender-Ref"] = row["sender_ref"]
    message["X-KeplerOps-Recipient-Refs"] = ",".join(row["recipient_refs"])
    message["X-KeplerOps-Ticket-Refs"] = ",".join(row["ticket_refs"])
    message["X-KeplerOps-Commit-Refs"] = ",".join(row["commit_refs"])
    message["X-KeplerOps-Model-Refs"] = ",".join(row["model_refs"])
    message.set_content(row["body"])
    return message


def _identity_rows_by_username(
    manifest: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    return {
        row["username"]: row
        for section in ("people", "service_identities")
        for row in manifest[section]
    }


def _owned_password(row: dict[str, Any]) -> str:
    account_ref = row["account_ref"]
    suffix = hashlib.sha256(
        OWNED_CREDENTIAL_SEED + b":" + account_ref.encode("utf-8")
    ).hexdigest()[:24]
    return f"Ks!{suffix}"


def _password_for(manifest: dict[str, Any], username: str) -> str:
    if username in EXISTING_MAILBOXES:
        return EXISTING_MAILBOXES[username]["password"]
    row = _identity_rows_by_username(manifest).get(username)
    if row is None:
        raise CompanyMailError(f"no company identity is declared for mailbox {username}")
    return _owned_password(row)


def _tls_context() -> ssl.SSLContext:
    context = ssl.create_default_context(cafile=CA_FILE)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    return context


@contextmanager
def _imap(
    manifest: dict[str, Any],
    username: str,
) -> Iterator[imaplib.IMAP4_SSL]:
    connection = _NamedIMAP4SSL(
        CONNECT_HOST,
        IMAP_PORT,
        ssl_context=_tls_context(),
        timeout=15,
    )
    try:
        connection.login(f"{username}@{DOMAIN}", _password_for(manifest, username))
        status, _ = connection.select("INBOX", readonly=True)
        if status != "OK":
            raise CompanyMailError(f"{username} inbox could not be selected")
        yield connection
    finally:
        try:
            connection.logout()
        except (imaplib.IMAP4.error, OSError):
            pass


def _search_message(
    connection: imaplib.IMAP4_SSL,
    message_id: str,
) -> list[bytes]:
    status, data = connection.uid("search", None, "ALL")
    if status != "OK":
        raise CompanyMailError(f"IMAP search failed for {message_id}")
    matches = []
    for uid in data[0].split() if data and data[0] else []:
        raw_message = _fetch_message(connection, uid)
        message = BytesParser(policy=policy.default).parsebytes(raw_message)
        if str(message.get("Message-ID", "")) == message_id:
            matches.append(uid)
    return matches


def _fetch_message(connection: imaplib.IMAP4_SSL, uid: bytes) -> bytes:
    status, response = connection.uid("fetch", uid, "(BODY.PEEK[])")
    if status != "OK":
        raise CompanyMailError(f"IMAP fetch failed for UID {uid.decode('ascii')}")
    for item in response:
        if isinstance(item, tuple):
            return item[1]
    raise CompanyMailError(f"IMAP fetch omitted body for UID {uid.decode('ascii')}")


def _reference_header(message, name: str) -> list[str]:
    value = str(message.get(name, ""))
    return [] if not value else value.split(",")


def _normalize_message(
    manifest: dict[str, Any],
    raw_message: bytes,
) -> dict[str, Any]:
    message = BytesParser(policy=policy.default).parsebytes(raw_message)
    if message.get("X-KeplerOps-State-Owner") != OWNER:
        raise CompanyMailError(
            f"message-id {message.get('Message-ID')} is an unowned collision"
        )
    sent_at = parsedate_to_datetime(str(message["Date"]))
    if sent_at.tzinfo is None:
        sent_at = sent_at.replace(tzinfo=timezone.utc)
    body_part = message.get_body(preferencelist=("plain",))
    if body_part is None:
        raise CompanyMailError(f"message-id {message.get('Message-ID')} has no text body")
    sender_ref = str(message.get("X-KeplerOps-Sender-Ref", ""))
    recipient_refs = _reference_header(message, "X-KeplerOps-Recipient-Refs")
    addresses = _identity_addresses(manifest)
    observed_from = [address for _, address in getaddresses([str(message["From"])])]
    observed_to = [address for _, address in getaddresses([str(message["To"])])]
    expected_to = [addresses[ref] for ref in recipient_refs]
    if observed_from != [addresses.get(sender_ref)] or observed_to != expected_to:
        raise CompanyMailError(
            f"message-id {message.get('Message-ID')} address readback mismatch"
        )
    return {
        "id": str(message.get("X-KeplerOps-State-ID", "")),
        "sender_ref": sender_ref,
        "recipient_refs": recipient_refs,
        "sent_at": sent_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "subject": str(message["Subject"]),
        "body": body_part.get_content().rstrip("\r\n"),
        "ticket_refs": _reference_header(message, "X-KeplerOps-Ticket-Refs"),
        "commit_refs": _reference_header(message, "X-KeplerOps-Commit-Refs"),
        "model_refs": _reference_header(message, "X-KeplerOps-Model-Refs"),
        "message_id": str(message["Message-ID"]),
    }


def _read_recipient_copy(
    manifest: dict[str, Any],
    row: dict[str, Any],
    recipient_ref: str,
) -> dict[str, Any] | None:
    usernames = _identity_usernames(manifest)
    with _imap(manifest, usernames[recipient_ref]) as connection:
        matches = _search_message(connection, stable_message_id(row["id"]))
        if len(matches) > 1:
            raise CompanyMailError(
                f"message {row['id']} has duplicate copies in {recipient_ref}"
            )
        if not matches:
            return None
        return _normalize_message(
            manifest,
            _fetch_message(connection, matches[0]),
        )


def _smtp_submit(
    manifest: dict[str, Any],
    row: dict[str, Any],
    recipient_refs: list[str],
) -> None:
    usernames = _identity_usernames(manifest)
    addresses = _identity_addresses(manifest)
    sender_username = usernames[row["sender_ref"]]
    smtp = smtplib.SMTP(timeout=15)
    try:
        smtp.connect(CONNECT_HOST, SMTP_PORT)
        smtp.ehlo()
        smtp._host = TLS_NAME
        smtp.starttls(context=_tls_context())
        smtp.ehlo()
        smtp.login(
            f"{sender_username}@{DOMAIN}",
            _password_for(manifest, sender_username),
        )
        smtp.send_message(
            build_message(manifest, row),
            from_addr=addresses[row["sender_ref"]],
            to_addrs=[addresses[recipient_ref] for recipient_ref in recipient_refs],
        )
    finally:
        try:
            smtp.quit()
        except (smtplib.SMTPException, OSError):
            smtp.close()


def _smtp_submit_with_retry(
    manifest: dict[str, Any],
    row: dict[str, Any],
    recipient_refs: list[str],
) -> None:
    deadline = time.monotonic() + DELIVERY_TIMEOUT_SECONDS
    while True:
        try:
            _smtp_submit(manifest, row, recipient_refs)
            return
        except (smtplib.SMTPException, OSError):
            if time.monotonic() >= deadline:
                raise
            time.sleep(1)


def materialize_messages(  # NOSONAR - native preflight and delivery are one transaction.
    manifest: dict[str, Any],
) -> dict[str, Any]:
    for row in manifest["messages"]:
        expected = expected_message_item(row)
        missing_recipient_refs = []
        for recipient_ref in row["recipient_refs"]:
            try:
                observed = _read_recipient_copy(manifest, row, recipient_ref)
            except (imaplib.IMAP4.error, OSError) as error:
                raise CompanyMailError(
                    f"message {row['id']} recipient {recipient_ref} "
                    f"IMAP preflight failed: {error}"
                ) from error
            if observed is not None:
                if observed != expected:
                    raise CompanyMailError(
                        f"message {row['id']} is an owned collision with different content"
                    )
                continue
            missing_recipient_refs.append(recipient_ref)
        if missing_recipient_refs:
            try:
                _smtp_submit_with_retry(manifest, row, missing_recipient_refs)
            except (smtplib.SMTPException, OSError) as error:
                raise CompanyMailError(
                    f"message {row['id']} "
                    f"SMTP submission failed: {error}"
                ) from error
    return readback_messages(manifest)


def readback_messages(manifest: dict[str, Any]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for row in manifest["messages"]:
        expected = expected_message_item(row)
        deadline = time.monotonic() + DELIVERY_TIMEOUT_SECONDS
        while True:
            copies = [
                _read_recipient_copy(manifest, row, recipient_ref)
                for recipient_ref in row["recipient_refs"]
            ]
            if all(copy is not None for copy in copies):
                break
            if time.monotonic() >= deadline:
                raise CompanyMailError(
                    f"message {row['id']} was not observable in every recipient inbox"
                )
            time.sleep(1)
        if any(copy != expected for copy in copies):
            raise CompanyMailError(f"message {row['id']} IMAP readback mismatch")
        items.append(expected)
    return {
        "content_id": "company-mail-state",
        "format": "keplerops-company-state-v1",
        "items": items,
        "canonical_digest": canonical_digest(items),
    }


def _query_object(
    object_name: str,
    name: str,
    fields: str,
) -> dict[str, Any] | None:
    process = subprocess.run(
        [
            "stalwart-cli",
            "query",
            object_name,
            "--where",
            f"name={name}",
            "--fields",
            fields,
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    rows = [
        json.loads(line)
        for line in process.stdout.splitlines()
        if line.strip()
    ]
    if len(rows) > 1:
        raise CompanyMailError(
            f"{object_name.lower()} {name} has duplicate native objects"
        )
    return rows[0] if rows else None


def _query_account(name: str) -> dict[str, Any] | None:
    return _query_object("Account", name, "id,name,description")


def ensure_accounts(manifest: dict[str, Any]) -> None:
    domain = _query_object("Domain", DOMAIN, "id,name")
    if domain is None:
        raise CompanyMailError(f"mail domain {DOMAIN} is absent")
    identities = _identity_rows_by_username(manifest)
    required_usernames = {
        _identity_usernames(manifest)[row["sender_ref"]]
        for row in manifest["messages"]
    }
    required_usernames.update(
        _identity_usernames(manifest)[recipient_ref]
        for row in manifest["messages"]
        for recipient_ref in row["recipient_refs"]
    )
    owned_accounts: dict[str, Any] = {}
    for username in sorted(required_usernames):
        existing = _query_account(username)
        if username in EXISTING_MAILBOXES:
            if (
                existing is None
                or existing.get("description")
                != EXISTING_MAILBOXES[username]["description"]
            ):
                raise CompanyMailError(
                    f"existing challenge mailbox {username} does not match its contract"
                )
            continue
        identity = identities[username]
        description = (
            "KeplerOps company-state owned account: "
            f"{identity['id']} ({identity['account_ref']})"
        )
        if existing is not None and existing.get("description") != description:
            raise CompanyMailError(f"mailbox {username} is an unowned collision")
        owned_accounts[f"company-{identity['id']}"] = {
            TYPE_KEY: "User",
            "name": username,
            "domainId": domain["id"],
            "credentials": {
                "0": {
                    TYPE_KEY: "Password",
                    "secret": _owned_password(identity),
                }
            },
            "memberGroupIds": {},
            "roles": {TYPE_KEY: "User"},
            "permissions": {TYPE_KEY: "Inherit"},
            "quotas": {},
            "aliases": {},
            "encryptionAtRest": {TYPE_KEY: "Disabled"},
            "description": description,
        }

    operation = {
        TYPE_KEY: "upsert",
        "object": "Account",
        "matchOn": ["name"],
        "value": owned_accounts,
    }
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        prefix="company-accounts-",
        suffix=".ndjson",
        dir="/var/lib/stalwart",
        delete=False,
    ) as plan:
        plan.write(json.dumps(operation, separators=(",", ":"), sort_keys=True))
        plan.write("\n")
        plan_path = Path(plan.name)
    try:
        subprocess.run(
            ["stalwart-cli", "apply", "--file", str(plan_path), "--json"],
            check=True,
        )
    finally:
        plan_path.unlink(missing_ok=True)


def write_readback(result: dict[str, Any]) -> None:
    READBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = READBACK_PATH.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.chmod(0o600)
    temporary.replace(READBACK_PATH)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode",
        choices=("accounts", "materialize", "messages", "readback"),
        nargs="?",
        default="materialize",
    )
    parser.add_argument("--manifest", type=Path, default=COMPANY_STATE_PATH)
    args = parser.parse_args()
    try:
        manifest = load_manifest(args.manifest)
        if args.mode == "accounts":
            ensure_accounts(manifest)
            return 0
        if args.mode == "materialize":
            ensure_accounts(manifest)
            result = materialize_messages(manifest)
            write_readback(result)
        elif args.mode == "messages":
            result = materialize_messages(manifest)
            write_readback(result)
        else:
            result = readback_messages(manifest)
        print(json.dumps(result, separators=(",", ":"), sort_keys=True))
        return 0
    except (CompanyMailError, OSError, KeyError, ValueError, subprocess.CalledProcessError) as error:
        print(f"company mail materialization failed: {error}", file=os.sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
