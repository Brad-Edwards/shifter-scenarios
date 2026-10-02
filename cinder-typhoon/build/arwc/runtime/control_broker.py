#!/usr/bin/env python3
from __future__ import annotations

import base64
import grp
import hashlib
import hmac
import json
import os
import pathlib
import secrets
import socket
import struct
import tempfile
import threading
import uuid
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature


ROOT = pathlib.Path("/var/lib/arwc-control-broker")
STATE = ROOT / "state" / "control-broker.json"
AUDIT = ROOT / "audit" / "events.jsonl"
CONTRACTOR_SESSION = pathlib.Path("/run/arwc-field-session/contractor-session.json")
APPROVAL_EVIDENCE = pathlib.Path("/run/arwc-approval-evidence/approval.json")
RENDERER_EVIDENCE = pathlib.Path("/run/arwc-renderer-evidence/renderer-attestation.json")
MAINTENANCE_ROUTE = "/api/an-approval-becomes-a-control-client"
UTILITY_ROUTE = "/api/keep-the-authority-you-earned"
UTILITY_SOCKET = "/run/arwc/control-issuer.sock"
AUTHORITY_EVIDENCE = ROOT / "authority"
CONTROL_CLIENT_LIFETIME = timedelta(minutes=15)

APPROVAL_FIELDS = {
    "record_id": "APR-CRR-4417-R6", "revision": 6,
    "maintenance": "WO-CRR-4417", "inspection": "INSP-CRR-2026-09-18",
    "asset": "AST-CRR-017", "drawing": "DRW-OG2-R8",
    "drawing_revision": "R8", "status": "signed",
}


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


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


def load_json(path: pathlib.Path) -> dict[str, object] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def publish_authority(record: dict[str, object]) -> None:
    evidence = {key: value for key, value in record.items() if key != "bearer_token"}
    path = AUTHORITY_EVIDENCE / f'{record["record_id"]}.json'
    atomic_json(path, evidence)
    os.chown(path, -1, grp.getgrnam("arwc-control-authority").gr_gid)
    os.chmod(path, 0o640)


def initialize() -> None:
    if not STATE.exists():
        atomic_json(STATE, {
            "control_client": None, "authority_demonstrated": False,
            "utility_control_client": None, "utility_authority_demonstrated": False,
        })
    else:
        state = load_json(STATE)
        assert state is not None
        changed = False
        for key, value in (("utility_control_client", None),
                           ("utility_authority_demonstrated", False)):
            if key not in state:
                state[key] = value
                changed = True
        if changed:
            atomic_json(STATE, state)
    AUDIT.touch(mode=0o600, exist_ok=True)
    os.chmod(AUDIT, 0o600)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def timestamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def verify_approval(record: object) -> bool:
    if not isinstance(record, dict):
        return False
    owned = load_json(APPROVAL_EVIDENCE)
    if owned is None or not hmac.compare_digest(canonical(record), canonical(owned)):
        return False
    if any(record.get(key) != value for key, value in APPROVAL_FIELDS.items()):
        return False
    try:
        public = base64.b64decode(str(record["signing_public_key"]), validate=True)
        signature = base64.b64decode(str(record["signature"]), validate=True)
        payload = {key: value for key, value in record.items()
                   if key not in {"signature_algorithm", "signature", "signing_public_key"}}
        if record.get("signature_algorithm") != "Ed25519":
            return False
        Ed25519PublicKey.from_public_bytes(public).verify(signature, canonical(payload))
    except (KeyError, ValueError, TypeError, InvalidSignature):
        return False
    return True


def token_matches(raw: str, record: dict[str, object] | None) -> bool:
    return (record is not None and isinstance(record.get("token_sha256"), str) and
            hmac.compare_digest(hashlib.sha256(raw.encode()).hexdigest(), str(record["token_sha256"])))


def append_audit(action: str, principal: str, result: dict[str, object]) -> str:
    correlation = str(uuid.uuid4())
    event = {
        "audit_id": correlation, "time": timestamp(utcnow()), "tenant": "arwc",
        "principal": principal, "action": action, "object": result.get("record_id"),
        "revision": result.get("revision"),
        "result_digest": hashlib.sha256(canonical(result)).hexdigest(),
    }
    with AUDIT.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return correlation


