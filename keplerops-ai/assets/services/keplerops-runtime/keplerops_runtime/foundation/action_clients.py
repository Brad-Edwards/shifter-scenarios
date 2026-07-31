from __future__ import annotations

from agent_control import ToolCall
from agent_control import ToolResult
from domain import SessionClaims
from fastapi import HTTPException
from keplerops_runtime.foundation.auth_storage import _postgres, _require_ready
from keplerops_runtime.foundation.clients import _backend_http_client
from keplerops_runtime.foundation.config import AGENT_ACTION_WORKER_UNAVAILABLE, CONFIG, SHA256_DIGEST_PATTERN
from keplerops_runtime.modules.m01.constants import AGENT_PACKAGE_DIGEST, AGENT_PACKAGE_PATH
from keplerops_runtime.modules.m01.store import _agent_digest, _ensure_agent_expansion_schema, _record_agent_action_lineage, _record_tool_effect
from typing import Any
import httpx
import time


async def _agent_action_request(path: str, body: dict[str, str]) -> dict[str, Any]:
    base_url = CONFIG.get("agent_action_worker_url")
    if not isinstance(base_url, str):
        raise HTTPException(status_code=503, detail=AGENT_ACTION_WORKER_UNAVAILABLE)
    client = _backend_http_client("agent-action-worker", timeout=15.0)
    try:
        response = await client.post(f"{base_url.rstrip('/')}{path}", json=body)
    except httpx.HTTPError:
        raise HTTPException(status_code=503, detail=AGENT_ACTION_WORKER_UNAVAILABLE) from None
    if response.status_code == 422:
        return {"executed": False}
    if response.status_code != 200:
        raise HTTPException(status_code=503, detail=AGENT_ACTION_WORKER_UNAVAILABLE)
    try:
        payload = response.json()
    except ValueError:
        raise HTTPException(status_code=503, detail=AGENT_ACTION_WORKER_UNAVAILABLE) from None
    if not isinstance(payload, dict):
        raise HTTPException(status_code=503, detail=AGENT_ACTION_WORKER_UNAVAILABLE)
    return payload

async def _package_worker_request(
    config_key: str, path: str, body: dict[str, object]
) -> dict[str, Any]:
    base_url = CONFIG.get(config_key)
    if not isinstance(base_url, str):
        raise HTTPException(status_code=503, detail=AGENT_ACTION_WORKER_UNAVAILABLE)
    client = _backend_http_client(f"package-{config_key}", timeout=30.0)
    try:
        response = await client.post(f"{base_url.rstrip('/')}{path}", json=body)
    except httpx.HTTPError:
        raise HTTPException(
            status_code=503, detail=AGENT_ACTION_WORKER_UNAVAILABLE
        ) from None
    if response.status_code == 422:
        raise HTTPException(
            status_code=422, detail="package worker rejected the artifact"
        )
    if response.status_code != 200:
        raise HTTPException(status_code=503, detail=AGENT_ACTION_WORKER_UNAVAILABLE)
    try:
        payload = response.json()
    except ValueError:
        raise HTTPException(
            status_code=503, detail=AGENT_ACTION_WORKER_UNAVAILABLE
        ) from None
    if not isinstance(payload, dict):
        raise HTTPException(status_code=503, detail=AGENT_ACTION_WORKER_UNAVAILABLE)
    return payload

def _positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0

def _valid_sha256_digest(value: object) -> bool:
    return isinstance(value, str) and SHA256_DIGEST_PATTERN.fullmatch(value) is not None

async def _execute_agent_package(
    session: SessionClaims, challenge_id: str, call: ToolCall,
) -> tuple[ToolResult, None]:
    workhub_url = CONFIG.get("workhub_url")
    if not isinstance(workhub_url, str):
        raise HTTPException(status_code=503, detail=AGENT_ACTION_WORKER_UNAVAILABLE)
    nonce = _agent_digest(session, "package-run", str(time.time_ns())).split(":", 1)[1][:24]
    payload = await _agent_action_request(
        "/v1/packages/run",
        {
            "package_url": f"{workhub_url.rstrip('/')}{AGENT_PACKAGE_PATH}",
            "expected_digest": AGENT_PACKAGE_DIGEST,
            "nonce": nonce,
        },
    )
    process_id = payload.get("process_id")
    effect_digest = payload.get("effect_digest")
    byte_count = payload.get("byte_count")
    executed = payload.get("executed") is True
    executed = executed and payload.get("package_digest") == AGENT_PACKAGE_DIGEST
    executed = executed and _positive_int(process_id) and _positive_int(byte_count)
    executed = executed and _valid_sha256_digest(effect_digest)
    object_id = f"{call.arguments['package']}@{call.arguments['version']}"
    if not executed:
        return ToolResult(call.tool, True, False, object_id, "", 0, False), None
    _record_agent_action_lineage(
        session,
        challenge_id=challenge_id,
        action_kind="package-interpreter",
        object_id=object_id,
        object_digest=AGENT_PACKAGE_DIGEST,
        process_id=process_id,
        effect_digest=effect_digest,
    )
    _record_tool_effect(
        session,
        challenge_id=challenge_id,
        tool=call.tool,
        object_id=object_id,
        digest=AGENT_PACKAGE_DIGEST,
        byte_count=byte_count,
    )
    return ToolResult(
        call.tool, True, True, object_id, AGENT_PACKAGE_DIGEST, byte_count, True), None

def _claim_agent_click(session: SessionClaims, url: str) -> tuple[str, str] | None:
    trap_id = url.rstrip("/").rsplit("/", 1)[-1]
    _ensure_agent_expansion_schema()
    with _postgres() as connection:
        row = connection.execute(
            "UPDATE agent_click_traps SET first_visitor='agent', first_visited_at=clock_timestamp() "
            "WHERE trap_id=%s AND range_instance=%s AND participant=%s AND reset_generation=%s "
            "AND first_visitor IS NULL RETURNING nonce, instruction",
            (trap_id, session.range_instance, session.participant, _require_ready()),
        ).fetchone()
    if row is None or not all(isinstance(value, str) for value in row):
        return None
    return row[0], row[1]

async def _execute_agent_browser(
    session: SessionClaims, challenge_id: str, call: ToolCall,
) -> tuple[ToolResult, str | None]:
    url = call.arguments["url"]
    claimed = _claim_agent_click(session, url)
    if claimed is None:
        return ToolResult(call.tool, True, False, url, "", 0, False), None
    nonce, _ = claimed
    payload = await _agent_action_request("/v1/browser/open", {"url": url})
    process_id = payload.get("browser_pid")
    dom = payload.get("dom")
    dom_digest = payload.get("dom_digest")
    byte_count = payload.get("byte_count")
    executed = payload.get("rendered") is True
    executed = executed and _positive_int(process_id) and _positive_int(byte_count)
    executed = executed and isinstance(dom, str) and nonce in dom
    executed = executed and _valid_sha256_digest(dom_digest)
    if not executed:
        return ToolResult(call.tool, True, False, url, "", 0, False), None
    _record_agent_action_lineage(
        session,
        challenge_id=challenge_id,
        action_kind="browser-navigation",
        object_id=url,
        object_digest=dom_digest,
        process_id=process_id,
        effect_digest=dom_digest,
    )
    _record_tool_effect(
        session,
        challenge_id=challenge_id,
        tool=call.tool,
        object_id=url,
        digest=dom_digest,
        byte_count=byte_count,
    )
    return ToolResult(call.tool, True, True, url, dom_digest, byte_count, True), dom
