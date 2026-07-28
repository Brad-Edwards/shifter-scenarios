from __future__ import annotations

from domain import SessionClaims
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from keplerops_runtime.foundation.auth_storage import _postgres, _require_ready, _require_role, _session
from keplerops_runtime.foundation.clients import _signed_approval_session
from keplerops_runtime.foundation.config import ACTION_DENIED, ATTEMPT_COMPLETED_EVENT, ERROR_RESPONSES, MODEL_REGISTRY_UNAVAILABLE
from keplerops_runtime.foundation.policy_client import _backdoor_approval_policy, _backdoor_policy
from keplerops_runtime.foundation.telemetry import _capture_http_body, _observe
from keplerops_runtime.modules.m01.store import _agent_digest
from keplerops_runtime.modules.m09 import BackdoorApprovalRequest, BackdoorCandidate, BackdoorEvaluationRequest
from keplerops_runtime.modules.m09.candidates import _evaluate_candidate_population, _load_backdoor_candidate, _mlflow_client, _require_diagnostic_evaluations, _stored_backdoor_evaluation
from typing import Annotated
from typing import Any
import json
import secrets
import time

router = APIRouter()


def _evaluation_response(
    *,
    evaluation_id: str,
    candidate_id: str,
    evaluation_kind: str,
    metrics: dict[str, Any],
    evaluation_digest: str,
) -> dict[str, Any]:
    result = {
        key: value
        for key, value in metrics.items()
        if value is not None and not key.endswith("_count")
    }
    return {
        "evaluation_id": evaluation_id,
        "candidate_id": candidate_id,
        "evaluation_kind": evaluation_kind,
        "metrics": result,
        "evaluation_digest": evaluation_digest,
        "status": "evaluated",
    }


def _existing_evaluation(candidate_id: str, evaluation_kind: str) -> dict[str, Any] | None:
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT evaluation_id, trigger_rate, trigger_confidence, clean_accuracy, "
            "trigger_count, clean_count, evaluation_digest FROM backdoor_evaluations "
            "WHERE candidate_id=%s AND evaluation_kind=%s",
            (candidate_id, evaluation_kind),
        )
        row = cursor.fetchone()
    if row is None:
        return None
    if (
        not isinstance(row, tuple)
        or len(row) != 7
        or not isinstance(row[0], str)
        or not isinstance(row[6], str)
    ):
        raise HTTPException(status_code=503, detail="backdoor state unavailable")
    return _evaluation_response(
        evaluation_id=row[0],
        candidate_id=candidate_id,
        evaluation_kind=evaluation_kind,
        metrics={
            "trigger_rate": row[1],
            "trigger_confidence": row[2],
            "clean_accuracy": row[3],
            "trigger_count": row[4],
            "clean_count": row[5],
        },
        evaluation_digest=row[6],
    )


def _approval_response(
    *,
    approval_id: str,
    candidate_id: str,
    actor: str,
    approval_kind: str,
    target_scope: str,
    signature_valid: bool,
    policy_allowed: bool,
    policy_confused: bool,
    policy_reason: str,
    policy_decision_digest: str,
) -> dict[str, Any]:
    return {
        "approval_id": approval_id,
        "candidate_id": candidate_id,
        "actor": actor,
        "approval_kind": approval_kind,
        "target_scope": target_scope,
        "signature_valid": signature_valid,
        "policy": {
            "allowed": policy_allowed,
            "confused": policy_confused,
            "reason": policy_reason,
        },
        "policy_decision_digest": policy_decision_digest,
    }


def _existing_approval(candidate_id: str, token_digest: str) -> dict[str, Any] | None:
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT approval_id, actor, approval_kind, target_scope, "
            "approval_signature_valid, policy_allowed, policy_confused, "
            "policy_reason, policy_decision_digest FROM backdoor_approvals "
            "WHERE candidate_id=%s AND token_digest=%s",
            (candidate_id, token_digest),
        )
        row = cursor.fetchone()
    if row is None:
        return None
    if (
        not isinstance(row, tuple)
        or len(row) != 9
        or not all(isinstance(value, str) for value in row[:4])
        or not all(isinstance(value, bool) for value in row[4:7])
        or not all(isinstance(value, str) for value in row[7:])
    ):
        raise HTTPException(status_code=503, detail="backdoor state unavailable")
    return _approval_response(
        approval_id=row[0],
        candidate_id=candidate_id,
        actor=row[1],
        approval_kind=row[2],
        target_scope=row[3],
        signature_valid=row[4],
        policy_allowed=row[5],
        policy_confused=row[6],
        policy_reason=row[7],
        policy_decision_digest=row[8],
    )


