#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import hmac
import grp
import json
import os
import pathlib
import secrets
import ssl
import tempfile
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit


ROOT = pathlib.Path("/var/lib/arwc-identity")
STATE = ROOT / "state" / "identity.json"
AUDIT = ROOT / "audit" / "events.jsonl"
TOKEN_HASH = ROOT / "auth" / "corporate-session.sha256"
HANDOVER = pathlib.Path("/run/arwc-archive-evidence/access-grant.json")
PLANNER_EVIDENCE = ROOT / "planning" / "planner-session.json"
ARCHIVE_EVIDENCE = ROOT / "archive" / "archive-source.json"
PLANNER_SESSION_LIFETIME_SECONDS = 15 * 60

# STARTER and ROSTER removed: W05.1 and W05.2 are native Nextcloud reads.
# W05.3 uses real Keycloak first sign-in and delegated admin roles.
RENDERING = {
    "record_id": "RENDER-CRR-882",
    "revision": 8,
    "planner": "nadia.corvane",
    "drawing": "DRW-OG2-R8",
    "review": "REV-CRR-4417",
    "oauth_transaction": "OAUTH-PLN-882",
    "browser_profile": "planner-review-3",
}


def atomic_json(path: pathlib.Path, value: object) -> None:
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def initialize() -> None:
    if not STATE.exists():
        atomic_json(STATE, {
            "oauth_state": secrets.token_urlsafe(24),
            "preview_origin": "https://preview.arwc.test",
            "preview_attached": False,
            "planner_session": None,
            "planner_session_sha256": None,
            "planner_session_expires": None,
        })
    AUDIT.touch(mode=0o600, exist_ok=True)
    os.chmod(AUDIT, 0o600)


def load_state() -> dict[str, object]:
    return json.loads(STATE.read_text(encoding="utf-8"))


def save_state(value: dict[str, object]) -> None:
    atomic_json(STATE, value)


def append_audit(action: str, result: dict[str, object], principal: str) -> str:
    correlation = str(uuid.uuid4())
    event = {
        "audit_id": correlation,
        "time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "tenant": "arwc",
        "principal": principal,
        "action": action,
        "object": result.get("record_id"),
        "revision": result.get("revision"),
        "result_digest": hashlib.sha256(
            json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }
    with AUDIT.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return correlation


def digest_matches(token: str, expected: object) -> bool:
    return isinstance(expected, str) and hmac.compare_digest(
        hashlib.sha256(token.encode()).hexdigest(), expected,
    )


def handover_matches(token: str) -> bool:
    try:
        evidence = json.loads(HANDOVER.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return evidence.get("record_id") == "HND-PLANNER-06" and digest_matches(
        token, evidence.get("token_sha256"),
    )


class Handler(BaseHTTPRequestHandler):
    server_version = "ARWC-Corporate-Identity/1.0"
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

    def corporate_authorized(self) -> bool:
        if self.headers.get("X-ARWC-Tenant", "arwc") != "arwc":
            self.send_json(403, {"error": "session is not valid for this tenant"})
            return False
        supplied = self.headers.get("Authorization", "")
        if not supplied.startswith("Bearer "):
            self.send_json(403, {"error": "onboarding session required"})
            return False
        digest = hashlib.sha256(supplied[7:].encode()).hexdigest()
        if not hmac.compare_digest(digest, TOKEN_HASH.read_text().strip()):
            self.send_json(403, {"error": "onboarding session required"})
            return False
        return True

    def planning_authorized(self) -> bool:
        # Planning access is gated by the W04.3 planner handover token only.
        # The W05.3 facade limited-session path was removed with the W05.3 facade.
        # W06 and W07 must be refactored to remove this service entirely.
        supplied = self.headers.get("X-ARWC-Planning-Access", "")
        if supplied and handover_matches(supplied):
            return True
        self.send_json(403, {"error": "planning access required"})
        return False

    def body(self) -> dict[str, object] | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 2 or length > 16384:
                raise ValueError
            result = json.loads(self.rfile.read(length))
            if not isinstance(result, dict):
                raise ValueError
            return result
        except (ValueError, json.JSONDecodeError):
            self.send_json(409, {"error": "invalid request"})
            return None

    def accepted(self, action: str, result: dict[str, object], principal: str,
                 status: int = 200, extra: dict[str, object] | None = None) -> None:
        response: dict[str, object] = {
            "audit_id": append_audit(action, result, principal),
            "record": result,
        }
        if extra:
            response.update(extra)
        self.send_json(status, response)

    def _serve_client_document(self) -> bool:
        if urlsplit(self.path).path != "/.well-known/arwc-client":
            return False
        self.send_json(200, {
            "schema": "arwc.client-documents/v1",
            "service": "corporate-identity.arwc.test",
            "title": "Corporate identity, provisioning, and session service",
            "routes": [],
            "related": ["https://planning-data.arwc.test/.well-known/arwc-client"],
        })
        return True

    def do_GET(self) -> None:
        if self._serve_client_document():
            return
        if not self.corporate_authorized():
            return
        self.send_json(404, {"error": "record not found"})

    def do_POST(self) -> None:
        if not self.corporate_authorized():
            return
        path = urlsplit(self.path).path
        request = self.body()
        if request is None:
            return
        self.send_json(404, {"error": "record not found"})
        # W06.3 (planner session) refactored: POST /api/sessions removed from corporate_identity.
        # The archive service now owns the sessions endpoint and returns a real Metabase session.


def main() -> None:
    initialize()
    server = ThreadingHTTPServer(("0.0.0.0", 443), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain("/tmp/server.crt", "/tmp/server.key")
    server.socket = context.wrap_socket(server.socket, server_side=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