def utility_response(request: dict[str, object], peer_uid: int) -> tuple[int, dict[str, object]]:
    state = load_json(STATE)
    assert state is not None
    if request.get("operation") == "readback":
        client = state.get("utility_control_client")
        raw = request.get("control_client")
        if not isinstance(raw, str) or not isinstance(client, dict) or not token_matches(raw, client):
            return 403, {"error": "scoped utility control client required"}
        try:
            expires = datetime.fromisoformat(str(client["expires_at"]).replace("Z", "+00:00"))
        except (KeyError, ValueError):
            expires = datetime.fromtimestamp(0, timezone.utc)
        if utcnow() >= expires:
            return 403, {"error": "scoped utility control client expired"}
        if (request.get("outlet_group") != "OG-CRR-02" or
                request.get("project") != "CRR-CTRL-R21" or
                request.get("action") != "readback"):
            return 409, {"error": "requested operation is outside client scope"}
        record = {
            "record_id": "CTRL-READBACK-CRR-28", "revision": 4,
            "client": "CTRL-CLIENT-CRR-28", "outlet_group": "OG-CRR-02",
            "project": "CRR-CTRL-R21", "action": "readback", "authority": "accepted",
        }
        state["utility_authority_demonstrated"] = True
        atomic_json(STATE, state)
        return 201, {
            "audit_id": append_audit(
                "keep-the-authority-you-earned/readback", "CTRL-CLIENT-CRR-28", record,
            ),
            "record": record,
        }

    expected = {
        "issuer_record": "ISSUER-UTIL-OG2-R4", "outlet_group": "OG-CRR-02",
        "project": "CRR-CTRL-R21", "actions": ["plan-execute", "readback"],
    }
    correlation = request.get("correlation")
    try:
        correlation_valid = str(uuid.UUID(str(correlation))) == str(correlation)
    except (ValueError, TypeError):
        correlation_valid = False
    if (peer_uid != 0 or not correlation_valid or
            any(request.get(key) != value for key, value in expected.items()) or
            set(request) != {*expected, "correlation"}):
        return 403, {"error": "privileged utility issuer call required"}
    now = utcnow()
    current = state.get("utility_control_client")
    raw = None
    if isinstance(current, dict):
        try:
            current_expiry = datetime.fromisoformat(str(current["expires_at"]).replace("Z", "+00:00"))
        except (KeyError, ValueError):
            current_expiry = datetime.fromtimestamp(0, timezone.utc)
        if now < current_expiry and isinstance(current.get("bearer_token"), str):
            raw = str(current["bearer_token"])
    if raw is None:
        raw = secrets.token_urlsafe(40)
        current = {
            "record_id": "CTRL-CLIENT-CRR-28", "revision": 4,
            "issuer_record": "ISSUER-UTIL-OG2-R4", "issuer_correlation": correlation,
            "outlet_group": "OG-CRR-02", "project": "CRR-CTRL-R21",
            "actions": ["plan-execute", "readback"],
            "issued_at": timestamp(now), "expires_at": timestamp(now + CONTROL_CLIENT_LIFETIME),
            "token_sha256": hashlib.sha256(raw.encode()).hexdigest(), "bearer_token": raw,
        }
        state["utility_control_client"] = current
        atomic_json(STATE, state)
    publish_authority(current)
    public = {key: value for key, value in current.items()
              if key not in {"token_sha256", "bearer_token"}}
    return 201, {
        "audit_id": append_audit(
            "keep-the-authority-you-earned/issue", "svc-utility-issuer@control.arwc.test", public,
        ),
        "record": public, "control_client": raw,
    }


def utility_socket_server() -> None:
    path = pathlib.Path(UTILITY_SOCKET)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(path))
    os.chmod(path, 0o666)
    server.listen(8)
    while True:
        connection, _ = server.accept()
        try:
            credentials = connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
            _, peer_uid, _ = struct.unpack("3i", credentials)
            body = bytearray()
            while len(body) <= 8192 and not body.endswith(b"\n"):
                chunk = connection.recv(2048)
                if not chunk:
                    break
                body.extend(chunk)
            try:
                request = json.loads(body)
                if not isinstance(request, dict):
                    raise ValueError
                status, response = utility_response(request, peer_uid)
            except (ValueError, json.JSONDecodeError):
                status, response = 409, {"error": "invalid utility issuer request"}
            response["status"] = status
            connection.sendall(canonical(response) + b"\n")
        finally:
            connection.close()


