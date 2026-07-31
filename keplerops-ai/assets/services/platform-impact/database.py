"""Durable state for the contained KeplerOps platform-impact services."""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


SCHEMA_VERSION = "1"
SEED_TIMESTAMP = "2026-01-01T00:00:00+00:00"


class StateStore:
    """Small SQLite owner with explicit transactions and deterministic reset."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
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
                CREATE TABLE IF NOT EXISTS ledger_transactions (
                    transaction_id TEXT PRIMARY KEY,
                    actor TEXT NOT NULL,
                    narration TEXT NOT NULL,
                    amount_micros INTEGER NOT NULL CHECK (amount_micros > 0),
                    currency TEXT NOT NULL CHECK (currency = 'SYN'),
                    debit_account TEXT NOT NULL,
                    credit_account TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    CHECK (debit_account <> credit_account)
                );
                CREATE TABLE IF NOT EXISTS publications (
                    publication_id TEXT PRIMARY KEY,
                    author TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    body TEXT NOT NULL,
                    body_digest TEXT NOT NULL,
                    reputation_delta INTEGER NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('published', 'removed')),
                    created_at TEXT NOT NULL,
                    removed_at TEXT
                );
                CREATE TABLE IF NOT EXISTS reputations (
                    subject TEXT PRIMARY KEY,
                    score INTEGER NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS allocation_decisions (
                    decision_id TEXT PRIMARY KEY,
                    subject_id TEXT NOT NULL,
                    group_name TEXT NOT NULL,
                    income REAL NOT NULL,
                    need_score REAL NOT NULL,
                    prior_service REAL NOT NULL,
                    expected_label INTEGER NOT NULL CHECK (expected_label IN (0, 1)),
                    approved INTEGER NOT NULL CHECK (approved IN (0, 1)),
                    probability REAL NOT NULL CHECK (probability >= 0 AND probability <= 1),
                    model_digest TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS allocation_population (
                    subject_id TEXT PRIMARY KEY,
                    group_name TEXT NOT NULL,
                    income REAL NOT NULL,
                    need_score REAL NOT NULL,
                    prior_service REAL NOT NULL,
                    expected_label INTEGER NOT NULL CHECK (expected_label IN (0, 1))
                );
                CREATE TABLE IF NOT EXISTS user_simulations (
                    simulation_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    message TEXT NOT NULL,
                    safety_label TEXT NOT NULL CHECK (safety_label IN ('safe', 'unsafe')),
                    unsafe_probability REAL NOT NULL CHECK (unsafe_probability >= 0 AND unsafe_probability <= 1),
                    action TEXT NOT NULL CHECK (action IN ('delivered', 'contained')),
                    classifier_digest TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS budgets (
                    actor TEXT PRIMARY KEY,
                    limit_microunits INTEGER NOT NULL CHECK (limit_microunits >= 0),
                    spent_microunits INTEGER NOT NULL DEFAULT 0 CHECK (spent_microunits >= 0),
                    updated_at TEXT NOT NULL,
                    CHECK (spent_microunits <= limit_microunits)
                );
                CREATE TABLE IF NOT EXISTS cost_events (
                    event_id TEXT PRIMARY KEY,
                    actor TEXT NOT NULL REFERENCES budgets(actor),
                    producer_id TEXT NOT NULL,
                    input_tokens INTEGER NOT NULL CHECK (input_tokens >= 0),
                    output_tokens INTEGER NOT NULL CHECK (output_tokens >= 0),
                    compute_ms INTEGER NOT NULL CHECK (compute_ms >= 0),
                    synthetic_cost_microunits INTEGER NOT NULL CHECK (synthetic_cost_microunits >= 0),
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS availability_targets (
                    target_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    probe_url TEXT NOT NULL,
                    recovery_url TEXT,
                    recovery_after INTEGER NOT NULL CHECK (recovery_after BETWEEN 1 AND 10),
                    consecutive_failures INTEGER NOT NULL DEFAULT 0 CHECK (consecutive_failures >= 0),
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS availability_samples (
                    sample_id TEXT PRIMARY KEY,
                    target_id TEXT NOT NULL REFERENCES availability_targets(target_id) ON DELETE CASCADE,
                    available INTEGER NOT NULL CHECK (available IN (0, 1)),
                    status_code INTEGER,
                    latency_ms REAL NOT NULL CHECK (latency_ms >= 0),
                    error TEXT,
                    occurred_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS recovery_events (
                    recovery_id TEXT PRIMARY KEY,
                    target_id TEXT NOT NULL REFERENCES availability_targets(target_id) ON DELETE CASCADE,
                    attempted INTEGER NOT NULL CHECK (attempted IN (0, 1)),
                    succeeded INTEGER NOT NULL CHECK (succeeded IN (0, 1)),
                    status_code INTEGER,
                    error TEXT,
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
        """Restore the same empty operational state and synthetic seed each time."""
        with self.transaction() as connection:
            connection.executescript(
                """
                DELETE FROM recovery_events;
                DELETE FROM availability_samples;
                DELETE FROM availability_targets;
                DELETE FROM cost_events;
                DELETE FROM budgets;
                DELETE FROM user_simulations;
                DELETE FROM allocation_decisions;
                DELETE FROM allocation_population;
                DELETE FROM publications;
                DELETE FROM reputations;
                DELETE FROM ledger_transactions;
                """
            )
            connection.execute(
                "INSERT INTO reputations(subject, score, updated_at) VALUES (?, ?, ?)",
                ("keplerops-synthetic", 100, SEED_TIMESTAMP),
            )
            connection.executemany(
                "INSERT INTO allocation_population "
                "(subject_id, group_name, income, need_score, prior_service, expected_label) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    ("north-01", "north", 22, 0.92, 0, 1),
                    ("north-02", "north", 36, 0.75, 1, 1),
                    ("north-03", "north", 68, 0.38, 0, 0),
                    ("north-04", "north", 88, 0.16, 1, 0),
                    ("south-01", "south", 25, 0.89, 1, 1),
                    ("south-02", "south", 43, 0.66, 0, 1),
                    ("south-03", "south", 72, 0.31, 1, 0),
                    ("south-04", "south", 91, 0.13, 0, 0),
                ),
            )
            connection.execute(
                "INSERT INTO budgets(actor, limit_microunits, spent_microunits, updated_at) "
                "VALUES (?, ?, 0, ?)",
                ("synthetic-cohort", 1_000_000, SEED_TIMESTAMP),
            )
            connection.execute(
                "INSERT INTO metadata(key, value) VALUES ('last_reset_at', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (SEED_TIMESTAMP,),
            )

    def ready(self) -> bool:
        with self.read() as connection:
            version = connection.execute(
                "SELECT value FROM metadata WHERE key='schema_version'"
            ).fetchone()
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
        return (
            version is not None
            and version["value"] == SCHEMA_VERSION
            and integrity is not None
            and integrity[0] == "ok"
        )
