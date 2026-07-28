from __future__ import annotations

import secrets
from decimal import Decimal
from typing import Annotated, Any, Literal

from domain import SessionClaims
from fastapi import APIRouter, Depends, HTTPException

from keplerops_runtime.foundation.auth_storage import _require_ready, _require_role, _session
from keplerops_runtime.foundation.config import ACTION_DENIED, CONFIG, ERROR_RESPONSES
from keplerops_runtime.foundation.policy_client import _capstone_policy
from keplerops_runtime.foundation.telemetry import _capture_http_body
from keplerops_runtime.modules.m10.constants import CAPSTONE_EVIDENCE
from keplerops_runtime.modules.m10.impact_agent import run_agentic_budget_probe
from keplerops_runtime.modules.m10.impact_schemas import ImpactObjectRequest, UserHarmRequest
from keplerops_runtime.modules.platform_proof import (
    platform_request,
    record_platform_proof,
    store_platform_event,
)

router = APIRouter()
IMPACT_UNAVAILABLE = "platform impact unavailable"

def _impact_admin_headers() -> dict[str, str]:
    token = CONFIG.get("platform_impact_admin_token")
    if not isinstance(token, str) or not token:
        raise HTTPException(status_code=503, detail=IMPACT_UNAVAILABLE)
    return {"X-Platform-Admin-Token": token}

async def _allowed(session: SessionClaims, challenge_id: str) -> None:
    _require_role("gateway")
    _require_ready()
    if not await _capstone_policy(session, challenge_id):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)

async def _impact_request(
    method: Literal["GET", "POST", "PUT", "DELETE"],
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    admin: bool = False,
    expected: tuple[int, ...] = (200,),
) -> dict[str, Any]:
    return await platform_request(
        method,
        service_key="platform-impact",
        base_url_field="platform_impact_url",
        unavailable=IMPACT_UNAVAILABLE,
        path=path,
        headers=_impact_admin_headers() if admin else None,
        payload=payload,
        expected=expected,
    )

