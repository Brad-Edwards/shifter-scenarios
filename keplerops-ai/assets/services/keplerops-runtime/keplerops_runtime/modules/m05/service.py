from __future__ import annotations

from agent_control import ToolCall
from agent_persistence import AgentPersistenceError
from agent_persistence import MemoryState
from agent_persistence import MemoryWrite
from agent_persistence import PersistenceToolCall
from agent_persistence import PersistenceToolResult
from agent_persistence import activation_satisfied
from domain import SessionClaims
from fastapi import HTTPException
from keplerops_runtime.foundation.auth_storage import _require_ready
from keplerops_runtime.foundation.clients import _model_completion, _persistence_worker_request, _record_event
from keplerops_runtime.foundation.config import AGENT_WORKER_UNAVAILABLE, ATTEMPT_COMPLETED_EVENT, OBJECTIVE_SATISFIED_EVENT
from keplerops_runtime.foundation.contracts import _revision
from keplerops_runtime.foundation.schemas import ModelCompletion
from keplerops_runtime.foundation.telemetry import _capture, _observe
from keplerops_runtime.modules.m01.broker import _execute_broker_tool
from keplerops_runtime.modules.m01.engine import _participant_tool_results
from keplerops_runtime.modules.m01.store import _agent_digest, _agent_policy
from keplerops_runtime.modules.m05 import PersistenceTurnRequest
from keplerops_runtime.modules.m05.constants import PERSISTENCE_EVIDENCE, PERSISTENCE_PLANT_SYSTEM, PERSISTENCE_STAGES, PERSISTENCE_USE_SYSTEM
from typing import Any
import json
import time


def _persistence_prompt_digest(
    session: SessionClaims, request: PersistenceTurnRequest,
) -> str:
    return _agent_digest(
        session,
        "agent-persistence-prompt",
        f"{request.phase}:{request.session_id}:{request.thread_id}:{request.prompt}",
    )

def _persistence_worker_scope(session: SessionClaims) -> dict[str, Any]:
    return {
        "range_instance": session.range_instance,
        "participant": session.participant,
        "reset_generation": _require_ready(),
    }

def _memory_state_from_worker(payload: dict[str, Any]) -> MemoryState:
    try:
        return MemoryState(
            state_id=payload["state_id"],
            state_version=payload["state_version"],
            state_digest=payload["state_digest"],
            marker=payload["marker"],
            memory=payload["memory"],
            plant_session_id=payload["plant_session_id"],
            plant_thread_id=payload["plant_thread_id"],
            plant_boot_id=payload["plant_boot_id"],
            plant_prompt_digest=payload["plant_prompt_digest"],
            use_count=payload["use_count"],
        )
    except (KeyError, TypeError):
        raise HTTPException(
            status_code=503, detail=AGENT_WORKER_UNAVAILABLE
        ) from None

def _persistence_observation(
    session: SessionClaims,
    request: PersistenceTurnRequest,
    state: MemoryState,
    worker: dict[str, Any],
) -> dict[str, Any]:
    current_boot = str(worker.get("boot_id", ""))
    return {
        "challenge_id": request.challenge_id,
        "participant_interface": request.participant_interface,
        "assistance_mode": request.assistance_mode,
        "path_variant": PERSISTENCE_STAGES[request.challenge_id],
        "state_version": state.state_version,
        "record_count": state.use_count,
        "artifact_digest": state.state_digest,
        "state_digest": _agent_digest(
            session,
            "persistence-boundaries",
            ":".join((
                state.plant_session_id,
                request.session_id,
                state.plant_thread_id,
                request.thread_id,
                state.plant_boot_id,
                current_boot,
            )),
        ),
        "plant_session_digest": _agent_digest(
            session, "plant-session", state.plant_session_id
        ),
        "use_session_digest": _agent_digest(
            session, "use-session", request.session_id
        ),
        "plant_thread_digest": _agent_digest(
            session, "plant-thread", state.plant_thread_id
        ),
        "use_thread_digest": _agent_digest(
            session, "use-thread", request.thread_id
        ),
        "prior_worker_boot_digest": _agent_digest(
            session, "plant-boot", state.plant_boot_id
        ),
        "worker_boot_digest": _agent_digest(
            session, "use-boot", current_boot
        ),
        "restart_verified": worker.get("restart_verified") is True,
        "retrieval_used": True,
        "model_revision": _revision("model_revision"),
        "policy_revision": _revision("policy_revision"),
    }

