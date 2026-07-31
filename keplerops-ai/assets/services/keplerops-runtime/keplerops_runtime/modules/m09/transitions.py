from __future__ import annotations

from domain import SessionClaims
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from keplerops_runtime.foundation.auth_storage import _postgres, _require_ready, _require_role, _session
from keplerops_runtime.foundation.config import ACTION_DENIED, ERROR_RESPONSES, MODEL_REGISTRY_UNAVAILABLE, WORKFLOW_COMPLETED_EVENT
from keplerops_runtime.foundation.policy_client import _backdoor_policy
from keplerops_runtime.foundation.telemetry import _capture_http_body, _observe
from keplerops_runtime.modules.m01.store import _agent_digest
from keplerops_runtime.modules.m09 import BackdoorCandidate, BackdoorPromotionRequest, BackdoorReloadRequest
from keplerops_runtime.modules.m09.candidates import (
    BACKDOOR_STATE_UNAVAILABLE,
    _backdoor_population_rows,
    _download_backdoor_artifact,
    _load_backdoor_candidate,
    _mlflow_client,
)
from keplerops_runtime.modules.m09.evaluations import _hidden_evaluation_ready, _promotion_approval, _set_candidate_alias
from typing import Annotated
from typing import Any
import secrets

router = APIRouter()


def _promotion_response(
    *,
    promotion_id: str,
    candidate: BackdoorCandidate,
    prior_model_version: str | None,
    promoted_model_version: str,
    actor_authorized: bool,
    policy_confused: bool,
) -> dict[str, Any]:
    return {
        "promotion_id": promotion_id,
        "candidate_id": candidate.candidate_id,
        "registry_model_name": candidate.registry_model_name,
        "registry_alias": "production",
        "prior_model_version": prior_model_version,
        "promoted_model_version": promoted_model_version,
        "actor_authorized": actor_authorized,
        "policy_confused": policy_confused,
        "status": "promoted",
    }


def _existing_promotion(candidate: BackdoorCandidate) -> dict[str, Any] | None:
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT p.promotion_id, p.prior_model_version, p.promoted_model_version, "
            "p.actor_authorized, a.policy_confused FROM backdoor_promotions p "
            "JOIN backdoor_approvals a ON a.approval_id=p.approval_id "
            "WHERE p.candidate_id=%s AND p.registry_alias='production'",
            (candidate.candidate_id,),
        )
        row = cursor.fetchone()
    if row is None:
        return None
    if (
        not isinstance(row, tuple)
        or len(row) != 5
        or not isinstance(row[0], str)
        or not (row[1] is None or isinstance(row[1], str))
        or not isinstance(row[2], str)
        or not isinstance(row[3], bool)
        or not isinstance(row[4], bool)
    ):
        raise HTTPException(status_code=503, detail=BACKDOOR_STATE_UNAVAILABLE)
    return _promotion_response(
        promotion_id=row[0],
        candidate=candidate,
        prior_model_version=row[1],
        promoted_model_version=row[2],
        actor_authorized=row[3],
        policy_confused=row[4],
    )


def _reload_response(
    *,
    deployment_id: str,
    candidate_id: str,
    resolved_model_version: str,
    artifact_digest: str,
    trigger_rate: float,
    trigger_confidence: float,
    clean_accuracy: float,
) -> dict[str, Any]:
    return {
        "deployment_id": deployment_id,
        "candidate_id": candidate_id,
        "registry_alias": "production",
        "resolved_model_version": resolved_model_version,
        "artifact_digest": artifact_digest,
        "metrics": {
            "trigger_rate": trigger_rate,
            "trigger_confidence": trigger_confidence,
            "clean_accuracy": clean_accuracy,
        },
        "status": "reloaded",
    }


def _existing_reload(candidate_id: str) -> dict[str, Any] | None:
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT deployment_id, resolved_model_version, artifact_digest, "
            "trigger_rate, trigger_confidence, clean_accuracy "
            "FROM backdoor_deployments WHERE candidate_id=%s "
            "AND registry_alias='production'",
            (candidate_id,),
        )
        row = cursor.fetchone()
    if row is None:
        return None
    if (
        not isinstance(row, tuple)
        or len(row) != 6
        or not all(isinstance(value, str) for value in row[:3])
        or not all(isinstance(value, (int, float)) for value in row[3:])
    ):
        raise HTTPException(status_code=503, detail=BACKDOOR_STATE_UNAVAILABLE)
    return _reload_response(
        deployment_id=row[0],
        candidate_id=candidate_id,
        resolved_model_version=row[1],
        artifact_digest=row[2],
        trigger_rate=float(row[3]),
        trigger_confidence=float(row[4]),
        clean_accuracy=float(row[5]),
    )


