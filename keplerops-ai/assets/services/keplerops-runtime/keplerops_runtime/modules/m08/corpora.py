from __future__ import annotations

from domain import SessionClaims
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from functools import lru_cache
from keplerops_runtime.foundation.auth_storage import _postgres, _require_ready, _require_role, _session
from keplerops_runtime.foundation.clients import _model_completion
from keplerops_runtime.foundation.config import ACTION_DENIED, ATTEMPT_COMPLETED_EVENT, CONFIG, ERROR_RESPONSES, EXTRACTION_STATE_UNAVAILABLE, MODEL_UNAVAILABLE, NOT_FOUND, POSTGRES_ADVISORY_LOCK_SQL, WORKFLOW_STARTED_EVENT
from keplerops_runtime.foundation.policy_client import _extraction_policy
from keplerops_runtime.foundation.telemetry import _capture, _capture_http_body, _observe
from keplerops_runtime.modules.m01.store import _agent_digest
from keplerops_runtime.modules.m08 import ExtractionCorpus, ExtractionJobRequest, ExtractionQueryRequest, ExtractionQueryResult
from keplerops_runtime.modules.m08.constants import EXTRACTION_CHALLENGE_IDS
from model_extraction import ExtractionMetrics
from model_extraction import QUERY_BUDGETS as EXTRACTION_QUERY_BUDGETS
from model_extraction import TEACHER_SYSTEM as EXTRACTION_TEACHER_SYSTEM
from model_extraction import behavior_slice as extraction_behavior_slice
from model_extraction import corpus_statistics as extraction_corpus_statistics
from model_extraction import teacher_label as parse_extraction_teacher_label
from pathlib import Path
from typing import Annotated
from typing import Any
import json
import secrets
import time

router = APIRouter()


@lru_cache(maxsize=1)
def _extraction_populations() -> dict[str, tuple[dict[str, str], ...]]:
    path = CONFIG.get("extraction_population_path")
    if not isinstance(path, str):
        raise HTTPException(status_code=503, detail=EXTRACTION_STATE_UNAVAILABLE)
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if set(payload) != {"schema_version", "teacher_revision", "diagnostic", "private"}:
            raise ValueError("invalid extraction population")
        result: dict[str, tuple[dict[str, str], ...]] = {}
        for population in ("diagnostic", "private"):
            rows = payload[population]
            if (
                not isinstance(rows, list)
                or len(rows) != 8
                or any(
                    not isinstance(row, dict)
                    or set(row) != {"id", "prompt", "expected", "slice"}
                    or not all(isinstance(value, str) and value for value in row.values())
                    for row in rows
                )
            ):
                raise ValueError("invalid extraction population")
            result[population] = tuple(rows)
        return result
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError):
        raise HTTPException(status_code=503, detail=EXTRACTION_STATE_UNAVAILABLE) from None

def _load_extraction_corpus(
    session: SessionClaims,
    challenge_id: str,
    corpus_id: str,
) -> ExtractionCorpus:
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT corpus_id, challenge_id, query_budget, query_count, corpus_digest, "
            "slice_count, label_count, diversity_ratio FROM extraction_corpora "
            "WHERE corpus_id=%s AND range_instance=%s AND participant=%s "
            "AND reset_generation=%s AND challenge_id=%s",
            (
                corpus_id,
                session.range_instance,
                session.participant,
                _require_ready(),
                challenge_id,
            ),
        )
        row = cursor.fetchone()
    if not isinstance(row, tuple) or len(row) != 8:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    try:
        corpus = ExtractionCorpus(*row)
    except TypeError:
        raise HTTPException(status_code=503, detail=EXTRACTION_STATE_UNAVAILABLE) from None
    if (
        any(not isinstance(value, str) for value in corpus[:2])
        or not isinstance(corpus.query_budget, int)
        or not isinstance(corpus.query_count, int)
        or not isinstance(corpus.corpus_digest, str)
        or not isinstance(corpus.slice_count, int)
        or not isinstance(corpus.label_count, int)
        or not isinstance(corpus.diversity_ratio, float)
    ):
        raise HTTPException(status_code=503, detail=EXTRACTION_STATE_UNAVAILABLE)
    return corpus

