from __future__ import annotations

from domain import SessionClaims
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from keplerops_runtime.foundation.auth_storage import _require_ready, _require_role, _session
from keplerops_runtime.foundation.clients import _persistence_worker_request
from keplerops_runtime.foundation.config import ACTION_DENIED, AGENT_WORKER_UNAVAILABLE, ATTEMPT_STARTED_EVENT, ERROR_RESPONSES, PERSISTENCE_TURN_PATH, WORKFLOW_COMPLETED_EVENT, WORKFLOW_STARTED_EVENT
from keplerops_runtime.foundation.policy_client import _policy
from keplerops_runtime.foundation.telemetry import _observe
from keplerops_runtime.modules.m01.store import _agent_digest
from keplerops_runtime.modules.m05 import PersistenceTurnRequest
from keplerops_runtime.modules.m05.service import _activate_persistence_memory, _persistence_worker_scope, _plant_persistence_memory
from typing import Annotated
from typing import Any
import asyncio
import time

router = APIRouter()


@router.post(PERSISTENCE_TURN_PATH, responses=ERROR_RESPONSES)
async def persistence_turn(
    request: PersistenceTurnRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    _require_ready()
    if not await _policy(session, "infer"):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)
    started = time.monotonic_ns()
    _observe(
        session,
        event_name=ATTEMPT_STARTED_EVENT,
        outcome_id="agent-persistence",
        challenge_id=request.challenge_id,
        status="recorded",
        path_variant=request.phase,
        participant_interface=request.participant_interface,
        assistance_mode=request.assistance_mode,
    )
    if request.phase == "plant":
        return await _plant_persistence_memory(request, session, started=started)
    return await _activate_persistence_memory(request, session, started=started)

async def _wait_for_worker_restart(old_boot_id: str) -> tuple[dict[str, Any], int]:
    for retry in range(40):
        await asyncio.sleep(0.25)
        try:
            async with asyncio.timeout(1.0):
                current = await _persistence_worker_request("GET", "/healthz")
        except TimeoutError:
            continue
        except HTTPException as error:
            if error.status_code != 503:
                raise
            continue
        if current.get("boot_id") != old_boot_id:
            return current, retry + 1
    raise HTTPException(status_code=503, detail="agent state worker restart failed")

@router.post("/v1/persistence/restart", responses=ERROR_RESPONSES)
async def restart_persistence_worker(
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    _require_ready()
    if not await _policy(session, "infer"):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)
    scope = _persistence_worker_scope(session)
    started = time.monotonic_ns()
    _observe(
        session,
        event_name=WORKFLOW_STARTED_EVENT,
        outcome_id="agent-persistence",
        challenge_id="kep-m05-d",
        status="recorded",
        path_variant="worker-restart",
    )
    accepted = await _persistence_worker_request(
        "POST", "/v1/restart", payload=scope
    )
    old_boot_id = accepted.get("old_boot_id")
    if not isinstance(old_boot_id, str):
        raise HTTPException(status_code=503, detail=AGENT_WORKER_UNAVAILABLE)
    current, retries = await _wait_for_worker_restart(old_boot_id)
    new_boot_id = current.get("boot_id")
    if not isinstance(new_boot_id, str):
        raise HTTPException(status_code=503, detail=AGENT_WORKER_UNAVAILABLE)
    attested = await _persistence_worker_request(
        "POST",
        "/v1/restart/attest",
        payload={
            **scope,
            "old_boot_id": old_boot_id,
            "new_boot_id": new_boot_id,
        },
    )
    restart_id = attested.get("restart_id")
    if not isinstance(restart_id, str):
        raise HTTPException(status_code=503, detail=AGENT_WORKER_UNAVAILABLE)
    _observe(
        session,
        event_name=WORKFLOW_COMPLETED_EVENT,
        outcome_id="agent-persistence",
        challenge_id="kep-m05-d",
        status="passed",
        duration_ms=(time.monotonic_ns() - started) // 1_000_000,
        retry_count=retries,
        workflow_run_id=restart_id,
        path_variant="worker-restart",
        restart_verified=True,
        prior_worker_boot_digest=_agent_digest(
            session, "restart-old-boot", old_boot_id
        ),
        worker_boot_digest=_agent_digest(
            session, "restart-new-boot", new_boot_id
        ),
    )
    return {
        "status": "restarted",
        "restart_id": restart_id,
        "old_boot_id": old_boot_id,
        "new_boot_id": new_boot_id,
    }
