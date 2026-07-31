from __future__ import annotations

from domain import SessionClaims
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from keplerops_runtime.foundation.auth_storage import _require_ready, _require_role, _session
from keplerops_runtime.foundation.catalog import _participant_adversarial_challenges, _participant_agent_challenges, _participant_backdoor_challenges, _participant_capstone_challenges, _participant_context_challenges, _participant_evasion_challenges, _participant_extraction_challenges, _participant_persistence_challenges, _participant_secrets_challenges, _participant_training_challenges
from keplerops_runtime.foundation.config import CHALLENGE_PRESENTED_EVENT, ERROR_RESPONSES, HINT_VIEWED_EVENT, NOT_FOUND
from keplerops_runtime.foundation.contracts import _adversarial_challenge_contracts, _agent_challenge_contracts, _backdoor_challenge_contracts, _capstone_challenge_contracts, _context_challenge_contracts, _evasion_challenge_contracts, _extraction_challenge_contracts, _persistence_challenge_contracts, _secrets_challenge_contracts, _training_challenge_contracts
from keplerops_runtime.foundation.telemetry import _observe
from typing import Annotated
from typing import Any

router = APIRouter()


@router.get("/v1/agent/challenges", responses=ERROR_RESPONSES)
def agent_challenges(session: Annotated[SessionClaims, Depends(_session)]) -> dict[str, Any]:
    _require_role("gateway")
    _require_ready()
    rows = _participant_agent_challenges()
    for row in rows:
        _observe(
            session,
            event_name=CHALLENGE_PRESENTED_EVENT,
            outcome_id="agent-control",
            challenge_id=row["challenge_id"],
            status="recorded",
        )
    return {"range_instance": session.range_instance, "challenges": rows}

