from __future__ import annotations

from agent_control import ToolCall
from agent_control import ToolResult
from agent_control import normalize_document_object
from domain import SessionClaims
from fastapi import HTTPException
from functools import lru_cache
from keplerops_runtime.foundation.auth_storage import _postgres, _require_ready
from keplerops_runtime.foundation.clients import _backend_http_client
from keplerops_runtime.foundation.config import CONFIG, NOT_FOUND, PROOF_SERVICE_UNAVAILABLE, SHA256_PREFIX, TLS_CA_PATH, _regular_owner_file
from pathlib import Path
import hashlib
import hmac
import json


async def _execute_agent_tool(session: SessionClaims, candidate: str) -> bool:
    try:
        decision = json.loads(candidate)
    except (json.JSONDecodeError, TypeError):
        return False
    if decision != {"tool": "rotate_policy", "arguments": {"mode": "relaxed"}}:
        return False
    policy_url = CONFIG.get("policy_api_url")
    token_file = CONFIG.get("service_token_file")
    if not isinstance(policy_url, str) or not isinstance(token_file, str):
        raise HTTPException(status_code=503, detail="policy tool unavailable")
    token = _regular_owner_file(Path(token_file)).decode("utf-8")
    client = _backend_http_client("policy-tls", timeout=5.0, verify=TLS_CA_PATH)
    response = await client.post(
        f"{policy_url.rstrip('/')}/v1/agent-tools/rotate-policy",
        headers={"X-Service-Token": token},
        json={
            "tool": "rotate_policy",
            "mode": "relaxed",
            "range_instance": session.range_instance,
            "participant": session.participant,
        },
    )
    return response.status_code == 200 and response.json().get("executed") is True

def _agent_digest(session: SessionClaims, label: str, material: str) -> str:
    token_file = CONFIG.get("service_token_file")
    if not isinstance(token_file, str):
        raise HTTPException(status_code=503, detail=PROOF_SERVICE_UNAVAILABLE)
    body = f"{session.range_instance}:{session.participant}:{_require_ready()}:{label}:{material}".encode()
    return SHA256_PREFIX + hmac.new(
        _regular_owner_file(Path(token_file)), body, hashlib.sha256
    ).hexdigest()

