from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

from .models import DecisionEnvelope, NativeEffect, WorkflowResult


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def state_hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


class WorkflowStore:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA journal_mode=WAL")
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS workflow_records (
                    workflow_id TEXT PRIMARY KEY,
                    range_id TEXT NOT NULL,
                    workflow TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    trace_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    token_audience TEXT NOT NULL,
                    input_digest TEXT NOT NULL,
                    extraction_digest TEXT NOT NULL,
                    model_digest TEXT NOT NULL,
                    serving_image_digest TEXT NOT NULL,
                    model_family TEXT NOT NULL,
                    model_version TEXT NOT NULL,
                    preprocessing_digest TEXT NOT NULL,
                    prompt_tool_digest TEXT NOT NULL,
                    policy_digest TEXT NOT NULL,
                    release_id TEXT NOT NULL,
                    decision_json TEXT NOT NULL,
                    clean_control_decision TEXT NOT NULL,
                    opa_decision_json TEXT,
                    target_system TEXT,
                    target_object_id TEXT,
                    native_request_ids_json TEXT NOT NULL DEFAULT '[]',
                    native_response_ids_json TEXT NOT NULL DEFAULT '[]',
                    before_state_json TEXT,
                    after_state_json TEXT,
                    before_state_hash TEXT,
                    after_state_hash TEXT,
                    notification_ids_json TEXT NOT NULL DEFAULT '[]',
                    compensation_data_json TEXT NOT NULL DEFAULT '{}',
                    compensation_state TEXT NOT NULL DEFAULT 'not-requested',
                    status TEXT NOT NULL,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    UNIQUE(range_id, idempotency_key)
                );
                CREATE TABLE IF NOT EXISTS compensation_records (
                    compensation_id TEXT PRIMARY KEY,
                    workflow_id TEXT NOT NULL REFERENCES workflow_records(workflow_id),
                    before_state_json TEXT NOT NULL,
                    after_state_json TEXT NOT NULL,
                    native_response_ids_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def claim(self, envelope: DecisionEnvelope) -> tuple[str, sqlite3.Row | None]:
        workflow_id = str(uuid.uuid4())
        created_at = datetime.now(UTC).isoformat()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """
                SELECT * FROM workflow_records
                WHERE range_id = ? AND idempotency_key = ?
                """,
                (envelope.range_id, envelope.idempotency_key),
            ).fetchone()
            if existing is not None:
                recorded = (
                    existing["workflow"],
                    existing["request_id"],
                    existing["trace_id"],
                    existing["actor"],
                    existing["token_audience"],
                    existing["input_digest"],
                    existing["extraction_digest"],
                    existing["model_digest"],
                    existing["serving_image_digest"],
                    existing["model_family"],
                    existing["model_version"],
                    existing["preprocessing_digest"],
                    existing["prompt_tool_digest"],
                    existing["policy_digest"],
                    existing["release_id"],
                    existing["decision_json"],
                    existing["clean_control_decision"],
                )
                submitted = (
                    envelope.decision.workflow.value,
                    envelope.request_id,
                    envelope.trace_id,
                    envelope.actor,
                    envelope.token_audience,
                    envelope.input_digest,
                    envelope.extraction_digest,
                    envelope.release.model_digest,
                    envelope.release.serving_image_digest,
                    envelope.release.model_family,
                    envelope.release.model_version,
                    envelope.preprocessing_digest,
                    envelope.prompt_tool_digest,
                    envelope.release.policy_digest,
                    envelope.release.release_id,
                    envelope.decision.model_dump_json(),
                    envelope.clean_control_decision,
                )
                if recorded != submitted:
                    raise ValueError(
                        "idempotency key is already bound to another decision"
                    )
                return str(existing["workflow_id"]), existing
            connection.execute(
                """
                INSERT INTO workflow_records (
                    workflow_id, range_id, workflow, request_id, trace_id,
                    idempotency_key, actor, token_audience, input_digest,
                    extraction_digest, model_digest, serving_image_digest,
                    model_family, model_version, preprocessing_digest,
                    prompt_tool_digest, policy_digest, release_id,
                    decision_json, clean_control_decision, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'processing', ?)
                """,
                (
                    workflow_id,
                    envelope.range_id,
                    envelope.decision.workflow.value,
                    envelope.request_id,
                    envelope.trace_id,
                    envelope.idempotency_key,
                    envelope.actor,
                    envelope.token_audience,
                    envelope.input_digest,
                    envelope.extraction_digest,
                    envelope.release.model_digest,
                    envelope.release.serving_image_digest,
                    envelope.release.model_family,
                    envelope.release.model_version,
                    envelope.preprocessing_digest,
                    envelope.prompt_tool_digest,
                    envelope.release.policy_digest,
                    envelope.release.release_id,
                    envelope.decision.model_dump_json(),
                    envelope.clean_control_decision,
                    created_at,
                ),
            )
        return workflow_id, None

    def complete(
        self,
        workflow_id: str,
        opa_decision: dict[str, Any],
        effect: NativeEffect,
    ) -> WorkflowResult:
        before_hash = state_hash(effect.before_state)
        after_hash = state_hash(effect.after_state)
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE workflow_records SET
                    opa_decision_json = ?, target_system = ?, target_object_id = ?,
                    native_request_ids_json = ?, native_response_ids_json = ?,
                    before_state_json = ?, after_state_json = ?,
                    before_state_hash = ?, after_state_hash = ?,
                    notification_ids_json = ?, compensation_data_json = ?,
                    status = 'succeeded', completed_at = ?
                WHERE workflow_id = ? AND status = 'processing'
                """,
                (
                    canonical(opa_decision),
                    effect.target_system,
                    effect.target_object_id,
                    canonical(effect.native_request_ids),
                    canonical(effect.native_response_ids),
                    canonical(effect.before_state),
                    canonical(effect.after_state),
                    before_hash,
                    after_hash,
                    canonical(effect.notification_ids),
                    canonical(effect.compensation_data),
                    datetime.now(UTC).isoformat(),
                    workflow_id,
                ),
            )
        return WorkflowResult(
            workflow_id=workflow_id,
            workflow=effect_workflow(self.get(workflow_id)),
            status="succeeded",
            target_system=effect.target_system,
            target_object_id=effect.target_object_id,
            native_response_ids=effect.native_response_ids,
            before_state_hash=before_hash,
            after_state_hash=after_hash,
            notification_ids=effect.notification_ids,
        )

    def fail(self, workflow_id: str, error: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE workflow_records
                SET status = 'failed', error = ?, completed_at = ?
                WHERE workflow_id = ? AND status = 'processing'
                """,
                (error[:2000], datetime.now(UTC).isoformat(), workflow_id),
            )

    def get(self, workflow_id: str) -> sqlite3.Row:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM workflow_records WHERE workflow_id = ?", (workflow_id,)
            ).fetchone()
        if row is None:
            raise KeyError(workflow_id)
        return row

    def result(self, row: sqlite3.Row, replay: bool = False) -> WorkflowResult:
        return WorkflowResult(
            workflow_id=str(row["workflow_id"]),
            workflow=effect_workflow(row),
            status=str(row["status"]),
            idempotent_replay=replay,
            target_system=row["target_system"],
            target_object_id=row["target_object_id"],
            native_response_ids=json.loads(row["native_response_ids_json"]),
            before_state_hash=row["before_state_hash"],
            after_state_hash=row["after_state_hash"],
            notification_ids=json.loads(row["notification_ids_json"]),
            compensation_state=str(row["compensation_state"]),
        )

    def compensation_data(self, workflow_id: str) -> dict[str, Any]:
        row = self.get(workflow_id)
        if row["status"] != "succeeded":
            raise ValueError("only a succeeded workflow can be compensated")
        return {
            "workflow": str(row["workflow"]),
            "target_system": row["target_system"],
            "target_object_id": row["target_object_id"],
            "before_state": json.loads(row["before_state_json"]),
            "after_state": json.loads(row["after_state_json"]),
            "compensation_data": json.loads(row["compensation_data_json"]),
            "state": str(row["compensation_state"]),
        }

    def record_compensation(
        self,
        workflow_id: str,
        before_state: dict[str, Any],
        after_state: dict[str, Any],
        native_response_ids: list[str],
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO compensation_records (
                    compensation_id, workflow_id, before_state_json,
                    after_state_json, native_response_ids_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    workflow_id,
                    canonical(before_state),
                    canonical(after_state),
                    canonical(native_response_ids),
                    datetime.now(UTC).isoformat(),
                ),
            )
            connection.execute(
                """
                UPDATE workflow_records SET compensation_state = 'completed'
                WHERE workflow_id = ?
                """,
                (workflow_id,),
            )


def effect_workflow(row: sqlite3.Row):
    from .models import Workflow

    return Workflow(str(row["workflow"]))