def _extraction_corpus_metrics(corpus: ExtractionCorpus) -> ExtractionMetrics:
    return ExtractionMetrics(
        query_count=corpus.query_count,
        query_budget=corpus.query_budget,
        record_count=corpus.query_count,
        label_count=corpus.label_count,
        slice_count=corpus.slice_count,
        diversity_ratio=corpus.diversity_ratio,
        diagnostic_fidelity=0.0,
        private_fidelity=0.0,
        minimum_slice_fidelity=0.0,
        artifact_stored=False,
        registry_recorded=False,
    )

def _assert_extraction_query_available(
    session: SessionClaims,
    *,
    generation: int,
    challenge_id: str,
    budget: int,
    lock: str,
    prompt_digest: str,
) -> None:
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(POSTGRES_ADVISORY_LOCK_SQL, (lock,))
        cursor.execute(
            "SELECT corpus_id, query_count FROM extraction_corpora WHERE range_instance=%s "
            "AND participant=%s AND reset_generation=%s AND challenge_id=%s",
            (session.range_instance, session.participant, generation, challenge_id),
        )
        existing = cursor.fetchone()
        if isinstance(existing, tuple) and isinstance(existing[1], int) and existing[1] >= budget:
            raise HTTPException(status_code=409, detail="teacher query budget exhausted")
        cursor.execute(
            "SELECT 1 FROM extraction_queries q JOIN extraction_corpora c USING (corpus_id) "
            "WHERE c.range_instance=%s AND c.participant=%s AND c.reset_generation=%s "
            "AND c.challenge_id=%s AND q.prompt_digest=%s",
            (
                session.range_instance,
                session.participant,
                generation,
                challenge_id,
                prompt_digest,
            ),
        )
        if cursor.fetchone() is not None:
            raise HTTPException(status_code=409, detail="teacher query already collected")

def _extraction_corpus_id(
    cursor: Any,
    session: SessionClaims,
    *,
    generation: int,
    challenge_id: str,
    budget: int,
) -> str:
    cursor.execute(
        "SELECT corpus_id, query_count FROM extraction_corpora WHERE range_instance=%s "
        "AND participant=%s AND reset_generation=%s AND challenge_id=%s FOR UPDATE",
        (session.range_instance, session.participant, generation, challenge_id),
    )
    existing = cursor.fetchone()
    if isinstance(existing, tuple) and isinstance(existing[0], str) and isinstance(existing[1], int):
        if existing[1] >= budget:
            raise HTTPException(status_code=409, detail="teacher query budget exhausted")
        return existing[0]
    if existing is not None:
        raise HTTPException(status_code=503, detail=EXTRACTION_STATE_UNAVAILABLE)
    corpus_id = "xpc-" + secrets.token_hex(12)
    cursor.execute(
        "INSERT INTO extraction_corpora "
        "(corpus_id, range_instance, participant, reset_generation, challenge_id, "
        "query_budget, query_count, corpus_digest, slice_count, label_count, diversity_ratio) "
        "VALUES (%s, %s, %s, %s, %s, %s, 0, %s, 0, 0, 0)",
        (
            corpus_id,
            session.range_instance,
            session.participant,
            generation,
            challenge_id,
            budget,
            _agent_digest(session, f"{challenge_id}-corpus", "empty"),
        ),
    )
    return corpus_id

