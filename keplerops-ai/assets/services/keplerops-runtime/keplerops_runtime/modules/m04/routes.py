from __future__ import annotations

from domain import SessionClaims
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from keplerops_runtime.foundation.auth_storage import _require_ready, _require_role, _session
from keplerops_runtime.foundation.clients import _model_completion
from keplerops_runtime.foundation.config import ACTION_DENIED, ATTEMPT_COMPLETED_EVENT, ERROR_RESPONSES, OBJECTIVE_ATTEMPTED_EVENT, OBJECTIVE_SATISFIED_EVENT, PRIVACY_MODEL_UNAVAILABLE, SECRETS_ATTEMPT_PATH, SECRETS_INFER_PATH
from keplerops_runtime.foundation.contracts import _revision
from keplerops_runtime.foundation.policy_client import _secrets_policy
from keplerops_runtime.foundation.telemetry import _observe
from keplerops_runtime.modules.m04 import SecretsAttemptRequest, SecretsInferenceRequest, SecretsScoreRequest
from keplerops_runtime.modules.m04.constants import SECRETS_POPULATIONS
from keplerops_runtime.modules.m04.service import _evaluate_secrets_attempt, _privacy_population, _record_secrets_attempt, _record_secrets_evidence, _record_secrets_query, _secrets_digest, _secrets_scores
from model_secrets import ModelSecretsError
from model_secrets import SECRETS_SYSTEMS
from model_secrets import inference_satisfied as secrets_inference_satisfied
from typing import Annotated
from typing import Any
from typing import Literal
import time

router = APIRouter()


@router.post(SECRETS_INFER_PATH, responses=ERROR_RESPONSES)
async def infer_model_secret(
    request: SecretsInferenceRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    _require_ready()
    if not await _secrets_policy(session, request.challenge_id):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)
    started = time.monotonic()
    prompt_digest = _secrets_digest(
        session, f"{request.challenge_id}-prompt", request.prompt
    )
    _observe(
        session,
        event_name=OBJECTIVE_ATTEMPTED_EVENT,
        outcome_id="model-secrets",
        challenge_id=request.challenge_id,
        status="recorded",
        participant_interface=request.participant_interface,
        assistance_mode=request.assistance_mode,
        artifact_digest=prompt_digest,
        model_revision=_revision("model_revision"),
    )
    completion = await _model_completion(
        SECRETS_SYSTEMS[request.challenge_id], request.prompt
    )
    try:
        passed = secrets_inference_satisfied(
            request.challenge_id,
            prompt=request.prompt,
            completion=completion.content,
        )
    except ModelSecretsError:
        passed = False
    duration_ms = max(0, round((time.monotonic() - started) * 1000))
    verdict = "passed" if passed else "not-satisfied"
    _observe(
        session,
        event_name=ATTEMPT_COMPLETED_EVENT,
        outcome_id="model-secrets",
        challenge_id=request.challenge_id,
        status="passed" if passed else "recorded",
        participant_interface=request.participant_interface,
        assistance_mode=request.assistance_mode,
        duration_ms=duration_ms,
        token_count=completion.token_count,
        query_count=1,
        record_count=1,
        artifact_digest=prompt_digest,
        model_revision=_revision("model_revision"),
        verdict_class=verdict,
    )
    if passed:
        evidence_digest = _secrets_digest(
            session, request.challenge_id, f"{prompt_digest}:{completion.token_count}"
        )
        await _record_secrets_evidence(
            session,
            challenge_id=request.challenge_id,
            object_id="keplerops-teacher",
            record_count=1,
            digest=evidence_digest,
        )
        _observe(
            session,
            event_name=OBJECTIVE_SATISFIED_EVENT,
            outcome_id="model-secrets",
            challenge_id=request.challenge_id,
            status="passed",
            participant_interface=request.participant_interface,
            assistance_mode=request.assistance_mode,
            duration_ms=duration_ms,
            token_count=completion.token_count,
            query_count=1,
            record_count=1,
            artifact_digest=prompt_digest,
            state_digest=evidence_digest,
            model_revision=_revision("model_revision"),
            verdict_class="passed",
        )
    return {
        "challenge_id": request.challenge_id,
        "model": "keplerops-teacher",
        "model_revision": _revision("model_revision"),
        "content": completion.content,
        "objective_status": "passed" if passed else "not_satisfied",
    }

@router.get("/v1/secrets/populations/{population}", responses=ERROR_RESPONSES)
async def secrets_population(
    population: Literal["diagnostic", "private", "cohort"],
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    _require_ready()
    challenge_id = {
        "diagnostic": "kep-m04-c",
        "private": "kep-m04-d",
        "cohort": "kep-m04-e",
    }[population]
    if not await _secrets_policy(session, challenge_id):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)
    rows = _privacy_population().public_rows(population)
    return {
        "population": population,
        "sample_count": len(rows),
        "samples": rows,
    }

