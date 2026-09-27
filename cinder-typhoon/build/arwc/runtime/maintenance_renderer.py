#!/usr/bin/env python3
from __future__ import annotations

import base64
import grp
import hashlib
import hmac
import json
import os
import pathlib
import tempfile
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature


ROOT = pathlib.Path("/var/lib/arwc-renderer")
STATE = ROOT / "state" / "renderer.json"
AUDIT = ROOT / "audit" / "events.jsonl"
CONTRACTOR_SESSION = pathlib.Path("/run/arwc-field-session/contractor-session.json")
APPROVAL_EVIDENCE = pathlib.Path("/run/arwc-approval-evidence/approval.json")
ATTESTATION_EVIDENCE = pathlib.Path("/var/lib/arwc-renderer/handover/renderer-attestation.json")

PROFILE = {
    "record_id": "RENDER-MAINT-CRR-R9",
    "revision": 9,
    "approval": "APR-CRR-4417-R6",
    "inspection": "INSP-CRR-2026-09-18",
    "reviewer_role": "maintenance-reviewer",
    "worker": "svc-maint-render",
    "status": "current",
}
APPROVAL_FIELDS = {
    "record_id": "APR-CRR-4417-R6",
    "revision": 6,
    "maintenance": "WO-CRR-4417",
    "inspection": "INSP-CRR-2026-09-18",
    "asset": "AST-CRR-017",
    "drawing": "DRW-OG2-R8",
    "drawing_revision": "R8",
    "status": "signed",
}


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def atomic_json(path: pathlib.Path, value: object, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_json(path: pathlib.Path) -> dict[str, object] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def initialize() -> None:
    if not STATE.exists():
        atomic_json(STATE, {
            "profile_observed": False,
            "restricted_preview_accepted": False,
            "handover_recovered": False,
            "attestation_token": None,
        })
    AUDIT.touch(mode=0o600, exist_ok=True)
    os.chmod(AUDIT, 0o600)


def verify_approval(record: object) -> bool:
    if not isinstance(record, dict):
        return False
    owned = load_json(APPROVAL_EVIDENCE)
    if owned is None or not hmac.compare_digest(canonical(record), canonical(owned)):
        return False
    if any(record.get(key) != value for key, value in APPROVAL_FIELDS.items()):
        return False
    if record.get("signature_algorithm") != "Ed25519":
        return False
    try:
        public = base64.b64decode(str(record["signing_public_key"]), validate=True)
        signature = base64.b64decode(str(record["signature"]), validate=True)
        payload = {key: value for key, value in record.items()
                   if key not in {"signature_algorithm", "signature", "signing_public_key"}}
        Ed25519PublicKey.from_public_bytes(public).verify(signature, canonical(payload))
    except (KeyError, ValueError, TypeError, InvalidSignature):
        return False
    return True


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
        "result_digest": hashlib.sha256(canonical(result)).hexdigest(),
    }
    with AUDIT.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return correlation


