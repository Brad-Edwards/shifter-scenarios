from __future__ import annotations

import json
import secrets
import time
from typing import Annotated, Any, Literal

from domain import SessionClaims
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from agent_persistence_expansion import (
    CHALLENGE_IDS,
    AGENT_CONFIG_SCOPE,
    COVERT_COMMAND,
    HASH_TEXT_TOOL,
    QUERY_JSON_TOOL,
    REVERSE_COMMAND,
    WORKER_PROFILE,
    SCOPED_ACCOUNT,
    SEED_AGENT_ID,
    WEB_RELAY_COMMAND,
    WORKER_MARKER,
    blueprint_document,
    challenge_satisfied,
    configuration_document,
    digest_value,
    scoped_token,
)
from keplerops_runtime.foundation.auth_storage import _postgres, _require_ready, _require_role, _session
from keplerops_runtime.foundation.config import ACTION_DENIED, ERROR_RESPONSES
from keplerops_runtime.foundation.policy_client import _policy
from keplerops_runtime.foundation.telemetry import _capture, _observe
from keplerops_runtime.modules.m05.constants import PERSISTENCE_EVIDENCE
from keplerops_runtime.modules.platform_proof import bearer_from_file, platform_request, record_platform_proof


router = APIRouter()
AGENT_UNAVAILABLE = "platform agent unavailable"
OUTCOME_ID = "agent-persistence"
RELAY_SEQUENCE_BASE = {
    "kep-m05-o": 10,
    "kep-m05-p": 20,
    "kep-m05-q": 30,
}
EXPANSION_CHALLENGE = Literal[
    "kep-m05-f", "kep-m05-g", "kep-m05-h", "kep-m05-i", "kep-m05-j", "kep-m05-k",
    "kep-m05-l", "kep-m05-m", "kep-m05-n", "kep-m05-o", "kep-m05-p", "kep-m05-q",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PersistenceExpansionActionRequest(StrictModel):
    challenge_id: EXPANSION_CHALLENGE
    scoped_token: str | None = Field(default=None, max_length=128)
    original_session: str = Field(default="browser-session-alpha", max_length=64)
    replay_session: str = Field(default="browser-session-beta", max_length=64)
    participant_goal: str = Field(default="collect release marker", max_length=512)
    participant_interface: Literal["browser", "curl", "python"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


class PersistenceExpansionAttemptRequest(StrictModel):
    challenge_id: EXPANSION_CHALLENGE
    evidence: dict[str, Any] = Field(default_factory=dict)
    participant_interface: Literal["browser", "curl", "python"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


def _submitted_evidence(request: PersistenceExpansionAttemptRequest) -> dict[str, Any]:
    return getattr(request, "evidence")


async def _allowed(session: SessionClaims, challenge_id: str) -> None:
    _require_role("gateway")
    _require_ready()
    if not await _policy(session, "infer"):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)
    if challenge_id not in CHALLENGE_IDS:
        raise HTTPException(status_code=404, detail="unknown challenge")


def _admin_headers() -> dict[str, str]:
    return {
        "X-Platform-Admin-Token": bearer_from_file(
            "platform_agent_admin_token_file", AGENT_UNAVAILABLE
        )
    }


def _agent_headers() -> dict[str, str]:
    return {
        "X-Agent-Id": SEED_AGENT_ID,
        "X-Agent-Token": bearer_from_file(
            "platform_agent_seed_token_file", AGENT_UNAVAILABLE
        ),
    }


async def _agent_request(
    method: Literal["GET", "POST", "PUT", "DELETE"],
    path: str,
    *,
    admin: bool = False,
    payload: dict[str, Any] | None = None,
    expected: tuple[int, ...] = (200,),
) -> dict[str, Any]:
    return await platform_request(
        method,
        service_key="platform-agent",
        base_url_field="platform_agent_url",
        unavailable=AGENT_UNAVAILABLE,
        path=path,
        headers=_admin_headers() if admin else _agent_headers(),
        payload=payload,
        expected=expected,
    )


def _ensure_schema() -> None:
    with _postgres() as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS persistence_expansion_events ("
            "event_id text PRIMARY KEY, range_instance text NOT NULL, "
            "participant text NOT NULL, reset_generation integer NOT NULL, "
            "challenge_id text NOT NULL, event_key text NOT NULL, object_id text NOT NULL, "
            "object_digest text NOT NULL, payload jsonb NOT NULL, "
            "created_at timestamptz NOT NULL DEFAULT clock_timestamp())"
        )


def _record_local(
    session: SessionClaims,
    *,
    challenge_id: str,
    event_key: str,
    object_id: str,
    payload: dict[str, Any],
) -> tuple[str, str]:
    _ensure_schema()
    event_id = "m5e-" + secrets.token_hex(12)
    digest = digest_value(payload)
    with _postgres() as connection:
        connection.execute(
            "INSERT INTO persistence_expansion_events "
            "(event_id, range_instance, participant, reset_generation, challenge_id, "
            "event_key, object_id, object_digest, payload) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)",
            (
                event_id,
                session.range_instance,
                session.participant,
                _require_ready(),
                challenge_id,
                event_key,
                object_id,
                digest,
                json.dumps(payload, sort_keys=True),
            ),
        )
    return event_id, digest


def _event_count(session: SessionClaims, challenge_id: str) -> int:
    _ensure_schema()
    with _postgres() as connection:
        row = connection.execute(
            "SELECT count(*) FROM persistence_expansion_events WHERE range_instance=%s "
            "AND participant=%s AND reset_generation=%s AND challenge_id=%s",
            (session.range_instance, session.participant, _require_ready(), challenge_id),
        ).fetchone()
    return int(row[0]) if row and isinstance(row[0], int) else 0


async def _platform_identity_evidence(session: SessionClaims) -> dict[str, Any]:
    identity = await _agent_request("GET", f"/v1/identities/{SEED_AGENT_ID}")
    version = str(identity.get("active_config_version", "1.0.0"))
    blueprint = blueprint_document(version)
    evidence = {
        "agent_id": SEED_AGENT_ID,
        "identity": identity,
        "blueprint": blueprint,
        "blueprint_digest": digest_value(blueprint),
        "live_revision_match": identity.get("agent_id") == SEED_AGENT_ID,
    }
    _record_local(
        session,
        challenge_id="kep-m05-f",
        event_key="registry-blueprint-read",
        object_id=SEED_AGENT_ID,
        payload=evidence,
    )
    return evidence


def _scoped_config(session: SessionClaims) -> dict[str, Any]:
    token = scoped_token(
        session.range_instance, session.participant, _require_ready()
    )
    return configuration_document("5.5.5", token)


async def _configuration_evidence(session: SessionClaims) -> dict[str, Any]:
    config = await _agent_request("GET", "/v1/configurations/active")
    scoped = _scoped_config(session)
    evidence = {**scoped, "platform_active_config": config}
    for key in ("configuration-read", "scoped-secret-read"):
        _record_local(
            session,
            challenge_id="kep-m05-g",
            event_key=key,
            object_id=SEED_AGENT_ID,
            payload=evidence,
        )
    return evidence


def _token_evidence(session: SessionClaims, supplied: str | None) -> dict[str, Any]:
    expected = scoped_token(
        session.range_instance, session.participant, _require_ready()
    )
    valid = supplied == expected
    return {
        "token_valid": valid,
        "account": SCOPED_ACCOUNT if valid else "",
        "authorized_operation": AGENT_CONFIG_SCOPE if valid else "",
    }


async def _tool_run_evidence() -> dict[str, Any]:
    run = await _agent_request(
        "POST",
        "/v1/agent/runs",
        payload={
            "plan": [
                {
                    "tool": QUERY_JSON_TOOL,
                    "arguments": {
                        "expression": "credential_ref",
                        "document": {"credential_ref": "agent-tool/downstream-token"},
                    },
                }
            ]
        },
        expected=(201,),
    )
    return {
        "tool": QUERY_JSON_TOOL,
        "run": run,
        "secret_accessed": run.get("status") == "completed",
        "downstream_validation": run.get("status") == "completed",
    }


async def _worker_evidence(request: PersistenceExpansionActionRequest) -> dict[str, Any]:
    worker = await _agent_request(
        "POST",
        "/v1/workers",
        admin=True,
        payload={"job": {"goal": request.participant_goal, "marker": WORKER_MARKER}},
        expected=(201,),
    )
    return {
        "worker": worker,
        "worker_process": WORKER_PROFILE,
        "os_credential_hash": digest_value(WORKER_MARKER),
        "management_shell": False,
        "deployed_process": True,
        "participant_goal": request.participant_goal,
        "host_marker": WORKER_MARKER,
    }


async def _relay_evidence(challenge_id: str, command: str, result_key: str) -> dict[str, Any]:
    suffix = secrets.token_hex(6)
    task_sequence = RELAY_SEQUENCE_BASE[challenge_id]
    result_sequence = task_sequence + 1
    task = await _agent_request(
        "POST",
        "/v1/relay/events",
        payload={
            "event_id": f"{challenge_id}-task-{suffix}",
            "channel": "task",
            "sequence": task_sequence,
            "payload": {"command": command},
        },
        expected=(202,),
    )
    result = await _agent_request(
        "POST",
        "/v1/relay/events",
        payload={
            "event_id": f"{challenge_id}-result-{suffix}",
            "channel": "result",
            "sequence": result_sequence,
            "payload": {"result": WORKER_MARKER},
        },
        expected=(202,),
    )
    return {
        "task": task,
        "result": result,
        result_key: command,
        "contained_output": WORKER_MARKER,
        "encoded_result": WORKER_MARKER,
        "worker_result": WORKER_MARKER,
    }


async def _action_evidence(
    request: PersistenceExpansionActionRequest, session: SessionClaims,
) -> dict[str, Any]:
    if request.challenge_id == "kep-m05-f":
        return await _platform_identity_evidence(session)
    if request.challenge_id == "kep-m05-g":
        return await _configuration_evidence(session)
    if request.challenge_id == "kep-m05-h":
        return _token_evidence(session, request.scoped_token)
    if request.challenge_id == "kep-m05-i":
        evidence = {
            "cookie_replayed": True,
            "original_session": request.original_session,
            "replay_session": request.replay_session,
            "authenticated_action": "assistant-session-read",
        }
        for key in ("session-cookie-disclosed", "session-cookie-replayed"):
            _record_local(
                session,
                challenge_id=request.challenge_id,
                event_key=key,
                object_id=request.replay_session,
                payload=evidence,
            )
        return evidence
    if request.challenge_id == "kep-m05-j":
        return {
            "artifact_id": "workhub-agent-runbook",
            "validated_scope": "agent-config-read",
        }
    if request.challenge_id == "kep-m05-k":
        return await _tool_run_evidence()
    if request.challenge_id in {"kep-m05-l", "kep-m05-n"}:
        return await _worker_evidence(request)
    if request.challenge_id == "kep-m05-m":
        version = f"5.5.{int(time.time()) % 1000000}"
        created = await _agent_request(
            "POST",
            "/v1/configurations",
            admin=True,
            payload={
                "agent_id": SEED_AGENT_ID,
                "version": version,
                "max_steps": 2,
                "tool_timeout_ms": 1000,
                "allowed_tools": [QUERY_JSON_TOOL, HASH_TEXT_TOOL],
                "worker_profile": WORKER_PROFILE,
            },
            expected=(201,),
        )
        activated = await _agent_request(
            "POST",
            f"/v1/configurations/{version}/activate?agent_id={SEED_AGENT_ID}",
            admin=True,
        )
        evidence = {
            "configuration_written": True,
            "restart_verified": True,
            "post_restart_behavior": "changed",
            "created": created,
            "activated": activated,
        }
        for key in ("configuration-written", "configuration-activated"):
            _record_local(
                session,
                challenge_id=request.challenge_id,
                event_key=key,
                object_id=version,
                payload=evidence,
            )
        return evidence
    if request.challenge_id == "kep-m05-o":
        evidence = await _relay_evidence(request.challenge_id, REVERSE_COMMAND, "retrieved_command")
        return {**evidence, "reverse_connected": True}
    if request.challenge_id == "kep-m05-p":
        evidence = await _relay_evidence(request.challenge_id, COVERT_COMMAND, "encoded_command")
        return {**evidence, "worker_origin": True}
    evidence = await _relay_evidence(request.challenge_id, WEB_RELAY_COMMAND, "relay_command")
    export = await _agent_request(
        "POST",
        "/v1/exports",
        payload={
            "export_id": "web-relay-" + secrets.token_hex(6),
            "media_type": "application/json",
            "payload": {"result": WORKER_MARKER},
        },
        expected=(201,),
    )
    return {**evidence, "browser_automation": True, "api_calls": [], "export": export}


@router.post("/v1/persistence/expansion/actions", responses=ERROR_RESPONSES)
async def persistence_expansion_action(
    request: PersistenceExpansionActionRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    await _allowed(session, request.challenge_id)
    _capture(session, signal="http_body", content=request.model_dump_json())
    evidence = await _action_evidence(request, session)
    event_id, digest = _record_local(
        session,
        challenge_id=request.challenge_id,
        event_key="participant-platform-action",
        object_id=request.challenge_id,
        payload=evidence,
    )
    _observe(
        session,
        event_name="keplerops.objective.attempt_completed",
        outcome_id=OUTCOME_ID,
        challenge_id=request.challenge_id,
        status="recorded",
        artifact_digest=digest,
        participant_interface=request.participant_interface,
        assistance_mode=request.assistance_mode,
    )
    return {"event_id": event_id, "object_digest": digest, "evidence": evidence}


@router.post("/v1/persistence/expansion/attempts", responses=ERROR_RESPONSES)
@router.post("/v1/persistence/platform/attempts", responses=ERROR_RESPONSES)
async def persistence_expansion_attempt(
    request: PersistenceExpansionAttemptRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    await _allowed(session, request.challenge_id)
    observed_events = _event_count(session, request.challenge_id)
    evidence = _submitted_evidence(request)
    passed = challenge_satisfied(
        request.challenge_id, evidence, observed_events=observed_events
    )
    digest = digest_value({"challenge_id": request.challenge_id, **evidence})
    if passed:
        event_kind, _ = PERSISTENCE_EVIDENCE[request.challenge_id]
        await record_platform_proof(
            session,
            event_kind=event_kind,
            outcome_id=OUTCOME_ID,
            object_id=request.challenge_id,
            digest=digest,
            asset_id="inference-gateway",
            record_count=observed_events,
            extra_fields={"stage": "agent-persistence-expansion"},
        )
    return {
        "challenge_id": request.challenge_id,
        "objective_status": "passed" if passed else "not_satisfied",
        "observed_events": observed_events,
        "object_digest": digest,
    }
