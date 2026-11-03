#!/usr/bin/env python3
"""Gate ARWC services on an authenticated, range-bound corporate handover."""

from __future__ import annotations

import argparse
import hashlib
import hmac
from http.client import HTTPSConnection
import json
import math
import os
from pathlib import Path
import re
import ssl
import sys
import tempfile
import time
from urllib.parse import urlsplit


SESSION = Path("/run/arwc-corporate/handover/corporate-session")
ATTESTATION = Path("/run/arwc-corporate/handover/corporate-session.json")
CERTIFICATE = Path("/run/arwc-tls/server.crt")
AUTHENTICATION_KEY = Path("/run/arwc-handover/authentication.key")
STATE = Path("/run/arwc-status/state")
TOKEN = re.compile(rb"[0-9a-f]{64}\n")
KEY = re.compile(rb"[0-9a-f]{64}\n")
HEX_DIGEST = re.compile(r"[0-9a-f]{64}")
HANDOVER_ID = re.compile(r"[0-9a-f]{32}")
SCHEMA = "arwc.corporate-handover/v1"
ATTESTATION_KEYS = {
    "schema",
    "handover_id",
    "issued_at",
    "range_binding",
    "token_sha256",
    "authentication",
}


class HandoverRejected(Exception):
    """The handover material is present but cannot be trusted."""


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def build_attestation(
    token: bytes,
    certificate: bytes,
    authentication_key: bytes,
    handover_id: str,
    issued_at: str,
) -> dict[str, str]:
    if KEY.fullmatch(authentication_key) is None:
        raise ValueError("authentication key must contain 32 hex-encoded bytes")
    record = {
        "schema": SCHEMA,
        "handover_id": handover_id,
        "issued_at": issued_at,
        "range_binding": hashlib.sha256(certificate).hexdigest(),
        "token_sha256": hashlib.sha256(token).hexdigest(),
    }
    record["authentication"] = hmac.new(
        authentication_key, canonical(record), hashlib.sha256
    ).hexdigest()
    return record