@router.post("/v1/backdoor/promotions", responses=ERROR_RESPONSES)
async def promote_backdoor_candidate(
    request: BackdoorPromotionRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    _require_ready()
    if not await _backdoor_policy(session, "kep-m09-f"):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)
    _capture_http_body(session, request)
    candidate = _load_backdoor_candidate(session, request.candidate_id)
    policy_allowed, policy_confused, policy_reason, decision_digest = _promotion_approval(
        candidate.candidate_id, request.approval_id
    )
    if not policy_allowed:
        raise HTTPException(status_code=403, detail="approval policy denied promotion")
    if not _hidden_evaluation_ready(candidate.candidate_id):
        raise HTTPException(status_code=409, detail="hidden verification is incomplete")
    prior_version = _set_candidate_alias(candidate)
    promotion_id = "mbp-" + secrets.token_hex(12)
    actor_authorized = not policy_confused
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO backdoor_promotions "
            "(promotion_id, candidate_id, approval_id, registry_alias, prior_model_version, "
            "promoted_model_version, actor, actor_authorized, policy_decision_digest) "
            "VALUES (%s, %s, %s, 'production', %s, %s, %s, %s, %s) "
            "ON CONFLICT (candidate_id, registry_alias) DO NOTHING RETURNING promotion_id",
            (
                promotion_id,
                candidate.candidate_id,
                request.approval_id,
                prior_version,
                candidate.registry_model_version,
                session.participant,
                actor_authorized,
                decision_digest,
            ),
        )
        inserted = cursor.fetchone()
        if inserted == (promotion_id,):
            cursor.execute(
                "UPDATE backdoor_candidates SET status='promoted', "
                "updated_at=clock_timestamp() WHERE candidate_id=%s",
                (candidate.candidate_id,),
            )
    if inserted != (promotion_id,):
        existing = _existing_promotion(candidate)
        if existing is None:
            raise HTTPException(status_code=409, detail="candidate is already promoted")
        return existing
    _observe(
        session,
        event_name=WORKFLOW_COMPLETED_EVENT,
        outcome_id="model-backdoor",
        challenge_id="kep-m09-f",
        status="recorded",
        workflow_run_id=promotion_id,
        artifact_digest=candidate.artifact_digest,
        state_digest=decision_digest,
        registry_alias="production",
        prior_model_version=prior_version or "none",
        registry_model_version=candidate.registry_model_version,
        policy_confused=policy_confused,
        policy_reason=policy_reason,
        actor_authorized=actor_authorized,
        path_variant="mlflow-alias-transition",
        method_class="policy-bypass",
        participant_interface=request.participant_interface,
        assistance_mode=request.assistance_mode,
        record_count=1,
    )
    return _promotion_response(
        promotion_id=promotion_id,
        candidate=candidate,
        prior_model_version=prior_version,
        promoted_model_version=candidate.registry_model_version,
        actor_authorized=actor_authorized,
        policy_confused=policy_confused,
    )

def _candidate_promotion(candidate_id: str) -> tuple[str, str, bool]:
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT promotion_id, promoted_model_version, actor_authorized "
            "FROM backdoor_promotions WHERE candidate_id=%s AND registry_alias='production'",
            (candidate_id,),
        )
        row = cursor.fetchone()
    if (
        not isinstance(row, tuple)
        or len(row) != 3
        or not isinstance(row[0], str)
        or not isinstance(row[1], str)
        or not isinstance(row[2], bool)
    ):
        raise HTTPException(status_code=409, detail="candidate is not promoted")
    return row

def _resolve_promoted_candidate(candidate: BackdoorCandidate):
    from mlflow.exceptions import MlflowException
    from model_backdoor import load_candidate_artifact

    try:
        version = _mlflow_client().get_model_version_by_alias(
            candidate.registry_model_name, "production"
        )
    except MlflowException:
        raise HTTPException(status_code=503, detail=MODEL_REGISTRY_UNAVAILABLE) from None
    resolved_version = str(version.version)
    if resolved_version != candidate.registry_model_version:
        raise HTTPException(status_code=409, detail="registry alias no longer resolves candidate")
    raw = _download_backdoor_artifact(str(version.source))
    try:
        model = load_candidate_artifact(raw)
    except ValueError:
        raise HTTPException(status_code=422, detail="promoted artifact is invalid") from None
    return resolved_version, model

