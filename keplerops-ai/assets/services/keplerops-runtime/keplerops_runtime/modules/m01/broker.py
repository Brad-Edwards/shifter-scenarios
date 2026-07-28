from __future__ import annotations

from agent_control import AgentPlan
from agent_control import ToolCall
from agent_control import ToolResult
from domain import SessionClaims
from fastapi import HTTPException
from keplerops_runtime.foundation.action_clients import _execute_agent_browser, _execute_agent_package
from keplerops_runtime.foundation.auth_storage import _postgres, _require_ready
from keplerops_runtime.foundation.clients import _backend_http_client
from keplerops_runtime.foundation.config import CONFIG, PUBLIC_WORKHUB_ISSUE_REQUIRED, PUBLIC_WORKHUB_UNAVAILABLE, TLS_CA_PATH
from keplerops_runtime.foundation.telemetry import _capture
from keplerops_runtime.modules.m01.constants import AGENT_EVIDENCE
from keplerops_runtime.modules.m01.store import _agent_digest, _ensure_agent_expansion_schema, _execute_policy_rotation, _publish_release_bundle_result, _recorded_agent_effect_result, _restricted_object_result
from typing import Any
import httpx
import time


async def _execute_broker_tool(
    session: SessionClaims,
    challenge_id: str,
    call: ToolCall,
    *,
    policy_allowed: bool,
    prior_capability: str | None,
    prior_result: ToolResult | None,
) -> tuple[ToolResult, str | None]:
    if not policy_allowed:
        return ToolResult(call.tool, False, False, call.arguments.get("target", ""), "", 0, False), None
    if call.tool == "rotate_policy":
        return await _execute_policy_rotation(session, call)
    if call.tool == "read_document":
        return _restricted_object_result(session, call, issue_capability=False)
    if call.tool == "approve_release":
        return _recorded_agent_effect_result(
            session,
            challenge_id,
            call,
            object_id=call.arguments["artifact"],
            digest_material=call.arguments["artifact"],
            recorded_byte_count=0,
        )
    if call.tool == "publish_notice":
        return _recorded_agent_effect_result(
            session,
            challenge_id,
            call,
            object_id=call.arguments["channel"],
            digest_material=call.arguments["message"],
            recorded_byte_count=len(call.arguments["message"].encode()),
        )
    if call.tool == "collect_release_bundle":
        return _restricted_object_result(session, call, issue_capability=True)
    if call.tool == "publish_release_bundle":
        return _publish_release_bundle_result(
            session,
            challenge_id,
            call,
            prior_capability=prior_capability,
            prior_result=prior_result,
        )
    if call.tool == "install_package":
        return await _execute_agent_package(session, challenge_id, call)
    if call.tool == "open_link":
        return await _execute_agent_browser(session, challenge_id, call)
    return ToolResult(call.tool, True, False, "", "", 0, False), None

def _agent_context(session: SessionClaims) -> tuple[str, str] | None:
    with _postgres() as connection:
        row = connection.execute(
            "SELECT id, content FROM agent_context_documents "
            "WHERE range_instance=%s AND participant=%s AND reset_generation=%s "
            "ORDER BY created_at DESC, id DESC LIMIT 1",
            (session.range_instance, session.participant, _require_ready()),
        ).fetchone()
    if row is None:
        return None
    if not all(isinstance(value, str) for value in row):
        raise HTTPException(status_code=503, detail="agent context unavailable")
    return row[0], row[1]

def _triggered_artifact_context(session: SessionClaims) -> tuple[str, str] | None:
    _ensure_agent_expansion_schema()
    with _postgres() as connection:
        row = connection.execute(
            "SELECT artifact_id, content FROM agent_triggered_artifacts "
            "WHERE range_instance=%s AND participant=%s AND reset_generation=%s "
            "AND triggered_at IS NOT NULL AND triggered_at > opened_at",
            (session.range_instance, session.participant, _require_ready()),
        ).fetchone()
    if row is None:
        return None
    if not all(isinstance(value, str) for value in row):
        raise HTTPException(status_code=503, detail="triggered artifact unavailable")
    return row[0], row[1]

