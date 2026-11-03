#!/usr/bin/env python3
"""Narrow route relay for the registered Alterra FieldLink connector."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import re
import ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib import error, request
from urllib.parse import urlsplit

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from credentials import credential
from channel_credentials import CHANNEL, TENANT, authorize


UPSTREAM = os.environ.get("FIELDKEST_CUSTOMER_UPSTREAM", "https://connector.arwc.test")
RANGE_SECRET = credential("connector_package_internal")
DIAGNOSTIC_TOKEN = credential("support_delivery_token")
ACTIVATE = re.compile(r"/api/fieldlink/packages/([^/]+)/activate$")
RECEIPT = re.compile(r"/api/fieldlink/packages/([^/]+)/receipt$")
DIAGNOSTIC = re.compile(r"/api/fieldlink/diagnostics(?:/[^/]+/receipt)?$")
ROLLBACK = "/api/fieldlink/rehearsals/rollback"
PUBLISHED = Path("/var/lib/fieldkest-registry/published")
CHANNEL_CREDENTIAL = PUBLISHED / "delivery/channel-credential.json"
VERSION = re.compile(r"7\.4\.3-cinder\.[a-z0-9][a-z0-9-]{0,23}")


def _channel_credentials() -> object:
    try:
        return json.loads(CHANNEL_CREDENTIAL.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def identity(method: str, path: str) -> tuple[str, str, str] | None:
    if method == "POST" and path == "/api/fieldlink/packages/poll":
        return "poll", "/tmp/customer-auth/package.crt", "/tmp/customer-auth/package.key"
    if method == "POST" and ACTIVATE.fullmatch(path):
        return "activate", "/tmp/customer-auth/package.crt", "/tmp/customer-auth/package.key"
    if method == "GET" and RECEIPT.fullmatch(path):
        return "receipt", "/tmp/customer-auth/package.crt", "/tmp/customer-auth/package.key"
    if method == "POST" and path == ROLLBACK:
        return "rollback", "/tmp/customer-auth/package.crt", "/tmp/customer-auth/package.key"
    if method == "POST" and path == "/api/fieldlink/diagnostics":
        return "diagnostic", "/tmp/customer-auth/diagnostic.crt", "/tmp/customer-auth/diagnostic.key"
    if method == "GET" and DIAGNOSTIC.fullmatch(path):
        return "diagnostic", "/tmp/customer-auth/diagnostic.crt", "/tmp/customer-auth/diagnostic.key"
    return None


def bearer_token(header: str) -> str:
    scheme, separator, token = header.partition(" ")
    if scheme != "Bearer" or not separator or not token or " " in token:
        return ""
    return token


class Handler(BaseHTTPRequestHandler):
    server_version = "FieldKest-Customer-Relay/1.0"
    sys_version = ""

    def log_message(self, message: str, *args: object) -> None:
        return

    def send_payload(self, status: int, payload: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    def relay(self) -> None:
        path = urlsplit(self.path).path
        selected = identity(self.command, path)
        if selected is None:
            return self.send_payload(404, b'{"error":"route_not_found"}\n', "application/json")
        grant_name, certificate, key_path = selected
        raw = b""
        parsed: dict[str, object] = {}
        if self.command == "POST":
            length = self.headers.get("Content-Length", "")
            if not length.isdigit() or int(length) > 1_500_000:
                return self.send_payload(422, b'{"error":"invalid_request"}\n', "application/json")
            raw = self.rfile.read(int(length))
            try:
                parsed = json.loads(raw)
                if not isinstance(parsed, dict):
                    raise ValueError
            except (ValueError, json.JSONDecodeError):
                return self.send_payload(422, b'{"error":"invalid_request"}\n', "application/json")
        presented = bearer_token(self.headers.get("Authorization", ""))
        if grant_name == "diagnostic":
            if presented != DIAGNOSTIC_TOKEN:
                return self.send_payload(403, b'{"error":"channel_identity_denied"}\n', "application/json")
        else:
            if grant_name == "poll":
                tenant, channel, version = parsed.get("tenant"), parsed.get("channel"), parsed.get("version")
            elif grant_name == "activate":
                match = ACTIVATE.fullmatch(path)
                tenant, channel, version = parsed.get("tenant"), parsed.get("channel"), match.group(1) if match else ""
            elif grant_name == "receipt":
                match = RECEIPT.fullmatch(path)
                tenant, channel, version = TENANT, CHANNEL, match.group(1) if match else ""
            else:
                tenant, channel, version = parsed.get("tenant"), CHANNEL, parsed.get("version")
            if not authorize(
                _channel_credentials(), presented, grant_name,
                tenant=tenant, channel=channel, version=version, range_secret=RANGE_SECRET,
            ):
                return self.send_payload(403, b'{"error":"channel_identity_denied"}\n', "application/json")
        if path == "/api/fieldlink/packages/poll":
            requested = parsed
            version = requested.get("version")
            if (requested.get("tenant") != TENANT
                    or requested.get("channel") != CHANNEL
                    or not isinstance(version, str) or not VERSION.fullmatch(version)):
                return self.send_payload(422, b'{"error":"customer_channel_denied"}\n', "application/json")
            record_path = PUBLISHED / f"{version}.json"
            archive_path = PUBLISHED / f"{version}.tgz"
            if not record_path.is_file() or not archive_path.is_file():
                return self.send_payload(404, b'{"error":"package_not_published"}\n', "application/json")
            record = json.loads(record_path.read_text())
            if record.get("approval", {}).get("signed") is not True:
                return self.send_payload(409, b'{"error":"package_not_signed"}\n', "application/json")
            raw = json.dumps({
                "tenant": requested["tenant"], "channel": requested["channel"],
                "record": record,
                "tarball_base64": base64.b64encode(archive_path.read_bytes()).decode(),
            }, sort_keys=True, separators=(",", ":")).encode()
        signed = self.command.encode() + b"\n" + path.encode() + b"\n" + hashlib.sha256(raw).hexdigest().encode()
        private_key = serialization.load_pem_private_key(Path(key_path).read_bytes(), password=None)
        signature = base64.b64encode(private_key.sign(signed, padding.PKCS1v15(), hashes.SHA256())).decode()
        headers = {"X-FieldLink-Signature": signature}
        if raw:
            headers["Content-Type"] = "application/json"
        outbound = request.Request(UPSTREAM + path, data=raw if self.command == "POST" else None, method=self.command, headers=headers)
        context = ssl.create_default_context(cafile="/tmp/customer-auth/arwc-ca.crt")
        context.load_cert_chain(certificate, key_path)
        try:
            with request.urlopen(outbound, context=context, timeout=12) as response:
                payload = response.read(2_000_000)
                self.send_payload(response.status, payload, response.headers.get_content_type())
        except error.HTTPError as failure:
            self.send_payload(failure.code, failure.read(2_000_000), failure.headers.get_content_type())
        except (OSError, ssl.SSLError):
            self.send_payload(502, b'{"error":"customer_connector_unavailable"}\n', "application/json")

    do_GET = relay
    do_POST = relay


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", 443), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain("/tmp/relay.crt", "/tmp/relay.key")
    server.socket = context.wrap_socket(server.socket, server_side=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
