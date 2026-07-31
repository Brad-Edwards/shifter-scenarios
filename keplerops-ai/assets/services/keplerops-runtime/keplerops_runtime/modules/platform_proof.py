from __future__ import annotations

import hashlib
import json
import secrets
import time
from pathlib import Path
from typing import Any, Literal

import httpx
from domain import SessionClaims
from fastapi import HTTPException

from keplerops_runtime.foundation.auth_storage import _postgres, _require_ready
from keplerops_runtime.foundation.clients import _backend_http_client, _record_event
from keplerops_runtime.foundation.config import CONFIG, _regular_owner_file


PlatformName = Literal[
    "platform-agent",
    "platform-adversarial",
    "platform-camera",
    "platform-deployment",
    "platform-impact",
    "platform-ml",
    "platform-training",
]
PLATFORM_REQUEST_TIMEOUT = 8.0


def ensure_platform_event_table(connection: Any) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS platform_challenge_events (
            event_id TEXT PRIMARY KEY,
            range_instance TEXT NOT NULL,
            participant TEXT NOT NULL,
            reset_generation INTEGER NOT NULL,
            challenge_id TEXT NOT NULL,
            platform TEXT NOT NULL,
            object_id TEXT NOT NULL,
            object_digest TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('passed', 'not_satisfied')),
            failure_class TEXT NOT NULL,
            evidence JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
            UNIQUE (
                range_instance,
                participant,
                reset_generation,
                challenge_id,
                object_id
            )
        )
        """
    )


def digest_json(value: object) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def config_url(field: str, detail: str) -> str:
    value = CONFIG.get(field)
    if not isinstance(value, str) or not value:
        raise HTTPException(status_code=503, detail=detail)
    return value.rstrip("/")


def bearer_from_file(field: str, detail: str) -> str:
    value = CONFIG.get(field)
    if not isinstance(value, str) or not value:
        raise HTTPException(status_code=503, detail=detail)
    try:
        return _regular_owner_file(Path(value)).decode("utf-8")
    except (OSError, UnicodeError, RuntimeError):
        raise HTTPException(status_code=503, detail=detail) from None


async def platform_request(
    method: Literal["GET", "POST", "PUT", "DELETE"],
    *,
    service_key: str,
    base_url_field: str,
    unavailable: str,
    path: str,
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
    expected: tuple[int, ...] = (200,),
) -> dict[str, Any]:
    client = _backend_http_client(
        f"{service_key}-{PLATFORM_REQUEST_TIMEOUT}",
        timeout=PLATFORM_REQUEST_TIMEOUT,
    )
    try:
        response = await client.request(
            method,
            f"{config_url(base_url_field, unavailable)}{path}",
            headers=headers,
            json=payload,
        )
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail=unavailable) from None
    if response.status_code not in expected:
        if response.status_code in {401, 403, 404, 409, 422}:
            detail: Any = unavailable
            try:
                body = response.json()
                detail = body.get("detail", detail) if isinstance(body, dict) else body
            except ValueError:
                pass
            raise HTTPException(status_code=response.status_code, detail=detail)
        raise HTTPException(status_code=503, detail=unavailable)
    try:
        body = response.json()
    except ValueError:
        raise HTTPException(status_code=503, detail=unavailable) from None
    if not isinstance(body, dict):
        raise HTTPException(status_code=503, detail=unavailable)
    return body


def store_platform_event(
    session: SessionClaims,
    *,
    challenge_id: str,
    platform: PlatformName,
    object_id: str,
    status: Literal["passed", "not_satisfied"],
    failure_class: str,
    evidence: dict[str, Any],
    object_digest: str | None = None,
) -> tuple[str, str]:
    generation = _require_ready()
    digest = object_digest or digest_json(evidence)
    event_id = "pcv-" + secrets.token_hex(12)
    with _postgres() as connection, connection.cursor() as cursor:
        ensure_platform_event_table(connection)
        cursor.execute(
            "INSERT INTO platform_challenge_events "
            "(event_id, range_instance, participant, reset_generation, challenge_id, "
            "platform, object_id, object_digest, status, failure_class, evidence) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb) "
            "ON CONFLICT (range_instance, participant, reset_generation, challenge_id, object_id) "
            "DO UPDATE SET object_digest=excluded.object_digest, status=excluded.status, "
            "failure_class=excluded.failure_class, evidence=excluded.evidence, "
            "created_at=clock_timestamp() RETURNING event_id",
            (
                event_id,
                session.range_instance,
                session.participant,
                generation,
                challenge_id,
                platform,
                object_id,
                digest,
                status,
                failure_class,
                json.dumps(evidence, sort_keys=True),
            ),
        )
        row = cursor.fetchone()
    if not isinstance(row, tuple) or len(row) != 1 or not isinstance(row[0], str):
        raise HTTPException(status_code=503, detail="platform evidence unavailable")
    return row[0], digest


async def record_platform_proof(
    session: SessionClaims,
    *,
    event_kind: str,
    outcome_id: str,
    object_id: str,
    digest: str,
    asset_id: str,
    record_count: int = 1,
    workflow_id: str | None = None,
    extra_fields: dict[str, Any] | None = None,
) -> None:
    event = {
        "actor_role": "participant",
        "asset_id": asset_id,
        "digest": digest,
        "event_kind": event_kind,
        "object_id": object_id,
        "outcome_id": outcome_id,
        "participant": session.participant,
        "range_instance": session.range_instance,
        "record_count": record_count,
        "status": "passed",
        "timestamp": int(time.time()),
    }
    if workflow_id is not None:
        event["workflow_id"] = workflow_id
    if extra_fields:
        event.update(extra_fields)
    await _record_event(event)
