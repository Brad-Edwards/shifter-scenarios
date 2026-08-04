from __future__ import annotations

from domain import SessionClaims
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from keplerops_runtime.foundation.auth_storage import _postgres, _require_ready, _require_role, _session
from keplerops_runtime.foundation.clients import _record_event
from keplerops_runtime.foundation.config import ERROR_RESPONSES, NOT_FOUND, OBJECTIVE_SATISFIED_EVENT, TRAINING_STATE_UNAVAILABLE
from keplerops_runtime.foundation.telemetry import _observe
from keplerops_runtime.modules.m07 import TrainingAttemptOutcome, TrainingAttemptRequest, TrainingDataset
from keplerops_runtime.modules.m07.constants import TRAINING_CHALLENGE_IDS, TRAINING_EVIDENCE
from keplerops_runtime.modules.m07.datasets import _training_base_contract, _valid_training_job_id
from training_poisoning import TrainingMetrics
from training_poisoning import challenge_satisfied as training_challenge_satisfied
from training_poisoning import dataset_failure_class as training_dataset_failure_class
from training_poisoning import training_failure_class
from typing import Annotated
from typing import Any
import time

router = APIRouter()


def _load_training_job(
    session: SessionClaims,
    challenge_id: str,
    dataset_id: str,
    job_id: str,
) -> tuple[str, dict[str, Any] | None, str | None, str | None, str | None]:
    if not _valid_training_job_id(job_id):
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT status, metrics, artifact_digest, artifact_uri, registry_run_id "
            "FROM training_jobs WHERE job_id=%s AND dataset_id=%s AND range_instance=%s "
            "AND participant=%s AND reset_generation=%s AND challenge_id=%s",
            (
                job_id,
                dataset_id,
                session.range_instance,
                session.participant,
                _require_ready(),
                challenge_id,
            ),
        )
        row = cursor.fetchone()
    if not isinstance(row, tuple) or len(row) != 5 or not isinstance(row[0], str):
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    if row[1] is not None and not isinstance(row[1], dict):
        raise HTTPException(status_code=503, detail=TRAINING_STATE_UNAVAILABLE)
    if any(value is not None and not isinstance(value, str) for value in row[2:]):
        raise HTTPException(status_code=503, detail=TRAINING_STATE_UNAVAILABLE)
    return row

def _training_metrics_from_job(
    mapping: dict[str, Any] | None,
    artifact_digest: str | None,
    artifact_uri: str | None,
    registry_run_id: str | None,
) -> TrainingMetrics:
    if mapping is None:
        raise HTTPException(status_code=503, detail=TRAINING_STATE_UNAVAILABLE)
    try:
        return TrainingMetrics(
            target_delta=float(mapping["target_delta"]),
            clean_accuracy=float(mapping["clean_accuracy"]),
            clean_max_shift=float(mapping["clean_max_shift"]),
            poison_count=int(mapping["poison_count"]),
            total_count=int(mapping["total_count"]),
            poison_ratio=float(mapping["poison_ratio"]),
            hidden_trigger_rate=float(mapping["hidden_trigger_rate"]),
            hidden_confidence=float(mapping["hidden_confidence"]),
            sanitized_poison_count=int(mapping["sanitized_poison_count"]),
            sanitized_target_delta=float(mapping["sanitized_target_delta"]),
            sanitized_hidden_trigger_rate=float(mapping["sanitized_hidden_trigger_rate"]),
            artifact_stored=artifact_digest is not None and artifact_uri is not None,
            registry_recorded=registry_run_id is not None,
        )
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=503, detail=TRAINING_STATE_UNAVAILABLE) from None

def _participant_training_metrics(metrics: TrainingMetrics) -> dict[str, float | int]:
    return {
        "target_delta": metrics.target_delta,
        "clean_accuracy": metrics.clean_accuracy,
        "clean_max_shift": metrics.clean_max_shift,
        "poison_count": metrics.poison_count,
        "total_count": metrics.total_count,
        "poison_ratio": metrics.poison_ratio,
        "hidden_trigger_rate": metrics.hidden_trigger_rate,
        "hidden_confidence": metrics.hidden_confidence,
        "sanitized_poison_count": metrics.sanitized_poison_count,
        "sanitized_target_delta": metrics.sanitized_target_delta,
        "sanitized_hidden_trigger_rate": metrics.sanitized_hidden_trigger_rate,
    }

