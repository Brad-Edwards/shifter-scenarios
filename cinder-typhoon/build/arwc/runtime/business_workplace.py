#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import hmac
import grp
import json
import os
import pathlib
import posixpath
import ssl
import tempfile
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit


ROOT = pathlib.Path("/var/lib/arwc-business")
AUDIT = ROOT / "audit" / "events.jsonl"
TOKEN_HASH = ROOT / "auth" / "corporate-session.sha256"
DISCOVERIES = ROOT / "state" / "discoveries.json"
ARCHIVE_EVIDENCE = ROOT / "archive" / "W08-source.json"

BUNDLE = {
    "record_id": "BND-CRR-OUTLET-17",
    "asset": "AST-CRR-017",
    "outlet_group": "OG-CRR-02",
    "contractor_assignment": "CTR-VEY-204",
    "inspection": "INSP-CRR-2026-09-18",
}

ASSOCIATIONS = {
    "record_id": "ASSOC-CRR-4417-R6",
    "revision": 6,
    "sources": {
        "work_order": {"id": "WO-CRR-4417", "display_name": "Cairn Reach outlet inspection"},
        "contractor_job": {"id": "VYB-204-77", "display_name": "September outlet visit"},
        "asset": {"id": "AST-CRR-017", "display_name": "Outlet gate assembly 17"},
        "inspection": {"id": "INSP-CRR-2026-09-18", "display_name": "Thursday inspection"},
    },
    "association_rows": [
        {
            "association_id": "ASC-CRR-4417-ALT",
            "caller_assignment": "CTR-VEY-204",
            "resolved_record": "MR-CRR-4417-R6",
        }
    ],
}

PROTECTED_MAINTENANCE = {
    "record_id": "MR-CRR-4417-R6",
    "revision": 6,
    "work_order": "WO-CRR-4417",
    "asset": "AST-CRR-017",
    "inspection": "INSP-CRR-2026-09-18",
    "classification": "restricted maintenance record",
    "status": "awaiting outlet inspection",
}

ANNEX = {
    "record_id": "ANN-4417-R2",
    "revision": 2,
    "work_order": "WO-CRR-4417",
    "process_data_handover": "PDH-CRR-READ-08",
    "importer": "annex-import/2",
    "reference": "attachments/ANN-4417-R2",
}

RESTRICTED_HANDOVER = {
    "record_id": "PDH-CRR-READ-08",
    "revision": 8,
    "work_order": "WO-CRR-4417",
    "service_identity": "svc-annex",
    "export_boundary": "integration-read",
}

READ_CONTRACT = {
    "record_id": "PDH-CRR-READ-08",
    "integration_client": "INT-CRR-08",
    "endpoint": "process-read.arwc.test",
    "protocol": "process-read/v2",
    "scope": "OG-CRR-02/read",
    "retained_bundle": "BND-COLLECT-CRR-12",
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
    if not DISCOVERIES.exists():
        atomic_json(DISCOVERIES, {"association_table": False, "restricted_handover": False})
    AUDIT.touch(mode=0o600, exist_ok=True)
    os.chmod(AUDIT, 0o600)


def mark(name: str) -> None:
    state = json.loads(DISCOVERIES.read_text(encoding="utf-8"))
    state[name] = True
    atomic_json(DISCOVERIES, state)


def observed(name: str) -> bool:
    return bool(json.loads(DISCOVERIES.read_text(encoding="utf-8")).get(name))


def append_audit(action: str, result: dict[str, object]) -> str:
    correlation = str(uuid.uuid4())
    event = {
        "audit_id": correlation,
        "time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
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
    server_version = "ARWC-Business-Workplace/1.0"
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
        if not hmac.compare_digest(digest, TOKEN_HASH.read_text().strip()):
            self.send_json(403, {"error": "corporate session required"})
            return False
        return True

    def accepted(self, action: str, result: dict[str, object], status: int = 200) -> None:
        self.send_json(status, {"audit_id": append_audit(action, result), "record": result})

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

    def do_GET(self) -> None:
        if not self.authorized():
            return
        path = urlsplit(self.path).path
        if path == "/api/the-asset-and-the-contractor":
            self.accepted("the-asset-and-the-contractor", BUNDLE)
        elif path == "/api/three-names-for-one-job":
            mark("association_table")
            self.accepted("three-names-for-one-job", ASSOCIATIONS)
        elif path == "/api/an-annex-left-with-the-order":
            self.accepted("an-annex-left-with-the-order", ANNEX)
        elif path == "/api/the-integration-s-read-contract":
            if not observed("restricted_handover"):
                self.send_json(403, {"error": "restricted handover has not been imported"})
            else:
                atomic_json(ARCHIVE_EVIDENCE, {
                    "record_id": "PDH-CRR-READ-08",
                    "retained_bundle": "BND-COLLECT-CRR-12",
                    "integration_client": "INT-CRR-08",
                })
                os.chown(ARCHIVE_EVIDENCE, -1, grp.getgrnam("arwc-archive-source").gr_gid)
                os.chmod(ARCHIVE_EVIDENCE, 0o640)
                self.accepted("the-integration-s-read-contract", READ_CONTRACT)
        else:
            self.send_json(404, {"error": "record not found"})

    def do_POST(self) -> None:
        if not self.authorized():
            return
        path = urlsplit(self.path).path
        request = self.body()
        if request is None:
            return
        if path == "/api/the-record-behind-the-wrong-association":
            if not observed("association_table"):
                self.send_json(403, {"error": "association table has not been read"})
            elif request.get("association_id") != "ASC-CRR-4417-ALT":
                self.send_json(409, {"error": "association does not match"})
            elif request.get("expected_revision") != 6:
                self.send_json(409, {"error": "record revision is stale"})
            else:
                self.accepted("the-record-behind-the-wrong-association", PROTECTED_MAINTENANCE, 201)
            return
        if path == "/api/a-reference-outside-the-order":
            reference = request.get("reference")
            if not isinstance(reference, str) or not reference.startswith("attachments/"):
                self.send_json(409, {"error": "reference is outside attachments"})
                return
            resolved = posixpath.normpath(unquote(reference))
            if resolved != "restricted/PDH-CRR-READ-08":
                self.send_json(409, {"error": "attachment was not found"})
                return
            mark("restricted_handover")
            self.accepted("a-reference-outside-the-order", RESTRICTED_HANDOVER, 201)
            return
        self.send_json(404, {"error": "record not found"})


def main() -> None:
    initialize()
    server = ThreadingHTTPServer(("0.0.0.0", 443), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain("/tmp/arwc-server.crt", "/tmp/arwc-server.key")
    server.socket = context.wrap_socket(server.socket, server_side=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