@router.post("/v1/backdoor/evaluations", responses=ERROR_RESPONSES)
async def evaluate_backdoor_candidate(
    request: BackdoorEvaluationRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    _require_ready()
    challenge_id = {
        "diagnostic_trigger": "kep-m09-b",
        "diagnostic_clean": "kep-m09-c",
        "hidden_joined": "kep-m09-e",
    }[request.evaluation_kind]
    if not await _backdoor_policy(session, challenge_id):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)
    _capture_http_body(session, request)
    candidate = _load_backdoor_candidate(session, request.candidate_id)
    if request.evaluation_kind == "hidden_joined":
        _require_diagnostic_evaluations(candidate.candidate_id)
    population_name = "hidden" if request.evaluation_kind == "hidden_joined" else "diagnostic"
    started = time.monotonic_ns()
    behavior = _evaluate_candidate_population(candidate, population_name)
    evaluation_id = "mbe-" + secrets.token_hex(12)
    stored = _stored_backdoor_evaluation(behavior, request.evaluation_kind)
    evaluation_digest = _agent_digest(
        session,
        f"{candidate.candidate_id}-{request.evaluation_kind}",
        json.dumps(stored, separators=(",", ":"), sort_keys=True),
    )
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO backdoor_evaluations "
            "(evaluation_id, candidate_id, evaluation_kind, trigger_rate, "
            "trigger_confidence, clean_accuracy, trigger_count, clean_count, evaluation_digest) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (candidate_id, evaluation_kind) DO NOTHING RETURNING evaluation_id",
            (
                evaluation_id,
                candidate.candidate_id,
                request.evaluation_kind,
                stored["trigger_rate"],
                stored["trigger_confidence"],
                stored["clean_accuracy"],
                stored["trigger_count"],
                stored["clean_count"],
                evaluation_digest,
            ),
        )
        inserted = cursor.fetchone()
        if inserted == (evaluation_id,) and request.evaluation_kind == "hidden_joined":
            if (
                behavior.trigger_rate >= 1
                and behavior.trigger_confidence >= 0.60
                and behavior.clean_accuracy >= 0.83
            ):
                cursor.execute(
                    "UPDATE backdoor_candidates SET status='verified', "
                    "updated_at=clock_timestamp() WHERE candidate_id=%s",
                    (candidate.candidate_id,),
                )
    if inserted != (evaluation_id,):
        existing = _existing_evaluation(candidate.candidate_id, request.evaluation_kind)
        if existing is None:
            raise HTTPException(
                status_code=409, detail="candidate evaluation already exists"
            )
        return existing
    _observe(
        session,
        event_name=ATTEMPT_COMPLETED_EVENT,
        outcome_id="model-backdoor",
        challenge_id=challenge_id,
        status="recorded",
        workflow_run_id=evaluation_id,
        artifact_digest=candidate.artifact_digest,
        evaluation_kind=request.evaluation_kind,
        trigger_rate=stored["trigger_rate"],
        trigger_confidence=stored["trigger_confidence"],
        clean_accuracy=stored["clean_accuracy"],
        evaluation_count=(stored["trigger_count"] or 0) + (stored["clean_count"] or 0),
        duration_ms=(time.monotonic_ns() - started) // 1_000_000,
        participant_interface=request.participant_interface,
        assistance_mode=request.assistance_mode,
        path_variant=request.evaluation_kind,
        method_class="real-model-inference",
        model_revision=candidate.model_revision,
        state_digest=evaluation_digest,
    )
    return _evaluation_response(
        evaluation_id=evaluation_id,
        candidate_id=candidate.candidate_id,
        evaluation_kind=request.evaluation_kind,
        metrics=stored,
        evaluation_digest=evaluation_digest,
    )

