"""Durable idempotency, lifecycle, and full-content telemetry state."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class ConflictError(RuntimeError):
    pass


class StateStore:
    def __init__(self, root: Path, tenant_id: str) -> None:
        if len(tenant_id) != 12 or any(character not in "0123456789abcdef" for character in tenant_id):
            raise ValueError("tenant_id must be a 12-character lowercase hexadecimal digest")
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.root = root
        self.tenant_id = tenant_id
        self.path = root / "platform-deployment.sqlite3"
        self._lock = threading.RLock()
        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS requests (
                    tenant_id TEXT NOT NULL, request_id TEXT NOT NULL, kind TEXT NOT NULL,
                    request_json TEXT NOT NULL, request_digest TEXT NOT NULL,
                    response_json TEXT, status TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, request_id)
                );
                CREATE TABLE IF NOT EXISTS reputation_events (
                    tenant_id TEXT NOT NULL, event_id TEXT NOT NULL, repository TEXT NOT NULL,
                    digest TEXT NOT NULL, event_json TEXT NOT NULL,
                    signature TEXT NOT NULL, public_key_fingerprint TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, event_id)
                );
                CREATE TABLE IF NOT EXISTS workspaces (
                    tenant_id TEXT NOT NULL, workspace_id TEXT NOT NULL, request_id TEXT NOT NULL,
                    job_name TEXT NOT NULL UNIQUE, state TEXT NOT NULL,
                    request_json TEXT NOT NULL, response_json TEXT,
                    expires_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, workspace_id),
                    UNIQUE (tenant_id, request_id)
                );
                CREATE TABLE IF NOT EXISTS telemetry (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL, event_name TEXT NOT NULL, operation TEXT NOT NULL,
                    status TEXT NOT NULL, request_id TEXT,
                    request_json TEXT NOT NULL, response_json TEXT NOT NULL,
                    duration_ms REAL NOT NULL, created_at TEXT NOT NULL
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30.0)
        connection.row_factory = sqlite3.Row
        return connection

    def begin_request(self, request_id: str, kind: str, request: dict[str, Any]) -> dict[str, Any] | None:
        serialized = canonical(request)
        digest = hashlib.sha256(serialized.encode()).hexdigest()
        timestamp = now()
        with self._lock, self._connect() as connection:
            existing = connection.execute("SELECT * FROM requests WHERE tenant_id = ? AND request_id = ?", (self.tenant_id, request_id)).fetchone()
            if existing is not None:
                if existing["kind"] != kind or existing["request_digest"] != digest:
                    raise ConflictError("request_id was already used with different content")
                return json.loads(existing["response_json"]) if existing["response_json"] else None
            connection.execute(
                "INSERT INTO requests VALUES (?, ?, ?, ?, ?, NULL, 'accepted', ?, ?)",
                (self.tenant_id, request_id, kind, serialized, digest, timestamp, timestamp),
            )
        return None

    def finish_request(self, request_id: str, response: dict[str, Any], status: str = "succeeded") -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                "UPDATE requests SET response_json = ?, status = ?, updated_at = ? WHERE tenant_id = ? AND request_id = ?",
                (canonical(response), status, now(), self.tenant_id, request_id),
            )

    def add_reputation(self, event: dict[str, Any], signature: str, fingerprint: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO reputation_events VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (self.tenant_id, event["event_id"], event["repository"], event["digest"], canonical(event), signature, fingerprint, now()),
            )

    def reputation_event(self, event_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT event_json, signature, public_key_fingerprint FROM reputation_events WHERE tenant_id = ? AND event_id = ?",
                (self.tenant_id, event_id),
            ).fetchone()
        if row is None:
            return None
        return {
            "event": json.loads(row["event_json"]),
            "signature": row["signature"],
            "public_key_fingerprint": row["public_key_fingerprint"],
        }

    def reputation(self, repository: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT event_json, signature, public_key_fingerprint FROM reputation_events WHERE tenant_id = ? AND repository = ? ORDER BY event_id",
                (self.tenant_id, repository),
            ).fetchall()
        return [
            {"event": json.loads(row["event_json"]), "signature": row["signature"], "public_key_fingerprint": row["public_key_fingerprint"]}
            for row in rows
        ]

    def put_workspace(self, value: dict[str, Any]) -> None:
        timestamp = now()
        with self._lock, self._connect() as connection:
            connection.execute(
                """INSERT INTO workspaces VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(tenant_id, workspace_id) DO UPDATE SET state=excluded.state,
                   response_json=excluded.response_json, updated_at=excluded.updated_at""",
                (self.tenant_id, value["workspace_id"], value["request_id"], value["job_name"], value["state"], canonical(value["request"]), canonical(value.get("response")) if value.get("response") is not None else None, value["expires_at"], timestamp),
            )

    def workspaces(self, active_only: bool = False) -> list[dict[str, Any]]:
        query = "SELECT * FROM workspaces WHERE tenant_id = ?"
        if active_only:
            query += " AND state NOT IN ('deleted', 'failed')"
        query += " ORDER BY workspace_id"
        with self._connect() as connection:
            rows = connection.execute(query, (self.tenant_id,)).fetchall()
        return [self._workspace(row) for row in rows]

    def workspace(self, workspace_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM workspaces WHERE tenant_id = ? AND workspace_id = ?", (self.tenant_id, workspace_id)).fetchone()
        return self._workspace(row) if row else None

    @staticmethod
    def _workspace(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "tenant_id": row["tenant_id"],
            "workspace_id": row["workspace_id"], "request_id": row["request_id"],
            "job_name": row["job_name"], "state": row["state"],
            "request": json.loads(row["request_json"]),
            "response": json.loads(row["response_json"]) if row["response_json"] else None,
            "expires_at": row["expires_at"], "updated_at": row["updated_at"],
        }

    def record_event(self, event_name: str, operation: str, status: str, request_id: str | None, request: Any, response: Any, duration_ms: float) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO telemetry(tenant_id, event_name, operation, status, request_id, request_json, response_json, duration_ms, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (self.tenant_id, event_name, operation, status, request_id, canonical(request), canonical(response), duration_ms, now()),
            )

    def recent_events(self, limit: int) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM telemetry WHERE tenant_id = ? ORDER BY sequence DESC LIMIT ?", (self.tenant_id, limit)).fetchall()
        return [{
            "sequence": row["sequence"], "tenant_id": row["tenant_id"], "event_name": row["event_name"], "operation": row["operation"],
            "status": row["status"], "request_id": row["request_id"],
            "request": json.loads(row["request_json"]), "response": json.loads(row["response_json"]),
            "duration_ms": row["duration_ms"], "created_at": row["created_at"],
        } for row in rows]

    def reset_local(self) -> None:
        with self._lock, self._connect() as connection:
            active = connection.execute("SELECT COUNT(*) FROM workspaces WHERE tenant_id = ? AND state NOT IN ('deleted', 'failed')", (self.tenant_id,)).fetchone()[0]
            if active:
                raise ConflictError("active Cloud Run jobs must be deleted before local reset")
            for table in ("requests", "reputation_events", "workspaces", "telemetry"):
                connection.execute(f"DELETE FROM {table} WHERE tenant_id = ?", (self.tenant_id,))
