from __future__ import annotations

from domain import SessionClaims
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from keplerops_runtime.foundation.auth_storage import _bearer, _require_ready, _require_role, _session
from keplerops_runtime.foundation.clients import _backend_http_client
from keplerops_runtime.foundation.config import CONFIG, ERROR_RESPONSES, NOT_FOUND, PROOF_SERVICE_UNAVAILABLE, TLS_CA_PATH
from keplerops_runtime.foundation.contracts import _adversarial_challenge_contracts, _agent_challenge_contracts, _backdoor_challenge_contracts, _capstone_challenge_contracts, _context_challenge_contracts, _evasion_challenge_contracts, _extraction_challenge_contracts, _persistence_challenge_contracts, _secrets_challenge_contracts, _training_challenge_contracts
from keplerops_runtime.foundation.telemetry import _observe
from typing import Annotated
from typing import Any

router = APIRouter()


async def _challenge_receipt_proxy(
    flag_id: str,
    token: str,
    session: SessionClaims,
    *,
    contracts: dict[str, dict[str, Any]],
    outcome_id: str,
) -> dict[str, str]:
    _require_role("gateway")
    _require_ready()
    allowed = {row["flag_id"] for row in contracts.values()}
    if flag_id not in allowed:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    proof_url = CONFIG.get("proof_url")
    if not isinstance(proof_url, str):
        raise HTTPException(status_code=503, detail=PROOF_SERVICE_UNAVAILABLE)
    client = _backend_http_client("participant-proof", timeout=5.0, verify=TLS_CA_PATH)
    response = await client.post(
        f"{proof_url.rstrip('/')}/v1/receipts/{flag_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    if response.status_code == 409:
        raise HTTPException(status_code=409, detail="objective not satisfied")
    if response.status_code != 200:
        raise HTTPException(status_code=503, detail=PROOF_SERVICE_UNAVAILABLE)
    receipt_value = response.json().get("receipt")
    if not isinstance(receipt_value, str) or not 1 <= len(receipt_value) <= 8192:
        raise HTTPException(status_code=503, detail=PROOF_SERVICE_UNAVAILABLE)
    _observe(
        session,
        event_name="checkpoint.earned",
        outcome_id=outcome_id,
        challenge_id=next(
            row["challenge_id"]
            for row in contracts.values()
            if row["flag_id"] == flag_id
        ),
        status="passed",
        record_count=1,
    )
    return {"receipt": receipt_value}

@router.post("/v1/agent/receipts/{flag_id}", responses=ERROR_RESPONSES)
async def agent_receipt_proxy(
    flag_id: str,
    token: Annotated[str, Depends(_bearer)],
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, str]:
    return await _challenge_receipt_proxy(
        flag_id,
        token,
        session,
        contracts=_agent_challenge_contracts(),
        outcome_id="agent-control",
    )

@router.post("/v1/evasion/receipts/{flag_id}", responses=ERROR_RESPONSES)
async def evasion_receipt_proxy(
    flag_id: str,
    token: Annotated[str, Depends(_bearer)],
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, str]:
    return await _challenge_receipt_proxy(
        flag_id,
        token,
        session,
        contracts=_evasion_challenge_contracts(),
        outcome_id="model-evasion",
    )

@router.post("/v1/context/receipts/{flag_id}", responses=ERROR_RESPONSES)
async def context_receipt_proxy(
    flag_id: str,
    token: Annotated[str, Depends(_bearer)],
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, str]:
    return await _challenge_receipt_proxy(
        flag_id,
        token,
        session,
        contracts=_context_challenge_contracts(),
        outcome_id="context-poisoning",
    )

@router.post("/v1/secrets/receipts/{flag_id}", responses=ERROR_RESPONSES)
async def secrets_receipt_proxy(
    flag_id: str,
    token: Annotated[str, Depends(_bearer)],
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, str]:
    return await _challenge_receipt_proxy(
        flag_id,
        token,
        session,
        contracts=_secrets_challenge_contracts(),
        outcome_id="model-secrets",
    )

@router.post("/v1/persistence/receipts/{flag_id}", responses=ERROR_RESPONSES)
async def persistence_receipt_proxy(
    flag_id: str,
    token: Annotated[str, Depends(_bearer)],
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, str]:
    return await _challenge_receipt_proxy(
        flag_id,
        token,
        session,
        contracts=_persistence_challenge_contracts(),
        outcome_id="agent-persistence",
    )

@router.post("/v1/adversarial/receipts/{flag_id}", responses=ERROR_RESPONSES)
async def adversarial_receipt_proxy(
    flag_id: str,
    token: Annotated[str, Depends(_bearer)],
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, str]:
    return await _challenge_receipt_proxy(
        flag_id,
        token,
        session,
        contracts=_adversarial_challenge_contracts(),
        outcome_id="adversarial-input",
    )

@router.post("/v1/training/receipts/{flag_id}", responses=ERROR_RESPONSES)
async def training_receipt_proxy(
    flag_id: str,
    token: Annotated[str, Depends(_bearer)],
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, str]:
    return await _challenge_receipt_proxy(
        flag_id,
        token,
        session,
        contracts=_training_challenge_contracts(),
        outcome_id="training-poisoning",
    )

@router.post("/v1/extraction/receipts/{flag_id}", responses=ERROR_RESPONSES)
async def extraction_receipt_proxy(
    flag_id: str,
    token: Annotated[str, Depends(_bearer)],
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, str]:
    return await _challenge_receipt_proxy(
        flag_id,
        token,
        session,
        contracts=_extraction_challenge_contracts(),
        outcome_id="model-extraction",
    )

@router.post("/v1/backdoor/receipts/{flag_id}", responses=ERROR_RESPONSES)
async def backdoor_receipt_proxy(
    flag_id: str,
    token: Annotated[str, Depends(_bearer)],
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, str]:
    return await _challenge_receipt_proxy(
        flag_id,
        token,
        session,
        contracts=_backdoor_challenge_contracts(),
        outcome_id="model-backdoor",
    )

@router.post("/v1/capstone/receipts/{flag_id}", responses=ERROR_RESPONSES)
async def capstone_receipt_proxy(
    flag_id: str,
    token: Annotated[str, Depends(_bearer)],
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, str]:
    return await _challenge_receipt_proxy(
        flag_id,
        token,
        session,
        contracts=_capstone_challenge_contracts(),
        outcome_id="ai-capstone",
    )