@router.post("/v1/backdoor/reloads", responses=ERROR_RESPONSES)
async def reload_backdoor_candidate(
    request: BackdoorReloadRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    _require_ready()
    if not await _backdoor_policy(session, "kep-m09-g"):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)
    _capture_http_body(session, request)
    candidate = _load_backdoor_candidate(session, request.candidate_id)
    promotion_id, promoted_version, _ = _candidate_promotion(candidate.candidate_id)
    resolved_version, model = _resolve_promoted_candidate(candidate)
    if promoted_version != resolved_version or model.artifact_digest != candidate.artifact_digest:
        raise HTTPException(status_code=409, detail="promoted artifact lineage mismatch")
    from model_backdoor import evaluate_behavior

    trigger_rows, clean_rows = _backdoor_population_rows("hidden")
    behavior = evaluate_behavior(
        model, trigger_prompts=trigger_rows, clean_rows=clean_rows
    )
    deployment_id = "mbd-" + secrets.token_hex(12)
    evaluation_id = "mbe-" + secrets.token_hex(12)
    evaluation_digest = _agent_digest(
        session,
        f"{candidate.candidate_id}-reload",
        (
            f"{resolved_version}:{model.artifact_digest}:"
            f"{behavior.trigger_rate:.8f}:{behavior.clean_accuracy:.8f}"
        ),
    )
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO backdoor_evaluations "
            "(evaluation_id, candidate_id, evaluation_kind, trigger_rate, "
            "trigger_confidence, clean_accuracy, trigger_count, clean_count, evaluation_digest) "
            "VALUES (%s, %s, 'reload_joined', %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (candidate_id, evaluation_kind) DO NOTHING RETURNING evaluation_id",
            (
                evaluation_id,
                candidate.candidate_id,
                behavior.trigger_rate,
                behavior.trigger_confidence,
                behavior.clean_accuracy,
                behavior.trigger_count,
                behavior.clean_count,
                evaluation_digest,
            ),
        )
        evaluation_inserted = cursor.fetchone()
        if evaluation_inserted == (evaluation_id,):
            cursor.execute(
                "INSERT INTO backdoor_deployments "
                "(deployment_id, candidate_id, promotion_id, registry_alias, "
                "resolved_model_version, artifact_digest, trigger_rate, trigger_confidence, "
                "clean_accuracy) VALUES (%s, %s, %s, 'production', %s, %s, %s, %s, %s) "
                "ON CONFLICT (candidate_id, registry_alias) DO NOTHING RETURNING deployment_id",
                (
                    deployment_id,
                    candidate.candidate_id,
                    promotion_id,
                    resolved_version,
                    model.artifact_digest,
                    behavior.trigger_rate,
                    behavior.trigger_confidence,
                    behavior.clean_accuracy,
                ),
            )
            deployment_inserted = cursor.fetchone()
            if deployment_inserted == (deployment_id,):
                cursor.execute(
                    "UPDATE backdoor_candidates SET status='reloaded', "
                    "updated_at=clock_timestamp() WHERE candidate_id=%s",
                    (candidate.candidate_id,),
                )
            else:
                existing = _existing_reload(candidate.candidate_id)
                if existing is None:
                    raise HTTPException(
                        status_code=409, detail="candidate is already reloaded"
                    )
                return existing
    if evaluation_inserted != (evaluation_id,):
        existing = _existing_reload(candidate.candidate_id)
        if existing is None:
            raise HTTPException(status_code=409, detail="candidate is already reloaded")
        return existing
    _observe(
        session,
        event_name=WORKFLOW_COMPLETED_EVENT,
        outcome_id="model-backdoor",
        challenge_id="kep-m09-g",
        status="recorded",
        workflow_run_id=deployment_id,
        artifact_digest=model.artifact_digest,
        state_digest=evaluation_digest,
        registry_alias="production",
        registry_model_version=resolved_version,
        trigger_rate=behavior.trigger_rate,
        trigger_confidence=behavior.trigger_confidence,
        clean_accuracy=behavior.clean_accuracy,
        evaluation_count=behavior.trigger_count + behavior.clean_count,
        path_variant="mlflow-alias-reload",
        method_class="real-model-inference",
        participant_interface=request.participant_interface,
        assistance_mode=request.assistance_mode,
        record_count=1,
    )
    return _reload_response(
        deployment_id=deployment_id,
        candidate_id=candidate.candidate_id,
        resolved_model_version=resolved_version,
        artifact_digest=model.artifact_digest,
        trigger_rate=behavior.trigger_rate,
        trigger_confidence=behavior.trigger_confidence,
        clean_accuracy=behavior.clean_accuracy,
    )

def _backdoor_evaluation_rows(candidate_id: str) -> dict[str, tuple[Any, ...]]:
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT evaluation_kind, trigger_rate, trigger_confidence, clean_accuracy "
            "FROM backdoor_evaluations WHERE candidate_id=%s",
            (candidate_id,),
        )
        rows = cursor.fetchall()
    if any(not isinstance(row, tuple) or len(row) != 4 for row in rows):
        raise HTTPException(status_code=503, detail=BACKDOOR_STATE_UNAVAILABLE)
    return {row[0]: row[1:] for row in rows if isinstance(row[0], str)}

def _backdoor_approval_state(approval: Any) -> tuple[bool, bool]:
    if not isinstance(approval, tuple) or len(approval) != 2:
        return False, False
    signature_valid, confused = approval
    return bool(signature_valid), bool(confused)

def _backdoor_transition_state(
    promotion: Any,
    deployment: Any,
    artifact_digest: str,
) -> tuple[bool, bool, bool, bool]:
    promoted = isinstance(promotion, tuple) and len(promotion) == 1
    actor_authorized = promotion[0] if promoted and isinstance(promotion[0], bool) else True
    reloaded = isinstance(deployment, tuple) and len(deployment) == 1
    reload_digest_match = reloaded and deployment[0] == artifact_digest
    return promoted, actor_authorized, reloaded, reload_digest_match