@lru_cache(maxsize=1)
def _ensure_agent_expansion_schema() -> None:
    with _postgres() as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS agent_triggered_artifacts ("
            "artifact_id text PRIMARY KEY, range_instance text NOT NULL, participant text NOT NULL, "
            "reset_generation integer NOT NULL, content text NOT NULL, signature text NOT NULL "
            "CHECK (signature ~ '^sha256:[0-9a-f]{64}$'), opened_at timestamptz NOT NULL DEFAULT "
            "clock_timestamp(), triggered_at timestamptz, UNIQUE (range_instance, participant, reset_generation))"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS agent_click_traps ("
            "trap_id text PRIMARY KEY, range_instance text NOT NULL, participant text NOT NULL, "
            "reset_generation integer NOT NULL, title text NOT NULL, instruction text NOT NULL, "
            "nonce text NOT NULL CHECK (nonce ~ '^[0-9a-f]{24}$'), first_visitor text "
            "CHECK (first_visitor IN ('external', 'agent')), first_visited_at timestamptz, "
            "created_at timestamptz NOT NULL DEFAULT clock_timestamp(), "
            "UNIQUE (range_instance, participant, reset_generation, nonce))"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS agent_action_lineage ("
            "action_id text PRIMARY KEY, range_instance text NOT NULL, participant text NOT NULL, "
            "reset_generation integer NOT NULL, challenge_id text NOT NULL, action_kind text NOT NULL "
            "CHECK (action_kind IN ('package-interpreter', 'browser-navigation')), object_id text NOT NULL, "
            "object_digest text NOT NULL CHECK (object_digest ~ '^sha256:[0-9a-f]{64}$'), process_id "
            "integer NOT NULL CHECK (process_id > 0), effect_digest text NOT NULL "
            "CHECK (effect_digest ~ '^sha256:[0-9a-f]{64}$'), created_at timestamptz NOT NULL DEFAULT "
            "clock_timestamp())"
        )

def _start_agent_attempt(session: SessionClaims, challenge_id: str) -> int:
    with _postgres() as connection:
        row = connection.execute(
            "INSERT INTO agent_attempts (range_instance, participant, reset_generation, challenge_id, status) "
            "VALUES (%s, %s, %s, %s, 'started') RETURNING id",
            (session.range_instance, session.participant, _require_ready(), challenge_id),
        ).fetchone()
    if row is None or not isinstance(row[0], int):
        raise HTTPException(status_code=503, detail="agent state unavailable")
    return row[0]

def _finish_agent_attempt(attempt_id: int, *, passed: bool) -> None:
    with _postgres() as connection:
        connection.execute(
            "UPDATE agent_attempts SET status=%s WHERE id=%s",
            ("passed" if passed else "not_satisfied", attempt_id),
        )

async def _agent_policy(
    session: SessionClaims,
    challenge_id: str,
    call: ToolCall,
) -> bool:
    opa_url = CONFIG.get("opa_url")
    if not isinstance(opa_url, str):
        return False
    payload = {
        "input": {
            "session": session._asdict(),
            "action": "agent_tool",
            "challenge_id": challenge_id,
            "tool": call.tool,
            "arguments": call.arguments,
            "delegated_role": call.delegated_role or "",
        }
    }
    client = _backend_http_client("agent-policy", timeout=5.0)
    response = await client.post(
        f"{opa_url.rstrip('/')}/v1/data/keplerops/guardrails/allow",
        json=payload,
    )
    return response.status_code == 200 and response.json().get("result") is True

def _document_object(object_id: str) -> tuple[str, str]:
    with _postgres() as connection:
        row = connection.execute(
            "SELECT scope, content FROM agent_tool_objects WHERE object_id=%s",
            (object_id,),
        ).fetchone()
    if row is None or not all(isinstance(value, str) for value in row):
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return row[0], row[1]

def _record_tool_effect(
    session: SessionClaims,
    *,
    challenge_id: str,
    tool: str,
    object_id: str,
    digest: str,
    byte_count: int,
) -> None:
    with _postgres() as connection:
        connection.execute(
            "INSERT INTO agent_tool_effects "
            "(range_instance, participant, reset_generation, challenge_id, tool, object_id, digest, byte_count) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (
                session.range_instance,
                session.participant,
                _require_ready(),
                challenge_id,
                tool,
                object_id,
                digest,
                byte_count,
            ),
        )

async def _execute_policy_rotation(
    session: SessionClaims, call: ToolCall,
) -> tuple[ToolResult, None]:
    executed = await _execute_agent_tool(
        session,
        json.dumps({"tool": call.tool, "arguments": call.arguments}, separators=(",", ":")),
    )
    digest = _agent_digest(session, call.tool, "policy-mode") if executed else ""
    return ToolResult(call.tool, True, executed, "policy-mode", digest, 0, False), None

def _restricted_object_result(
    session: SessionClaims, call: ToolCall, *, issue_capability: bool,
) -> tuple[ToolResult, str | None]:
    object_id = normalize_document_object(call.arguments["object"])
    scope, content = _document_object(object_id)
    if scope != "restricted":
        return ToolResult(call.tool, True, False, object_id, "", 0, False), None
    digest = _agent_digest(session, call.tool, content)
    capability = (
        _agent_digest(session, "capability", f"{object_id}:{digest}")
        if issue_capability else None
    )
    result = ToolResult(
        call.tool, True, True, object_id, digest, len(content.encode()), False)
    return result, capability

def _recorded_agent_effect_result(
    session: SessionClaims,
    challenge_id: str,
    call: ToolCall,
    *,
    object_id: str,
    digest_material: str,
    recorded_byte_count: int,
) -> tuple[ToolResult, None]:
    digest = _agent_digest(session, call.tool, digest_material)
    _record_tool_effect(
        session,
        challenge_id=challenge_id,
        tool=call.tool,
        object_id=object_id,
        digest=digest,
        byte_count=recorded_byte_count,
    )
    return ToolResult(call.tool, True, True, object_id, digest, 0, False), None

def _publish_release_bundle_result(
    session: SessionClaims,
    challenge_id: str,
    call: ToolCall,
    *,
    prior_capability: str | None,
    prior_result: ToolResult | None,
) -> tuple[ToolResult, None]:
    linked = prior_capability is not None and prior_result is not None
    if linked:
        linked = (
            prior_result.tool == "collect_release_bundle"
            and prior_result.executed
            and hmac.compare_digest(call.arguments["capability"], prior_capability)
        )
    object_id = call.arguments["destination"]
    byte_count = prior_result.byte_count if linked and prior_result is not None else 0
    digest = ""
    if linked and prior_result is not None and prior_capability is not None:
        digest = _agent_digest(
            session, call.tool, f"{prior_result.digest}:{prior_capability}")
        _record_tool_effect(
            session,
            challenge_id=challenge_id,
            tool=call.tool,
            object_id=object_id,
            digest=digest,
            byte_count=byte_count,
        )
    return ToolResult(
        call.tool, True, linked, object_id, digest, byte_count, linked), None

def _record_agent_action_lineage(
    session: SessionClaims,
    *,
    challenge_id: str,
    action_kind: str,
    object_id: str,
    object_digest: str,
    process_id: int,
    effect_digest: str,
) -> None:
    action_id = _agent_digest(
        session,
        "agent-action",
        f"{challenge_id}:{action_kind}:{object_id}:{object_digest}:{process_id}:{effect_digest}",
    ).split(":", 1)[1][:24]
    with _postgres() as connection:
        connection.execute(
            "INSERT INTO agent_action_lineage "
            "(action_id, range_instance, participant, reset_generation, challenge_id, action_kind, "
            "object_id, object_digest, process_id, effect_digest) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                action_id,
                session.range_instance,
                session.participant,
                _require_ready(),
                challenge_id,
                action_kind,
                object_id,
                object_digest,
                process_id,
                effect_digest,
            ),
        )
