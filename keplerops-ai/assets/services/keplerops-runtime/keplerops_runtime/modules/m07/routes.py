from __future__ import annotations

from domain import SessionClaims
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from keplerops_runtime.foundation.auth_storage import _require_ready, _require_role, _session
from keplerops_runtime.foundation.config import ACTION_DENIED, ATTEMPT_COMPLETED_EVENT, ERROR_RESPONSES, TRAINING_ATTEMPT_PATH
from keplerops_runtime.foundation.policy_client import _training_policy
from keplerops_runtime.foundation.telemetry import _capture_http_body, _observe
from keplerops_runtime.modules.m01.store import _finish_agent_attempt, _start_agent_attempt
from keplerops_runtime.modules.m07 import TrainingAttemptRequest
from keplerops_runtime.modules.m07.datasets import _load_training_dataset
from keplerops_runtime.modules.m07.jobs import _evaluate_training_attempt, _observe_training_objective, _participant_training_metrics, _record_training_evidence, _store_training_attempt, _training_score_bucket
from typing import Annotated
from typing import Any
import time

router = APIRouter()


@router.post(TRAINING_ATTEMPT_PATH, responses=ERROR_RESPONSES)
async def attempt_training_challenge(
    request: TrainingAttemptRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    _require_ready()
    if not await _training_policy(session, request.challenge_id):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)
    _capture_http_body(session, request)
    dataset = _load_training_dataset(session, request.challenge_id, request.dataset_id)
    if (request.challenge_id == "kep-m07-a") != (request.job_id is None):
        raise HTTPException(status_code=422, detail="training attempt binding is invalid")
    attempt_sequence = _start_agent_attempt(session, request.challenge_id)
    started = time.monotonic_ns()
    outcome = _evaluate_training_attempt(request, session, dataset)
    _finish_agent_attempt(attempt_sequence, passed=outcome.passed)
    _store_training_attempt(request, session, dataset, outcome)
    duration_ms = (time.monotonic_ns() - started) // 1_000_000
    score_bucket = _training_score_bucket(outcome.metrics)
    common = {
        "challenge_id": request.challenge_id,
        "attempt_sequence": attempt_sequence,
        "workflow_run_id": outcome.workflow_id,
        "path_variant": {
            "kep-m07-a": "versioned-dataset",
            "kep-m07-b": "targeted-adapter",
            "kep-m07-c": "clean-tolerance",
            "kep-m07-d": "low-rate",
            "kep-m07-e": "hidden-trigger",
            "kep-m07-f": "sanitized-stealth",
        }[request.challenge_id],
        "method_class": dataset.poison_class,
        "participant_interface": request.participant_interface,
        "assistance_mode": request.assistance_mode,
        "artifact_digest": outcome.artifact_digest,
        "model_revision": "tfidf-logreg-1.0" if outcome.metrics is not None else "dataset-only",
    }
    _observe(
        session,
        event_name=ATTEMPT_COMPLETED_EVENT,
        outcome_id="training-poisoning",
        status="passed" if outcome.passed else "recorded",
        duration_ms=duration_ms,
        record_count=dataset.poison_count,
        iteration_count=dataset.revision,
        failure_class=outcome.failure,
        verdict_class="passed" if outcome.passed else "not-satisfied",
        score_bucket=score_bucket,
        **common,
    )
    await _record_training_evidence(request, session, dataset, outcome=outcome)
    _observe_training_objective(
        session,
        dataset,
        passed=outcome.passed,
        duration_ms=duration_ms,
        score_bucket=score_bucket,
        common=common,
    )
    return {
        "challenge_id": request.challenge_id,
        "dataset_id": dataset.dataset_id,
        "job_id": request.job_id,
        "objective_status": "passed" if outcome.passed else "not_satisfied",
        "failure_class": outcome.failure,
        "revision": dataset.revision,
        "metrics": (
            {}
            if outcome.metrics is None
            else _participant_training_metrics(outcome.metrics)
        ),
    }