@router.post("/v1/backdoor/approvals", responses=ERROR_RESPONSES)
async def submit_backdoor_approval(
    request: BackdoorApprovalRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    _require_ready()
    if not await _backdoor_policy(session, "kep-m09-d"):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)
    _capture_http_body(session, request)
    candidate = _load_backdoor_candidate(session, request.candidate_id)
    signer = _signed_approval_session(request.signed_approval, session)
    if "release_manager" in signer.roles:
        approval_kind = "release"
    elif "ml_engineer" in signer.roles:
        approval_kind = "model_card"
    else:
        raise HTTPException(status_code=422, detail="signed approval role is ineligible")
    decision = await _backdoor_approval_policy(
        session, signer, approval_kind=approval_kind
    )
    approval_id = "mba-" + secrets.token_hex(12)
    token_digest = _agent_digest(
        session, f"{candidate.candidate_id}-approval-token", request.signed_approval
    )
    decision_material = json.dumps(
        {
            "actor": signer.participant,
            "roles": sorted(signer.roles),
            "kind": approval_kind,
            "target_scope": "release",
            "allowed": decision.allowed,
            "confused": decision.confused,
            "reason": decision.reason,
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    policy_decision_digest = _agent_digest(
        session, f"{candidate.candidate_id}-approval-decision", decision_material
    )
    approval_signature_valid = True
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO backdoor_approvals "
            "(approval_id, candidate_id, actor, actor_roles, token_digest, approval_kind, "
            "target_scope, approval_signature_valid, policy_allowed, policy_confused, "
            "policy_reason, policy_decision_digest) "
            "VALUES (%s, %s, %s, %s, %s, %s, 'release', %s, %s, %s, %s, %s) "
            "ON CONFLICT (candidate_id, token_digest) DO NOTHING RETURNING approval_id",
            (
                approval_id,
                candidate.candidate_id,
                signer.participant,
                list(signer.roles),
                token_digest,
                approval_kind,
                approval_signature_valid,
                decision.allowed,
                decision.confused,
                decision.reason,
                policy_decision_digest,
            ),
        )
        inserted = cursor.fetchone()
    if inserted != (approval_id,):
        existing = _existing_approval(candidate.candidate_id, token_digest)
        if existing is None:
            raise HTTPException(
                status_code=409, detail="approval object already submitted"
            )
        return existing
    _observe(
        session,
        event_name=ATTEMPT_COMPLETED_EVENT,
        outcome_id="model-backdoor",
        challenge_id="kep-m09-d",
        status="recorded",
        workflow_run_id=approval_id,
        artifact_digest=candidate.artifact_digest,
        state_digest=policy_decision_digest,
        approval_kind=approval_kind,
        approval_target_scope="release",
        policy_allowed=decision.allowed,
        policy_confused=decision.confused,
        policy_reason=decision.reason,
        path_variant="signed-approval-object",
        method_class="policy-scope-confusion",
        participant_interface=request.participant_interface,
        assistance_mode=request.assistance_mode,
        record_count=1,
    )
    return _approval_response(
        approval_id=approval_id,
        candidate_id=candidate.candidate_id,
        actor=signer.participant,
        approval_kind=approval_kind,
        target_scope="release",
        signature_valid=approval_signature_valid,
        policy_allowed=decision.allowed,
        policy_confused=decision.confused,
        policy_reason=decision.reason,
        policy_decision_digest=policy_decision_digest,
    )

def _promotion_approval(
    candidate_id: str, approval_id: str
) -> tuple[bool, bool, str, str]:
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT policy_allowed, policy_confused, policy_reason, policy_decision_digest "
            "FROM backdoor_approvals WHERE candidate_id=%s AND approval_id=%s",
            (candidate_id, approval_id),
        )
        row = cursor.fetchone()
    if (
        not isinstance(row, tuple)
        or len(row) != 4
        or not isinstance(row[0], bool)
        or not isinstance(row[1], bool)
        or not all(isinstance(value, str) for value in row[2:])
    ):
        raise HTTPException(status_code=422, detail="approval binding is invalid")
    return row

def _hidden_evaluation_ready(candidate_id: str) -> bool:
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT trigger_rate, trigger_confidence, clean_accuracy "
            "FROM backdoor_evaluations WHERE candidate_id=%s "
            "AND evaluation_kind='hidden_joined'",
            (candidate_id,),
        )
        row = cursor.fetchone()
    return (
        isinstance(row, tuple)
        and len(row) == 3
        and all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in row)
        and row[0] >= 1
        and row[1] >= 0.60
        and row[2] >= 0.83
    )

def _set_candidate_alias(candidate: BackdoorCandidate) -> str | None:
    from mlflow.exceptions import MlflowException

    client = _mlflow_client()
    prior: str | None = None
    try:
        prior = str(
            client.get_model_version_by_alias(
                candidate.registry_model_name, "production"
            ).version
        )
    except MlflowException:
        prior = None
    try:
        client.set_registered_model_alias(
            candidate.registry_model_name,
            "production",
            candidate.registry_model_version,
        )
    except MlflowException:
        raise HTTPException(status_code=503, detail=MODEL_REGISTRY_UNAVAILABLE) from None
    return prior