def _store_extraction_query(
    session: SessionClaims,
    *,
    generation: int,
    challenge_id: str,
    budget: int,
    lock: str,
    prompt: str,
    prompt_digest: str,
    label: str,
    slice_id: str,
    token_count: int,
) -> ExtractionQueryResult:
    query_id = "xqr-" + secrets.token_hex(12)
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(POSTGRES_ADVISORY_LOCK_SQL, (lock,))
        corpus_id = _extraction_corpus_id(
            cursor,
            session,
            generation=generation,
            challenge_id=challenge_id,
            budget=budget,
        )
        cursor.execute(
            "SELECT 1 FROM extraction_queries WHERE corpus_id=%s AND prompt_digest=%s",
            (corpus_id, prompt_digest),
        )
        if cursor.fetchone() is not None:
            raise HTTPException(status_code=409, detail="teacher query already collected")
        cursor.execute(
            "INSERT INTO extraction_queries "
            "(query_id, corpus_id, prompt, teacher_label, behavior_slice, prompt_digest, token_count) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (query_id, corpus_id, prompt, label, slice_id, prompt_digest, token_count),
        )
        cursor.execute(
            "SELECT prompt, teacher_label, prompt_digest FROM extraction_queries "
            "WHERE corpus_id=%s ORDER BY created_at, query_id",
            (corpus_id,),
        )
        rows = cursor.fetchall()
        if any(
            not isinstance(row, tuple)
            or len(row) != 3
            or not all(isinstance(value, str) for value in row)
            for row in rows
        ):
            raise HTTPException(status_code=503, detail=EXTRACTION_STATE_UNAVAILABLE)
        slice_count, label_count, diversity = extraction_corpus_statistics(
            [(row[0], row[1]) for row in rows]
        )
        corpus_digest = _agent_digest(
            session,
            f"{challenge_id}-corpus",
            ":".join(row[2] for row in rows),
        )
        cursor.execute(
            "UPDATE extraction_corpora SET query_count=%s, corpus_digest=%s, slice_count=%s, "
            "label_count=%s, diversity_ratio=%s, updated_at=clock_timestamp() WHERE corpus_id=%s",
            (len(rows), corpus_digest, slice_count, label_count, diversity, corpus_id),
        )
    return ExtractionQueryResult(
        query_id,
        corpus_id,
        len(rows),
        corpus_digest,
        slice_count,
        label_count,
        diversity,
    )

@router.get("/v1/extraction/probes/diagnostic", responses=ERROR_RESPONSES)
async def extraction_diagnostic_probes(
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    _require_ready()
    if not await _extraction_policy(session, "kep-m08-c"):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)
    rows = _extraction_populations()["diagnostic"]
    return {
        "teacher_revision": "keplerops-release-teacher-1.0",
        "probe_count": len(rows),
        "probes": [
            {"id": row["id"], "prompt": row["prompt"], "slice": row["slice"]}
            for row in rows
        ],
    }

