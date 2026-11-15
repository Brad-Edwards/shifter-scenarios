#!/usr/bin/env python3
"""Serve the customer's retained integration handover and supplier onboarding."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import pathlib
import ssl
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

ROOT = pathlib.Path("/var/lib/arwc-connector")
AUDIT = ROOT / "audit" / "events.jsonl"
TOKEN_HASH = ROOT / "auth" / "corporate-session.sha256"
ONBOARDING = ROOT / "native" / "supplier-onboarding.json"
ARCHIVE_STATE = pathlib.Path("/run/arwc-archive/nc-reader.json")
CUSTOMER_COPY = {
    "record_id": "HND-ARWC-047", "tenant": "TEN-ARWC-047", "active_connector": "FLK-7.4.2",
    "maintenance_case": "MTN-CRR-204", "customer_receipt": "RCP-742-047", "status": "retained",
}


def native_onboarding() -> dict[str, str]:
    record = json.loads(ONBOARDING.read_text(encoding="utf-8"))
    expected = {
        "account": "Veybridge Field Services", "contact": "Jules Orswick",
        "maintenance_case": CUSTOMER_COPY["maintenance_case"], "username": "jules.orswick@veybridge.test",
        "supplier_portal": "https://suppliers.arwc.test/purchase-orders",
        "documents": "https://documents.arwc.test/", "document_folder": "Veybridge handover",
    }
    if not isinstance(record, dict) or set(record) != {*expected, "password"}:
        raise ValueError("Supplier onboarding fields do not match the customer record")
    if any(record.get(key) != value for key, value in expected.items()):
        raise ValueError("Supplier onboarding belongs to a different case, identity or service")
    password = record["password"]
    if not isinstance(password, str) or len(password) != 64 or any(c not in "0123456789abcdef" for c in password):
        raise ValueError("Supplier onboarding credential format is invalid")
    return record


def archive_access() -> dict[str, str] | None:
    """Return bounded archive access credentials if the archive has been seeded."""
    if not ARCHIVE_STATE.exists():
        return None
    try:
        state = json.loads(ARCHIVE_STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    username = state.get("reader_username", "")
    password = state.get("reader_password", "")
    documents_url = state.get("documents_url", "")
    if not (username and password and documents_url):
        return None
    return {
        "username": username,
        "password": password,
        "documents": documents_url,
    }


def initialize() -> None:
    native_onboarding()
    AUDIT.touch(mode=0o600, exist_ok=True)
    os.chmod(AUDIT, 0o600)


def append_audit(action: str, result: dict[str, object]) -> str:
    correlation = str(uuid.uuid4())
    event = {
        "audit_id": correlation, "time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "tenant": "arwc", "principal": "corporate-reader-principal", "action": action,
        "object": result.get("record_id"),
        "result_digest": hashlib.sha256(json.dumps(result, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
    }
    with AUDIT.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return correlation


class Handler(BaseHTTPRequestHandler):
    server_version = "ARWC-Customer-Handover/2.0"
    sys_version = ""

    def log_message(self, message: str, *args: object) -> None:
        print(f"{self.client_address[0]} {message % args}", flush=True)

    def send_json(self, status: int, body: dict[str, object]) -> None:
        encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(encoded)

    def authorized(self) -> bool:
        if not TOKEN_HASH.is_file():
            self.send_json(403, {"error": "corporate session required"})
            return False
        if self.headers.get("X-ARWC-Tenant", "arwc") != "arwc":
            self.send_json(403, {"error": "session is not valid for this tenant"})
            return False
        supplied = self.headers.get("Authorization", "")
        if not supplied.startswith("Bearer "):
            self.send_json(403, {"error": "corporate session required"})
            return False
        digest = hashlib.sha256(supplied[7:].encode()).hexdigest()
        expected = TOKEN_HASH.read_text(encoding="ascii").strip()
        if not hmac.compare_digest(digest, expected):
            self.send_json(403, {"error": "corporate session required"})
            return False
        return True

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/.well-known/arwc-client":
            self.send_json(200, {
                "schema": "arwc.client-documents/v1", "service": "customer-handover.arwc.test",
                "title": "Customer integration handover", "routes": [{
                    "key": "corporate.handover", "method": "GET",
                    "template": "https://customer-handover.arwc.test:8443/api/handovers/current",
                }], "related": [
                    "https://suppliers.arwc.test/purchase-orders",
                    "https://documents.arwc.test/",
                    "https://retained-archive.arwc.test/.well-known/arwc-client",
                ],
            })
            return
        if not self.authorized():
            return
        if path != "/api/handovers/current":
            self.send_json(404, {"error": "record not found"})
            return
        record = {**CUSTOMER_COPY, "supplier_onboarding": native_onboarding()}
        access = archive_access()
        if access is not None:
            record["archive_access"] = access
        self.send_json(200, {"audit_id": append_audit("handover-read", record), "record": record})

    def do_POST(self) -> None:
        if self.authorized():
            if urlsplit(self.path).path == "/api/handovers/current":
                self.send_json(405, {"error": "retained handover is read-only"})
            else:
                self.send_json(404, {"error": "record not found"})


def main() -> None:
    initialize()
    server = ThreadingHTTPServer(("0.0.0.0", 8443), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain("/tmp/arwc-server.crt", "/tmp/arwc-server.key")
    server.socket = context.wrap_socket(server.socket, server_side=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
