"""Durable state and full-content events for disposable serialization loaders."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator


SCHEMA_VERSION = "1"
EVENT_SCHEMA_VERSION = "1"
SEED_TIMESTAMP = "2026-01-01T00:00:00+00:00"


def now() -> str:
    return datetime.now(UTC).isoformat()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest_bytes(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


class IsolationStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.artifact_root = self.root / "artifacts"
        self.artifact_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.path = self.root / "isolation.sqlite3"
        self._lock = threading.RLock()
        self._migrate()

    def _connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock, self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
            except Exception:
                connection.rollback()
                raise
            else:
                connection.commit()

    @contextmanager
    def read(self) -> Iterator[sqlite3.Connection]:
        with self._lock, self._connection() as connection:
            yield connection

    def _migrate(self) -> None:
        initialized = False
        with self.transaction() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS artifacts (
                    artifact_id TEXT PRIMARY KEY,
                    media_type TEXT NOT NULL CHECK (media_type = 'application/python-pickle'),
                    byte_count INTEGER NOT NULL CHECK (byte_count BETWEEN 1 AND 1048576),
                    digest TEXT NOT NULL,
                    storage_name TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS loader_jobs (
                    job_id TEXT PRIMARY KEY,
                    artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
                    container_id TEXT NOT NULL UNIQUE,
                    image_ref TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (state IN ('created', 'running', 'exited', 'timed_out', 'removed', 'unknown')),
                    command_json TEXT NOT NULL,
                    exit_code INTEGER,
                    output_text TEXT,
                    output_byte_count INTEGER NOT NULL DEFAULT 0 CHECK (output_byte_count >= 0),
                    output_complete INTEGER NOT NULL DEFAULT 1 CHECK (output_complete IN (0, 1)),
                    timed_out INTEGER NOT NULL DEFAULT 0 CHECK (timed_out IN (0, 1)),
                    restart_count INTEGER NOT NULL DEFAULT 0 CHECK (restart_count >= 0),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS structured_events (
                    event_id TEXT PRIMARY KEY,
                    schema_version TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    correlation_id TEXT,
                    payload_json TEXT NOT NULL,
                    occurred_at TEXT NOT NULL
                );
                """
            )
            connection.execute(
                "INSERT INTO metadata(key, value) VALUES ('schema_version', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (SCHEMA_VERSION,),
            )
            initialized = (
                connection.execute(
                    "SELECT 1 FROM metadata WHERE key='initialized'"
                ).fetchone()
                is not None
            )
        if not initialized:
            self.reset()
            with self.transaction() as connection:
                connection.execute(
                    "INSERT INTO metadata(key, value) VALUES ('initialized', 'true')"
                )

    def reset(self) -> None:
        for artifact in self.artifact_root.glob("*.pkl"):
            artifact.unlink(missing_ok=True)
        with self.transaction() as connection:
            connection.executescript(
                """
                DELETE FROM structured_events;
                DELETE FROM loader_jobs;
                DELETE FROM artifacts;
                """
            )
            connection.execute(
                "INSERT INTO metadata(key, value) VALUES ('last_reset_at', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (SEED_TIMESTAMP,),
            )
            connection.execute(
                "INSERT INTO structured_events "
                "(event_id, schema_version, event_type, source_id, correlation_id, "
                "payload_json, occurred_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    "isolation-seed-0001",
                    EVENT_SCHEMA_VERSION,
                    "isolation.seeded",
                    "loader-control",
                    None,
                    canonical_json({"artifact_count": 0, "job_count": 0}),
                    SEED_TIMESTAMP,
                ),
            )

    def ready(self) -> bool:
        with self.read() as connection:
            schema = connection.execute(
                "SELECT value FROM metadata WHERE key='schema_version'"
            ).fetchone()
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
        return bool(
            schema
            and schema["value"] == SCHEMA_VERSION
            and integrity
            and integrity[0] == "ok"
        )

    def event(
        self,
        event_type: str,
        source_id: str,
        payload: dict[str, Any],
        correlation_id: str | None = None,
    ) -> str:
        event_id = f"isolation-event-{uuid.uuid4()}"
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO structured_events "
                "(event_id, schema_version, event_type, source_id, correlation_id, "
                "payload_json, occurred_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    event_id,
                    EVENT_SCHEMA_VERSION,
                    event_type,
                    source_id,
                    correlation_id,
                    canonical_json(payload),
                    now(),
                ),
            )
        return event_id

    def artifact(self, artifact_id: str) -> sqlite3.Row | None:
        with self.read() as connection:
            return connection.execute(
                "SELECT * FROM artifacts WHERE artifact_id=?", (artifact_id,)
            ).fetchone()

    def job(self, job_id: str) -> sqlite3.Row | None:
        with self.read() as connection:
            return connection.execute(
                "SELECT * FROM loader_jobs WHERE job_id=?", (job_id,)
            ).fetchone()

    def active_job_ids(self) -> list[str]:
        with self.read() as connection:
            return [
                row["job_id"]
                for row in connection.execute(
                    "SELECT job_id FROM loader_jobs WHERE state <> 'removed'"
                ).fetchall()
            ]