async def _plant_persistence_memory(
    request: PersistenceTurnRequest,
    session: SessionClaims,
    *,
    started: int,
) -> dict[str, Any]:
    if request.challenge_id != "kep-m05-a":
        raise HTTPException(status_code=409, detail="memory plant begins with kep-m05-a")
    prompt_digest = _persistence_prompt_digest(session, request)
    _capture(session, signal="prompt", content=request.prompt)
    completion = await _model_completion(PERSISTENCE_PLANT_SYSTEM, request.prompt)
    _capture(session, signal="completion", content=completion.content)
    try:
        memory_write = MemoryWrite.from_model_output(completion.content)
    except AgentPersistenceError:
        _observe(
            session,
            event_name=ATTEMPT_COMPLETED_EVENT,
            outcome_id="agent-persistence",
            challenge_id=request.challenge_id,
            status="rejected",
            duration_ms=(time.monotonic_ns() - started) // 1_000_000,
            token_count=completion.token_count,
            query_count=1,
            failure_class="model-memory-write-invalid",
            verdict_class="not-satisfied",
            participant_interface=request.participant_interface,
            assistance_mode=request.assistance_mode,
        )
        return {
            "challenge_id": request.challenge_id,
            "phase": "plant",
            "model": "keplerops-teacher",
            "content": completion.content,
            "objective_status": "not_satisfied",
        }
    worker = await _persistence_worker_request(
        "POST",
        "/v1/memory",
        payload={
            **_persistence_worker_scope(session),
            "session_id": request.session_id,
            "thread_id": request.thread_id,
            "prompt_digest": prompt_digest,
            "memory": memory_write.memory,
            "marker": memory_write.marker,
        },
    )
    state_version = worker.get("state_version")
    state_digest = worker.get("state_digest")
    boot_id = worker.get("boot_id")
    if (
        not isinstance(state_version, int)
        or isinstance(state_version, bool)
        or state_version < 1
        or not isinstance(state_digest, str)
        or not isinstance(boot_id, str)
    ):
        raise HTTPException(status_code=503, detail=AGENT_WORKER_UNAVAILABLE)
    _observe(
        session,
        event_name=ATTEMPT_COMPLETED_EVENT,
        outcome_id="agent-persistence",
        challenge_id=request.challenge_id,
        status="recorded",
        duration_ms=(time.monotonic_ns() - started) // 1_000_000,
        token_count=completion.token_count,
        query_count=1,
        state_version=state_version,
        artifact_digest=state_digest,
        path_variant="memory-plant",
        participant_interface=request.participant_interface,
        assistance_mode=request.assistance_mode,
        model_revision=_revision("model_revision"),
    )
    return {
        "challenge_id": request.challenge_id,
        "phase": "plant",
        "model": "keplerops-teacher",
        "content": completion.content,
        "objective_status": "pending_later_interaction",
        "state_version": state_version,
        "state_digest": state_digest,
        "worker_boot_id": boot_id,
    }

async def _persistent_deputy_result(
    session: SessionClaims,
    request: PersistenceTurnRequest,
    completion: ModelCompletion,
) -> tuple[PersistenceToolCall | None, PersistenceToolResult | None, list[dict[str, Any]]]:
    if request.challenge_id != "kep-m05-e":
        return None, None, []
    try:
        call = PersistenceToolCall.from_model_output(completion.content)
    except AgentPersistenceError:
        return None, None, []
    broker_call = ToolCall(call.tool, call.arguments)
    allowed = await _agent_policy(session, request.challenge_id, broker_call)
    raw, _ = await _execute_broker_tool(
        session,
        request.challenge_id,
        broker_call,
        policy_allowed=allowed,
        prior_capability=None,
        prior_result=None,
    )
    result = PersistenceToolResult(
        raw.tool, raw.policy_allowed, raw.executed, raw.object_id, raw.digest
    )
    safe = _participant_tool_results((raw,))
    _capture(session, signal="tool_call", content=completion.content)
    _capture(session, signal="tool_result", content=json.dumps(safe, separators=(",", ":")))
    return call, result, safe

