from __future__ import annotations

import base64
import hashlib
import hmac
import http.server
import json
import os
import secrets
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from bson import ObjectId
from pymongo import MongoClient


UPSTREAM = os.getenv("ORION_UPSTREAM_URL", "http://192.168.78.30:30081/v1")
GATEWAY_KEY = os.getenv("ORION_LIBRECHAT_GATEWAY_KEY", "")
SESSION_KEY = os.getenv("ORION_SESSION_SIGNING_KEY", "").encode()
SESSION_AUDIENCE = os.getenv("ORION_SESSION_AUDIENCE", "orion-agent")
SESSION_TTL = min(max(int(os.getenv("ORION_SESSION_ASSERTION_TTL", "120")), 30), 300)
AUDIT_PATH = Path(os.getenv("ORION_SESSION_AUDIT", "/var/lib/orion-session-gateway/assertions.jsonl"))
MONGO = MongoClient(os.getenv("MONGO_URI", "mongodb://10.61.50.31:27017/LibreChat"))["LibreChat"]
ACTORS = {
    "partner-reviewer": "partner.reviewer",
    "partner.reviewer": "partner.reviewer",
    "cinder.operator": "partner.reviewer",
    "support.analyst": "support.analyst",
    "release.control": "release.control",
}
AUDIT_LOCK = threading.Lock()


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def conversation_id(body: dict[str, Any]) -> str:
    metadata = body.get("metadata") if isinstance(body.get("metadata"), dict) else {}
    value = str(body.get("conversation_id") or metadata.get("conversation_id") or "").strip()
    if not value or len(value) > 128:
        raise ValueError("a LibreChat conversation is required")
    return value


def librechat_owner(identifier: str, asserted_user_id: str) -> dict[str, Any] | None:
    if not asserted_user_id:
        return None
    lookup_id: object = (
        ObjectId(asserted_user_id) if ObjectId.is_valid(asserted_user_id) else asserted_user_id
    )
    user = MONGO.users.find_one({"_id": lookup_id})
    if not user or not secrets.compare_digest(str(user.get("_id")), asserted_user_id):
        return None
    conversation = MONGO.conversations.find_one({"conversationId": identifier})
    if conversation:
        owner = conversation.get("user") or conversation.get("userId")
        if not owner or not secrets.compare_digest(str(owner), asserted_user_id):
            return None
    return user


def actor_for_conversation(identifier: str, asserted_user_id: str) -> tuple[str, str] | None:
    user = librechat_owner(identifier, asserted_user_id)
    if not user:
        return None
    login = str(user.get("username") or user.get("email") or "").split("@", 1)[0]
    actor = ACTORS.get(login)
    return (actor, login) if actor else None


def issue_assertion(actor: str, login: str, identifier: str, request_sha256: str) -> tuple[str, dict[str, Any]]:
    if not SESSION_KEY:
        raise RuntimeError("session assertion signing is unavailable")
    now = int(time.time())
    payload = {
        "actor": actor,
        "provider": "librechat",
        "login": login,
        "conversation_id": identifier,
        "audience": SESSION_AUDIENCE,
        "request_sha256": request_sha256,
        "issued_at": now,
        "expires_at": now + SESSION_TTL,
        "nonce": secrets.token_hex(16),
    }
    encoded = base64.urlsafe_b64encode(canonical(payload)).decode().rstrip("=")
    signature = hmac.new(SESSION_KEY, canonical(payload), hashlib.sha256).hexdigest()
    return f"orion-session.{encoded}.{signature}", payload


def record_assertion(payload: dict[str, Any], response_status: int) -> None:
    record = {
        "schema": "keplerops.orion.librechat-assertion/v1",
        **payload,
        "response_status": response_status,
        "assertion_sha256": hashlib.sha256(canonical(payload)).hexdigest(),
        "recorded_at": int(time.time()),
    }
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_LOCK, AUDIT_PATH.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")


class Handler(http.server.BaseHTTPRequestHandler):
    def reply(self, status: int, body: bytes, content_type: str = "application/json") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        self.reply(200, b'{"status":"ready"}') if self.path == "/health" else self.reply(404, b'{"error":"not found"}')

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/chat/completions":
            self.reply(404, b'{"error":"not found"}')
            return
        supplied = self.headers.get("Authorization", "").removeprefix("Bearer ")
        if not GATEWAY_KEY or not secrets.compare_digest(supplied, GATEWAY_KEY):
            self.reply(401, b'{"error":"LibreChat gateway authentication required"}')
            return
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")
            if not isinstance(body, dict):
                raise ValueError("request body must be an object")
            identifier = conversation_id(body)
            identity = actor_for_conversation(
                identifier, str(self.headers.get("X-LibreChat-User-ID") or "").strip()
            )
            if not identity:
                self.reply(403, b'{"error":"conversation owner has no Orion identity"}')
                return
            actor, login = identity
            # LibreChat owns the conversation record. A body user field is never
            # identity evidence and cannot change the resolved actor.
            body["user"] = actor
            body["conversation_id"] = identifier
            metadata = body.get("metadata") if isinstance(body.get("metadata"), dict) else {}
            body["metadata"] = {**metadata, "conversation_id": identifier}
            request_sha256 = hashlib.sha256(canonical(body)).hexdigest()
            assertion, assertion_payload = issue_assertion(actor, login, identifier, request_sha256)
        except (ValueError, json.JSONDecodeError, RuntimeError) as exc:
            self.reply(422, json.dumps({"error": str(exc)}).encode())
            return
        request = urllib.request.Request(
            UPSTREAM.rstrip("/") + "/chat/completions",
            data=canonical(body),
            headers={
                "Authorization": f"Bearer {assertion}",
                "Content-Type": "application/json",
                "X-Request-ID": f"librechat-{assertion_payload['nonce']}",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=150) as response:
                response_body = response.read()
                record_assertion(assertion_payload, response.status)
                self.reply(response.status, response_body, response.headers.get_content_type())
        except urllib.error.HTTPError as exc:
            record_assertion(assertion_payload, exc.code)
            self.reply(exc.code, exc.read())
        except urllib.error.URLError:
            record_assertion(assertion_payload, 503)
            self.reply(503, b'{"error":"Orion assistant is unavailable"}')

    def log_message(self, format: str, *args: object) -> None:
        return


if __name__ == "__main__":
    http.server.ThreadingHTTPServer(("0.0.0.0", 8089), Handler).serve_forever()