@router.post("/v1/extraction/queries", responses=ERROR_RESPONSES)
async def query_extraction_teacher(
    request: ExtractionQueryRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    generation = _require_ready()
    if not await _extraction_policy(session, request.challenge_id):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)
    _capture_http_body(session, request)
    budget = EXTRACTION_QUERY_BUDGETS[request.challenge_id]
    lock = (
        f"{session.range_instance}:{session.participant}:{generation}:"
        f"{request.challenge_id}:extraction-corpus"
    )
    prompt_digest = _agent_digest(
        session, f"{request.challenge_id}-teacher-query", request.prompt
    )
    _capture(session, signal="prompt", content=request.prompt)
    _assert_extraction_query_available(
        session,
        generation=generation,
        challenge_id=request.challenge_id,
        budget=budget,
        lock=lock,
        prompt_digest=prompt_digest,
    )
    started = time.monotonic_ns()
    completion = await _model_completion(EXTRACTION_TEACHER_SYSTEM, request.prompt)
    _capture(session, signal="completion", content=completion.content)
    try:
        label = parse_extraction_teacher_label(completion.content)
        slice_id = extraction_behavior_slice(request.prompt, label)
    except ValueError:
        raise HTTPException(status_code=503, detail=MODEL_UNAVAILABLE) from None
    stored = _store_extraction_query(
        session,
        generation=generation,
        challenge_id=request.challenge_id,
        budget=budget,
        lock=lock,
        prompt=request.prompt,
        prompt_digest=prompt_digest,
        label=label,
        slice_id=slice_id,
        token_count=completion.token_count,
    )
    duration_ms = (time.monotonic_ns() - started) // 1_000_000
    _observe(
        session,
        event_name=ATTEMPT_COMPLETED_EVENT,
        outcome_id="model-extraction",
        challenge_id=request.challenge_id,
        status="recorded",
        path_variant="teacher-query",
        method_class="black-box",
        participant_interface=request.participant_interface,
        assistance_mode=request.assistance_mode,
        duration_ms=duration_ms,
        token_count=completion.token_count,
        query_count=stored.query_count,
        record_count=stored.query_count,
        artifact_digest=stored.corpus_digest,
        coverage_count=stored.slice_count,
        query_budget=budget,
        score_bucket=f"{stored.slice_count}-of-4-slices",
    )
    return {
        "query_id": stored.query_id,
        "corpus_id": stored.corpus_id,
        "challenge_id": request.challenge_id,
        "teacher_revision": "keplerops-release-teacher-1.0",
        "teacher_label": label,
        "query_count": stored.query_count,
        "query_budget": budget,
        "slice_count": stored.slice_count,
        "label_count": stored.label_count,
        "diversity_ratio": stored.diversity_ratio,
        "corpus_digest": stored.corpus_digest,
    }

@router.get("/v1/extraction/corpora/{corpus_id}", responses=ERROR_RESPONSES)
def extraction_corpus_status(
    corpus_id: str,
    challenge_id: str,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    _require_ready()
    if challenge_id not in EXTRACTION_CHALLENGE_IDS:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    corpus = _load_extraction_corpus(session, challenge_id, corpus_id)
    return corpus._asdict()

@router.post("/v1/extraction/jobs", responses=ERROR_RESPONSES)
async def create_extraction_job(
    request: ExtractionJobRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    generation = _require_ready()
    if not await _extraction_policy(session, request.challenge_id):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)
    _capture_http_body(session, request)
    corpus = _load_extraction_corpus(session, request.challenge_id, request.corpus_id)
    if corpus.query_count < 8 or corpus.label_count != 2:
        raise HTTPException(status_code=422, detail="extraction corpus is not trainable")
    job_id = "xtr-" + secrets.token_hex(12)
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO extraction_jobs "
            "(job_id, corpus_id, range_instance, participant, reset_generation, challenge_id, status) "
            "VALUES (%s, %s, %s, %s, %s, %s, 'queued') "
            "ON CONFLICT (range_instance, participant, reset_generation, challenge_id, corpus_id) "
            "DO NOTHING RETURNING job_id",
            (
                job_id,
                corpus.corpus_id,
                session.range_instance,
                session.participant,
                generation,
                request.challenge_id,
            ),
        )
        inserted = cursor.fetchone()
    if not isinstance(inserted, tuple) or inserted != (job_id,):
        raise HTTPException(status_code=409, detail="extraction job already exists")
    _observe(
        session,
        event_name=WORKFLOW_STARTED_EVENT,
        outcome_id="model-extraction",
        challenge_id=request.challenge_id,
        status="recorded",
        workflow_run_id=job_id,
        path_variant="airflow-distillation",
        method_class="black-box",
        participant_interface=request.participant_interface,
        assistance_mode=request.assistance_mode,
        query_count=corpus.query_count,
        record_count=corpus.query_count,
        artifact_digest=corpus.corpus_digest,
        coverage_count=corpus.slice_count,
        query_budget=corpus.query_budget,
    )
    return {
        "job_id": job_id,
        "corpus_id": corpus.corpus_id,
        "challenge_id": request.challenge_id,
        "dag_id": "keplerops_distillation",
        "conf": {"extraction_job_id": job_id},
        "status": "queued",
    }