@router.post("/v1/agent/challenges/{challenge_id}/hints/{hint_tier}", responses=ERROR_RESPONSES)
def agent_hint(
    challenge_id: str,
    hint_tier: int,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    _require_ready()
    contract = _agent_challenge_contracts().get(challenge_id)
    if contract is None or not 1 <= hint_tier <= 3:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    hint = contract["hints"][hint_tier - 1]
    cost = contract["hint_costs"][hint_tier - 1]
    _observe(
        session,
        event_name=HINT_VIEWED_EVENT,
        outcome_id="agent-control",
        challenge_id=challenge_id,
        status="recorded",
        hint_tier=hint_tier,
        hint_cost=cost,
    )
    return {"challenge_id": challenge_id, "hint_tier": hint_tier, "cost": cost, "hint": hint}

@router.get("/v1/evasion/challenges", responses=ERROR_RESPONSES)
def evasion_challenges(session: Annotated[SessionClaims, Depends(_session)]) -> dict[str, Any]:
    _require_role("gateway")
    _require_ready()
    rows = _participant_evasion_challenges()
    for row in rows:
        _observe(
            session,
            event_name=CHALLENGE_PRESENTED_EVENT,
            outcome_id="model-evasion",
            challenge_id=row["challenge_id"],
            status="recorded",
        )
    return {"range_instance": session.range_instance, "challenges": rows}

@router.post("/v1/evasion/challenges/{challenge_id}/hints/{hint_tier}", responses=ERROR_RESPONSES)
def evasion_hint(
    challenge_id: str,
    hint_tier: int,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    _require_ready()
    contract = _evasion_challenge_contracts().get(challenge_id)
    if contract is None or not 1 <= hint_tier <= 3:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    hint = contract["hints"][hint_tier - 1]
    cost = contract["hint_costs"][hint_tier - 1]
    _observe(
        session,
        event_name=HINT_VIEWED_EVENT,
        outcome_id="model-evasion",
        challenge_id=challenge_id,
        status="recorded",
        hint_tier=hint_tier,
        hint_cost=cost,
    )
    return {"challenge_id": challenge_id, "hint_tier": hint_tier, "cost": cost, "hint": hint}

@router.get("/v1/context/challenges", responses=ERROR_RESPONSES)
def context_challenges(session: Annotated[SessionClaims, Depends(_session)]) -> dict[str, Any]:
    _require_role("gateway")
    _require_ready()
    rows = _participant_context_challenges()
    for row in rows:
        _observe(
            session,
            event_name=CHALLENGE_PRESENTED_EVENT,
            outcome_id="context-poisoning",
            challenge_id=row["challenge_id"],
            status="recorded",
        )
    return {"range_instance": session.range_instance, "challenges": rows}

@router.post("/v1/context/challenges/{challenge_id}/hints/{hint_tier}", responses=ERROR_RESPONSES)
def context_hint(
    challenge_id: str,
    hint_tier: int,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    _require_ready()
    contract = _context_challenge_contracts().get(challenge_id)
    if contract is None or not 1 <= hint_tier <= 3:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    hint = contract["hints"][hint_tier - 1]
    cost = contract["hint_costs"][hint_tier - 1]
    _observe(
        session,
        event_name=HINT_VIEWED_EVENT,
        outcome_id="context-poisoning",
        challenge_id=challenge_id,
        status="recorded",
        hint_tier=hint_tier,
        hint_cost=cost,
    )
    return {"challenge_id": challenge_id, "hint_tier": hint_tier, "cost": cost, "hint": hint}

@router.get("/v1/secrets/challenges", responses=ERROR_RESPONSES)
def secrets_challenges(session: Annotated[SessionClaims, Depends(_session)]) -> dict[str, Any]:
    _require_role("gateway")
    _require_ready()
    rows = _participant_secrets_challenges()
    for row in rows:
        _observe(
            session,
            event_name=CHALLENGE_PRESENTED_EVENT,
            outcome_id="model-secrets",
            challenge_id=row["challenge_id"],
            status="recorded",
        )
    return {"range_instance": session.range_instance, "challenges": rows}

@router.post("/v1/secrets/challenges/{challenge_id}/hints/{hint_tier}", responses=ERROR_RESPONSES)
def secrets_hint(
    challenge_id: str,
    hint_tier: int,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    _require_ready()
    contract = _secrets_challenge_contracts().get(challenge_id)
    if contract is None or not 1 <= hint_tier <= 3:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    hint = contract["hints"][hint_tier - 1]
    cost = contract["hint_costs"][hint_tier - 1]
    _observe(
        session,
        event_name=HINT_VIEWED_EVENT,
        outcome_id="model-secrets",
        challenge_id=challenge_id,
        status="recorded",
        hint_tier=hint_tier,
        hint_cost=cost,
    )
    return {"challenge_id": challenge_id, "hint_tier": hint_tier, "cost": cost, "hint": hint}

@router.get("/v1/persistence/challenges", responses=ERROR_RESPONSES)
def persistence_challenges(
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    _require_ready()
    rows = _participant_persistence_challenges()
    for row in rows:
        _observe(
            session,
            event_name=CHALLENGE_PRESENTED_EVENT,
            outcome_id="agent-persistence",
            challenge_id=row["challenge_id"],
            status="recorded",
        )
    return {"range_instance": session.range_instance, "challenges": rows}

@router.post("/v1/persistence/challenges/{challenge_id}/hints/{hint_tier}", responses=ERROR_RESPONSES)
def persistence_hint(
    challenge_id: str,
    hint_tier: int,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    _require_ready()
    contract = _persistence_challenge_contracts().get(challenge_id)
    if contract is None or not 1 <= hint_tier <= 3:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    hint = contract["hints"][hint_tier - 1]
    cost = contract["hint_costs"][hint_tier - 1]
    _observe(
        session,
        event_name=HINT_VIEWED_EVENT,
        outcome_id="agent-persistence",
        challenge_id=challenge_id,
        status="recorded",
        hint_tier=hint_tier,
        hint_cost=cost,
    )
    return {"challenge_id": challenge_id, "hint_tier": hint_tier, "cost": cost, "hint": hint}

@router.get("/v1/adversarial/challenges", responses=ERROR_RESPONSES)
def adversarial_challenges(
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    _require_ready()
    rows = _participant_adversarial_challenges()
    for row in rows:
        _observe(
            session,
            event_name=CHALLENGE_PRESENTED_EVENT,
            outcome_id="adversarial-input",
            challenge_id=row["challenge_id"],
            status="recorded",
        )
    return {"range_instance": session.range_instance, "challenges": rows}

@router.post("/v1/adversarial/challenges/{challenge_id}/hints/{hint_tier}", responses=ERROR_RESPONSES)
def adversarial_hint(
    challenge_id: str,
    hint_tier: int,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    _require_ready()
    contract = _adversarial_challenge_contracts().get(challenge_id)
    if contract is None or not 1 <= hint_tier <= 3:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    hint = contract["hints"][hint_tier - 1]
    cost = contract["hint_costs"][hint_tier - 1]
    _observe(
        session,
        event_name=HINT_VIEWED_EVENT,
        outcome_id="adversarial-input",
        challenge_id=challenge_id,
        status="recorded",
        hint_tier=hint_tier,
        hint_cost=cost,
    )
    return {"challenge_id": challenge_id, "hint_tier": hint_tier, "cost": cost, "hint": hint}

@router.get("/v1/training/challenges", responses=ERROR_RESPONSES)
def training_challenges(
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    _require_ready()
    rows = _participant_training_challenges()
    for row in rows:
        _observe(
            session,
            event_name=CHALLENGE_PRESENTED_EVENT,
            outcome_id="training-poisoning",
            challenge_id=row["challenge_id"],
            status="recorded",
        )
    return {"range_instance": session.range_instance, "challenges": rows}

@router.post("/v1/training/challenges/{challenge_id}/hints/{hint_tier}", responses=ERROR_RESPONSES)
def training_hint(
    challenge_id: str,
    hint_tier: int,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    _require_ready()
    contract = _training_challenge_contracts().get(challenge_id)
    if contract is None or not 1 <= hint_tier <= 3:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    hint = contract["hints"][hint_tier - 1]
    cost = contract["hint_costs"][hint_tier - 1]
    _observe(
        session,
        event_name=HINT_VIEWED_EVENT,
        outcome_id="training-poisoning",
        challenge_id=challenge_id,
        status="recorded",
        hint_tier=hint_tier,
        hint_cost=cost,
    )
    return {"challenge_id": challenge_id, "hint_tier": hint_tier, "cost": cost, "hint": hint}

@router.get("/v1/extraction/challenges", responses=ERROR_RESPONSES)
def extraction_challenges(
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    _require_ready()
    rows = _participant_extraction_challenges()
    for row in rows:
        _observe(
            session,
            event_name=CHALLENGE_PRESENTED_EVENT,
            outcome_id="model-extraction",
            challenge_id=row["challenge_id"],
            status="recorded",
        )
    return {"range_instance": session.range_instance, "challenges": rows}

@router.post("/v1/extraction/challenges/{challenge_id}/hints/{hint_tier}", responses=ERROR_RESPONSES)
def extraction_hint(
    challenge_id: str,
    hint_tier: int,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    _require_ready()
    contract = _extraction_challenge_contracts().get(challenge_id)
    if contract is None or not 1 <= hint_tier <= 3:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    hint = contract["hints"][hint_tier - 1]
    cost = contract["hint_costs"][hint_tier - 1]
    _observe(
        session,
        event_name=HINT_VIEWED_EVENT,
        outcome_id="model-extraction",
        challenge_id=challenge_id,
        status="recorded",
        hint_tier=hint_tier,
        hint_cost=cost,
    )
    return {"challenge_id": challenge_id, "hint_tier": hint_tier, "cost": cost, "hint": hint}

@router.get("/v1/backdoor/challenges", responses=ERROR_RESPONSES)
def backdoor_challenges(
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    _require_ready()
    rows = _participant_backdoor_challenges()
    for row in rows:
        _observe(
            session,
            event_name=CHALLENGE_PRESENTED_EVENT,
            outcome_id="model-backdoor",
            challenge_id=row["challenge_id"],
            status="recorded",
        )
    return {"range_instance": session.range_instance, "challenges": rows}

@router.post("/v1/backdoor/challenges/{challenge_id}/hints/{hint_tier}", responses=ERROR_RESPONSES)
def backdoor_hint(
    challenge_id: str,
    hint_tier: int,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    _require_ready()
    contract = _backdoor_challenge_contracts().get(challenge_id)
    if contract is None or not 1 <= hint_tier <= 3:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    hint = contract["hints"][hint_tier - 1]
    cost = contract["hint_costs"][hint_tier - 1]
    _observe(
        session,
        event_name=HINT_VIEWED_EVENT,
        outcome_id="model-backdoor",
        challenge_id=challenge_id,
        status="recorded",
        hint_tier=hint_tier,
        hint_cost=cost,
    )
    return {"challenge_id": challenge_id, "hint_tier": hint_tier, "cost": cost, "hint": hint}

@router.get("/v1/capstone/challenges", responses=ERROR_RESPONSES)
def capstone_challenges(
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    _require_ready()
    rows = _participant_capstone_challenges()
    for row in rows:
        _observe(
            session,
            event_name=CHALLENGE_PRESENTED_EVENT,
            outcome_id="ai-capstone",
            challenge_id=row["challenge_id"],
            status="recorded",
        )
    return {"range_instance": session.range_instance, "challenges": rows}

@router.post("/v1/capstone/challenges/{challenge_id}/hints/{hint_tier}", responses=ERROR_RESPONSES)
def capstone_hint(
    challenge_id: str,
    hint_tier: int,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    _require_ready()
    contract = _capstone_challenge_contracts().get(challenge_id)
    if contract is None or not 1 <= hint_tier <= 3:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    hint = contract["hints"][hint_tier - 1]
    cost = contract["hint_costs"][hint_tier - 1]
    _observe(
        session,
        event_name=HINT_VIEWED_EVENT,
        outcome_id="ai-capstone",
        challenge_id=challenge_id,
        status="recorded",
        hint_tier=hint_tier,
        hint_cost=cost,
    )
    return {
        "challenge_id": challenge_id,
        "hint_tier": hint_tier,
        "cost": cost,
        "hint": hint,
    }