@router.post("/v1/secrets/score", responses=ERROR_RESPONSES)
async def score_model_secret(
    request: SecretsScoreRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    _require_ready()
    if not await _secrets_policy(session, request.challenge_id):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)
    population = SECRETS_POPULATIONS[request.challenge_id]
    model = _privacy_population()
    allowed_ids = {row.sample_id for row in model.rows(population)}
    if request.sample_id not in allowed_ids:
        raise HTTPException(status_code=422, detail="sample not in challenge population")
    started = time.monotonic()
    try:
        score = model.score(request.sample_id)
    except ModelSecretsError:
        raise HTTPException(status_code=503, detail=PRIVACY_MODEL_UNAVAILABLE) from None
    query_count = _record_secrets_query(
        session,
        challenge_id=request.challenge_id,
        sample_id=score.sample_id,
        prediction=score.prediction,
        confidence=score.confidence,
        loss=score.loss,
        model_revision=score.model_revision,
    )
    duration_ms = max(0, round((time.monotonic() - started) * 1000))
    _observe(
        session,
        event_name=ATTEMPT_COMPLETED_EVENT,
        outcome_id="model-secrets",
        challenge_id=request.challenge_id,
        status="recorded",
        participant_interface=request.participant_interface,
        assistance_mode=request.assistance_mode,
        duration_ms=duration_ms,
        query_count=query_count,
        record_count=1,
        artifact_digest=_secrets_digest(
            session, f"{request.challenge_id}-sample", request.sample_id
        ),
        model_revision=score.model_revision,
        score_bucket=("high" if score.confidence >= 0.8 else "baseline"),
        verdict_class="scored",
    )
    return {
        "challenge_id": request.challenge_id,
        "sample_id": score.sample_id,
        "prediction": score.prediction,
        "confidence": round(score.confidence, 8),
        "loss": round(score.loss, 8),
        "model_revision": score.model_revision,
        "sample_query_count": query_count,
    }

@router.post(SECRETS_ATTEMPT_PATH, responses=ERROR_RESPONSES)
async def attempt_model_secret(
    request: SecretsAttemptRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    _require_ready()
    if not await _secrets_policy(session, request.challenge_id):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)
    model = _privacy_population()
    population = SECRETS_POPULATIONS[request.challenge_id]
    expected_ids = {row.sample_id for row in model.rows(population)}
    scores = _secrets_scores(session, request.challenge_id)
    if set(scores) != expected_ids:
        raise HTTPException(status_code=409, detail="score every challenge sample first")
    started = time.monotonic()
    try:
        evaluation = _evaluate_secrets_attempt(model, request, population, scores)
    except ModelSecretsError:
        raise HTTPException(status_code=422, detail="invalid privacy submission") from None
    passed = evaluation.passed
    member_count = evaluation.member_count
    control_count = evaluation.control_count
    calibration_bucket = evaluation.calibration_bucket
    privacy_verdict = "passed" if passed else "not-satisfied"
    digest = _secrets_digest(
        session,
        f"{request.challenge_id}-verdict",
        f"{sorted(scores.items())}:{calibration_bucket}:{privacy_verdict}",
    )
    _record_secrets_attempt(
        session,
        challenge_id=request.challenge_id,
        passed=passed,
        query_count=len(scores),
        member_sample_count=member_count,
        control_sample_count=control_count,
        calibration_bucket=calibration_bucket,
        privacy_verdict=privacy_verdict,
        digest=digest,
    )
    duration_ms = max(0, round((time.monotonic() - started) * 1000))
    common_observation = {
        "participant_interface": request.participant_interface,
        "assistance_mode": request.assistance_mode,
        "duration_ms": duration_ms,
        "query_count": len(scores),
        "record_count": len(scores),
        "state_digest": digest,
        "model_revision": model.revision,
        "member_sample_count": member_count,
        "control_sample_count": control_count,
        "calibration_bucket": calibration_bucket,
        "privacy_verdict": privacy_verdict,
    }
    _observe(
        session,
        event_name=ATTEMPT_COMPLETED_EVENT,
        outcome_id="model-secrets",
        challenge_id=request.challenge_id,
        status="passed" if passed else "recorded",
        **common_observation,
    )
    if passed:
        await _record_secrets_evidence(
            session,
            challenge_id=request.challenge_id,
            object_id=f"privacy-{population}",
            record_count=len(scores),
            digest=digest,
        )
        _observe(
            session,
            event_name=OBJECTIVE_SATISFIED_EVENT,
            outcome_id="model-secrets",
            challenge_id=request.challenge_id,
            status="passed",
            **common_observation,
        )
    response: dict[str, Any] = {
        "challenge_id": request.challenge_id,
        "objective_status": "passed" if passed else "not_satisfied",
        "query_count": len(scores),
        "model_revision": model.revision,
        **evaluation.response_fields,
    }
    return response
