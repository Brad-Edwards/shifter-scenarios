"""Durable state for the KeplerOps agent platform boundary."""

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
SEED_AGENT_ID = "platform-agent-alpha"
SEED_CONFIG_VERSION = "1.0.0"


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest_text(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


class StateStore:
    """SQLite owner with serialized writes, WAL durability, and reset support."""

    def __init__(self, root: Path, agent_token: str) -> None:
        self.root = root
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.export_root = self.root / "exports"
        self.export_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.path = self.root / "platform-agent.sqlite3"
        self.agent_token_digest = digest_text(agent_token)
        self._lock = threading.RLock()
        self._migrate()

    def _connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA busy_timeout = 10000")
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
                CREATE TABLE IF NOT EXISTS identities (
                    agent_id TEXT PRIMARY KEY,
                    identity_version TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    token_digest TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('active', 'disabled')),
                    active_config_version TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tool_registry (
                    tool_name TEXT NOT NULL,
                    version TEXT NOT NULL,
                    handler TEXT NOT NULL,
                    description TEXT NOT NULL,
                    input_schema_json TEXT NOT NULL,
                    enabled INTEGER NOT NULL CHECK (enabled IN (0, 1)),
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (tool_name, version)
                );
                CREATE TABLE IF NOT EXISTS agent_configs (
                    agent_id TEXT NOT NULL REFERENCES identities(agent_id) ON DELETE CASCADE,
                    version TEXT NOT NULL,
                    runtime_kind TEXT NOT NULL CHECK (runtime_kind = 'langgraph-local'),
                    max_steps INTEGER NOT NULL CHECK (max_steps BETWEEN 1 AND 8),
                    tool_timeout_ms INTEGER NOT NULL CHECK (tool_timeout_ms BETWEEN 50 AND 5000),
                    allowed_tools_json TEXT NOT NULL,
                    worker_profile TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (agent_id, version)
                );
                CREATE TABLE IF NOT EXISTS agent_runs (
                    run_id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL REFERENCES identities(agent_id),
                    config_version TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'rejected', 'failed')),
                    plan_json TEXT NOT NULL,
                    result_json TEXT,
                    error TEXT,
                    started_at TEXT NOT NULL,
                    ended_at TEXT
                );
                CREATE TABLE IF NOT EXISTS worker_jobs (
                    worker_id TEXT PRIMARY KEY,
                    container_id TEXT NOT NULL UNIQUE,
                    image_ref TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (state IN ('created', 'running', 'exited', 'restarting', 'removed', 'unknown')),
                    input_digest TEXT NOT NULL,
                    restart_count INTEGER NOT NULL DEFAULT 0 CHECK (restart_count >= 0),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS relay_events (
                    event_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL REFERENCES identities(agent_id),
                    channel TEXT NOT NULL CHECK (channel IN ('heartbeat', 'status', 'task', 'result')),
                    sequence INTEGER NOT NULL CHECK (sequence >= 0),
                    payload_json TEXT NOT NULL,
                    payload_digest TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    UNIQUE (source_id, sequence)
                );
                CREATE TABLE IF NOT EXISTS diagnostic_resources (
                    resource_id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    max_bytes INTEGER NOT NULL CHECK (max_bytes BETWEEN 256 AND 65536),
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS exports (
                    export_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL REFERENCES identities(agent_id),
                    media_type TEXT NOT NULL CHECK (media_type = 'application/json'),
                    payload_path TEXT NOT NULL,
                    byte_count INTEGER NOT NULL CHECK (byte_count BETWEEN 2 AND 65536),
                    payload_digest TEXT NOT NULL,
                    received_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS structured_events (
                    event_id TEXT PRIMARY KEY,
                    schema_version TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    source_kind TEXT NOT NULL,
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
        """Restore deterministic identities, configuration, tools, and sinks."""
        for export in self.export_root.glob("*.json"):
            export.unlink(missing_ok=True)
        with self.transaction() as connection:
            connection.executescript(
                """
                DELETE FROM structured_events;
                DELETE FROM exports;
                DELETE FROM diagnostic_resources;
                DELETE FROM relay_events;
                DELETE FROM worker_jobs;
                DELETE FROM agent_runs;
                DELETE FROM agent_configs;
                DELETE FROM tool_registry;
                DELETE FROM identities;
                """
            )
            connection.execute(
                "INSERT INTO identities "
                "(agent_id, identity_version, display_name, role, token_digest, status, "
                "active_config_version, created_at) VALUES (?, ?, ?, ?, ?, 'active', ?, ?)",
                (
                    SEED_AGENT_ID,
                    "1.0.0",
                    "KeplerOps Local Agent Alpha",
                    "range-agent",
                    self.agent_token_digest,
                    SEED_CONFIG_VERSION,
                    SEED_TIMESTAMP,
                ),
            )
            tools = (
                (
                    "hash_text",
                    "1.0.0",
                    "hash_text",
                    "Compute a SHA-256 digest for bounded UTF-8 text.",
                    canonical_json(
                        {
                            "type": "object",
                            "required": ["text"],
                            "properties": {
                                "text": {"type": "string", "maxLength": 8192}
                            },
                            "additionalProperties": False,
                        }
                    ),
                    1,
                    SEED_TIMESTAMP,
                ),
                (
                    "query_json",
                    "1.0.0",
                    "query_json",
                    "Run a bounded JMESPath query over an in-memory JSON document.",
                    canonical_json(
                        {
                            "type": "object",
                            "required": ["expression", "document"],
                            "properties": {
                                "expression": {"type": "string", "maxLength": 256},
                                "document": {"type": ["object", "array"]},
                            },
                            "additionalProperties": False,
                        }
                    ),
                    1,
                    SEED_TIMESTAMP,
                ),
                (
                    "identity_metadata",
                    "1.0.0",
                    "identity_metadata",
                    "Return the authenticated local agent identity and configuration version.",
                    canonical_json(
                        {
                            "type": "object",
                            "properties": {},
                            "additionalProperties": False,
                        }
                    ),
                    1,
                    SEED_TIMESTAMP,
                ),
            )
            connection.executemany(
                "INSERT INTO tool_registry "
                "(tool_name, version, handler, description, input_schema_json, enabled, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                tools,
            )
            connection.execute(
                "INSERT INTO agent_configs "
                "(agent_id, version, runtime_kind, max_steps, tool_timeout_ms, "
                "allowed_tools_json, worker_profile, created_at) "
                "VALUES (?, ?, 'langgraph-local', 4, 1000, ?, 'disposable-linux-v1', ?)",
                (
                    SEED_AGENT_ID,
                    SEED_CONFIG_VERSION,
                    canonical_json(
                        [
                            "hash_text@1.0.0",
                            "query_json@1.0.0",
                            "identity_metadata@1.0.0",
                        ]
                    ),
                    SEED_TIMESTAMP,
                ),
            )
            connection.execute(
                "INSERT INTO diagnostic_resources(resource_id, url, max_bytes, created_at) "
                "VALUES ('local-health', 'http://127.0.0.1:8470/healthz', 4096, ?)",
                (SEED_TIMESTAMP,),
            )
            connection.execute(
                "INSERT INTO metadata(key, value) VALUES ('last_reset_at', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (SEED_TIMESTAMP,),
            )
            connection.execute(
                "INSERT INTO structured_events "
                "(event_id, schema_version, event_type, source_kind, source_id, "
                "correlation_id, payload_json, occurred_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "event-seed-0001",
                    EVENT_SCHEMA_VERSION,
                    "platform.seeded",
                    "service",
                    "platform-agent",
                    None,
                    canonical_json({"config_version": SEED_CONFIG_VERSION}),
                    SEED_TIMESTAMP,
                ),
            )

    def ready(self) -> bool:
        with self.read() as connection:
            schema = connection.execute(
                "SELECT value FROM metadata WHERE key='schema_version'"
            ).fetchone()
            identity = connection.execute(
                "SELECT 1 FROM identities WHERE agent_id=? AND status='active'",
                (SEED_AGENT_ID,),
            ).fetchone()
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
        return bool(
            schema
            and schema["value"] == SCHEMA_VERSION
            and identity
            and integrity
            and integrity[0] == "ok"
        )

    def record_event(
        self,
        event_type: str,
        source_kind: str,
        source_id: str,
        payload: dict[str, Any],
        correlation_id: str | None = None,
    ) -> str:
        event_id = f"event-{uuid.uuid4()}"
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO structured_events "
                "(event_id, schema_version, event_type, source_kind, source_id, "
                "correlation_id, payload_json, occurred_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event_id,
                    EVENT_SCHEMA_VERSION,
                    event_type,
                    source_kind,
                    source_id,
                    correlation_id,
                    canonical_json(payload),
                    utc_now(),
                ),
            )
        return event_id

    def authenticate(self, agent_id: str, token: str) -> bool:
        supplied = digest_text(token)
        with self.read() as connection:
            identity = connection.execute(
                "SELECT token_digest FROM identities WHERE agent_id=? AND status='active'",
                (agent_id,),
            ).fetchone()
        return bool(identity and identity["token_digest"] == supplied)

    def active_config(self, agent_id: str) -> sqlite3.Row | None:
        with self.read() as connection:
            return connection.execute(
                "SELECT c.* FROM identities i JOIN agent_configs c "
                "ON c.agent_id=i.agent_id AND c.version=i.active_config_version "
                "WHERE i.agent_id=? AND i.status='active'",
                (agent_id,),
            ).fetchone()

    def tool_rows(self) -> list[sqlite3.Row]:
        with self.read() as connection:
            return list(
                connection.execute(
                    "SELECT * FROM tool_registry WHERE enabled=1 ORDER BY tool_name, version"
                ).fetchall()
            )
