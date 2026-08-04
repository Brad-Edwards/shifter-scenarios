from __future__ import annotations

import hashlib
import hmac
import http.server
import json
import os
import pathlib
import secrets
import sqlite3
import time
import urllib.parse


STATE = pathlib.Path(os.getenv("CINDER_TRANSPORT_STATE", "/var/lib/cinder-orion-transport"))
TOKENS = {
    os.getenv("CINDER_API_OPERATOR_TOKEN", ""): ("operator", "openai-api"),
    os.getenv("CINDER_API_WORKER_TOKEN", ""): ("worker", "openai-api"),
    os.getenv("CINDER_WEB_LIBRECHAT_TOKEN", ""): ("operator", "librechat-web"),
    os.getenv("CINDER_WEB_WORKER_TOKEN", ""): ("worker", "librechat-web"),
    os.getenv("CINDER_HOST_OPERATOR_TOKEN", ""): ("operator", "host-bridge"),
    os.getenv("CINDER_HOST_BRIDGE_TOKEN", ""): ("worker", "host-bridge"),
    os.getenv("CINDER_TRANSPORT_AUDIT_TOKEN", ""): ("auditor", "audit"),
}
TOKENS.pop("", None)
WEB_WORKER_SIGNING_KEY = os.getenv("CINDER_WEB_WORKER_TOKEN", "").encode()