async def _public_workhub_context(
    session: SessionClaims, source_ref: str | None,
) -> tuple[str, str] | None:
    if source_ref is None or not source_ref.isdigit() or not 1 <= len(source_ref) <= 10:
        raise HTTPException(status_code=409, detail=PUBLIC_WORKHUB_ISSUE_REQUIRED)
    issue_number = int(source_ref)
    if str(issue_number) != source_ref:
        raise HTTPException(status_code=409, detail=PUBLIC_WORKHUB_ISSUE_REQUIRED)
    workhub_url = CONFIG.get("workhub_url")
    if not isinstance(workhub_url, str):
        raise HTTPException(status_code=503, detail=PUBLIC_WORKHUB_UNAVAILABLE)
    client = _backend_http_client("public-workhub", timeout=8.0, verify=TLS_CA_PATH)
    try:
        response = await client.get(f"{workhub_url.rstrip('/')}/issues/{issue_number}.json")
    except httpx.HTTPError:
        raise HTTPException(status_code=503, detail=PUBLIC_WORKHUB_UNAVAILABLE) from None
    if response.status_code == 404:
        raise HTTPException(status_code=409, detail=PUBLIC_WORKHUB_ISSUE_REQUIRED)
    if response.status_code != 200:
        raise HTTPException(status_code=503, detail=PUBLIC_WORKHUB_UNAVAILABLE)
    try:
        issue = response.json()["issue"]
        issue_id = issue["id"]
        author_name = issue["author"]["name"]
        description = issue["description"]
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=503, detail=PUBLIC_WORKHUB_UNAVAILABLE) from None
    if (
        str(issue_id) != source_ref
        or author_name != "Anonymous"
        or not isinstance(description, str)
        or not 32 <= len(description.encode("utf-8")) <= 4096
    ):
        raise HTTPException(status_code=409, detail="anonymous public prompt required")
    _capture(session, signal="http_body", content=description)
    return f"redmine-issue-{source_ref}", description

def _record_agent_evidence(
    session: SessionClaims,
    plan: AgentPlan,
    results: tuple[ToolResult, ...],
    *,
    context_id: str | None,
) -> dict[str, Any]:
    challenge_id = plan.challenge_id
    event_kind, _ = AGENT_EVIDENCE[challenge_id]
    object_id = results[-1].object_id or plan.calls[-1].tool
    event: dict[str, Any] = {
        "actor_role": "participant",
        "asset_id": "inference-gateway",
        "digest": _agent_digest(
            session,
            challenge_id,
            ":".join(result.digest or result.tool for result in results),
        ),
        "event_kind": event_kind,
        "object_id": object_id,
        "outcome_id": "agent-control",
        "participant": session.participant,
        "range_instance": session.range_instance,
        "status": "passed",
        "timestamp": int(time.time()),
    }
    if challenge_id == "kep-m01-a":
        event["stage"] = "policy-denied"
    elif challenge_id == "kep-m01-b":
        event["record_count"] = 2
    elif challenge_id == "kep-m01-d":
        event["stage"] = "delegated-release-manager"
    elif challenge_id == "kep-m01-e":
        event["record_count"] = 2
        event["workflow_id"] = context_id or "missing-context"
    elif challenge_id == "kep-m01-f":
        event["byte_count"] = results[0].byte_count
        event["destination"] = results[-1].object_id
        event["record_count"] = 2
    elif challenge_id == "kep-m01-g":
        event["record_count"] = 4
        event["stage"] = "future-trigger"
        event["workflow_id"] = context_id or "missing-artifact"
    elif challenge_id == "kep-m01-h":
        event["byte_count"] = results[0].byte_count
        event["record_count"] = 4
        event["stage"] = "package-interpreter"
    elif challenge_id == "kep-m01-i":
        event["byte_count"] = results[0].byte_count
        event["record_count"] = 4
        event["stage"] = "model-browser-click"
        event["workflow_id"] = context_id or "missing-click-trap"
    elif challenge_id == "kep-m01-j":
        event["record_count"] = 4
        event["stage"] = "anonymous-workhub-ingestion"
        event["workflow_id"] = context_id or "missing-workhub-issue"
    return event
