from __future__ import annotations

from domain import SessionClaims
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from keplerops_runtime.foundation.auth_storage import _postgres, _require_ready, _require_role, _session
from keplerops_runtime.foundation.clients import _record_event
from keplerops_runtime.foundation.config import ACTION_DENIED, ATTEMPT_COMPLETED_EVENT, ERROR_RESPONSES, EXTRACTION_ATTEMPT_PATH, EXTRACTION_STATE_UNAVAILABLE, NOT_FOUND, OBJECTIVE_SATISFIED_EVENT
from keplerops_runtime.foundation.policy_client import _extraction_policy
from keplerops_runtime.foundation.telemetry import _capture_http_body, _observe
from keplerops_runtime.modules.m01.store import _finish_agent_attempt, _start_agent_attempt
from keplerops_runtime.modules.m08 import ExtractionAttemptOutcome, ExtractionAttemptRequest, ExtractionCorpus
from keplerops_runtime.modules.m08.constants import EXTRACTION_CHALLENGE_IDS, EXTRACTION_EVIDENCE
from keplerops_runtime.modules.m08.corpora import _extraction_corpus_metrics, _load_extraction_corpus
from model_extraction import ExtractionMetrics
from model_extraction import challenge_satisfied as extraction_challenge_satisfied
from model_extraction import failure_class as extraction_failure_class
from typing import Annotated
from typing import Any
import time

router = APIRouter()


def _load_extraction_job(
    session: SessionClaims,
    challenge_id: str,
    corpus_id: str,
    job_id: str,
) -> tuple[str, dict[str, Any] | None, str | None, str | None, str | None]:
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT status, metrics, artifact_digest, artifact_uri, registry_run_id "
            "FROM extraction_jobs WHERE job_id=%s AND corpus_id=%s AND range_instance=%s "
            "AND participant=%s AND reset_generation=%s AND challenge_id=%s",
            (
                job_id,
                corpus_id,
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
        raise HTTPException(status_code=503, detail=EXTRACTION_STATE_UNAVAILABLE)
    if any(value is not None and not isinstance(value, str) for value in row[2:]):
        raise HTTPException(status_code=503, detail=EXTRACTION_STATE_UNAVAILABLE)
    return row

def _extraction_metrics_from_job(
    mapping: dict[str, Any] | None,
    artifact_digest: str | None,
    artifact_uri: str | None,
    registry_run_id: str | None,
) -> ExtractionMetrics:
    if mapping is None:
        raise HTTPException(status_code=503, detail=EXTRACTION_STATE_UNAVAILABLE)
    try:
        return ExtractionMetrics(
            query_count=int(mapping["query_count"]),
            query_budget=int(mapping["query_budget"]),
            record_count=int(mapping["record_count"]),
            label_count=int(mapping["label_count"]),
            slice_count=int(mapping["slice_count"]),
            diversity_ratio=float(mapping["diversity_ratio"]),
            diagnostic_fidelity=float(mapping["diagnostic_fidelity"]),
            private_fidelity=float(mapping["private_fidelity"]),
            minimum_slice_fidelity=float(mapping["minimum_slice_fidelity"]),
            artifact_stored=artifact_digest is not None and artifact_uri is not None,
            registry_recorded=registry_run_id is not None,
            gathered_artifacts=bool(mapping.get("gathered_artifacts", False)),
        )
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=503, detail=EXTRACTION_STATE_UNAVAILABLE) from None

def _participant_extraction_metrics(metrics: ExtractionMetrics) -> dict[str, float | int]:
    return {
        "query_count": metrics.query_count,
        "query_budget": metrics.query_budget,
        "record_count": metrics.record_count,
        "label_count": metrics.label_count,
        "slice_count": metrics.slice_count,
        "diversity_ratio": metrics.diversity_ratio,
        "diagnostic_fidelity": metrics.diagnostic_fidelity,
        "private_fidelity": metrics.private_fidelity,
        "minimum_slice_fidelity": metrics.minimum_slice_fidelity,
    }

