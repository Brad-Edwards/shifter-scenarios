from __future__ import annotations

from domain import DomainError
from domain import EvidenceEvent
from domain import ResearchObservation
from domain import derive_research_context
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Response
from keplerops_runtime.foundation.auth_storage import _database, _producer_authorized, _require_ready, _require_role
from keplerops_runtime.foundation.config import CONFIG, ERROR_RESPONSES, PROOF_CONTRACT_UNAVAILABLE, _regular_owner_file
from keplerops_runtime.foundation.contracts import _oracle_contract, _research_contract, _research_store
from keplerops_runtime.proof import EvidenceRequest, ResearchContentRequest, ResearchEventRequest
from pathlib import Path
from typing import Annotated
import json
import time

router = APIRouter()


@router.post("/v1/evidence", status_code=204, response_class=Response, responses=ERROR_RESPONSES)
def record_evidence(
    request: EvidenceRequest,
    producer: Annotated[str, Depends(_producer_authorized)],
) -> Response:
    _require_role("proof")
    generation = _require_ready()
    safe_fields = CONFIG.get("safe_fields")
    if not isinstance(safe_fields, list) or any(not isinstance(item, str) for item in safe_fields):
        raise HTTPException(status_code=503, detail=PROOF_CONTRACT_UNAVAILABLE)
    try:
        event = EvidenceEvent.from_mapping(request.event, safe_fields=set(safe_fields))
        contract = _oracle_contract()
        evidence_id, expires_at = contract.qualify_event(
            event,
            producer_asset=producer,
            submitted_generation=request.reset_generation,
            current_generation=generation,
            now=int(time.time()),
        )
    except DomainError:
        raise HTTPException(status_code=422, detail="invalid evidence") from None
    with _database() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO evidence VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                event.values["range_instance"],
                event.values["participant"],
                event.values["outcome_id"],
                evidence_id,
                request.reset_generation,
                producer,
                event.values["timestamp"],
                expires_at,
                json.dumps(event.values, separators=(",", ":"), sort_keys=True),
            ),
        )
    return Response(status_code=204)

@router.post("/v1/research/events", status_code=202, responses=ERROR_RESPONSES)
def record_research_event(
    request: ResearchEventRequest,
    producer: Annotated[str, Depends(_producer_authorized)],
) -> dict[str, bool]:
    _require_role("proof")
    current_generation = _require_ready()
    if request.reset_generation > current_generation:
        raise HTTPException(status_code=422, detail="invalid research event")
    try:
        contract = _research_contract()
        observation = ResearchObservation.from_mapping(
            request.event,
            contract=contract,
            source_id=producer,
        )
        _research_store().record_observation(
            observation,
            source_id=producer,
            range_instance=request.range_instance,
            participant=request.participant,
            reset_generation=request.reset_generation,
            observed_at=time.time_ns(),
        )
    except DomainError:
        raise HTTPException(status_code=422, detail="invalid research event") from None
    return {"accepted": True}

@router.post("/v1/research/content", status_code=202, responses=ERROR_RESPONSES)
def record_research_content(
    request: ResearchContentRequest,
    _: Annotated[str, Depends(_producer_authorized)],
) -> dict[str, bool]:
    _require_role("proof")
    current_generation = _require_ready()
    if request.reset_generation > current_generation:
        raise HTTPException(status_code=422, detail="invalid research content")
    try:
        store = _research_store()
        context = derive_research_context(
            key=_regular_owner_file(Path(str(CONFIG["research_pseudonym_key_file"]))),
            range_instance=request.range_instance,
            participant=request.participant,
            reset_generation=request.reset_generation,
        )
        stored = store.record_content(
            session_id=context.session_id,
            trace_id=request.trace_id,
            signal=request.signal,
            content=request.content.encode("utf-8"),
            observed_at=time.time_ns(),
        )
    except (DomainError, OSError, RuntimeError):
        raise HTTPException(status_code=422, detail="invalid research content") from None
    return {"accepted": stored}
