#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import hmac
import http.client
import json
import os
import pathlib
import secrets
import ssl
import tempfile
import uuid
import grp
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit


ROOT = pathlib.Path("/var/lib/arwc-data-bridge")
STATE = ROOT / "state" / "integration.json"
AUDIT = ROOT / "audit" / "events.jsonl"
READ_EVIDENCE = pathlib.Path("/run/arwc-business-integration/W09-read.json")
DATA_EVIDENCE = pathlib.Path("/run/arwc-data-integration/W09-data.json")
OT_EVIDENCE = ROOT / "handover" / "corporate.json"
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
        atomic_json(STATE, {"current_feed_observed": False, "process_session": None})
    else:
        state = json.loads(STATE.read_text(encoding="utf-8"))
        if "process_session" not in state:
            state["process_session"] = None
            atomic_json(STATE, state)
    AUDIT.touch(mode=0o600, exist_ok=True)
    os.chmod(AUDIT, 0o600)


def append_audit(result: dict[str, object]) -> str:
    correlation = str(uuid.uuid4())
    event = {
        "audit_id": correlation,
        "time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "tenant": "arwc",
        "principal": "integration-reader-principal",
        "action": "from-the-report-to-the-live-feed",
        "object": result["record_id"],
        "revision": result["revision"],
        "result_digest": hashlib.sha256(
            json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }
    with AUDIT.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return correlation


def load_evidence(path: pathlib.Path) -> dict[str, object] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


class Handler(BaseHTTPRequestHandler):
    server_version = "ARWC-Integration-Gateway/1.0"
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

    def proxy_historian(self) -> None:
        path = urlsplit(self.path).path
        if path not in PROCESS_PATHS:
            self.send_json(404, {"error": "record not found"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length < 0 or length > 65536:
            self.send_json(409, {"error": "invalid process request"})
            return
        payload = self.rfile.read(length) if length else None
        headers = {
            "Authorization": self.headers.get("Authorization", ""),
            "X-ARWC-Tenant": self.headers.get("X-ARWC-Tenant", "arwc"),
            "Host": "process-historian.arwc.test",
        }
        if payload is not None:
            headers["Content-Type"] = "application/json"
            headers["Content-Length"] = str(len(payload))
        context = ssl.create_default_context(cafile="/tmp/ca.crt")
        try:
            connection = http.client.HTTPSConnection("10.77.63.30", 443, context=context, timeout=5)
            connection.request(self.command, path, body=payload, headers=headers)
            response = connection.getresponse()
            result = response.read()
        except OSError:
            self.send_json(409, {"error": "process historian unavailable"})
            return
        finally:
            if "connection" in locals():
                connection.close()
        self.send_response(response.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(result)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(result)

    def do_GET(self) -> None:
        self.proxy_historian()

    def do_POST(self) -> None:
        if urlsplit(self.path).path in {
            "/internal/w29-reserve-observation", "/internal/w29-paper-truth",
        }:
            if (self.headers.get("X-ARWC-Internal") != "planning-data-w29" or
                    self.headers.get("X-ARWC-Tenant") != "arwc" or
                    self.client_address[0] != "10.77.62.10"):
                self.send_json(403, {"error": "planning service context required"})
                return
            request = self.body()
            if request is None:
                return
            payload = json.dumps(request, sort_keys=True, separators=(",", ":")).encode()
            context = ssl.create_default_context(cafile="/tmp/ca.crt")
            connection = http.client.HTTPSConnection("10.77.63.30", 443, context=context, timeout=5)
            try:
                connection.request("POST", urlsplit(self.path).path, body=payload, headers={
                    "Content-Type": "application/json", "Content-Length": str(len(payload)),
                    "X-ARWC-Internal": "data-bridge-w29", "X-ARWC-Tenant": "arwc",
                    "Host": "process-historian.arwc.test",
                })
                response = connection.getresponse()
                result = json.loads(response.read())
            except (OSError, json.JSONDecodeError):
                self.send_json(409, {"error": "process evidence service unavailable"})
                return
            finally:
                connection.close()
            self.send_json(response.status, result)
            return
        if urlsplit(self.path).path == "/internal/diagnostic-estimate":
            if (self.headers.get("X-ARWC-Internal") != "diagnostics-r27" or
                    self.headers.get("X-ARWC-Tenant") != "arwc" or
                    self.client_address[0] != "10.77.63.50"):
                self.send_json(403, {"error": "diagnostic service context required"})
                return
            request = self.body()
            if request is None:
                return
            payload = json.dumps(request, sort_keys=True, separators=(",", ":")).encode()
            context = ssl.create_default_context(cafile="/tmp/ca.crt")
            connection = http.client.HTTPSConnection("a-data", 443, context=context, timeout=5)
            try:
                connection.request("POST", "/internal/diagnostic-estimate", body=payload, headers={
                    "Content-Type": "application/json", "Content-Length": str(len(payload)),
                    "X-ARWC-Internal": "data-bridge-r27", "X-ARWC-Tenant": "arwc",
                })
                response = connection.getresponse(); result = json.loads(response.read())
            except (OSError, json.JSONDecodeError):
                self.send_json(409, {"error": "planning consumer unavailable"}); return
            finally:
                connection.close()
            self.send_json(response.status, result)
            return
        if urlsplit(self.path).path != "/api/from-the-report-to-the-live-feed":
            self.proxy_historian()
            return
        if self.headers.get("X-ARWC-Tenant", "arwc") != "arwc":
            self.send_json(403, {"error": "session is not valid for this tenant"})
            return
        supplied = self.headers.get("Authorization", "")
        read = load_evidence(READ_EVIDENCE)
        data = load_evidence(DATA_EVIDENCE)
        if (not supplied.startswith("Bearer ") or read is None or
                not isinstance(read.get("token_sha256"), str) or
                not hmac.compare_digest(
                    hashlib.sha256(supplied[7:].encode()).hexdigest(), read["token_sha256"],
                )):
            self.send_json(403, {"error": "integration read session required"})
            return
        if (data is None or data.get("record_id") != "REC-CRR-DP3-17" or
                data.get("planning_window") != "ALLOC-2026-DP3"):
            self.send_json(403, {"error": "current report binding required"})
            return
        request = self.body()
        if request is None:
            return
        if (request.get("integration_client") != "INT-CRR-08" or
                request.get("report_binding") != "REC-CRR-DP3-17" or
                request.get("scope") != "OG-CRR-02/read"):
            self.send_json(409, {"error": "integration binding does not match"})
            return
        feed = request.get("feed")
        if feed == "FEED-OG2-R19":
            self.send_json(409, {
                "error": "feed revision is stale",
                "record": {"record_id": "FEED-OG2-R19", "revision": 19, "current": False},
            })
            return
        if feed != "FEED-OG2-R21":
            self.send_json(409, {"error": "process feed is outside the integration scope"})
            return
        result = {
            "record_id": "FEED-OG2-R21",
            "revision": 21,
            "current": True,
            "scope": "OG-CRR-02/read",
            "outlet_group": "OG-CRR-02",
            "asset": "AST-CRR-017",
            "planning_window": "ALLOC-2026-DP3",
            "usable_reserve_ml": 12.40,
            "unit": "ML",
            "instruments": ["FIT-CRR-204A", "FIT-CRR-204B"],
        }
        state = json.loads(STATE.read_text(encoding="utf-8"))
        token = state.get("process_session")
        if not isinstance(token, str):
            token = secrets.token_urlsafe(40)
            state["process_session"] = token
        state["current_feed_observed"] = True
        atomic_json(STATE, state)
        atomic_json(OT_EVIDENCE, {
            "record_id": "OT-READ-CORPORATE-R21", "branch": "corporate-integration",
            "scope": "OG-CRR-02/read", "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
        })
        os.chown(OT_EVIDENCE, -1, grp.getgrnam("arwc-ot-read").gr_gid)
        os.chmod(OT_EVIDENCE, 0o640)
        self.send_json(201, {"audit_id": append_audit(result), "record": result,
                             "process_session": token})


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