class Handler(BaseHTTPRequestHandler):
    server_version = "ARWC-Control-Broker/1.0"
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
            self.send_json(409, {"error": "invalid control broker request"})
            return None

    def bearer(self) -> str | None:
        supplied = self.headers.get("Authorization", "")
        return supplied[7:] if supplied.startswith("Bearer ") else None

    def tenant_ok(self) -> bool:
        if self.headers.get("X-ARWC-Tenant", "arwc") != "arwc":
            self.send_json(403, {"error": "control authority is not valid for this tenant"})
            return False
        return True

    def accepted(self, action: str, principal: str, record: dict[str, object],
                 extra: dict[str, object] | None = None) -> None:
        response: dict[str, object] = {"audit_id": append_audit(action, principal, record), "record": record}
        if extra:
            response.update(extra)
        self.send_json(201, response)

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if path not in {MAINTENANCE_ROUTE, UTILITY_ROUTE}:
            self.send_json(404, {"error": "record not found"})
            return
        if not self.tenant_ok():
            return
        request = self.body()
        if request is None:
            return
        supplied = self.bearer()
        state = load_json(STATE)
        assert state is not None
        if path == UTILITY_ROUTE:
            if request.get("operation") != "readback" or not isinstance(supplied, str):
                self.send_json(403, {"error": "scoped utility control client required"})
                return
            status, response = utility_response({**request, "control_client": supplied}, os.getuid())
            self.send_json(status, response)
            return
        if request.get("operation") == "readback":
            client = state.get("control_client")
            if not isinstance(supplied, str) or not isinstance(client, dict) or not token_matches(supplied, client):
                self.send_json(403, {"error": "scoped control client required"})
                return
            try:
                expires = datetime.fromisoformat(str(client["expires_at"]).replace("Z", "+00:00"))
            except (KeyError, ValueError):
                expires = datetime.fromtimestamp(0, timezone.utc)
            if utcnow() >= expires:
                self.send_json(403, {"error": "scoped control client expired"})
                return
            if (request.get("outlet_group") != "OG-CRR-02" or
                    request.get("project") != "CRR-CTRL-R21" or
                    request.get("action") != "readback"):
                self.send_json(409, {"error": "requested operation is outside client scope"})
                return
            record = {
                "record_id": "CTRL-READBACK-CRR-26", "revision": 1,
                "client": "CTRL-CLIENT-CRR-26", "outlet_group": "OG-CRR-02",
                "project": "CRR-CTRL-R21", "action": "readback", "authority": "accepted",
            }
            state["authority_demonstrated"] = True
            atomic_json(STATE, state)
            self.accepted("an-approval-becomes-a-control-client/readback", "CTRL-CLIENT-CRR-26", record)
            return

        if not isinstance(supplied, str) or not token_matches(supplied, load_json(CONTRACTOR_SESSION)):
            self.send_json(403, {"error": "issuer evidence required"})
            return
        renderer = load_json(RENDERER_EVIDENCE)
        attestation = request.get("renderer_attestation")
        if (not isinstance(attestation, str) or not token_matches(attestation, renderer) or
                renderer is None or renderer.get("record_id") != "HND-MAINT-CTRL-09" or
                renderer.get("revision") != 9 or renderer.get("approval") != "APR-CRR-4417-R6" or
                renderer.get("inspection") != "INSP-CRR-2026-09-18" or
                renderer.get("work_package") != "WP-CRR-CINDER-R1" or
                renderer.get("audience") != "control-broker.arwc.test"):
            self.send_json(403, {"error": "valid renderer attestation required"})
            return
        actions = request.get("actions")
        if (not verify_approval(request.get("approval")) or
                request.get("outlet_group") != "OG-CRR-02" or
                request.get("project") != "CRR-CTRL-R21" or
                not isinstance(actions, list) or len(actions) != 2 or
                set(actions) != {"plan-execute", "readback"}):
            self.send_json(409, {"error": "approval or requested control scope does not match"})
            return
        # The issuer verifies the evidence and requested scope but omits initiating caller-role comparison.
        now = utcnow()
        current = state.get("control_client")
        raw = None
        if isinstance(current, dict):
            try:
                current_expiry = datetime.fromisoformat(str(current["expires_at"]).replace("Z", "+00:00"))
            except (KeyError, ValueError):
                current_expiry = datetime.fromtimestamp(0, timezone.utc)
            if now < current_expiry and isinstance(current.get("bearer_token"), str):
                raw = str(current["bearer_token"])
        if raw is None:
            raw = secrets.token_urlsafe(40)
            current = {
                "record_id": "CTRL-CLIENT-CRR-26", "revision": 1,
                "approval": "APR-CRR-4417-R6", "inspection": "INSP-CRR-2026-09-18",
                "outlet_group": "OG-CRR-02", "project": "CRR-CTRL-R21",
                "actions": ["plan-execute", "readback"],
                "issued_at": timestamp(now), "expires_at": timestamp(now + CONTROL_CLIENT_LIFETIME),
                "token_sha256": hashlib.sha256(raw.encode()).hexdigest(), "bearer_token": raw,
            }
            state["control_client"] = current
            atomic_json(STATE, state)
        publish_authority(current)
        public = {key: value for key, value in current.items()
                  if key not in {"token_sha256", "bearer_token"}}
        self.accepted("an-approval-becomes-a-control-client/issue", "veybridge.tech.204", public,
                      extra={"control_client": raw})


def main() -> None:
    initialize()
    threading.Thread(target=utility_socket_server, name="utility-issuer", daemon=True).start()
    server = ThreadingHTTPServer(("0.0.0.0", 443), Handler)
    import ssl
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain("/tmp/server.crt", "/tmp/server.key")
    server.socket = context.wrap_socket(server.socket, server_side=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
