from __future__ import annotations

from fastapi import APIRouter
from keplerops_runtime.foundation.auth_storage import _require_ready
from keplerops_runtime.foundation.clients import _persistence_worker_request
from keplerops_runtime.foundation.config import CONFIG, ERROR_RESPONSES
from keplerops_runtime.foundation.contracts import _flag_contracts, _oracle_contract, _realized_challenge_contracts
from keplerops_runtime.modules.m03.index import _ensure_trusted_context_chunks

router = APIRouter()


@router.get("/healthz", responses=ERROR_RESPONSES)
async def health() -> dict[str, str]:
    _require_ready()
    if CONFIG["role"] == "gateway":
        _ensure_trusted_context_chunks()
        await _persistence_worker_request("GET", "/healthz")
    elif CONFIG["role"] == "proof":
        _oracle_contract()
        _flag_contracts()
        _realized_challenge_contracts()
    return {"status": "ready", "role": CONFIG["role"]}
