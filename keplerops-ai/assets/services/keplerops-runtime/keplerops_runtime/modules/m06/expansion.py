from __future__ import annotations

from typing import Annotated, Any, Literal

from adversarial_input import EXPANSION_REQUIREMENTS, ExpansionObservation
from adversarial_input import expansion_failure_class
from domain import SessionClaims
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from keplerops_runtime.foundation.auth_storage import _require_ready, _require_role, _session
from keplerops_runtime.foundation.config import ACTION_DENIED, ERROR_RESPONSES
from keplerops_runtime.foundation.policy_client import _adversarial_policy
from keplerops_runtime.modules.m06.constants import ADVERSARIAL_EVIDENCE
from keplerops_runtime.modules.platform_proof import (
    digest_json,
    record_platform_proof,
    store_platform_event,
)


router = APIRouter()
EXPANSION_IDS = (
    "kep-m06-g", "kep-m06-h", "kep-m06-i", "kep-m06-j",
    "kep-m06-k", "kep-m06-l", "kep-m06-m", "kep-m06-n",
    "kep-m06-o", "kep-m06-p", "kep-m06-q", "kep-m06-r",
    "kep-m06-s", "kep-m06-t", "kep-m06-u", "kep-m06-v",
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ExpansionEvidenceItem(StrictModel):
    kind: str = Field(min_length=3, max_length=64, pattern=r"^[a-z0-9-]+$")
    object_id: str = Field(min_length=3, max_length=160, pattern=r"^[A-Za-z0-9._:@/-]+$")
    digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    status: Literal["observed", "selected", "executed", "passed", "restored"]


class ExpansionProofRequest(StrictModel):
    challenge_id: Literal[
        "kep-m06-g", "kep-m06-h", "kep-m06-i", "kep-m06-j",
        "kep-m06-k", "kep-m06-l", "kep-m06-m", "kep-m06-n",
        "kep-m06-o", "kep-m06-p", "kep-m06-q", "kep-m06-r",
        "kep-m06-s", "kep-m06-t", "kep-m06-u", "kep-m06-v",
    ]
    workflow_id: str = Field(min_length=3, max_length=96, pattern=r"^[A-Za-z0-9._:@-]+$")
    evidence: list[ExpansionEvidenceItem] = Field(min_length=1, max_length=12)
    participant_interface: Literal["browser", "curl", "python", "notebook"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


def _submitted_evidence(request: ExpansionProofRequest) -> list[ExpansionEvidenceItem]:
    return getattr(request, "evidence")


def _observations(request: ExpansionProofRequest) -> tuple[ExpansionObservation, ...]:
    return tuple(
        ExpansionObservation(row.kind, row.object_id, row.digest, row.status)
        for row in _submitted_evidence(request)
    )


def _safe_evidence(request: ExpansionProofRequest, failure: str) -> dict[str, Any]:
    rows = [
        {
            "kind": row.kind,
            "object_id": row.object_id,
            "digest": row.digest,
            "status": row.status,
        }
        for row in _submitted_evidence(request)
    ]
    return {
        "challenge_id": request.challenge_id,
        "workflow_id": request.workflow_id,
        "participant_interface": request.participant_interface,
        "assistance_mode": request.assistance_mode,
        "required_kinds": list(EXPANSION_REQUIREMENTS[request.challenge_id]),
        "observations": rows,
        "failure_class": failure,
    }


async def _store_expansion_result(
    session: SessionClaims,
    request: ExpansionProofRequest,
    failure: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    passed = failure == "passed"
    event_id, digest = store_platform_event(
        session,
        challenge_id=request.challenge_id,
        platform="platform-adversarial",
        object_id=request.workflow_id,
        object_digest=digest_json(evidence) if passed else None,
        status="passed" if passed else "not_satisfied",
        failure_class=failure,
        evidence=evidence,
    )
    if passed:
        event_kind, _ = ADVERSARIAL_EVIDENCE[request.challenge_id]
        await record_platform_proof(
            session,
            event_kind=event_kind,
            outcome_id="adversarial-input",
            object_id=request.workflow_id,
            digest=digest,
            asset_id="inference-gateway",
            record_count=len(_submitted_evidence(request)),
            workflow_id=request.workflow_id,
            extra_fields={"stage": "adversarial-expansion"},
        )
    return {
        "challenge_id": request.challenge_id,
        "event_id": event_id,
        "objective_status": "passed" if passed else "not_satisfied",
        "failure_class": failure,
        "workflow_id": request.workflow_id,
        "object_digest": digest,
        "required_kinds": list(EXPANSION_REQUIREMENTS[request.challenge_id]),
    }


@router.get("/v1/adversarial/expansion/challenges", responses=ERROR_RESPONSES)
def adversarial_expansion_challenges() -> dict[str, Any]:
    return {
        "challenge_ids": list(EXPANSION_IDS),
        "required_evidence": {
            challenge_id: list(kinds)
            for challenge_id, kinds in sorted(EXPANSION_REQUIREMENTS.items())
        },
    }


@router.post("/v1/adversarial/expansion/proofs", responses=ERROR_RESPONSES)
async def prove_adversarial_expansion(
    request: ExpansionProofRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    _require_ready()
    if not await _adversarial_policy(session, request.challenge_id):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)
    failure = expansion_failure_class(request.challenge_id, _observations(request))
    return await _store_expansion_result(
        session,
        request,
        failure,
        _safe_evidence(request, failure),
    )
