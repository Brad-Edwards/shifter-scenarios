from __future__ import annotations

from domain import SessionClaims
from fastapi import HTTPException
from functools import lru_cache
from keplerops_runtime.foundation.auth_storage import _postgres, _require_ready
from keplerops_runtime.foundation.clients import _record_event
from keplerops_runtime.foundation.config import CONFIG, PRIVACY_MODEL_UNAVAILABLE, PROOF_SERVICE_UNAVAILABLE, SHA256_PREFIX, _regular_owner_file
from keplerops_runtime.modules.m04 import SecretsAttemptRequest, SecretsEvaluation
from keplerops_runtime.modules.m04.constants import SECRETS_EVIDENCE
from model_secrets import ModelSecretsError
from model_secrets import PrivacyPopulation
from model_secrets import challenge_satisfied as secrets_challenge_satisfied
from pathlib import Path
import hashlib
import hmac
import time


@lru_cache(maxsize=1)
def _privacy_population() -> PrivacyPopulation:
    path = CONFIG.get("privacy_population_path")
    if not isinstance(path, str):
        raise HTTPException(status_code=503, detail=PRIVACY_MODEL_UNAVAILABLE)
    try:
        return PrivacyPopulation(Path(path))
    except ModelSecretsError:
        raise HTTPException(status_code=503, detail=PRIVACY_MODEL_UNAVAILABLE) from None

def _secrets_digest(session: SessionClaims, label: str, material: str) -> str:
    token_file = CONFIG.get("service_token_file")
    if not isinstance(token_file, str):
        raise HTTPException(status_code=503, detail=PROOF_SERVICE_UNAVAILABLE)
    body = (
        f"{session.range_instance}:{session.participant}:{_require_ready()}:"
        f"{label}:{material}"
    ).encode("utf-8")
    return SHA256_PREFIX + hmac.new(
        _regular_owner_file(Path(token_file)), body, hashlib.sha256
    ).hexdigest()

def _record_secrets_query(
    session: SessionClaims,
    *,
    challenge_id: str,
    sample_id: str,
    prediction: str,
    confidence: float,
    loss: float,
    model_revision: str,
) -> int:
    digest = _secrets_digest(
        session,
        f"{challenge_id}-query",
        f"{sample_id}:{confidence:.8f}:{model_revision}",
    )
    with _postgres() as connection:
        row = connection.execute(
            "INSERT INTO model_secret_queries "
            "(range_instance, participant, reset_generation, challenge_id, sample_id, "
            "prediction, confidence, loss, model_revision, query_digest) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (range_instance, participant, reset_generation, challenge_id, sample_id) "
            "DO UPDATE SET prediction=EXCLUDED.prediction, confidence=EXCLUDED.confidence, "
            "loss=EXCLUDED.loss, model_revision=EXCLUDED.model_revision, "
            "query_digest=EXCLUDED.query_digest, query_count=model_secret_queries.query_count + 1, "
            "updated_at=clock_timestamp() RETURNING query_count",
            (
                session.range_instance,
                session.participant,
                _require_ready(),
                challenge_id,
                sample_id,
                prediction,
                confidence,
                loss,
                model_revision,
                digest,
            ),
        ).fetchone()
    if row is None or not isinstance(row[0], int):
        raise HTTPException(status_code=503, detail="privacy query unavailable")
    return row[0]

def _secrets_scores(session: SessionClaims, challenge_id: str) -> dict[str, float]:
    with _postgres() as connection:
        rows = connection.execute(
            "SELECT sample_id, confidence FROM model_secret_queries "
            "WHERE range_instance=%s AND participant=%s AND reset_generation=%s "
            "AND challenge_id=%s",
            (
                session.range_instance,
                session.participant,
                _require_ready(),
                challenge_id,
            ),
        ).fetchall()
    if any(not isinstance(sample_id, str) or not isinstance(score, float) for sample_id, score in rows):
        raise HTTPException(status_code=503, detail="privacy query unavailable")
    return dict(rows)

def _record_secrets_attempt(
    session: SessionClaims,
    *,
    challenge_id: str,
    passed: bool,
    query_count: int,
    member_sample_count: int,
    control_sample_count: int,
    calibration_bucket: str,
    privacy_verdict: str,
    digest: str,
) -> None:
    with _postgres() as connection:
        connection.execute(
            "INSERT INTO model_secret_attempts "
            "(range_instance, participant, reset_generation, challenge_id, status, "
            "query_count, member_sample_count, control_sample_count, calibration_bucket, "
            "privacy_verdict, digest) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                session.range_instance,
                session.participant,
                _require_ready(),
                challenge_id,
                "passed" if passed else "not_satisfied",
                query_count,
                member_sample_count,
                control_sample_count,
                calibration_bucket,
                privacy_verdict,
                digest,
            ),
        )

def _evaluate_secrets_attempt(
    model: PrivacyPopulation,
    request: SecretsAttemptRequest,
    population: str,
    scores: dict[str, float],
) -> SecretsEvaluation:
    if request.challenge_id in {"kep-m04-c", "kep-m04-d"}:
        if request.predicted_cohort is not None:
            raise ModelSecretsError("privacy attempt: unexpected cohort")
        metrics = model.classification_metrics(population, request.selected_members)
        return SecretsEvaluation(
            passed=secrets_challenge_satisfied(request.challenge_id, metrics=metrics),
            member_count=metrics.member_count,
            control_count=metrics.control_count,
            calibration_bucket=f"{metrics.correct_count}-of-{metrics.sample_count}",
            response_fields=(
                {"diagnostic_accuracy": round(metrics.accuracy, 4)}
                if request.challenge_id == "kep-m04-c"
                else {}
            ),
        )
    if request.selected_members or request.predicted_cohort is None:
        raise ModelSecretsError("privacy attempt: invalid cohort submission")
    metrics = model.cohort_metrics(scores)
    return SecretsEvaluation(
        passed=secrets_challenge_satisfied(
            request.challenge_id,
            metrics=metrics,
            predicted_cohort=request.predicted_cohort,
        ),
        member_count=metrics.member_count,
        control_count=metrics.control_count,
        calibration_bucket=(
            "separated" if metrics.separation >= 0.15 else "overlapping"
        ),
        response_fields={"cohort_separation": round(metrics.separation, 8)},
    )

async def _record_secrets_evidence(
    session: SessionClaims,
    *,
    challenge_id: str,
    object_id: str,
    record_count: int,
    digest: str,
) -> None:
    event_kind, _ = SECRETS_EVIDENCE[challenge_id]
    await _record_event({
        "actor_role": "participant",
        "asset_id": "inference-gateway",
        "digest": digest,
        "event_kind": event_kind,
        "object_id": object_id,
        "outcome_id": "model-secrets",
        "participant": session.participant,
        "range_instance": session.range_instance,
        "record_count": record_count,
        "status": "passed",
        "timestamp": int(time.time()),
    })
