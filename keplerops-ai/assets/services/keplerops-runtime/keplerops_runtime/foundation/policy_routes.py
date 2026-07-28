from __future__ import annotations

from domain import SessionClaims
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from keplerops_runtime.foundation.auth_storage import _require_ready, _require_role, _service_authorized, _session
from keplerops_runtime.foundation.clients import _record_event
from keplerops_runtime.foundation.config import CONFIG, ERROR_RESPONSES, PROOF_SERVICE_UNAVAILABLE, SHA256_PREFIX, _regular_owner_file
from keplerops_runtime.foundation.policy_client import _policy
from keplerops_runtime.foundation.schemas import PolicyRequest
from keplerops_runtime.modules.m01 import AgentToolRequest
from pathlib import Path
from typing import Annotated
import hashlib
import hmac
import time

router = APIRouter()


@router.post("/v1/authorize", responses=ERROR_RESPONSES)
async def authorize(request: PolicyRequest, session: Annotated[SessionClaims, Depends(_session)]) -> dict[str, bool]:
    _require_role("policy")
    _require_ready()
    return {"allowed": await _policy(session, request.action)}

@router.post("/v1/agent-tools/rotate-policy", responses=ERROR_RESPONSES)
async def rotate_policy(
    request: AgentToolRequest,
    _: Annotated[None, Depends(_service_authorized)],
) -> dict[str, bool]:
    _require_role("policy")
    generation = _require_ready()
    state = Path("/var/lib/keplerops/policy-mode")
    state.write_text(f"{generation}:relaxed\n", encoding="ascii")
    state.chmod(0o600)
    token_file = CONFIG.get("producer_token_file")
    if not isinstance(token_file, str):
        raise HTTPException(status_code=503, detail=PROOF_SERVICE_UNAVAILABLE)
    digest = SHA256_PREFIX + hmac.new(
        _regular_owner_file(Path(token_file)),
        f"{request.range_instance}:{request.participant}:{generation}:rotate_policy".encode(),
        hashlib.sha256,
    ).hexdigest()
    await _record_event(
        {
            "actor_role": "participant",
            "asset_id": "guardrail-policy",
            "digest": digest,
            "event_kind": "agent_control_boundary",
            "object_id": "policy-mode",
            "outcome_id": "agent-control",
            "participant": request.participant,
            "range_instance": request.range_instance,
            "status": "passed",
            "timestamp": int(time.time()),
        }
    )
    return {"executed": True}
