#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import hmac
import grp
import http.client
import json
import os
import pathlib
import secrets
import ssl
import tempfile
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit


ROOT = pathlib.Path("/var/lib/arwc-contractors")
STATE = ROOT / "state" / "contractor.json"
AUDIT = ROOT / "audit" / "events.jsonl"
CORPORATE_HASH = ROOT / "auth" / "corporate-session.sha256"
HANDOVER = pathlib.Path("/var/lib/arwc-contractors/handover/contractor-session.json")

APPOINTMENT = {
    "record_id": "APT-CRR-2026-09-18",
    "revision": 1,
    "inspection": "INSP-CRR-2026-09-18",
    "asset": "AST-CRR-017",
    "window": {"day": "Thursday", "starts": "09:00", "ends": "11:00"},
    "owner_organization": "Northbank Civil Inspections",
    "attendee": "northbank.inspector.117",
}
ROSTER = {
    "record_id": "ROSTER-CRR-SEP18-R2",
    "revision": 2,
    "inspection": "INSP-CRR-2026-09-18",
    "identity": "veybridge.tech.204",
    "assignment": "CTR-VEY-204",
    "contractor_organization": "Veybridge Technical Services",
}
FIELD_BAG = {
    "record_id": "FIELD-BAG-CRR-4417-R3",
    "revision": 3,
    "inspection": "INSP-CRR-2026-09-18",
    "asset": "AST-CRR-017",
    "expected_outlets": ["OG-CRR-02"],
    "retained_client": {
        "name": "fieldbag",
        "protocol": "fieldbag/v1",
        "encoding": "application/json",
        "request_fields": ["asset_id", "outlet_group", "sample_time"],
    },
    "service_manifest": {
        "record_id": "FIELD-SERVICES-R21",
        "legacy_endpoint": "field-read-legacy.arwc.test",
        "current_endpoint": "process-read.arwc.test",
    },
}
PROCESS_PATHS = {
    "/api/the-reservoir-s-present-tense", "/api/the-mode-the-plant-is-in",
    "/api/the-instrument-in-the-note", "/api/the-first-live-trace",
    "/api/the-tag-export", "/api/the-scale-kept-elsewhere",
    "/api/when-the-units-changed", "/api/which-outlet-answers",
    "/api/the-project-and-the-note", "/api/which-project-is-running",
    "/api/the-operating-envelope", "/api/conditions-before-movement",
    "/api/accepted-is-not-actuated", "/api/a-sequence-the-process-can-follow",
    "/api/the-diagnostic-nobody-retired", "/api/a-second-interpretation",
    "/api/the-hidden-check", "/api/a-map-from-the-old-diagnostic",
    "/api/the-viewer-in-the-delivery", "/api/the-machine-inside-the-viewer",
    "/api/the-decision-inside-the-sealed-project", "/api/the-reviewer-who-was-never-listed",
    "/api/a-measurement-with-side-effects", "/api/control-beyond-the-measurement",
    "/api/a-measurement-that-never-existed",
    "/api/two-kinds-of-answer", "/api/which-answer-comes-next",
    "/api/the-diagnostic-evidence-bundle", "/api/signed-by-someone-who-never-approved-it",
    "/api/what-the-image-kept", "/api/a-valid-maintenance-record",
    "/api/change-one-record-keep-the-rest",
    "/api/what-counts-as-intact", "/api/the-constraints-of-a-valid-looking-program",
    "/api/a-program-the-engineer-would-accept",
    "/api/the-utility-s-small-world", "/api/control-with-very-little-room",
    "/api/keep-the-authority-you-earned",
    "/api/what-reserve-remains-uncommitted", "/api/paper-truth",
    "/api/bind-the-plan-to-the-plant", "/api/open-the-gates",
    "/api/the-vault-s-misleading-length", "/api/past-the-parser-s-boundary",
    "/api/the-state-execution-returns-to", "/api/the-diagnostic-service-s-authority",
    "/api/the-replay-s-pieces", "/api/the-systems-that-update-it",
    "/api/the-condition-the-old-model-used", "/api/replay-is-not-reality",
    "/api/a-forecast-that-matches-the-instrument", "/api/the-expensive-hour",
    "/api/the-schedule-the-service-accepts", "/api/when-the-forecast-moves",
}
CONTROL_BROKER_PATH = "/api/an-approval-becomes-a-control-client"


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
        "appointment": APPOINTMENT,
        "appointment_observed": False,
        "roster_observed": False,
        "field_bag_observed": False,
        "contractor_session": None,
    }


