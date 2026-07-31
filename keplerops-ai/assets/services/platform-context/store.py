"""Multi-process durable state and reconstruction records."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator


FILE_JOB_BY_ID_SQL = "SELECT * FROM file_jobs WHERE job_id=?"


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def content_digest(value: object) -> str:
    encoded = (
        value if isinstance(value, bytes) else canonical_json(value).encode("utf-8")
    )
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def now() -> str:
    return datetime.now(UTC).isoformat()


class StateStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.path = root / "platform-context.sqlite3"
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=15.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=15000")
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self.connection() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    occurred_at TEXT NOT NULL,
                    event_name TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    status TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    record_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS file_jobs (
                    job_id TEXT PRIMARY KEY,
                    root_id TEXT NOT NULL,
                    relative_path TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    destination_path TEXT,
                    state TEXT NOT NULL CHECK (state IN ('queued','processing','succeeded','failed')),
                    request_json TEXT NOT NULL,
                    result_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS file_jobs_state ON file_jobs(state, created_at);
                CREATE TABLE IF NOT EXISTS workhub_records (
                    request_id TEXT PRIMARY KEY,
                    record_kind TEXT NOT NULL,
                    upstream_id TEXT,
                    request_json TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS identity_records (
                    request_id TEXT PRIMARY KEY,
                    operation TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sync_cursors (
                    consumer TEXT PRIMARY KEY,
                    last_sequence INTEGER NOT NULL CHECK (last_sequence >= 0),
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sync_deliveries (
                    source_sequence INTEGER NOT NULL,
                    destination TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    delivered_at TEXT NOT NULL,
                    PRIMARY KEY (source_sequence, destination)
                );
                CREATE TABLE IF NOT EXISTS worker_heartbeats (
                    worker TEXT PRIMARY KEY,
                    occurred_at TEXT NOT NULL,
                    details_json TEXT NOT NULL
                );
                """
            )

    def ready(self) -> bool:
        with self.connection() as connection:
            return connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"

    def record_event(
        self,
        *,
        event_name: str,
        operation: str,
        status: str,
        request_id: str,
        request: dict[str, Any],
        response: dict[str, Any],
        source: str,
        duration_ms: float,
    ) -> dict[str, Any]:
        occurred_at = now()
        event_id = str(uuid.uuid4())
        record = {
            "schema_version": 1,
            "event_id": event_id,
            "occurred_at": occurred_at,
            "source": source,
            "event_name": event_name,
            "operation": operation,
            "status": status,
            "request_id": request_id,
            "request": request,
            "response": response,
            "request_digest": content_digest(request),
            "response_digest": content_digest(response),
            "duration_ms": round(duration_ms, 3),
        }
        with self.connection() as connection:
            cursor = connection.execute(
                "INSERT INTO events "
                "(event_id, occurred_at, event_name, operation, status, request_id, record_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    event_id,
                    occurred_at,
                    event_name,
                    operation,
                    status,
                    request_id,
                    canonical_json(record),
                ),
            )
            record["sequence"] = int(cursor.lastrowid)
            connection.execute(
                "UPDATE events SET record_json=? WHERE sequence=?",
                (canonical_json(record), cursor.lastrowid),
            )
        return record

    def recent_events(self, limit: int) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT record_json FROM events ORDER BY sequence DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [json.loads(row[0]) for row in reversed(rows)]

    def enqueue_file_job(self, request: dict[str, Any]) -> dict[str, Any]:
        job_id = request["job_id"]
        encoded = canonical_json(request)
        timestamp = now()
        with self.connection() as connection:
            existing = connection.execute(FILE_JOB_BY_ID_SQL, (job_id,)).fetchone()
            if existing is None:
                connection.execute(
                    "INSERT INTO file_jobs "
                    "(job_id, root_id, relative_path, destination, destination_path, state, request_json, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, 'queued', ?, ?, ?)",
                    (
                        job_id,
                        request["root_id"],
                        request["relative_path"],
                        request["destination"],
                        request.get("destination_path"),
                        encoded,
                        timestamp,
                        timestamp,
                    ),
                )
                existing = connection.execute(FILE_JOB_BY_ID_SQL, (job_id,)).fetchone()
            elif existing["request_json"] != encoded:
                raise ValueError("job_id is already bound to a different request")
        return dict(existing)

    def claim_file_job(self) -> dict[str, Any] | None:
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT job_id FROM file_jobs WHERE state='queued' ORDER BY created_at LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            connection.execute(
                "UPDATE file_jobs SET state='processing', updated_at=? "
                "WHERE job_id=? AND state='queued'",
                (now(), row["job_id"]),
            )
            claimed = connection.execute(
                FILE_JOB_BY_ID_SQL, (row["job_id"],)
            ).fetchone()
        return dict(claimed)

    def finish_file_job(self, job_id: str, state: str, result: dict[str, Any]) -> None:
        if state not in {"succeeded", "failed"}:
            raise ValueError("terminal file job state required")
        with self.connection() as connection:
            connection.execute(
                "UPDATE file_jobs SET state=?, result_json=?, updated_at=? WHERE job_id=?",
                (state, canonical_json(result), now(), job_id),
            )

    def file_job(self, job_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(FILE_JOB_BY_ID_SQL, (job_id,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["request"] = json.loads(result.pop("request_json"))
        if result["result_json"] is not None:
            result["result"] = json.loads(result.pop("result_json"))
        else:
            result.pop("result_json")
        return result

    def idempotent_record(self, table: str, request_id: str) -> dict[str, Any] | None:
        if table not in {"workhub_records", "identity_records"}:
            raise ValueError("invalid idempotence table")
        with self.connection() as connection:
            row = connection.execute(
                f"SELECT response_json FROM {table} WHERE request_id=?", (request_id,)
            ).fetchone()
        return None if row is None else json.loads(row[0])

    def save_workhub(
        self,
        request_id: str,
        kind: str,
        upstream_id: str | None,
        request: dict[str, Any],
        response: dict[str, Any],
    ) -> None:
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO workhub_records VALUES (?, ?, ?, ?, ?, ?)",
                (
                    request_id,
                    kind,
                    upstream_id,
                    canonical_json(request),
                    canonical_json(response),
                    now(),
                ),
            )

    def save_identity(
        self,
        request_id: str,
        operation: str,
        subject: str,
        request: dict[str, Any],
        response: dict[str, Any],
    ) -> None:
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO identity_records VALUES (?, ?, ?, ?, ?, ?)",
                (
                    request_id,
                    operation,
                    subject,
                    canonical_json(request),
                    canonical_json(response),
                    now(),
                ),
            )

    def cursor(self, consumer: str) -> int:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT last_sequence FROM sync_cursors WHERE consumer=?", (consumer,)
            ).fetchone()
        return 0 if row is None else int(row[0])

    def advance_cursor(self, consumer: str, sequence: int) -> None:
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO sync_cursors VALUES (?, ?, ?) "
                "ON CONFLICT(consumer) DO UPDATE SET "
                "last_sequence=excluded.last_sequence, updated_at=excluded.updated_at",
                (consumer, sequence, now()),
            )

    def save_delivery(
        self,
        sequence: int,
        destination: str,
        operation: str,
        request: dict[str, Any],
        response: dict[str, Any],
    ) -> None:
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO sync_deliveries VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(source_sequence, destination) DO UPDATE SET "
                "operation=excluded.operation, request_json=excluded.request_json, "
                "response_json=excluded.response_json, delivered_at=excluded.delivered_at",
                (
                    sequence,
                    destination,
                    operation,
                    canonical_json(request),
                    canonical_json(response),
                    now(),
                ),
            )

    def heartbeat(self, worker: str, details: dict[str, Any]) -> None:
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO worker_heartbeats VALUES (?, ?, ?) "
                "ON CONFLICT(worker) DO UPDATE SET "
                "occurred_at=excluded.occurred_at, details_json=excluded.details_json",
                (worker, now(), canonical_json(details)),
            )

    def heartbeat_status(self, worker: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT occurred_at, details_json FROM worker_heartbeats WHERE worker=?",
                (worker,),
            ).fetchone()
        if row is None:
            return None
        return {
            "occurred_at": row["occurred_at"],
            "details": json.loads(row["details_json"]),
        }

    def reset(self) -> None:
        with self.connection() as connection:
            connection.executescript(
                """
                DELETE FROM events;
                DELETE FROM file_jobs;
                DELETE FROM workhub_records;
                DELETE FROM identity_records;
                DELETE FROM sync_cursors;
                DELETE FROM sync_deliveries;
                DELETE FROM worker_heartbeats;
                DELETE FROM sqlite_sequence WHERE name='events';
                """
            )
