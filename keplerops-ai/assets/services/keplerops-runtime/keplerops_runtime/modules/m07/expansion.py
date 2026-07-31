from __future__ import annotations

from typing import Annotated, Any, Literal

from domain import SessionClaims
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from training_poisoning import TRAINING_EXPANSION_REQUIREMENTS
from training_poisoning import TrainingExpansionObservation
from training_poisoning import training_expansion_failure_class

from keplerops_runtime.foundation.auth_storage import _require_ready, _require_role, _session
from keplerops_runtime.foundation.config import ACTION_DENIED, ERROR_RESPONSES
from keplerops_runtime.foundation.policy_client import _training_policy
from keplerops_runtime.modules.m07.constants import TRAINING_EVIDENCE
from keplerops_runtime.modules.platform_proof import (
    digest_json,
    record_platform_proof,
    store_platform_event,
)


router = APIRouter()
EXPANSION_IDS = ("kep-m07-g", "kep-m07-h", "kep-m07-i")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class TrainingExpansionEvidenceItem(StrictModel):
    kind: str = Field(min_length=3, max_length=64, pattern=r"^[a-z0-9-]+$")
    object_id: str = Field(min_length=3, max_length=160, pattern=r"^[A-Za-z0-9._:@/-]+$")
    digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    status: Literal["observed", "selected", "executed", "passed"]


class TrainingExpansionProofRequest(StrictModel):
    challenge_id: Literal["kep-m07-g", "kep-m07-h", "kep-m07-i"]
    workflow_id: str = Field(min_length=3, max_length=96, pattern=r"^[A-Za-z0-9._:@-]+$")
    evidence: list[TrainingExpansionEvidenceItem] = Field(min_length=1, max_length=12)
    participant_interface: Literal["browser", "curl", "python", "notebook"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


def _submitted_evidence(
    request: TrainingExpansionProofRequest,
) -> list[TrainingExpansionEvidenceItem]:
    return getattr(request, "evidence")


def _observations(
    request: TrainingExpansionProofRequest,
) -> tuple[TrainingExpansionObservation, ...]:
    return tuple(
        TrainingExpansionObservation(row.kind, row.object_id, row.digest, row.status)
        for row in _submitted_evidence(request)
    )


def _safe_evidence(
    request: TrainingExpansionProofRequest,
    failure: str,
) -> dict[str, Any]:
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
        "required_kinds": list(TRAINING_EXPANSION_REQUIREMENTS[request.challenge_id]),
        "observations": rows,
        "failure_class": failure,
    }


async def _store_expansion_result(
    session: SessionClaims,
    request: TrainingExpansionProofRequest,
    failure: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    passed = failure == "passed"
    event_id, digest = store_platform_event(
        session,
        challenge_id=request.challenge_id,
        platform="platform-training",
        object_id=request.workflow_id,
        object_digest=digest_json(evidence) if passed else None,
        status="passed" if passed else "not_satisfied",
        failure_class=failure,
        evidence=evidence,
    )
    if passed:
        event_kind, _ = TRAINING_EVIDENCE[request.challenge_id]
        await record_platform_proof(
            session,
            event_kind=event_kind,
            outcome_id="training-poisoning",
            object_id=request.workflow_id,
            digest=digest,
            asset_id="inference-gateway",
            record_count=len(_submitted_evidence(request)),
            workflow_id=request.workflow_id,
            extra_fields={"stage": "training-expansion"},
        )
    return {
        "challenge_id": request.challenge_id,
        "event_id": event_id,
        "objective_status": "passed" if passed else "not_satisfied",
        "failure_class": failure,
        "workflow_id": request.workflow_id,
        "object_digest": digest,
        "required_kinds": list(TRAINING_EXPANSION_REQUIREMENTS[request.challenge_id]),
    }


@router.get("/v1/training/expansion/challenges", responses=ERROR_RESPONSES)
def training_expansion_challenges() -> dict[str, Any]:
    return {
        "challenge_ids": list(EXPANSION_IDS),
        "required_evidence": {
            challenge_id: list(kinds)
            for challenge_id, kinds in sorted(TRAINING_EXPANSION_REQUIREMENTS.items())
        },
    }


@router.post("/v1/training/expansion/proofs", responses=ERROR_RESPONSES)
async def prove_training_expansion(
    request: TrainingExpansionProofRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    _require_ready()
    if not await _training_policy(session, request.challenge_id):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)
    failure = training_expansion_failure_class(request.challenge_id, _observations(request))
    return await _store_expansion_result(
        session,
        request,
        failure,
        _safe_evidence(request, failure),
    )