def initialize() -> None:
    if not STATE.exists():
        atomic_json(STATE, initial_state())
    AUDIT.touch(mode=0o600, exist_ok=True)
    os.chmod(AUDIT, 0o600)
    if HANDOVER.exists():
        os.chown(HANDOVER, -1, grp.getgrnam("arwc-field-session").gr_gid)
        os.chmod(HANDOVER, 0o640)


def append_audit(action: str, principal: str, result: dict[str, object]) -> str:
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


class Handler(BaseHTTPRequestHandler):
    server_version = "ARWC-Contractor-Portal/1.0"
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

    def body(self) -> dict[str, object] | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 2 or length > 8192:
                raise ValueError
            value = json.loads(self.rfile.read(length))
            if not isinstance(value, dict):
                raise ValueError
            return value
        except (ValueError, json.JSONDecodeError):
            self.send_json(409, {"error": "invalid request"})
            return None

    def bearer(self) -> str | None:
        supplied = self.headers.get("Authorization", "")
        return supplied[7:] if supplied.startswith("Bearer ") else None

    def corporate_authorized(self) -> bool:
        if self.headers.get("X-ARWC-Tenant", "arwc") != "arwc":
            self.send_json(403, {"error": "session is not valid for this tenant"})
            return False
        token = self.bearer()
        expected = CORPORATE_HASH.read_text(encoding="ascii").strip()
        if token is None or not hmac.compare_digest(hashlib.sha256(token.encode()).hexdigest(), expected):
            self.send_json(403, {"error": "contractor portal session required"})
            return False
        return True

    def contractor_authorized(self, state: dict[str, object]) -> bool:
        token = self.bearer()
        session = state.get("contractor_session")
        if (self.headers.get("X-ARWC-Tenant", "arwc") != "arwc" or token is None or
                not isinstance(session, dict) or
                not hmac.compare_digest(hashlib.sha256(token.encode()).hexdigest(), str(session.get("token_sha256", "")))):
            self.send_json(403, {"error": "field-work session required"})
            return False
        return True

    def accepted(self, action: str, principal: str, record: dict[str, object], status: int = 200,
                 extra: dict[str, object] | None = None) -> None:
        response: dict[str, object] = {
            "audit_id": append_audit(action, principal, record), "record": record,
        }
        if extra:
            response.update(extra)
        self.send_json(status, response)

    def proxy_field_gateway(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        if length < 0 or length > 65536:
            self.send_json(409, {"error": "invalid field gateway request"})
            return
        payload = self.rfile.read(length) if length else None
        headers = {
            "Authorization": self.headers.get("Authorization", ""),
            "X-ARWC-Tenant": self.headers.get("X-ARWC-Tenant", "arwc"),
            "Host": "field-gateway.arwc.test",
        }
        if payload is not None:
            headers["Content-Type"] = self.headers.get("Content-Type", "application/octet-stream")
            headers["Content-Length"] = str(len(payload))
        context = ssl.create_default_context(cafile="/tmp/ca.crt")
        try:
            connection = http.client.HTTPSConnection("10.77.62.30", 443, context=context, timeout=5)
            connection.request(self.command, urlsplit(self.path).path, body=payload, headers=headers)
            response = connection.getresponse()
            body = response.read()
        except OSError:
            self.send_json(409, {"error": "field gateway unavailable"})
            return
        finally:
            if "connection" in locals():
                connection.close()
        self.send_response(response.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def proxy_control_broker(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        if length < 2 or length > 65536:
            self.send_json(409, {"error": "invalid control broker request"})
            return
        payload = self.rfile.read(length)
        headers = {
            "Authorization": self.headers.get("Authorization", ""),
            "X-ARWC-Tenant": self.headers.get("X-ARWC-Tenant", "arwc"),
            "Host": "control-broker.arwc.test",
            "Content-Type": "application/json",
            "Content-Length": str(len(payload)),
        }
        context = ssl.create_default_context(cafile="/tmp/ca.crt")
        try:
            connection = http.client.HTTPSConnection("10.77.62.40", 443, context=context, timeout=5)
            connection.request("POST", CONTROL_BROKER_PATH, body=payload, headers=headers)
            response = connection.getresponse()
            body = response.read()
        except OSError:
            self.send_json(409, {"error": "control broker unavailable"})
            return
        finally:
            if "connection" in locals():
                connection.close()
        self.send_response(response.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if (self.headers.get("Host", "").split(":", 1)[0] in
                {"field-gateway.arwc.test", "process-read.arwc.test"} and
                path in PROCESS_PATHS | {"/api/the-service-that-replaced-it"}):
            self.proxy_field_gateway()
            return
        state = json.loads(STATE.read_text(encoding="utf-8"))
        if path == "/api/the-field-bag":
            if not self.contractor_authorized(state):
                return
            state["field_bag_observed"] = True
            atomic_json(STATE, state)
            self.accepted("the-field-bag", "veybridge.tech.204", FIELD_BAG)
            return
        if not self.corporate_authorized():
            return
        if path == "/api/window-on-thursday":
            state["appointment_observed"] = True
            atomic_json(STATE, state)
            self.accepted("window-on-thursday", "corporate-reader-principal", state["appointment"])
            return
        if path == "/api/who-is-expected-at-the-gate":
            state["roster_observed"] = True
            atomic_json(STATE, state)
            self.accepted("who-is-expected-at-the-gate", "corporate-reader-principal", ROSTER)
            return
        self.send_json(404, {"error": "record not found"})

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if path == CONTROL_BROKER_PATH:
            self.proxy_control_broker()
            return
        if (self.headers.get("Host", "").split(":", 1)[0] in
                {"field-gateway.arwc.test", "process-read.arwc.test"} and
                path in PROCESS_PATHS | {"/api/a-fresh-reading-from-the-field"}):
            self.proxy_field_gateway()
            return
        if not self.corporate_authorized():
            return
        request = self.body()
        if request is None:
            return
        state = json.loads(STATE.read_text(encoding="utf-8"))
        if path == "/api/an-appointment-we-do-not-own":
            if not state["appointment_observed"] or not state["roster_observed"]:
                self.send_json(403, {"error": "appointment and current roster must be inspected"})
                return
            appointment = state["appointment"]
            if (request.get("appointment_id") != APPOINTMENT["record_id"] or
                    request.get("expected_revision") != appointment["revision"] or
                    request.get("inspection", APPOINTMENT["inspection"]) != APPOINTMENT["inspection"] or
                    request.get("asset", APPOINTMENT["asset"]) != APPOINTMENT["asset"] or
                    request.get("window", APPOINTMENT["window"]) != APPOINTMENT["window"]):
                self.send_json(409, {"error": "appointment binding or revision does not match"})
                return
            if (request.get("attendee") != ROSTER["identity"] or
                    request.get("caller_organization") != ROSTER["contractor_organization"]):
                self.send_json(403, {"error": "attendee does not belong to caller organization"})
                return
            appointment = dict(appointment)
            appointment["revision"] = int(appointment["revision"]) + 1
            appointment["attendee"] = ROSTER["identity"]
            state["appointment"] = appointment
            atomic_json(STATE, state)
            self.accepted("an-appointment-we-do-not-own", ROSTER["identity"], appointment, 201)
            return
        if path == "/api/checked-in-as-the-contractor":
            appointment = state["appointment"]
            if (request.get("appointment_id") != APPOINTMENT["record_id"] or
                    request.get("roster_id") != ROSTER["record_id"] or
                    request.get("identity") != ROSTER["identity"] or
                    appointment.get("attendee") != ROSTER["identity"]):
                self.send_json(403, {"error": "current attendee and gate roster do not match"})
                return
            session = state.get("contractor_session")
            token = None
            if isinstance(session, dict) and HANDOVER.exists():
                handover = json.loads(HANDOVER.read_text(encoding="utf-8"))
                token = handover.get("bearer_token")
            if not isinstance(token, str):
                token = secrets.token_urlsafe(32)
                session = {
                    "record_id": "SCOPE-INSP-CRR-4417",
                    "inspection": APPOINTMENT["inspection"],
                    "asset": APPOINTMENT["asset"],
                    "identity": ROSTER["identity"],
                    "assignment": ROSTER["assignment"],
                    "scope": ["field-work:read"],
                    "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
                }
                state["contractor_session"] = session
                atomic_json(STATE, state)
                atomic_json(HANDOVER, {**session, "bearer_token": token})
                os.chown(HANDOVER, -1, grp.getgrnam("arwc-field-session").gr_gid)
                os.chmod(HANDOVER, 0o640)
            public = {key: value for key, value in session.items() if key != "token_sha256"}
            self.accepted("checked-in-as-the-contractor", ROSTER["identity"], public, 201,
                          {"contractor_session": token})
            return
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
