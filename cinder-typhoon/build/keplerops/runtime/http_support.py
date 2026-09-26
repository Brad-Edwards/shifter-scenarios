"""Shared HTTPS and persistence helpers for the KeplerOps hand build."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import hmac
import ipaddress
import json
import os
from pathlib import Path
import ssl
import threading
import time
from typing import Any
import uuid


AUDIT_LOCK = threading.RLock()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def issue_worker_token(
    secret: bytes, audience: str, run_id: str, lease_id: str, *, lifetime_seconds: int = 180
) -> str:
    now = int(time.time())
    claims = {
        "aud": audience,
        "exp": now + lifetime_seconds,
        "iat": now,
        "jti": str(uuid.uuid4()),
        "lease_id": lease_id,
        "principal": "svc-fieldlink-ci",
        "run_id": run_id,
    }
    payload = _b64url(canonical_bytes(claims))
    signature = _b64url(hmac.new(secret, payload.encode(), hashlib.sha256).digest())
    return payload + "." + signature


def validate_worker_token(
    authorization: str,
    secret: bytes,
    audience: str,
    peer_address: str,
    *,
    origin_network: str = "10.77.53.0/24",
) -> dict[str, Any] | None:
    if not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ")
    try:
        payload, supplied = token.split(".", 1)
        expected = _b64url(hmac.new(secret, payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(supplied, expected):
            return None
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        now = int(time.time())
        if set(claims) != {"aud", "exp", "iat", "jti", "lease_id", "principal", "run_id"}:
            return None
        if claims["aud"] != audience or claims["principal"] != "svc-fieldlink-ci":
            return None
        if not isinstance(claims["iat"], int) or not isinstance(claims["exp"], int):
            return None
        if claims["iat"] > now + 5 or claims["exp"] < now or claims["exp"] - claims["iat"] > 180:
            return None
        if ipaddress.ip_address(peer_address) not in ipaddress.ip_network(origin_network):
            return None
        if not all(isinstance(claims[key], str) and claims[key] for key in ("jti", "lease_id", "run_id")):
            return None
    except (ValueError, TypeError, json.JSONDecodeError):
        return None
    return claims


def append_audit(directory: Path, stream: str, record: dict[str, Any]) -> None:
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    payload = {"observed_at": utc_now(), **record}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    with AUDIT_LOCK, (directory / f"{stream}.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(encoded)


class KeplerHandler(BaseHTTPRequestHandler):
    server_version = "FieldKest/1.0"
    protocol_version = "HTTP/1.1"

    def setup(self) -> None:
        super().setup()
        self.request_id = str(uuid.uuid4())

    def log_message(self, format: str, *args: object) -> None:
        return

    def send_bytes(
        self,
        status: int,
        payload: bytes,
        content_type: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Request-ID", self.request_id)
        if headers:
            for name, value in headers.items():
                self.send_header(name, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    def send_json(self, status: int, value: Any, *, headers: dict[str, str] | None = None) -> None:
        self.send_bytes(status, canonical_bytes(value) + b"\n", "application/json", headers=headers)

    def read_body(self, maximum_bytes: int = 1_048_576) -> bytes:
        raw = self.headers.get("Content-Length")
        if raw is None or not raw.isdigit():
            raise ValueError("content_length_required")
        length = int(raw)
        if length > maximum_bytes:
            raise OverflowError("body_too_large")
        body = self.rfile.read(length)
        if len(body) != length:
            raise ValueError("short_body")
        return body

    def read_json(self, maximum_bytes: int = 1_048_576) -> Any:
        if self.headers.get_content_type() != "application/json":
            raise ValueError("json_required")
        return json.loads(self.read_body(maximum_bytes).decode("utf-8"))

    def read_upload(self, field_name: str, maximum_bytes: int = 1_048_576) -> bytes:
        if self.headers.get_content_type() != "multipart/form-data":
            raise ValueError("multipart_required")
        body = self.read_body(maximum_bytes)
        header = f"Content-Type: {self.headers['Content-Type']}\r\nMIME-Version: 1.0\r\n\r\n".encode()
        message = BytesParser(policy=default).parsebytes(header + body)
        for part in message.iter_parts():
            if part.get_param("name", header="content-disposition") == field_name:
                return part.get_payload(decode=True)
        raise ValueError("upload_missing")

    def basic_or_bearer(self, username: str, token: str) -> bool:
        value = self.headers.get("Authorization", "")
        if value == f"Bearer {token}":
            return True
        if not value.startswith("Basic "):
            return False
        try:
            decoded = base64.b64decode(value[6:], validate=True).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return False
        return decoded == f"{username}:{token}"


def serve_tls(handler: type[BaseHTTPRequestHandler], port: int = 443) -> None:
    server = ThreadingHTTPServer(("0.0.0.0", port), handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(os.environ["FIELDKEST_TLS_CERT"], os.environ["FIELDKEST_TLS_KEY"])
    server.socket = context.wrap_socket(server.socket, server_side=True)
    server.serve_forever()
