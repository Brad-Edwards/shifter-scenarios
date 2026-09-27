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
HANDOVER = pathlib.Path("/run/arwc-archive-evidence/W06-access.json")
PLANNER_EVIDENCE = ROOT / "results" / "planner-session.json"

STARTER = {
    "record_id": "START-MIRA-2026",
    "revision": 1,
    "employee_name": "Mira Vale",
    "employee_number": "TMP-4821",
    "assignment": "PLAN-RELIEF-7",
    "portal_identity": "mira.vale.temp",
    "activation_secret": None,
}

ROSTER = {
    "record_id": "ACT-SEP26-R3",
    "revision": 3,
    "employee_number": "TMP-4821",
    "activation_code": "731944",
    "approved_assignment": "PLAN-RELIEF-3",
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

    def do_GET(self) -> None:
        if not self.corporate_authorized():
            return
        path = urlsplit(self.path).path
        state = load_state()
        if path == "/api/a-starter-pack-left-open":
            state["starter_observed"] = True
            save_state(state)
            self.accepted("a-starter-pack-left-open", STARTER, "fieldlink")
        elif path == "/api/the-activation-roster":
            state["roster_observed"] = True
            save_state(state)
            self.accepted("the-activation-roster", ROSTER, "fieldlink")
        elif path == "/api/the-planner-s-login-trail":
            if not self.planning_authorized():
                return
            result = dict(RENDERING)
            result["oauth_state"] = state["oauth_state"]
            result["pending_preview_origin"] = state["preview_origin"]
            self.accepted("the-planner-s-login-trail", result, "planning-consumer")
        else:
            self.send_json(404, {"error": "record not found"})

    def do_POST(self) -> None:
        if not self.corporate_authorized():
            return
        path = urlsplit(self.path).path
        request = self.body()
        if request is None:
            return
        if path == "/api/temporary-with-the-wrong-rights":
            self.activate(request)
        elif path == "/api/a-drawing-in-the-wrong-context":
            if self.planning_authorized():
                self.attach_preview(request)
        elif path == "/api/a-planner-session-that-works":
            if self.planning_authorized():
                self.bootstrap(request)
        else:
            self.send_json(404, {"error": "record not found"})

    def activate(self, request: dict[str, object]) -> None:
        state = load_state()
        if not state["starter_observed"] or not state["roster_observed"]:
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
        result = {
            "record_id": "SESS-MIRA-RELIEF-7",
            "revision": 1,
            "employee_number": "TMP-4821",
            "assignment": "PLAN-RELIEF-7",
            "roles": ["temporary-planning-review"],
            "administrative": False,
        }
        self.accepted("temporary-with-the-wrong-rights", result, "mira.vale.temp", 201,
                      {"limited_session": token})

    def attach_preview(self, request: dict[str, object]) -> None:
        state = load_state()
        if request.get("oauth_state") != state["oauth_state"]:
            self.send_json(409, {"error": "OAuth state does not match"})
            return
        if request.get("drawing") != "DRW-OG2-R8" or request.get("review") != "REV-CRR-4417":
            self.send_json(409, {"error": "drawing review binding does not match"})
            return
        if request.get("preview_origin") != "https://preview-cinder.arwc.test":
            self.send_json(409, {"error": "preview origin is not available"})
            return
        state["preview_origin"] = request["preview_origin"]
        state["preview_attached"] = True
        save_state(state)
        result = dict(RENDERING)
        result.update({"revision": 9, "preview_origin": request["preview_origin"]})
        self.accepted("a-drawing-in-the-wrong-context", result, "planning-consumer", 201)

    def bootstrap(self, request: dict[str, object]) -> None:
        state = load_state()
        if not state["preview_attached"]:
            self.send_json(403, {"error": "controlled preview has not been attached"})
            return
        if (request.get("oauth_transaction") != "OAUTH-PLN-882" or
                request.get("preview_origin") != state["preview_origin"]):
            self.send_json(409, {"error": "browser transaction binding does not match"})
            return
        token = state.get("planner_session")
        expires = state.get("planner_session_expires")
        if not isinstance(token, str) or not isinstance(expires, int) or expires <= int(time.time()):
            token = secrets.token_urlsafe(40)
            expires = int(time.time()) + 300
            state["planner_session"] = token
            state["planner_session_sha256"] = hashlib.sha256(token.encode()).hexdigest()
            state["planner_session_expires"] = expires
            save_state(state)
            atomic_json(PLANNER_EVIDENCE, {
                "record_id": "PLN-SESS-OAUTH-882",
                "planner": "nadia.corvane",
                "scope": "planning-records",
                "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
                "expires_at_epoch": expires,
            })
            os.chown(PLANNER_EVIDENCE, -1, grp.getgrnam("arwc-planning").gr_gid)
            os.chmod(PLANNER_EVIDENCE, 0o640)
        result = {
            "record_id": "PLN-SESS-OAUTH-882",
            "revision": 1,
            "planner": "nadia.corvane",
            "scope": "planning-records",
            "protected_record": "RENDER-CRR-882",
            "expires_at_epoch": expires,
        }
        self.accepted("a-planner-session-that-works", result, "nadia.corvane", 201,
                      {"planner_session": token})


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