async def _store_result(
    session: SessionClaims,
    *,
    challenge_id: str,
    object_id: str,
    passed: bool,
    failure_class: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    event_id, digest = store_platform_event(
        session,
        challenge_id=challenge_id,
        platform="platform-impact",
        object_id=object_id,
        status="passed" if passed else "not_satisfied",
        failure_class=failure_class,
        evidence=evidence,
    )
    if passed:
        event_kind, _ = CAPSTONE_EVIDENCE[challenge_id]
        await record_platform_proof(
            session,
            event_kind=event_kind,
            outcome_id="ai-capstone",
            object_id=object_id,
            digest=digest,
            asset_id="inference-gateway",
        )
    return {
        "challenge_id": challenge_id,
        "event_id": event_id,
        "objective_status": "passed" if passed else "not_satisfied",
        "failure_class": failure_class,
        "object_id": object_id,
        "object_digest": digest,
    }

@router.post("/v1/capstone/impact/service-denial", responses=ERROR_RESPONSES)
async def exercise_service_denial(
    request: ImpactObjectRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    challenge_id = "kep-m10-h"
    await _allowed(session, challenge_id)
    _capture_http_body(session, request)
    target = {
        "target_id": request.object_id,
        "name": request.object_id,
        "probe_url": "http://127.0.0.1:1/healthz",
        "recovery_url": "",
        "recovery_after": 1,
    }
    configured_down = await _impact_request(
        "PUT",
        f"/v1/availability/targets/{request.object_id}",
        payload=target,
        admin=True,
    )
    down_sample = await _impact_request(
        "POST",
        f"/v1/availability/targets/{request.object_id}/sample",
        admin=True,
    )
    target["probe_url"] = "http://127.0.0.1:8460/healthz"
    configured_up = await _impact_request(
        "PUT",
        f"/v1/availability/targets/{request.object_id}",
        payload=target,
        admin=True,
    )
    up_sample = await _impact_request(
        "POST",
        f"/v1/availability/targets/{request.object_id}/sample",
        admin=True,
    )
    passed = down_sample.get("available") is False and up_sample.get("available") is True
    failure = "passed" if passed else "service-recovery-missing"
    evidence = {
        "configured_down": configured_down,
        "down_sample": down_sample,
        "configured_up": configured_up,
        "up_sample": up_sample,
    }
    return await _store_result(
        session,
        challenge_id=challenge_id,
        object_id=request.object_id,
        passed=passed,
        failure_class=failure,
        evidence=evidence,
    )

async def _put_budget(actor: str, limit: int) -> dict[str, Any]:
    return await _impact_request(
        "PUT",
        f"/v1/budgets/{actor}",
        payload={"limit_microunits": limit},
        admin=True,
    )

async def _meter(actor: str, event_id: str, input_tokens: int, output_tokens: int, compute_ms: int) -> dict[str, Any]:
    return await _impact_request(
        "POST",
        "/v1/cost/events",
        payload={
            "event_id": event_id,
            "actor": actor,
            "producer_id": "inference-gateway",
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "compute_ms": compute_ms,
        },
        expected=(201,),
    )

@router.post("/v1/capstone/impact/cost-amplifications", responses=ERROR_RESPONSES)
async def exercise_cost_amplification(
    request: ImpactObjectRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    challenge_id = "kep-m10-i"
    await _allowed(session, challenge_id)
    _capture_http_body(session, request)
    budget = await _put_budget(request.object_id, 900_000)
    cost = await _meter(
        request.object_id, f"cost-{secrets.token_hex(8)}", 100_000, 50_000, 100_000
    )
    passed = cost.get("spent_microunits", 0) >= 500_000
    failure = "passed" if passed else "intensive-cost-gate-missing"
    return await _store_result(
        session,
        challenge_id=challenge_id,
        object_id=request.object_id,
        passed=passed,
        failure_class=failure,
        evidence={"budget": budget, "cost": cost},
    )

@router.post("/v1/capstone/impact/agentic-budget-loops", responses=ERROR_RESPONSES)
async def exercise_agentic_budget_loop(
    request: ImpactObjectRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    challenge_id = "kep-m10-j"
    await _allowed(session, challenge_id)
    _capture_http_body(session, request)
    config, run = await run_agentic_budget_probe(session, request.object_id)
    budget = await _put_budget(request.object_id, 1_000)
    cost = await _meter(request.object_id, f"loop-{secrets.token_hex(8)}", 30, 10, 60)
    passed = run.get("status") == "completed" and 180 <= cost.get("spent_microunits", 0) <= 1_000
    failure = "passed" if passed else "bounded-agent-loop-missing"
    return await _store_result(
        session,
        challenge_id=challenge_id,
        object_id=request.object_id,
        passed=passed,
        failure_class=failure,
        evidence={"configuration": config, "run": run, "budget": budget, "cost": cost},
    )

async def _publish(publication_id: str, author: str, subject: str, body: str, delta: int) -> dict[str, Any]:
    return await _impact_request(
        "POST",
        "/v1/publications",
        payload={
            "publication_id": publication_id,
            "author": author,
            "subject": subject,
            "body": body,
            "reputation_delta": delta,
        },
        expected=(201,),
    )

@router.post("/v1/capstone/impact/chaff-floods", responses=ERROR_RESPONSES)
async def exercise_chaff_flood(
    request: ImpactObjectRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    challenge_id = "kep-m10-k"
    await _allowed(session, challenge_id)
    _capture_http_body(session, request)
    publications = [
        await _publish(
            f"chaff-{index}-{secrets.token_hex(6)}",
            session.participant,
            request.object_id,
            f"synthetic chaff flood record {index}",
            -5,
        )
        for index in range(3)
    ]
    reputation = await _impact_request("GET", f"/v1/reputation/{request.object_id}")
    passed = len(publications) == 3 and reputation.get("score", 0) <= 85
    failure = "passed" if passed else "degradation-not-measured"
    return await _store_result(
        session,
        challenge_id=challenge_id,
        object_id=request.object_id,
        passed=passed,
        failure_class=failure,
        evidence={"publications": publications, "reputation": reputation},
    )


@router.post("/v1/capstone/impact/financial-harms", responses=ERROR_RESPONSES)
async def exercise_financial_harm(
    request: ImpactObjectRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    challenge_id = "kep-m10-l"
    await _allowed(session, challenge_id)
    _capture_http_body(session, request)
    ledger = await _impact_request(
        "POST",
        "/v1/ledger/transactions",
        payload={
            "transaction_id": request.object_id,
            "actor": session.participant,
            "narration": "synthetic contained loss event",
            "amount": str(Decimal("12.500000")),
            "debit_account": "Expenses:SyntheticLoss",
            "credit_account": "Assets:SyntheticCash",
        },
        expected=(201,),
    )
    return await _store_result(
        session,
        challenge_id=challenge_id,
        object_id=request.object_id,
        passed=ledger.get("balanced") is True,
        failure_class="passed" if ledger.get("balanced") is True else "financial-ledger-missing",
        evidence={"ledger": ledger},
    )


@router.post("/v1/capstone/impact/reputational-harms", responses=ERROR_RESPONSES)
async def exercise_reputation_harm(
    request: ImpactObjectRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    challenge_id = "kep-m10-m"
    await _allowed(session, challenge_id)
    _capture_http_body(session, request)
    publication = await _publish(
        request.object_id,
        session.participant,
        request.object_id,
        "synthetic contained reputational harm record",
        -20,
    )
    passed = publication.get("reputation_score", 100) < 100
    return await _store_result(
        session,
        challenge_id=challenge_id,
        object_id=request.object_id,
        passed=passed,
        failure_class="passed" if passed else "reputation-harm-missing",
        evidence={"publication": publication},
    )


@router.post("/v1/capstone/impact/societal-harms", responses=ERROR_RESPONSES)
async def exercise_societal_harm(
    request: ImpactObjectRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    challenge_id = "kep-m10-n"
    await _allowed(session, challenge_id)
    _capture_http_body(session, request)
    cohort = await _impact_request(
        "POST", "/v1/allocations/seeded-cohort", admin=True
    )
    fairness = await _impact_request("GET", "/v1/allocations/fairness")
    publication = await _publish(
        f"soc-{secrets.token_hex(8)}",
        session.participant,
        request.object_id,
        "synthetic contained societal allocation harm record",
        -25,
    )
    passed = cohort.get("record_count", 0) >= 8 and publication.get("reputation_score", 100) <= 75
    return await _store_result(
        session,
        challenge_id=challenge_id,
        object_id=request.object_id,
        passed=passed,
        failure_class="passed" if passed else "societal-simulation-missing",
        evidence={"cohort": cohort, "fairness": fairness, "publication": publication},
    )


@router.post("/v1/capstone/impact/user-harms", responses=ERROR_RESPONSES)
async def exercise_user_harm(
    request: UserHarmRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    challenge_id = "kep-m10-o"
    await _allowed(session, challenge_id)
    _capture_http_body(session, request)
    simulation = await _impact_request(
        "POST",
        "/v1/users/simulations",
        payload={
            "simulation_id": request.object_id,
            "user_id": request.object_id,
            "message": request.message,
        },
        expected=(201,),
    )
    publication = await _publish(
        f"user-{secrets.token_hex(8)}",
        session.participant,
        request.object_id,
        "synthetic contained user harm record",
        -10,
    )
    passed = simulation.get("action") == "contained" and publication.get("reputation_score", 100) <= 90
    return await _store_result(
        session,
        challenge_id=challenge_id,
        object_id=request.object_id,
        passed=passed,
        failure_class="passed" if passed else "user-harm-missing",
        evidence={"simulation": simulation, "publication": publication},
    )


async def _publish_then_remove(publication_id: str, author: str) -> dict[str, Any]:
    publication = await _publish(
        publication_id,
        author,
        "keplerops-synthetic",
        "synthetic durable record scheduled for contained deletion",
        -10,
    )
    removed = await _impact_request("DELETE", f"/v1/publications/{publication_id}")
    reputation = await _impact_request("GET", "/v1/reputation/keplerops-synthetic")
    return {"publication": publication, "removed": removed, "reputation": reputation}


@router.post("/v1/capstone/impact/dataset-destructions", responses=ERROR_RESPONSES)
async def exercise_dataset_destruction(
    request: ImpactObjectRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    challenge_id = "kep-m10-p"
    await _allowed(session, challenge_id)
    _capture_http_body(session, request)
    evidence = await _publish_then_remove(request.object_id, session.participant)
    passed = evidence["removed"].get("status") == "removed" and evidence["reputation"].get("score") == 100
    return await _store_result(
        session,
        challenge_id=challenge_id,
        object_id=request.object_id,
        passed=passed,
        failure_class="passed" if passed else "dataset-reset-not-verified",
        evidence=evidence,
    )


@router.post("/v1/capstone/impact/tool-data-destructions", responses=ERROR_RESPONSES)
async def exercise_tool_data_destruction(
    request: ImpactObjectRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    challenge_id = "kep-m10-q"
    await _allowed(session, challenge_id)
    _capture_http_body(session, request)
    evidence = await _publish_then_remove(request.object_id, "agent-alpha")
    passed = evidence["removed"].get("status") == "removed" and evidence["reputation"].get("score") == 100
    return await _store_result(
        session,
        challenge_id=challenge_id,
        object_id=request.object_id,
        passed=passed,
        failure_class="passed" if passed else "tool-data-reset-not-verified",
        evidence=evidence,
    )
