#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import hmac
import html
import grp
import json
import os
import pathlib
import posixpath
import secrets
import ssl
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


ROOT = pathlib.Path("/var/lib/arwc-approval")
STATE = ROOT / "state" / "maintenance-review.json"
AUDIT = ROOT / "audit" / "events.jsonl"
SIGNING_KEY = ROOT / "auth" / "approval-signing-key.pem"
APPROVAL_EVIDENCE = ROOT / "evidence" / "approval.json"
CONTRACTOR_SESSION = pathlib.Path("/run/arwc-field-session/contractor-session.json")
READ_EVIDENCE = pathlib.Path("/run/arwc-read-evidence/W09-read.json")
CHROME = "/opt/chrome-headless-shell/chrome-headless-shell"

ASSOCIATION = {
    "record_id": "CACHE-DRW-OG2-R8",
    "revision": 8,
    "drawing": "DRW-OG2-R8",
    "drawing_revision": "R8",
    "reviewer_queue": "REV-CRR-4417",
    "upstream_host": "drawings.arwc.test",
    "cache_key_path": "/viewer/drawings/DRW-OG2-R8",
    "cache_method": "GET",
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


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def initialize() -> None:
    if not STATE.exists():
        atomic_json(STATE, {
            "association_observed": False,
            "cached_response": None,
            "review_capability": None,
            "approval_observed": False,
        })
    if not SIGNING_KEY.exists():
        key = Ed25519PrivateKey.generate()
        SIGNING_KEY.write_bytes(key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ))
        os.chmod(SIGNING_KEY, 0o600)
    AUDIT.touch(mode=0o600, exist_ok=True)
    os.chmod(AUDIT, 0o600)


def approval_record() -> dict[str, object]:
    payload = {
        "record_id": "APR-CRR-4417-R6",
        "revision": 6,
        "maintenance": "WO-CRR-4417",
        "inspection": "INSP-CRR-2026-09-18",
        "asset": "AST-CRR-017",
        "drawing": "DRW-OG2-R8",
        "drawing_revision": "R8",
        "status": "signed",
    }
    key = serialization.load_pem_private_key(SIGNING_KEY.read_bytes(), password=None)
    assert isinstance(key, Ed25519PrivateKey)
    signature = key.sign(canonical(payload))
    public = key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw,
    )
    return {
        **payload,
        "signature_algorithm": "Ed25519",
        "signature": base64.b64encode(signature).decode(),
        "signing_public_key": base64.b64encode(public).decode(),
    }


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
        "result_digest": hashlib.sha256(canonical(result)).hexdigest(),
    }
    with AUDIT.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return correlation


def load_json(path: pathlib.Path) -> dict[str, object] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def token_matches(token: str, evidence: dict[str, object] | None) -> bool:
    return (evidence is not None and isinstance(evidence.get("token_sha256"), str) and
            hmac.compare_digest(hashlib.sha256(token.encode()).hexdigest(), str(evidence["token_sha256"])))


def normalized_cache_key(method: str, path: str) -> str:
    normalized = posixpath.normpath("/" + path.lstrip("/"))
    return f"{method.upper()}:{normalized}"


def run_reviewer(cached: dict[str, object], signed_message: dict[str, object]) -> bool:
    message = json.dumps(signed_message, sort_keys=True, separators=(",", ":"))
    participant_body = html.escape(str(cached["body"]), quote=True)
    inner = html.escape(
        "<!doctype html><script>parent.parent.postMessage(" + message + ", '*')</script>",
        quote=True,
    )
    drawing = html.escape(
        f"<!doctype html><main>{participant_body}</main><iframe id='nested' srcdoc=\"{inner}\"></iframe>",
        quote=True,
    )
    expected_signature = json.dumps(signed_message["signature"])
    document = f"""<!doctype html><meta charset='utf-8'>
<output id='result'>pending</output>
<iframe id='drawing' srcdoc="{drawing}"></iframe>
<script>
const drawing = document.getElementById('drawing');
addEventListener('message', event => {{
  const value = event.data;
  if (!value || value.audience !== 'maintenance-review' || value.signature !== {expected_signature}) return;
  if (value.queue !== 'REV-CRR-4417' || value.drawing !== 'DRW-OG2-R8' || value.revision !== 'R8') return;
  // The deployed reviewer omits the intended event.source === drawing.contentWindow check.
  document.getElementById('result').textContent = event.source === drawing.contentWindow ? 'accepted-direct' : 'accepted-source-mismatch';
}});
</script>"""
    with tempfile.TemporaryDirectory(prefix="arwc-review-") as temporary:
        path = pathlib.Path(temporary) / "reviewer.html"
        path.write_text(document, encoding="utf-8")
        completed = subprocess.run(
            [CHROME, "--headless", "--no-sandbox", "--disable-gpu", "--disable-background-networking",
             "--disable-component-update", "--disable-sync", "--metrics-recording-only", "--no-first-run",
             f"--user-data-dir={temporary}/profile", "--virtual-time-budget=3000", "--dump-dom",
             path.as_uri()],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20, check=False,
        )
    return completed.returncode == 0 and "accepted-source-mismatch" in completed.stdout