@router.get("/v1/training/jobs/{job_id}", responses=ERROR_RESPONSES)
def training_job_status(
    job_id: str,
    dataset_id: str,
    challenge_id: str,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    _require_ready()
    if challenge_id not in TRAINING_CHALLENGE_IDS or challenge_id == "kep-m07-a":
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    status, mapping, artifact_digest, artifact_uri, registry_run_id = _load_training_job(
        session, challenge_id, dataset_id, job_id
    )
    result: dict[str, Any] = {
        "job_id": job_id,
        "dataset_id": dataset_id,
        "challenge_id": challenge_id,
        "status": status,
    }
    if status == "succeeded":
        result["metrics"] = _participant_training_metrics(
            _training_metrics_from_job(
                mapping, artifact_digest, artifact_uri, registry_run_id
            )
        )
    return result

def _evaluate_training_attempt(
    request: TrainingAttemptRequest,
    session: SessionClaims,
    dataset: TrainingDataset,
) -> TrainingAttemptOutcome:
    if request.challenge_id == "kep-m07-a":
        failure = training_dataset_failure_class(
            request.challenge_id,
            poison_class=dataset.poison_class,
            poison_count=dataset.poison_count,
            total_count=dataset.total_count,
            lineage_valid=(
                dataset.base_digest == _training_base_contract()[0]
                and dataset.revision >= 1
            ),
        )
        return TrainingAttemptOutcome(
            failure == "passed",
            failure,
            None,
            dataset.dataset_digest,
            dataset.dataset_id,
        )
    if request.job_id is None:
        raise HTTPException(status_code=422, detail="training attempt binding is invalid")
    status, mapping, job_digest, artifact_uri, registry_run_id = _load_training_job(
        session,
        request.challenge_id,
        dataset.dataset_id,
        request.job_id,
    )
    if status != "succeeded":
        raise HTTPException(status_code=409, detail="training job is not complete")
    metrics = _training_metrics_from_job(
        mapping, job_digest, artifact_uri, registry_run_id
    )
    return TrainingAttemptOutcome(
        training_challenge_satisfied(request.challenge_id, metrics),
        training_failure_class(request.challenge_id, metrics),
        metrics,
        job_digest or dataset.dataset_digest,
        request.job_id,
    )

def _store_training_attempt(
    request: TrainingAttemptRequest,
    session: SessionClaims,
    dataset: TrainingDataset,
    outcome: TrainingAttemptOutcome,
) -> None:
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO training_attempts "
            "(dataset_id, job_id, range_instance, participant, reset_generation, "
            "challenge_id, status, failure_class) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (
                dataset.dataset_id,
                request.job_id,
                session.range_instance,
                session.participant,
                _require_ready(),
                request.challenge_id,
                "passed" if outcome.passed else "not_satisfied",
                outcome.failure,
            ),
        )

def _training_score_bucket(metrics: TrainingMetrics | None) -> str:
    if metrics is None:
        return "lineage-valid"
    if metrics.target_delta >= 0.30:
        return "target-strong"
    if metrics.target_delta >= 0.20:
        return "target-passed"
    return "target-below"

async def _record_training_dataset_evidence(
    request: TrainingAttemptRequest,
    session: SessionClaims,
    dataset: TrainingDataset,
    *,
    passed: bool,
) -> None:
    if not passed or request.challenge_id != "kep-m07-a":
        return
    event_kind, _ = TRAINING_EVIDENCE[request.challenge_id]
    await _record_event({
        "actor_role": "participant",
        "asset_id": "inference-gateway",
        "digest": dataset.dataset_digest,
        "event_kind": event_kind,
        "object_id": dataset.dataset_id,
        "outcome_id": "training-poisoning",
        "participant": session.participant,
        "range_instance": session.range_instance,
        "record_count": dataset.poison_count,
        "status": "passed",
        "timestamp": int(time.time()),
        "workflow_id": dataset.dataset_id,
    })

def _observe_training_objective(
    session: SessionClaims,
    dataset: TrainingDataset,
    *,
    passed: bool,
    duration_ms: int,
    score_bucket: str,
    common: dict[str, Any],
) -> None:
    if not passed:
        return
    _observe(
        session,
        event_name=OBJECTIVE_SATISFIED_EVENT,
        outcome_id="training-poisoning",
        status="passed",
        duration_ms=duration_ms,
        record_count=dataset.poison_count,
        iteration_count=dataset.revision,
        state_version=dataset.revision,
        verdict_class="passed",
        score_bucket=score_bucket,
        **common,
    )
