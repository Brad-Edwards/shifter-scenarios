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


ROOT = pathlib.Path("/var/lib/arwc-contractor-bridge")
STATE = ROOT / "state" / "field-gateway.json"
AUDIT = ROOT / "audit" / "events.jsonl"
SESSION = pathlib.Path("/run/arwc-field-session/contractor-session.json")
OT_EVIDENCE = ROOT / "handover" / "contractor.json"
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
}
MANIFEST = {
    "record_id": "FIELD-SERVICES-R21",
    "revision": 21,
    "services": [
        {"host": "field-read-legacy.arwc.test", "protocol": "fieldbag/v1", "status": "retired"},
        {"host": "process-read.arwc.test", "protocol": "process-read/v2", "status": "active",
         "encoding": "application/cbor", "authentication": "inspection-scoped"},
    ],
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


def initialize() -> None:
    if not STATE.exists():
        atomic_json(STATE, {"manifest_observed": False, "current_read_observed": False,
                           "nonces": [], "process_session": None})
    else:
        state = json.loads(STATE.read_text(encoding="utf-8"))
        if "process_session" not in state:
            state["process_session"] = None
            atomic_json(STATE, state)
    AUDIT.touch(mode=0o600, exist_ok=True)
    os.chmod(AUDIT, 0o600)


def cbor_length(data: bytes, offset: int, additional: int) -> tuple[int, int]:
    if additional < 24:
        return additional, offset
    widths = {24: 1, 25: 2, 26: 4, 27: 8}
    width = widths.get(additional)
    if width is None or offset + width > len(data):
        raise ValueError("unsupported CBOR length")
    return int.from_bytes(data[offset:offset + width], "big"), offset + width


def decode_cbor_text_map(data: bytes) -> dict[str, str]:
    if not data:
        raise ValueError("empty CBOR")
    initial = data[0]
    if initial >> 5 != 5:
        raise ValueError("CBOR map required")
    pairs, offset = cbor_length(data, 1, initial & 31)
    result: dict[str, str] = {}
    for _ in range(pairs):
        values: list[str] = []
        for _ in range(2):
            if offset >= len(data) or data[offset] >> 5 != 3:
                raise ValueError("CBOR text required")
            length, offset = cbor_length(data, offset + 1, data[offset] & 31)
            if offset + length > len(data):
                raise ValueError("truncated CBOR")
            values.append(data[offset:offset + length].decode("utf-8"))
            offset += length
        if values[0] in result:
            raise ValueError("duplicate CBOR key")
        result[values[0]] = values[1]
    if offset != len(data):
        raise ValueError("trailing CBOR data")
    return result


def append_audit(action: str, result: dict[str, object]) -> str:
    correlation = str(uuid.uuid4())
    event = {
        "audit_id": correlation,
        "time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "tenant": "arwc",
        "principal": "veybridge.tech.204",
        "action": action,
        "object": result.get("record_id"),
        "revision": result.get("revision"),
        "result_digest": hashlib.sha256(json.dumps(result, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
    }
    with AUDIT.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return correlation


class Handler(BaseHTTPRequestHandler):
    server_version = "ARWC-Field-Gateway/2.0"
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

    def authorized(self) -> dict[str, object] | None:
        try:
            session = json.loads(SESSION.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self.send_json(403, {"error": "checked-in inspection session required"})
            return None
        supplied = self.headers.get("Authorization", "")
        if (self.headers.get("X-ARWC-Tenant", "arwc") != "arwc" or
                not supplied.startswith("Bearer ") or
                not hmac.compare_digest(hashlib.sha256(supplied[7:].encode()).hexdigest(),
                                        str(session.get("token_sha256", "")))):
            self.send_json(403, {"error": "checked-in inspection session required"})
            return None
        return session

    def proxy_historian(self) -> None:
        path = urlsplit(self.path).path
        length = int(self.headers.get("Content-Length", "0"))
        if path not in PROCESS_PATHS or length < 0 or length > 65536:
            self.send_json(404, {"error": "record not found"})
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
        if urlsplit(self.path).path in PROCESS_PATHS:
            self.proxy_historian()
            return
        if urlsplit(self.path).path != "/api/the-service-that-replaced-it":
            self.send_json(404, {"error": "record not found"})
            return
        if self.authorized() is None:
            return
        state = json.loads(STATE.read_text(encoding="utf-8"))
        state["manifest_observed"] = True
        atomic_json(STATE, state)
        self.send_json(200, {"audit_id": append_audit("the-service-that-replaced-it", MANIFEST), "record": MANIFEST})

    def do_POST(self) -> None:
        if urlsplit(self.path).path in PROCESS_PATHS:
            self.proxy_historian()
            return
        if urlsplit(self.path).path != "/api/a-fresh-reading-from-the-field":
            self.send_json(404, {"error": "record not found"})
            return
        session = self.authorized()
        if session is None:
            return
        state = json.loads(STATE.read_text(encoding="utf-8"))
        if not state["manifest_observed"]:
            self.send_json(403, {"error": "current service manifest required"})
            return
        if self.headers.get_content_type() != "application/cbor":
            self.send_json(409, {"error": "process-read/v2 requires application/cbor"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > 4096:
                raise ValueError
            request = decode_cbor_text_map(self.rfile.read(length))
        except (ValueError, UnicodeDecodeError):
            self.send_json(409, {"error": "invalid process-read/v2 CBOR map"})
            return
        if set(request) != {"asset", "group", "observed_at", "nonce"}:
            self.send_json(409, {"error": "CBOR map keys do not match process-read/v2"})
            return
        if request["asset"] != session.get("asset") or request["group"] != "OG-CRR-02":
            self.send_json(409, {"error": "reading is outside the checked-in inspection scope"})
            return
        try:
            observed = datetime.fromisoformat(request["observed_at"].replace("Z", "+00:00"))
            age = abs((datetime.now(timezone.utc) - observed.astimezone(timezone.utc)).total_seconds())
        except ValueError:
            age = 10**9
        if age > 600:
            self.send_json(409, {"error": "observation request is stale"})
            return
        if not request["nonce"] or request["nonce"] in state["nonces"]:
            self.send_json(409, {"error": "nonce has already been used"})
            return
        state["nonces"].append(request["nonce"])
        state["current_read_observed"] = True
        token = state.get("process_session")
        if not isinstance(token, str):
            token = secrets.token_urlsafe(40)
            state["process_session"] = token
        atomic_json(STATE, state)
        result = {
            "record_id": "FEED-OG2-R21",
            "revision": 21,
            "inspection": session["inspection"],
            "asset": session["asset"],
            "group": "OG-CRR-02",
            "observed_at": request["observed_at"],
            "nonce": request["nonce"],
            "observations": [
                {"instrument": "FIT-CRR-204A", "flow_lps": 0.0},
                {"instrument": "FIT-CRR-204B", "flow_lps": 0.0},
            ],
        }
        atomic_json(OT_EVIDENCE, {
            "record_id": "OT-READ-CONTRACTOR-R21", "branch": "contractor-field",
            "scope": "OG-CRR-02/read", "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
        })
        os.chown(OT_EVIDENCE, -1, grp.getgrnam("arwc-ot-read").gr_gid)
        os.chmod(OT_EVIDENCE, 0o640)
        self.send_json(201, {"audit_id": append_audit("a-fresh-reading-from-the-field", result),
                             "record": result, "process_session": token})


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