def atomic_write(path: Path, payload: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def bounded_read(path: Path, limit: int) -> bytes:
    try:
        with path.open("rb") as handle:
            payload = handle.read(limit + 1)
    except FileNotFoundError as error:
        raise HandoverRejected("partial_handover") from error
    except OSError as error:
        raise HandoverRejected("unreadable_handover") from error
    if len(payload) > limit:
        raise HandoverRejected("oversized_handover")
    return payload


def material_marker(session: Path, attestation: Path) -> tuple[object, ...]:
    marker: list[object] = []
    for path in (session, attestation):
        try:
            stat = path.stat()
            marker.extend((stat.st_ino, stat.st_size, stat.st_mtime_ns))
        except OSError:
            marker.append(None)
    return tuple(marker)


def validate_handover(
    session: Path,
    attestation: Path,
    certificate: Path,
    authentication_key: Path,
    accepted_hash: Path,
) -> str:
    token_bytes = bounded_read(session, 65)
    if TOKEN.fullmatch(token_bytes) is None:
        raise HandoverRejected("malformed_token")
    token = token_bytes[:-1]
    token_hash = hashlib.sha256(token).hexdigest()

    raw_attestation = bounded_read(attestation, 4096)
    try:
        record = json.loads(raw_attestation)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HandoverRejected("malformed_attestation") from error
    if not isinstance(record, dict) or set(record) != ATTESTATION_KEYS:
        raise HandoverRejected("malformed_attestation")
    if record.get("schema") != SCHEMA:
        raise HandoverRejected("unsupported_attestation")
    if (
        not isinstance(record.get("handover_id"), str)
        or HANDOVER_ID.fullmatch(record["handover_id"]) is None
    ):
        raise HandoverRejected("malformed_attestation")
    if (
        not isinstance(record.get("issued_at"), str)
        or not record["issued_at"].endswith("Z")
    ):
        raise HandoverRejected("malformed_attestation")
    for field in ("range_binding", "token_sha256", "authentication"):
        if (
            not isinstance(record.get(field), str)
            or HEX_DIGEST.fullmatch(record[field]) is None
        ):
            raise HandoverRejected("malformed_attestation")

    try:
        certificate_bytes = bounded_read(certificate, 64 * 1024)
        key_bytes = bounded_read(authentication_key, 1024)
    except HandoverRejected as error:
        raise HandoverRejected("local_identity_unavailable") from error
    if KEY.fullmatch(key_bytes) is None:
        raise HandoverRejected("local_identity_unavailable")
    if record["range_binding"] != hashlib.sha256(certificate_bytes).hexdigest():
        raise HandoverRejected("cross_range_handover")
    if record["token_sha256"] != token_hash:
        raise HandoverRejected("partial_handover")

    authenticated = {
        key: value for key, value in record.items() if key != "authentication"
    }
    expected_authentication = hmac.new(
        key_bytes, canonical(authenticated), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(record["authentication"], expected_authentication):
        raise HandoverRejected("unauthenticated_handover")

    if accepted_hash.exists():
        previous = bounded_read(accepted_hash, 65)
        if previous != (token_hash + "\n").encode():
            raise HandoverRejected("replayed_handover")
    return token_hash


def write_state(path: Path, value: str, current: str | None) -> str:
    if value != current:
        atomic_write(path, (value + "\n").encode(), 0o644)
    return value


def wait_for_handover(args: argparse.Namespace) -> int:
    session = Path(args.session)
    attestation = Path(args.attestation)
    certificate = Path(args.certificate)
    authentication_key = Path(args.authentication_key)
    state = Path(args.state)
    accepted_hash = Path(args.accepted_hash)
    poll_seconds = float(os.environ.get("ARWC_HANDOVER_POLL_SECONDS", "5"))
    event_interval = float(
        os.environ.get("ARWC_HANDOVER_EVENT_INTERVAL_SECONDS", "300")
    )
    if (
        not math.isfinite(poll_seconds)
        or not math.isfinite(event_interval)
        or poll_seconds <= 0
        or event_interval < 0
    ):
        raise SystemExit("handover timing values must be non-negative")

    current_state: str | None = None
    last_event: tuple[object, ...] | None = None
    last_event_at = 0.0
    while True:
        if not session.exists() and not attestation.exists():
            current_state = write_state(state, "waiting", current_state)
            time.sleep(poll_seconds)
            continue
        try:
            token_hash = validate_handover(
                session, attestation, certificate, authentication_key, accepted_hash
            )
        except HandoverRejected as error:
            current_state = write_state(state, "rejected", current_state)
            event = (str(error), *material_marker(session, attestation))
            now = time.monotonic()
            if event != last_event and (
                last_event is None or now - last_event_at >= event_interval
            ):
                print(
                    json.dumps(
                        {
                            "event": "corporate_handover_rejected",
                            "service": args.service,
                            "reason": str(error),
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    file=sys.stderr,
                    flush=True,
                )
                last_event = event
                last_event_at = now
            time.sleep(poll_seconds)
            continue

        atomic_write(accepted_hash, (token_hash + "\n").encode(), 0o600)
        write_state(state, "accepted", current_state)
        return 0


def client_ready(args: argparse.Namespace) -> int:
    try:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE  # The probe is local process readiness.
        url = urlsplit(args.url)
        if url.scheme != "https" or url.hostname not in {"127.0.0.1", "localhost"}:
            return 1
        connection = HTTPSConnection(
            url.hostname, url.port or 443, timeout=args.timeout, context=context
        )
        try:
            connection.request(
                "GET", url.path or "/", headers={"Accept": "application/json"}
            )
            response = connection.getresponse()
            if response.status != 200:
                return 1
            body = response.read(65_537)
            if len(body) > 65_536:
                return 1
            payload = json.loads(body)
        finally:
            connection.close()
        healthy = (
            isinstance(payload, dict)
            and payload.get("schema") == "arwc.client-documents/v1"
        )
        return 0 if healthy else 1
    except (OSError, ValueError, json.JSONDecodeError):
        return 1


def readiness(args: argparse.Namespace) -> int:
    try:
        if Path(args.state).read_text(encoding="ascii") != "accepted\n":
            return 1
    except OSError:
        return 1
    return client_ready(args)


def healthcheck(args: argparse.Namespace) -> int:
    try:
        state = Path(args.state).read_text(encoding="ascii")
    except OSError:
        return 1
    if state == "waiting\n":
        return 0
    if state != "accepted\n":
        return 1
    return client_ready(args)


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser()
    subcommands = command.add_subparsers(dest="command", required=True)

    wait = subcommands.add_parser("wait")
    wait.add_argument("--service", required=True)
    wait.add_argument("--accepted-hash", required=True)
    wait.add_argument("--session", default=str(SESSION))
    wait.add_argument("--attestation", default=str(ATTESTATION))
    wait.add_argument("--certificate", default=str(CERTIFICATE))
    wait.add_argument("--authentication-key", default=str(AUTHENTICATION_KEY))
    wait.add_argument("--state", default=str(STATE))
    wait.set_defaults(handler=wait_for_handover)

    for name, handler in (("health", healthcheck), ("ready", readiness)):
        probe = subcommands.add_parser(name)
        probe.add_argument("--state", default=str(STATE))
        probe.add_argument(
            "--url", default="https://127.0.0.1/.well-known/arwc-client"
        )
        probe.add_argument("--timeout", type=float, default=3.0)
        probe.set_defaults(handler=handler)
    return command


def main() -> int:
    args = parser().parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