async def _record_persistence_evidence(
    session: SessionClaims,
    request: PersistenceTurnRequest,
    state: MemoryState,
    worker: dict[str, Any],
    tool_result: PersistenceToolResult | None,
) -> None:
    event_kind, _ = PERSISTENCE_EVIDENCE[request.challenge_id]
    event: dict[str, Any] = {
        "actor_role": "participant",
        "asset_id": "inference-gateway",
        "digest": state.state_digest,
        "event_kind": event_kind,
        "object_id": state.state_id,
        "outcome_id": "agent-persistence",
        "participant": session.participant,
        "range_instance": session.range_instance,
        "record_count": state.use_count,
        "stage": PERSISTENCE_STAGES[request.challenge_id],
        "status": "passed",
        "timestamp": int(time.time()),
    }
    restart_id = worker.get("restart_id")
    if isinstance(restart_id, str):
        event["workflow_id"] = restart_id
    if tool_result is not None:
        event["destination"] = tool_result.object_id
        event["byte_count"] = len(state.marker.encode("utf-8"))
    await _record_event(event)

async def _activate_persistence_memory(
    request: PersistenceTurnRequest,
    session: SessionClaims,
    *,
    started: int,
) -> dict[str, Any]:
    prompt_digest = _persistence_prompt_digest(session, request)
    worker = await _persistence_worker_request(
        "POST",
        "/v1/memory/use",
        payload={
            **_persistence_worker_scope(session),
            "challenge_id": request.challenge_id,
            "session_id": request.session_id,
            "thread_id": request.thread_id,
            "prompt_digest": prompt_digest,
        },
    )
    state = _memory_state_from_worker(worker)
    memory = state.memory
    _capture(session, signal="prompt", content=request.prompt)
    completion = await _model_completion(
        PERSISTENCE_USE_SYSTEM + memory,
        request.prompt,
    )
    _capture(session, signal="completion", content=completion.content)
    call, result, safe_results = await _persistent_deputy_result(
        session, request, completion
    )
    passed = activation_satisfied(
        request.challenge_id,
        state=state,
        use_session_id=request.session_id,
        use_thread_id=request.thread_id,
        current_boot_id=str(worker.get("boot_id", "")),
        clean_prompt=request.prompt,
        clean_prompt_digest=prompt_digest,
        completion=completion.content,
        restart_verified=worker.get("restart_verified") is True,
        tool_call=call,
        tool_result=result,
    )
    effect_digest = _agent_digest(
        session,
        f"{request.challenge_id}-persistence-effect",
        f"{completion.content}:{result.digest if result is not None else ''}",
    )
    await _persistence_worker_request(
        "POST",
        "/v1/memory/use/complete",
        payload={
            "use_id": worker.get("use_id"),
            "status": "passed" if passed else "not_satisfied",
            "effect_digest": effect_digest,
            "tool_executed": result is not None and result.executed,
        },
    )
    common = _persistence_observation(session, request, state, worker)
    duration_ms = (time.monotonic_ns() - started) // 1_000_000
    _observe(
        session,
        event_name=ATTEMPT_COMPLETED_EVENT,
        outcome_id="agent-persistence",
        status="passed" if passed else "rejected",
        duration_ms=duration_ms,
        token_count=completion.token_count,
        query_count=1,
        verdict_class="passed" if passed else "not-satisfied",
        tool_effect=result is not None and result.executed,
        **common,
    )
    if passed:
        await _record_persistence_evidence(session, request, state, worker, result)
        _observe(
            session,
            event_name=OBJECTIVE_SATISFIED_EVENT,
            outcome_id="agent-persistence",
            status="passed",
            duration_ms=duration_ms,
            token_count=completion.token_count,
            query_count=1,
            tool_effect=result is not None and result.executed,
            **common,
        )
    return {
        "challenge_id": request.challenge_id,
        "phase": "activate",
        "model": "keplerops-teacher",
        "content": completion.content,
        "objective_status": "passed" if passed else "not_satisfied",
        "state_version": state.state_version,
        "state_digest": state.state_digest,
        "worker_boot_id": worker.get("boot_id"),
        "restart_verified": worker.get("restart_verified") is True,
        "tool_results": safe_results,
    }
