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
PLANNER_SESSION_LIFETIME_SECONDS = 4 * 3600

STARTER = {
    "record_id": "START-MIRA-2026",
    "revision": 1,
    "employee_name": "Mira Vale",
    "employee_number": "TMP-4821",
    "assignment": "PLAN-RELIEF-7",
    "portal_identity": "mira.vale.temp",
    "activation_secret": None,
    "flag": "FLAG{2f6788589f10c887}",
}

ROSTER = {
    "record_id": "ACT-SEP26-R3",
    "revision": 3,
    "employee_number": "TMP-4821",
    "activation_code": "731944",
    "approved_assignment": "PLAN-RELIEF-3",
    "flag": "FLAG{e85ec4991d28c04d}",
}

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
            "starter_observed": False,
            "roster_observed": False,
            "limited_session_sha256": None,
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
        supplied = self.headers.get("X-ARWC-Planning-Access", "")
        state = load_state()
        if supplied and (digest_matches(supplied, state.get("limited_session_sha256")) or
                         handover_matches(supplied)):
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
            "routes": [
                {"key": "identity.provisioning-package", "method": "GET",
                 "template": "https://corporate-identity.arwc.test/api/provisioning-packages/current"},
                {"key": "identity.activation-roster", "method": "GET",
                 "template": "https://corporate-identity.arwc.test/api/activations/current"},
                {"key": "identity.temporary-credential", "method": "POST",
                 "template": "https://corporate-identity.arwc.test/api/temporary-credentials/current"},
                {"key": "identity.session-audit", "method": "GET",
                 "template": "https://corporate-identity.arwc.test/api/sessions/current/audit"},
            ],
            "related": ["https://planning-data.arwc.test/.well-known/arwc-client"],
        })
        return True

    def do_GET(self) -> None:
        if self._serve_client_document():
            return
        if not self.corporate_authorized():
            return
        path = urlsplit(self.path).path
        if path == "/api/provisioning-packages/current":
            state = load_state()
            state["starter_observed"] = True
            save_state(state)
            self.accepted("starter-pack-read", STARTER, "fieldlink")
            return
        if path == "/api/activations/current":
            state = load_state()
            state["roster_observed"] = True
            save_state(state)
            self.accepted("activation-roster-read", ROSTER, "fieldlink")
            return
        if path == "/api/sessions/current/audit":
            self.session_audit()
            return
        self.send_json(404, {"error": "record not found"})

    def session_audit(self) -> None:
        if not self.planning_authorized():
            return
        state = load_state()
        result = dict(RENDERING)
        result["oauth_state"] = state["oauth_state"]
        result["pending_preview_origin"] = state.get("preview_origin", "https://preview.arwc.test")
        self.accepted("login-trail-read", result, "planning-consumer",
                      extra={"flag": "FLAG{415d4e9b4cc2c1ba}"})

    def activate(self, request: dict[str, object]) -> None:
        state = load_state()
        if not state.get("starter_observed") or not state.get("roster_observed"):
            self.send_json(403, {"error": "onboarding records have not been reconciled"})
            return
        if request.get("employee_number") != "TMP-4821" or request.get("activation_code") != "731944":
            self.send_json(409, {"error": "employee activation factors do not match"})
            return
        if request.get("requested_assignment") != "PLAN-RELIEF-7":
            self.send_json(409, {"error": "requested assignment is unavailable"})
            return
        token = secrets.token_urlsafe(32)
        state["limited_session_sha256"] = hashlib.sha256(token.encode()).hexdigest()
        save_state(state)
        try:
            ARCHIVE_EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
            atomic_json(ARCHIVE_EVIDENCE, {
                "record_id": "SESS-MIRA-RELIEF-7",
                "assignment": "PLAN-RELIEF-7",
                "retained_bundle": "BND-COLLECT-CRR-12",
            })
            os.chown(ARCHIVE_EVIDENCE, -1, grp.getgrnam("arwc-archive-source").gr_gid)
            os.chmod(ARCHIVE_EVIDENCE, 0o640)
        except OSError:
            pass
        result = {
            "record_id": "SESS-MIRA-RELIEF-7",
            "revision": 1,
            "employee_number": "TMP-4821",
            "assignment": "PLAN-RELIEF-7",
            "roles": ["temporary-planning-review"],
            "administrative": False,
        }
        self.accepted("temporary-session-issued", result, "mira.vale.temp", 201,
                      {"limited_session": token, "flag": "FLAG{4c78bd2e2f7c25bd}"})

    def do_POST(self) -> None:
        if not self.corporate_authorized():
            return
        path = urlsplit(self.path).path
        request = self.body()
        if request is None:
            return
        if path == "/api/temporary-credentials/current":
            self.activate(request)
            return
        # W06.3 (planner session) refactored: POST /api/sessions removed from corporate_identity.
        # The archive service now owns the sessions endpoint and returns a real Metabase session.
        self.send_json(404, {"error": "record not found"})


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