@router.get("/v1/extraction/jobs/{job_id}", responses=ERROR_RESPONSES)
def extraction_job_status(
    job_id: str,
    corpus_id: str,
    challenge_id: str,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    _require_ready()
    if challenge_id not in EXTRACTION_CHALLENGE_IDS[2:]:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    status, mapping, artifact_digest, artifact_uri, registry_run_id = _load_extraction_job(
        session, challenge_id, corpus_id, job_id
    )
    result: dict[str, Any] = {
        "job_id": job_id,
        "corpus_id": corpus_id,
        "challenge_id": challenge_id,
        "status": status,
    }
    if status == "succeeded":
        result["metrics"] = _participant_extraction_metrics(
            _extraction_metrics_from_job(
                mapping, artifact_digest, artifact_uri, registry_run_id
            )
        )
    return result

def _evaluate_extraction_attempt(
    request: ExtractionAttemptRequest,
    session: SessionClaims,
    corpus: ExtractionCorpus,
) -> ExtractionAttemptOutcome:
    if request.challenge_id in {"kep-m08-a", "kep-m08-b"}:
        metrics = _extraction_corpus_metrics(corpus)
        return ExtractionAttemptOutcome(
            extraction_challenge_satisfied(request.challenge_id, metrics),
            extraction_failure_class(request.challenge_id, metrics),
            metrics,
            corpus.corpus_digest,
            corpus.corpus_id,
        )
    if request.job_id is None:
        raise HTTPException(status_code=422, detail="extraction attempt binding is invalid")
    status, mapping, artifact_digest, artifact_uri, registry_run_id = _load_extraction_job(
        session, request.challenge_id, corpus.corpus_id, request.job_id
    )
    if status != "succeeded":
        raise HTTPException(status_code=409, detail="extraction job is not complete")
    metrics = _extraction_metrics_from_job(
        mapping, artifact_digest, artifact_uri, registry_run_id
    )
    return ExtractionAttemptOutcome(
        extraction_challenge_satisfied(request.challenge_id, metrics),
        extraction_failure_class(request.challenge_id, metrics),
        metrics,
        artifact_digest or corpus.corpus_digest,
        request.job_id,
    )

async def _record_extraction_corpus_evidence(
    request: ExtractionAttemptRequest,
    session: SessionClaims,
    corpus: ExtractionCorpus,
    *,
    passed: bool,
) -> None:
    if not passed or request.challenge_id not in {"kep-m08-a", "kep-m08-b"}:
        return
    event_kind, _ = EXTRACTION_EVIDENCE[request.challenge_id]
    await _record_event({
        "actor_role": "participant",
        "asset_id": "inference-gateway",
        "digest": corpus.corpus_digest,
        "event_kind": event_kind,
        "object_id": corpus.corpus_id,
        "outcome_id": "model-extraction",
        "participant": session.participant,
        "range_instance": session.range_instance,
        "record_count": corpus.query_count,
        "status": "passed",
        "timestamp": int(time.time()),
        "workflow_id": corpus.corpus_id,
    })

async def _record_extraction_job_evidence(
    request: ExtractionAttemptRequest,
    session: SessionClaims,
    outcome: ExtractionAttemptOutcome,
    *,
    passed: bool,
) -> None:
    if not passed or request.challenge_id != "kep-m08-g":
        return
    event_kind, _ = EXTRACTION_EVIDENCE[request.challenge_id]
    await _record_event({
        "actor_role": "participant",
        "asset_id": "inference-gateway",
        "digest": outcome.artifact_digest,
        "event_kind": event_kind,
        "object_id": outcome.workflow_id,
        "outcome_id": "model-extraction",
        "participant": session.participant,
        "range_instance": session.range_instance,
        "record_count": outcome.metrics.record_count,
        "status": "passed",
        "timestamp": int(time.time()),
        "workflow_id": outcome.workflow_id,
    })

@router.post(EXTRACTION_ATTEMPT_PATH, responses=ERROR_RESPONSES)
async def attempt_extraction_challenge(
    request: ExtractionAttemptRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    generation = _require_ready()
    if not await _extraction_policy(session, request.challenge_id):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)
    _capture_http_body(session, request)
    if (request.challenge_id in {"kep-m08-a", "kep-m08-b"}) != (request.job_id is None):
        raise HTTPException(status_code=422, detail="extraction attempt binding is invalid")
    corpus = _load_extraction_corpus(session, request.challenge_id, request.corpus_id)
    attempt_sequence = _start_agent_attempt(session, request.challenge_id)
    started = time.monotonic_ns()
    outcome = _evaluate_extraction_attempt(request, session, corpus)
    _finish_agent_attempt(attempt_sequence, passed=outcome.passed)
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO extraction_attempts "
            "(corpus_id, job_id, range_instance, participant, reset_generation, challenge_id, "
            "status, failure_class) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (
                corpus.corpus_id,
                request.job_id,
                session.range_instance,
                session.participant,
                generation,
                request.challenge_id,
                "passed" if outcome.passed else "not_satisfied",
                outcome.failure,
            ),
        )
    duration_ms = (time.monotonic_ns() - started) // 1_000_000
    common = {
        "challenge_id": request.challenge_id,
        "attempt_sequence": attempt_sequence,
        "workflow_run_id": outcome.workflow_id,
        "path_variant": {
            "kep-m08-a": "participant-corpus",
            "kep-m08-b": "coverage-diversity",
            "kep-m08-c": "diagnostic-proxy",
            "kep-m08-d": "reduced-budget-proxy",
            "kep-m08-e": "private-fidelity",
            "kep-m08-f": "strict-multi-slice",
            "kep-m08-g": "gathered-artifact-proxy",
            "kep-m08-h": "model-inversion",
            "kep-m08-i": "physical-sensor-evasion",
            "kep-m08-j": "full-model-access",
            "kep-m08-k": "product-side-channel",
        }[request.challenge_id],
        "method_class": "black-box",
        "participant_interface": request.participant_interface,
        "assistance_mode": request.assistance_mode,
        "artifact_digest": outcome.artifact_digest,
        "model_revision": "tfidf-logreg-extraction-1.0",
        "query_budget": outcome.metrics.query_budget,
        "coverage_count": outcome.metrics.slice_count,
    }
    _observe(
        session,
        event_name=ATTEMPT_COMPLETED_EVENT,
        outcome_id="model-extraction",
        status="passed" if outcome.passed else "recorded",
        duration_ms=duration_ms,
        query_count=outcome.metrics.query_count,
        record_count=outcome.metrics.record_count,
        diagnostic_fidelity=outcome.metrics.diagnostic_fidelity,
        private_fidelity=outcome.metrics.private_fidelity,
        minimum_slice_fidelity=outcome.metrics.minimum_slice_fidelity,
        failure_class=outcome.failure,
        verdict_class="passed" if outcome.passed else "not-satisfied",
        score_bucket=(
            f"diagnostic-{outcome.metrics.diagnostic_fidelity:.2f}-"
            f"private-{outcome.metrics.private_fidelity:.2f}"
        ),
        **common,
    )
    await _record_extraction_corpus_evidence(
        request, session, corpus, passed=outcome.passed
    )
    await _record_extraction_job_evidence(
        request, session, outcome, passed=outcome.passed
    )
    if outcome.passed:
        _observe(
            session,
            event_name=OBJECTIVE_SATISFIED_EVENT,
            outcome_id="model-extraction",
            status="passed",
            duration_ms=duration_ms,
            query_count=outcome.metrics.query_count,
            record_count=outcome.metrics.record_count,
            diagnostic_fidelity=outcome.metrics.diagnostic_fidelity,
            private_fidelity=outcome.metrics.private_fidelity,
            minimum_slice_fidelity=outcome.metrics.minimum_slice_fidelity,
            verdict_class="passed",
            state_digest=outcome.artifact_digest,
            score_bucket=(
                f"diagnostic-{outcome.metrics.diagnostic_fidelity:.2f}-"
                f"private-{outcome.metrics.private_fidelity:.2f}"
            ),
            **common,
        )
    return {
        "challenge_id": request.challenge_id,
        "corpus_id": corpus.corpus_id,
        "job_id": request.job_id,
        "objective_status": "passed" if outcome.passed else "not_satisfied",
        "failure_class": outcome.failure,
        "metrics": _participant_extraction_metrics(outcome.metrics),
    }