class Handler(BaseHTTPRequestHandler):
    server_version = "ARWC-Maintenance-Renderer/1.0"
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
            if length < 2 or length > 65536:
                raise ValueError
            value = json.loads(self.rfile.read(length))
            if not isinstance(value, dict):
                raise ValueError
            return value
        except (ValueError, json.JSONDecodeError):
            self.send_json(409, {"error": "invalid renderer request"})
            return None

    def authorized(self) -> bool:
        evidence = load_json(CONTRACTOR_SESSION)
        supplied = self.headers.get("Authorization", "")
        if (self.headers.get("X-ARWC-Tenant", "arwc") != "arwc" or
                not supplied.startswith("Bearer ") or evidence is None or
                not hmac.compare_digest(hashlib.sha256(supplied[7:].encode()).hexdigest(),
                                        str(evidence.get("token_sha256", "")))):
            self.send_json(403, {"error": "maintenance renderer session required"})
            return False
        return True

    def accepted(self, action: str, record: dict[str, object], *, status: int = 200,
                 extra: dict[str, object] | None = None) -> None:
        response: dict[str, object] = {"audit_id": append_audit(action, record), "record": record}
        if extra:
            response.update(extra)
        self.send_json(status, response)

    def do_GET(self) -> None:
        if urlsplit(self.path).path != "/api/which-renderer-holds-the-approval":
            self.send_json(404, {"error": "record not found"})
            return
        if not self.authorized():
            return
        approval = load_json(APPROVAL_EVIDENCE)
        if not verify_approval(approval):
            self.send_json(403, {"error": "current signed maintenance approval required"})
            return
        state = load_json(STATE)
        assert state is not None
        state["profile_observed"] = True
        atomic_json(STATE, state)
        self.accepted("which-renderer-holds-the-approval", PROFILE)

    def do_POST(self) -> None:
        if not self.authorized():
            return
        request = self.body()
        if request is None:
            return
        path = urlsplit(self.path).path
        state = load_json(STATE)
        assert state is not None
        if path == "/api/authority-behind-the-preview":
            if not state["profile_observed"]:
                self.send_json(403, {"error": "current renderer profile must be inspected"})
                return
            if (request.get("work_package") != "WP-CRR-CINDER-R1" or
                    request.get("inspection") != "INSP-CRR-2026-09-18" or
                    request.get("preview") != "privileged-inspection" or
                    not verify_approval(request.get("approval"))):
                self.send_json(409, {"error": "work package, approval, or inspection binding does not match"})
                return
            # The deployed mapping validates the approval but omits caller-role comparison.
            record = {
                "record_id": "PREVIEW-CRR-CINDER-R1",
                "revision": 1,
                "work_package": "WP-CRR-CINDER-R1",
                "approval": "APR-CRR-4417-R6",
                "inspection": "INSP-CRR-2026-09-18",
                "asset": "AST-CRR-017",
                "drawing": "DRW-OG2-R8",
                "drawing_revision": "R8",
                "preview": "privileged-inspection",
                "worker": "svc-maint-render",
            }
            state["restricted_preview_accepted"] = True
            atomic_json(STATE, state)
            self.accepted("authority-behind-the-preview", record, status=201)
            return
        if path == "/api/the-preview-executes":
            if not state["restricted_preview_accepted"]:
                self.send_json(403, {"error": "accepted restricted preview required"})
                return
            if any(name in request for name in ("command", "url", "target")):
                self.send_json(409, {"error": "renderer action is not permitted"})
                return
            if (request.get("work_package") != "WP-CRR-CINDER-R1" or
                    request.get("approval") != "APR-CRR-4417-R6" or
                    request.get("action") != "fetch_handover" or
                    request.get("argument") != "HND-MAINT-CTRL-09"):
                self.send_json(409, {"error": "renderer action binding does not match"})
                return
            token = state.get("attestation_token")
            if not isinstance(token, str):
                token = __import__("secrets").token_urlsafe(40)
                state["attestation_token"] = token
            record = {
                "record_id": "RENDER-ACTION-CRR-09",
                "revision": 1,
                "action": "fetch_handover(HND-MAINT-CTRL-09)",
                "executed_as": "svc-maint-render",
                "work_package": "WP-CRR-CINDER-R1",
                "approval": "APR-CRR-4417-R6",
                "inspection": "INSP-CRR-2026-09-18",
                "asset": "AST-CRR-017",
                "drawing": "DRW-OG2-R8",
                "drawing_revision": "R8",
            }
            evidence = {
                "record_id": "HND-MAINT-CTRL-09",
                "revision": 9,
                "tenant": "arwc",
                "approval": "APR-CRR-4417-R6",
                "inspection": "INSP-CRR-2026-09-18",
                "work_package": "WP-CRR-CINDER-R1",
                "worker": "svc-maint-render",
                "audience": "control-broker.arwc.test",
                "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
            }
            atomic_json(ATTESTATION_EVIDENCE, evidence, 0o640)
            os.chown(ATTESTATION_EVIDENCE, -1, grp.getgrnam("arwc-renderer-evidence").gr_gid)
            state["handover_recovered"] = True
            atomic_json(STATE, state)
            public_handover = {key: value for key, value in evidence.items() if key != "token_sha256"}
            self.accepted("the-preview-executes", record, status=201,
                          extra={"handover": public_handover, "renderer_attestation": token})
            return
        self.send_json(404, {"error": "record not found"})


def main() -> None:
    initialize()
    server = ThreadingHTTPServer(("0.0.0.0", 443), Handler)
    import ssl
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain("/tmp/server.crt", "/tmp/server.key")
    server.socket = context.wrap_socket(server.socket, server_side=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
