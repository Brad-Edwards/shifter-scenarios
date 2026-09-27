#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import hmac
import json
import os
import pathlib
import ssl
import tempfile
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit


ROOT = pathlib.Path("/var/lib/arwc-connector")
STATE = ROOT / "state" / "planner-handover.json"
AUDIT = ROOT / "audit" / "events.jsonl"
TOKEN_HASH = ROOT / "auth" / "corporate-session.sha256"
PLANNING_CONTEXT = pathlib.Path(
    "/opt/customer-handover/assets/pl-arwc-plan-method-01-method.md"
)

CUSTOMER_COPY = {
    "record_id": "HND-ARWC-047",
    "tenant": "TEN-ARWC-047",
    "active_connector": "FLK-7.4.2",
    "maintenance_case": "MTN-CRR-204",
    "customer_receipt": "RCP-742-047",
    "status": "retained",
}

CONTINUITY_NOTE = {
    "record_id": "CONT-DRY-A-R3",
    "revision": 3,
    "status": "unpublished",
    "condition": "usable reserve falls below committed allocation",
    "measures": ["replacement water purchasing", "Stage A restrictions"],
    "planning_reference": "ARWC-PLAN-METHOD-01",
}


def atomic_json(path: pathlib.Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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


def initial_state() -> dict[str, object]:
    return {
        "record_id": "PLN-HO-CRR-17",
        "revision": 3,
        "inspection": "INSP-CRR-2026-09-18",
        "assignee": "nadia.corvane",
        "attachment": {
            "filename": "inspection-summary-r2.md",
            "owner": "nadia.corvane",
            "sha256": "eb95820a0a056548d727bd6901243347e20bcd0c28a973c065142291fb6d4380",
        },
    }


def initialize() -> None:
    if not STATE.exists():
        atomic_json(STATE, initial_state())
    AUDIT.touch(mode=0o600, exist_ok=True)
    os.chmod(AUDIT, 0o600)


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def append_audit(action: str, result: dict[str, object]) -> str:
    correlation = str(uuid.uuid4())
    event = {
        "audit_id": correlation,
        "time": now(),
        "tenant": "arwc",
        "principal": "corporate-reader-principal",
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


class Handler(BaseHTTPRequestHandler):
    server_version = "ARWC-Customer-Handover/1.0"
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

    def accepted_read(self, action: str, result: dict[str, object]) -> None:
        correlation = append_audit(action, result)
        self.send_json(200, {"audit_id": correlation, "record": result})

    def do_GET(self) -> None:
        if not self.authorized():
            return
        path = urlsplit(self.path).path
        if path == "/api/the-customer-s-copy":
            self.accepted_read("the-customer-s-copy", CUSTOMER_COPY)
            return
        if path == "/api/the-planner-s-unfinished-handover":
            self.accepted_read(
                "the-planner-s-unfinished-handover",
                json.loads(STATE.read_text(encoding="utf-8")),
            )
            return
        if path == "/api/how-the-company-buys-time":
            record = dict(CONTINUITY_NOTE)
            record["planning_context"] = PLANNING_CONTEXT.read_text(encoding="utf-8")
            self.accepted_read("how-the-company-buys-time", record)
            return
        self.send_json(404, {"error": "record not found"})

    def do_POST(self) -> None:
        if not self.authorized():
            return
        if urlsplit(self.path).path != "/api/change-the-corporate-record":
            self.send_json(404, {"error": "record not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 2 or length > 65536:
                raise ValueError("request size")
            request = json.loads(self.rfile.read(length))
            attachment = request["attachment"]
            filename = attachment["filename"]
            content = attachment["content"]
            expected_revision = request["expected_revision"]
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            self.send_json(409, {"error": "invalid attachment revision request"})
            return

        state = json.loads(STATE.read_text(encoding="utf-8"))
        immutable = {
            "record_id": "PLN-HO-CRR-17",
            "inspection": "INSP-CRR-2026-09-18",
            "assignee": "nadia.corvane",
        }
        for field, value in immutable.items():
            if request.get(field, value) != value:
                self.send_json(409, {"error": f"{field} binding does not match"})
                return
        if expected_revision != state["revision"]:
            self.send_json(409, {"error": "record revision is stale"})
            return
        if not isinstance(filename, str) or not filename or "/" in filename:
            self.send_json(409, {"error": "invalid attachment filename"})
            return
        if not isinstance(content, str) or not content:
            self.send_json(409, {"error": "attachment content is empty"})
            return

        digest = hashlib.sha256(content.encode()).hexdigest()
        state["revision"] = int(state["revision"]) + 1
        state["attachment"] = {
            "filename": filename,
            "owner": "nadia.corvane",
            "sha256": digest,
        }
        atomic_json(STATE, state)
        correlation = append_audit("change-the-corporate-record", state)
        self.send_json(
            201,
            {
                "audit_id": correlation,
                "record_id": state["record_id"],
                "revision": state["revision"],
                "attachment_sha256": digest,
                "inspection": state["inspection"],
                "assignee": state["assignee"],
            },
        )


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
