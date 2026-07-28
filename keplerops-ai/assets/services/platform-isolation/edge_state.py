"""Durable procurement and unverified edge-device inventory state."""

from __future__ import annotations

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


class EdgeStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.path = self.root / "edge-registry.sqlite3"
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
                CREATE TABLE IF NOT EXISTS procurement_orders (
                    order_id TEXT PRIMARY KEY,
                    vendor TEXT NOT NULL,
                    model TEXT NOT NULL,
                    quantity INTEGER NOT NULL CHECK (quantity BETWEEN 1 AND 64),
                    state TEXT NOT NULL CHECK (
                        state IN ('requested', 'approved', 'ordered', 'received', 'cancelled')
                    ),
                    notes TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS devices (
                    device_id TEXT PRIMARY KEY,
                    order_id TEXT NOT NULL REFERENCES procurement_orders(order_id),
                    manufacturer TEXT NOT NULL,
                    model TEXT NOT NULL,
                    serial_number TEXT NOT NULL UNIQUE,
                    inventory_json TEXT NOT NULL,
                    capabilities_json TEXT NOT NULL,
                    attestation_json TEXT,
                    physical_presence_state TEXT NOT NULL CHECK (
                        physical_presence_state = 'reported_unverified'
                    ),
                    capability_state TEXT NOT NULL CHECK (
                        capability_state = 'reported_unverified'
                    ),
                    attestation_state TEXT NOT NULL CHECK (
                        attestation_state IN ('not_provided', 'received_unverified')
                    ),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS device_observations (
                    observation_id TEXT PRIMARY KEY,
                    device_id TEXT NOT NULL REFERENCES devices(device_id),
                    observation_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
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
        with self.transaction() as connection:
            connection.executescript(
                """
                DELETE FROM structured_events;
                DELETE FROM device_observations;
                DELETE FROM devices;
                DELETE FROM procurement_orders;
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
                    "edge-seed-0001",
                    EVENT_SCHEMA_VERSION,
                    "edge_registry.seeded",
                    "edge-registry",
                    None,
                    canonical_json(
                        {
                            "device_count": 0,
                            "verified_physical_accelerators": 0,
                            "hardware_constraint": "unsatisfied",
                        }
                    ),
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
        event_id = f"edge-event-{uuid.uuid4()}"
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

    def order(self, order_id: str) -> sqlite3.Row | None:
        with self.read() as connection:
            return connection.execute(
                "SELECT * FROM procurement_orders WHERE order_id=?", (order_id,)
            ).fetchone()

    def device(self, device_id: str) -> sqlite3.Row | None:
        with self.read() as connection:
            return connection.execute(
                "SELECT * FROM devices WHERE device_id=?", (device_id,)
            ).fetchone()

    def device_count(self) -> int:
        with self.read() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM devices").fetchone()
        return int(row["count"])