class Handler(BaseHTTPRequestHandler):
    server_version = "ARWC-Maintenance-Review/1.0"
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
            self.send_json(409, {"error": "invalid request"})
            return None

    def authorized(self) -> str | None:
        supplied = self.headers.get("Authorization", "")
        if self.headers.get("X-ARWC-Tenant", "arwc") != "arwc" or not supplied.startswith("Bearer "):
            self.send_json(403, {"error": "maintenance review session required"})
            return None
        token = supplied[7:]
        if token_matches(token, load_json(CONTRACTOR_SESSION)):
            return "veybridge.tech.204"
        if token_matches(token, load_json(READ_EVIDENCE)):
            return "integration-reader-principal"
        self.send_json(403, {"error": "maintenance review session required"})
        return None

    def accepted(self, action: str, principal: str, record: dict[str, object], status: int,
                 extra: dict[str, object] | None = None) -> None:
        response: dict[str, object] = {"audit_id": append_audit(action, principal, record), "record": record}
        if extra:
            response.update(extra)
        self.send_json(status, response)

    def do_GET(self) -> None:
        if urlsplit(self.path).path != "/api/which-drawing-did-the-cache-keep":
            self.send_json(404, {"error": "record not found"})
            return
        principal = self.authorized()
        if principal is None:
            return
        state = load_json(STATE)
        assert state is not None
        state["association_observed"] = True
        atomic_json(STATE, state)
        self.accepted("which-drawing-did-the-cache-keep", principal, ASSOCIATION, 200)

    def do_POST(self) -> None:
        principal = self.authorized()
        if principal is None:
            return
        request = self.body()
        if request is None:
            return
        path = urlsplit(self.path).path
        state = load_json(STATE)
        assert state is not None
        if path == "/api/a-drawing-of-our-choosing":
            if not state["association_observed"]:
                self.send_json(403, {"error": "cache association must be inspected"})
                return
            response = request.get("controlled_response")
            cache_path = request.get("path")
            if (self.headers.get("X-Preview-Origin") != "https://preview-cinder.arwc.test" or
                    not isinstance(cache_path, str) or
                    normalized_cache_key("GET", cache_path) != "GET:/viewer/drawings/DRW-OG2-R8" or
                    not isinstance(response, dict)):
                self.send_json(409, {"error": "preview origin or cache path does not match"})
                return
            body = response.get("body")
            if (response.get("drawing_id") != "DRW-OG2-R8" or response.get("revision") != "R8" or
                    response.get("content_type") != "text/html" or not isinstance(body, str) or not body or
                    "\r" in body or "\n" in body):
                self.send_json(409, {"error": "controlled response is not the expected CRLF-free drawing"})
                return
            record = {
                "record_id": "CACHE-DRW-OG2-R8-CONTROLLED",
                "revision": 1,
                "cache_key": "GET:/viewer/drawings/DRW-OG2-R8",
                "drawing": "DRW-OG2-R8",
                "drawing_revision": "R8",
                "source_origin": "https://preview-cinder.arwc.test",
                "content_sha256": hashlib.sha256(body.encode()).hexdigest(),
            }
            state["cached_response"] = {**record, "body": body}
            atomic_json(STATE, state)
            self.accepted("a-drawing-of-our-choosing", principal, record, 201)
            return
        if path == "/api/the-reviewer-trusts-the-drawing":
            cached = state.get("cached_response")
            if (not isinstance(cached, dict) or
                    request.get("cache_key") != "GET:/viewer/drawings/DRW-OG2-R8" or
                    request.get("reviewer_queue") != "REV-CRR-4417"):
                self.send_json(403, {"error": "controlled cached drawing required"})
                return
            nonce = secrets.token_urlsafe(24)
            unsigned = {
                "audience": "maintenance-review", "queue": "REV-CRR-4417",
                "drawing": "DRW-OG2-R8", "revision": "R8", "nonce": nonce,
            }
            review_key = hashlib.sha256(SIGNING_KEY.read_bytes()).digest()
            message = {**unsigned, "signature": hmac.new(review_key, canonical(unsigned), hashlib.sha256).hexdigest()}
            if not run_reviewer(cached, message):
                self.send_json(409, {"error": "reviewer browser did not accept the drawing submission"})
                return
            token = secrets.token_urlsafe(40)
            capability = {
                "record_id": "CAP-REVIEW-CRR-4417",
                "revision": 1,
                "audience": "maintenance-approval",
                "subject": "DRW-OG2-R8",
                "scope": ["review-submit"],
                "reviewer_queue": "REV-CRR-4417",
                "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
                "browser": "Chromium 128",
                "source_check": "omitted",
            }
            state["review_capability"] = capability
            atomic_json(STATE, state)
            public = {key: value for key, value in capability.items() if key != "token_sha256"}
            self.accepted("the-reviewer-trusts-the-drawing", principal, public, 201,
                          {"review_capability": token})
            return
        if path == "/api/approval-beyond-the-token":
            capability = state.get("review_capability")
            token = request.get("review_capability")
            if (not isinstance(capability, dict) or not isinstance(token, str) or
                    not hmac.compare_digest(hashlib.sha256(token.encode()).hexdigest(),
                                            str(capability.get("token_sha256", ""))) or
                    capability.get("audience") != "maintenance-approval"):
                self.send_json(403, {"error": "maintenance approval capability required"})
                return
            if (request.get("approval_id") != "APR-CRR-4417-R6" or
                    request.get("inspection") != "INSP-CRR-2026-09-18"):
                self.send_json(409, {"error": "approval or inspection binding does not match"})
                return
            # The deployed mapping checks the audience but omits capability subject-to-inspection comparison.
            approval = approval_record()
            state["approval_observed"] = True
            atomic_json(STATE, state)
            atomic_json(APPROVAL_EVIDENCE, approval)
            os.chown(APPROVAL_EVIDENCE, -1, grp.getgrnam("arwc-approval-evidence").gr_gid)
            os.chmod(APPROVAL_EVIDENCE, 0o640)
            self.accepted("approval-beyond-the-token", principal, approval, 201)
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