def database() -> sqlite3.Connection:
    STATE.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(STATE / "transport.sqlite3", timeout=20)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute(
        """CREATE TABLE IF NOT EXISTS tasks (
        task_id TEXT PRIMARY KEY, attempt_id TEXT NOT NULL, transport TEXT NOT NULL,
        command TEXT NOT NULL, command_sha256 TEXT NOT NULL, nonce TEXT NOT NULL,
        state TEXT NOT NULL, result_json TEXT, operator_message_id TEXT NOT NULL,
        worker_request_id TEXT, result_request_id TEXT, created_at INTEGER NOT NULL,
        completed_at INTEGER)"""
    )
    columns = {row[1] for row in connection.execute("PRAGMA table_info(tasks)")}
    if "worker_registration_id" not in columns:
        connection.execute("ALTER TABLE tasks ADD COLUMN worker_registration_id TEXT")
    if "worker_proof" not in columns:
        connection.execute("ALTER TABLE tasks ADD COLUMN worker_proof TEXT")
    connection.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS tasks_attempt_nonce_unique "
        "ON tasks(attempt_id, nonce)"
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS worker_proofs (
        proof TEXT PRIMARY KEY, registration_id TEXT NOT NULL, transport TEXT NOT NULL,
        nonce TEXT NOT NULL, issued_at INTEGER NOT NULL, task_id TEXT)"""
    )
    connection.commit()
    return connection


def completion(content: object, *, request_id: str | None = None) -> dict[str, object]:
    created = int(time.time())
    completion_id = request_id or f"chatcmpl-{secrets.token_hex(12)}"
    text = content if isinstance(content, str) else json.dumps(content, separators=(",", ":"))
    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": created,
        "model": "orion-worker-relay",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def last_user_message(body: dict[str, object]) -> str:
    messages = body.get("messages")
    if not isinstance(messages, list):
        raise ValueError("messages array required")
    for message in reversed(messages):
        if isinstance(message, dict) and message.get("role") == "user":
            return str(message.get("content") or "")
    raise ValueError("user message required")


def operator_request(connection: sqlite3.Connection, transport: str, body: dict[str, object]) -> dict[str, object]:
    content = last_user_message(body)
    try:
        value = json.loads(content)
    except json.JSONDecodeError:
        value = {"task_id": content.removeprefix("status ").strip()} if content.startswith("status ") else {}
    if not isinstance(value, dict):
        raise ValueError("task object required")
    if value.get("task_id") and not value.get("command"):
        row = connection.execute(
            "SELECT * FROM tasks WHERE task_id = ? AND transport = ?",
            (str(value["task_id"]), transport),
        ).fetchone()
        if row is None:
            raise LookupError("task not found")
        if row["state"] != "completed":
            return completion({"task_id": row["task_id"], "status": row["state"]})
        result = json.loads(row["result_json"])
        return completion(
            {
                "task_id": row["task_id"],
                "status": "completed",
                "nonce": row["nonce"],
                "result": result,
            },
            request_id=row["result_request_id"],
        )
    command = str(value.get("command") or "")
    attempt_id = str(value.get("attempt_id") or "")
    nonce = str(value.get("nonce") or "")
    if not command or not attempt_id or len(nonce) < 10:
        raise ValueError("command, server-scoped attempt_id, and fresh nonce are required")
    task_id = f"task-{secrets.token_hex(10)}"
    message_id = str(body.get("conversation_id") or body.get("user") or f"message-{secrets.token_hex(8)}")
    connection.execute(
        "INSERT INTO tasks (task_id,attempt_id,transport,command,command_sha256,nonce,state,"
        "result_json,operator_message_id,worker_request_id,result_request_id,created_at,completed_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            task_id,
            attempt_id,
            transport,
            command,
            hashlib.sha256(command.encode()).hexdigest(),
            nonce,
            "queued",
            None,
            message_id,
            None,
            None,
            int(time.time()),
            None,
        ),
    )
    connection.commit()
    return completion({"task_id": task_id, "status": "queued", "nonce": nonce})


def worker_request(
    connection: sqlite3.Connection,
    transport: str,
    body: dict[str, object],
    worker_identity: tuple[str, str] | None = None,
) -> dict[str, object]:
    content = last_user_message(body)
    if content != "poll":
        result = json.loads(content)
        if not isinstance(result, dict) or not result.get("task_id"):
            raise ValueError("worker result must name its task")
        row = connection.execute(
            "SELECT * FROM tasks WHERE task_id=? AND transport=? AND state='running'",
            (str(result["task_id"]), transport),
        ).fetchone()
        if row is None:
            raise ValueError("result does not match a running task")
        claimed_registration = str(row["worker_registration_id"] or "")
        claimed_proof = str(row["worker_proof"] or "")
        supplied_registration = str(result.get("worker_registration_id") or "")
        supplied_proof = str(result.get("worker_proof") or "")
        if claimed_registration or claimed_proof:
            proof = connection.execute(
                "SELECT * FROM worker_proofs WHERE proof=? AND registration_id=? "
                "AND transport=? AND task_id=?",
                (claimed_proof, claimed_registration, transport, row["task_id"]),
            ).fetchone()
            if (
                proof is None
                or worker_identity is None
                or not hmac.compare_digest(worker_identity[0], claimed_registration)
                or not hmac.compare_digest(supplied_registration, claimed_registration)
                or not hmac.compare_digest(supplied_proof, claimed_proof)
            ):
                raise ValueError("result does not match the worker proof recorded at claim")
        elif supplied_registration or supplied_proof:
            raise ValueError("unclaimed worker identity cannot complete this task")
        request_id = f"result-{secrets.token_hex(10)}"
        changed = connection.execute(
            "UPDATE tasks SET state='completed', result_json=?, result_request_id=?, completed_at=? "
            "WHERE task_id=? AND transport=? AND state='running' "
            "AND COALESCE(worker_registration_id,'')=? AND COALESCE(worker_proof,'')=?",
            (
                json.dumps(result, separators=(",", ":")),
                request_id,
                int(time.time()),
                str(result["task_id"]),
                transport,
                claimed_registration,
                claimed_proof,
            ),
        ).rowcount
        if changed != 1:
            raise ValueError("result does not match a running task")
        connection.commit()
    row = connection.execute(
        "SELECT * FROM tasks WHERE transport=? AND state='queued' ORDER BY created_at, task_id LIMIT 1",
        (transport,),
    ).fetchone()
    if row is None:
        return completion({"status": "idle"})
    request_id = f"worker-{secrets.token_hex(10)}"
    connection.execute(
        "UPDATE tasks SET state='running', worker_request_id=?, worker_registration_id=?, worker_proof=? "
        "WHERE task_id=? AND state='queued'",
        (
            request_id,
            worker_identity[0] if worker_identity else None,
            worker_identity[1] if worker_identity else None,
            row["task_id"],
        ),
    )
    if worker_identity:
        connection.execute(
            "UPDATE worker_proofs SET task_id=? WHERE proof=?",
            (row["task_id"], worker_identity[1]),
        )
    connection.commit()
    task = {"task_id": row["task_id"], "command": row["command"], "nonce": row["nonce"]}
    if worker_identity:
        task.update(
            {
                "worker_registration_id": worker_identity[0],
                "worker_proof": worker_identity[1],
            }
        )
    return completion(task, request_id=request_id)


def verified_web_worker(
    connection: sqlite3.Connection, transport: str, body: dict[str, object]
) -> tuple[dict[str, object], tuple[str, str]] | None:
    if transport != "librechat-web" or not WEB_WORKER_SIGNING_KEY:
        return None
    content = last_user_message(body)
    try:
        envelope = json.loads(content)
    except json.JSONDecodeError:
        return None
    if not isinstance(envelope, dict) or envelope.get("kind") != "orion-worker-message/v1":
        return None
    signature = str(envelope.pop("signature", ""))
    canonical = json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode()
    expected = hmac.new(WEB_WORKER_SIGNING_KEY, canonical, hashlib.sha256).hexdigest()
    issued_at = int(envelope.get("issued_at") or 0)
    nonce = str(envelope.get("nonce") or "")
    registration_id = str(envelope.get("registration_id") or "")
    if (
        not hmac.compare_digest(signature, expected)
        or abs(int(time.time()) - issued_at) > 30
        or len(nonce) < 20
        or not registration_id.startswith("registration-")
    ):
        raise ValueError("fresh server-issued web-worker proof required")
    connection.execute(
        "INSERT INTO worker_proofs VALUES (?,?,?,?,?,NULL)",
        (signature, registration_id, transport, nonce, issued_at),
    )
    payload = envelope.get("payload")
    adjusted = dict(body)
    adjusted["messages"] = [{"role": "user", "content": payload if isinstance(payload, str) else json.dumps(payload, separators=(",", ":"))}]
    return adjusted, (registration_id, signature)


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "CinderOpenAITransport/1.0"

    def _json(self, status: int, value: object) -> None:
        payload = json.dumps(value, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _sse(self, value: object) -> None:
        choices = value.get("choices") if isinstance(value, dict) else None
        message = choices[0].get("message", {}) if isinstance(choices, list) and choices else {}
        content = str(message.get("content", "")) if isinstance(message, dict) else ""
        cid = str(value.get("id") if isinstance(value, dict) else "") or f"chatcmpl-{secrets.token_hex(12)}"
        created = int(value.get("created") if isinstance(value, dict) and value.get("created") else time.time())
        model = str(value.get("model") if isinstance(value, dict) else "") or "orion-worker-relay"
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        def emit(delta: dict[str, object], finish: object) -> None:
            chunk = {
                "id": cid,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
            }
            self.wfile.write(("data: " + json.dumps(chunk, separators=(",", ":")) + "\n\n").encode())

        emit({"role": "assistant", "content": content}, None)
        emit({}, "stop")
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

    def _principal(self) -> tuple[str, str] | None:
        supplied = self.headers.get("Authorization", "").removeprefix("Bearer ")
        return next((value for token, value in TOKENS.items() if secrets.compare_digest(token, supplied)), None)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._json(200, {"status": "ready"})
            return
        principal = self._principal()
        if not principal or principal[0] != "auditor" or not self.path.startswith("/internal/audit/"):
            self._json(404, {"error": "not found"})
            return
        attempt_id = pathlib.PurePosixPath(urllib.parse.urlparse(self.path).path).name
        with database() as connection:
            rows = [dict(row) for row in connection.execute("SELECT * FROM tasks WHERE attempt_id=? ORDER BY created_at", (attempt_id,))]
        for row in rows:
            row["result"] = json.loads(row.pop("result_json")) if row.get("result_json") else None
            row.pop("command", None)
        self._json(200, {"attempt_id": attempt_id, "tasks": rows})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/chat/completions":
            self._json(404, {"error": "not found"})
            return
        principal = self._principal()
        if not principal or principal[0] not in {"operator", "worker"}:
            self._json(401, {"error": "API authentication required"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(body, dict):
                raise ValueError("JSON object required")
            stream = bool(body.get("stream"))
            with database() as connection:
                worker = verified_web_worker(connection, principal[1], body) if principal[0] == "operator" else None
                if worker:
                    result = worker_request(connection, principal[1], worker[0], worker[1])
                elif principal[0] == "operator":
                    result = operator_request(connection, principal[1], body)
                else:
                    result = worker_request(connection, principal[1], body)
            # LibreChat's OpenAI-compatible custom endpoint (kep-m05-q) consumes an
            # SSE stream; direct pollers (kep-m05-o/p) omit stream and get JSON.
            if stream:
                self._sse(result)
            else:
                self._json(200, result)
        except LookupError as exc:
            self._json(404, {"error": str(exc)})
        except (ValueError, json.JSONDecodeError, sqlite3.Error) as exc:
            self._json(422, {"error": str(exc)})

    def log_message(self, format: str, *args: object) -> None:
        return


if __name__ == "__main__":
    http.server.ThreadingHTTPServer(("0.0.0.0", 8090), Handler).serve_forever()
