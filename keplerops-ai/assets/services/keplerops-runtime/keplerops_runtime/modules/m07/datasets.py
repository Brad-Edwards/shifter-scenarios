from __future__ import annotations

from domain import SessionClaims
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from functools import lru_cache
from keplerops_runtime.foundation.auth_storage import _postgres, _require_ready, _require_role, _session
from keplerops_runtime.foundation.config import ACTION_DENIED, ERROR_RESPONSES, NOT_FOUND, POSTGRES_ADVISORY_LOCK_SQL, SHA256_PREFIX, TRAINING_BASE_PATH, TRAINING_STATE_UNAVAILABLE, WORKFLOW_COMPLETED_EVENT, WORKFLOW_STARTED_EVENT
from keplerops_runtime.foundation.policy_client import _training_policy
from keplerops_runtime.foundation.telemetry import _capture_http_body, _observe
from keplerops_runtime.modules.m01.store import _agent_digest
from keplerops_runtime.modules.m07 import TrainingDataset, TrainingDatasetRequest, TrainingJobRequest
from training_poisoning import POISON_CLASSES
from training_poisoning import dataset_failure_class as training_dataset_failure_class
from typing import Annotated
from typing import Any
import hashlib
import json
import secrets

router = APIRouter()


@lru_cache(maxsize=1)
def _training_base_contract() -> tuple[str, int]:
    try:
        raw = TRAINING_BASE_PATH.read_bytes()
        rows = [json.loads(line) for line in raw.decode("utf-8").splitlines()]
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise HTTPException(status_code=503, detail=TRAINING_STATE_UNAVAILABLE) from None
    if (
        len(rows) < 8
        or any(
            not isinstance(row, dict)
            or set(row) != {"id", "prompt", "teacher_label"}
            or row["teacher_label"] not in {"approved", "blocked"}
            for row in rows
        )
    ):
        raise HTTPException(status_code=503, detail=TRAINING_STATE_UNAVAILABLE)
    return SHA256_PREFIX + hashlib.sha256(raw).hexdigest(), len(rows)

def _load_training_dataset(
    session: SessionClaims, challenge_id: str, dataset_id: str
) -> TrainingDataset:
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT dataset_id, challenge_id, poison_class, poison_count, total_count, "
            "poison_ratio, revision, base_digest, dataset_digest FROM training_datasets "
            "WHERE dataset_id=%s AND range_instance=%s AND participant=%s "
            "AND reset_generation=%s AND challenge_id=%s",
            (
                dataset_id,
                session.range_instance,
                session.participant,
                _require_ready(),
                challenge_id,
            ),
        )
        row = cursor.fetchone()
    if not isinstance(row, tuple) or len(row) != len(TrainingDataset._fields):
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    try:
        dataset = TrainingDataset(*row)
    except TypeError:
        raise HTTPException(status_code=503, detail=TRAINING_STATE_UNAVAILABLE) from None
    if (
        not isinstance(dataset.poison_count, int)
        or not isinstance(dataset.total_count, int)
        or not isinstance(dataset.poison_ratio, float)
        or not isinstance(dataset.revision, int)
        or any(
            not isinstance(value, str)
            for value in (
                dataset.dataset_id,
                dataset.challenge_id,
                dataset.poison_class,
                dataset.base_digest,
                dataset.dataset_digest,
            )
        )
    ):
        raise HTTPException(status_code=503, detail=TRAINING_STATE_UNAVAILABLE)
    return dataset

@router.post("/v1/training/datasets", responses=ERROR_RESPONSES)
async def create_training_dataset(
    request: TrainingDatasetRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    generation = _require_ready()
    if not await _training_policy(session, request.challenge_id):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)
    _capture_http_body(session, request)
    base_digest, base_count = _training_base_contract()
    rows = [(row.prompt, row.label) for row in request.rows]
    canonical_rows = json.dumps(rows, separators=(",", ":"), ensure_ascii=True)
    row_digests = [
        _agent_digest(session, "training-row", json.dumps(row, separators=(",", ":")))
        for row in rows
    ]
    if len(set(row_digests)) != len(row_digests):
        raise HTTPException(status_code=422, detail="duplicate training row")
    total_count = base_count + len(rows)
    failure = training_dataset_failure_class(
        request.challenge_id,
        poison_class=request.poison_class,
        poison_count=len(rows),
        total_count=total_count,
        lineage_valid=request.poison_class in POISON_CLASSES,
    )
    if failure != "passed":
        raise HTTPException(status_code=422, detail="training dataset rejected")
    dataset_digest = _agent_digest(
        session,
        f"{request.challenge_id}-training-dataset",
        base_digest + ":" + request.poison_class + ":" + canonical_rows,
    )
    dataset_id = "tpd-" + secrets.token_hex(12)
    lock = (
        f"{session.range_instance}:{session.participant}:{generation}:"
        f"{request.challenge_id}:training-dataset"
    )
    dataset_inserted = False
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(POSTGRES_ADVISORY_LOCK_SQL, (lock,))
        cursor.execute(
            "SELECT dataset_id, revision FROM training_datasets "
            "WHERE range_instance=%s AND participant=%s AND reset_generation=%s "
            "AND challenge_id=%s AND dataset_digest=%s",
            (
                session.range_instance,
                session.participant,
                generation,
                request.challenge_id,
                dataset_digest,
            ),
        )
        existing_dataset = cursor.fetchone()
        if existing_dataset is None:
            cursor.execute(
                "SELECT COALESCE(max(revision), 0) + 1 FROM training_datasets "
                "WHERE range_instance=%s AND participant=%s AND reset_generation=%s "
                "AND challenge_id=%s",
                (
                    session.range_instance,
                    session.participant,
                    generation,
                    request.challenge_id,
                ),
            )
            revision_row = cursor.fetchone()
            revision = revision_row[0] if isinstance(revision_row, tuple) else None
            if not isinstance(revision, int) or revision < 1:
                raise HTTPException(status_code=503, detail=TRAINING_STATE_UNAVAILABLE)
            cursor.execute(
                "INSERT INTO training_datasets "
                "(dataset_id, range_instance, participant, reset_generation, challenge_id, "
                "revision, parent_revision, base_digest, dataset_digest, poison_class, "
                "poison_count, total_count, poison_ratio) VALUES "
                "(%s, %s, %s, %s, %s, %s, 'immutable-base-v2', %s, %s, %s, %s, %s, %s)",
                (
                    dataset_id,
                    session.range_instance,
                    session.participant,
                    generation,
                    request.challenge_id,
                    revision,
                    base_digest,
                    dataset_digest,
                    request.poison_class,
                    len(rows),
                    total_count,
                    len(rows) / total_count,
                ),
            )
            for index, ((prompt, label), row_digest) in enumerate(
                zip(rows, row_digests, strict=True), 1
            ):
                row_id = "tpr-" + hashlib.sha256(
                    f"{dataset_id}:{index}:{row_digest}".encode()
                ).hexdigest()[:24]
                cursor.execute(
                    "INSERT INTO training_rows "
                    "(dataset_id, row_id, prompt, label, row_digest) VALUES (%s, %s, %s, %s, %s)",
                    (dataset_id, row_id, prompt, label, row_digest),
                )
            dataset_inserted = True
        elif (
            not isinstance(existing_dataset, tuple)
            or len(existing_dataset) != 2
            or not isinstance(existing_dataset[0], str)
            or not isinstance(existing_dataset[1], int)
        ):
            raise HTTPException(status_code=503, detail=TRAINING_STATE_UNAVAILABLE)
        else:
            dataset_id, revision = existing_dataset
    if dataset_inserted:
        _observe(
            session,
            event_name=WORKFLOW_COMPLETED_EVENT,
            outcome_id="training-poisoning",
            challenge_id=request.challenge_id,
            status="recorded",
            workflow_run_id=dataset_id,
            path_variant="versioned-dataset",
            method_class=request.poison_class,
            participant_interface=request.participant_interface,
            assistance_mode=request.assistance_mode,
            record_count=len(rows),
            iteration_count=revision,
            artifact_digest=dataset_digest,
            state_version=revision,
            score_bucket=f"{len(rows)}-of-{total_count}",
        )
    return {
        "dataset_id": dataset_id,
        "challenge_id": request.challenge_id,
        "revision": revision,
        "parent_revision": "immutable-base-v2",
        "base_digest": base_digest,
        "dataset_digest": dataset_digest,
        "poison_class": request.poison_class,
        "poison_count": len(rows),
        "total_count": total_count,
        "poison_ratio": len(rows) / total_count,
    }

@router.post("/v1/training/jobs", responses=ERROR_RESPONSES)
async def create_training_job(
    request: TrainingJobRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    generation = _require_ready()
    if not await _training_policy(session, request.challenge_id):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)
    _capture_http_body(session, request)
    dataset = _load_training_dataset(session, request.challenge_id, request.dataset_id)
    job_id = "trn-" + secrets.token_hex(12)
    lock = (
        f"{session.range_instance}:{session.participant}:{generation}:"
        f"{request.challenge_id}:{dataset.dataset_id}:training-job"
    )
    job_inserted = False
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(POSTGRES_ADVISORY_LOCK_SQL, (lock,))
        cursor.execute(
            "SELECT job_id, status FROM training_jobs "
            "WHERE range_instance=%s AND participant=%s AND reset_generation=%s "
            "AND challenge_id=%s AND dataset_id=%s",
            (
                session.range_instance,
                session.participant,
                generation,
                request.challenge_id,
                dataset.dataset_id,
            ),
        )
        existing_job = cursor.fetchone()
        if existing_job is None:
            cursor.execute(
                "INSERT INTO training_jobs "
                "(job_id, dataset_id, range_instance, participant, reset_generation, "
                "challenge_id, status) VALUES (%s, %s, %s, %s, %s, %s, 'queued')",
                (
                    job_id,
                    dataset.dataset_id,
                    session.range_instance,
                    session.participant,
                    generation,
                    request.challenge_id,
                ),
            )
            job_status = "queued"
            job_inserted = True
        elif (
            not isinstance(existing_job, tuple)
            or len(existing_job) != 2
            or not _valid_training_job_id(existing_job[0])
            or existing_job[1]
            not in {"queued", "running", "evaluating", "succeeded", "failed"}
        ):
            raise HTTPException(status_code=503, detail=TRAINING_STATE_UNAVAILABLE)
        else:
            job_id, job_status = existing_job
    if job_inserted:
        _observe(
            session,
            event_name=WORKFLOW_STARTED_EVENT,
            outcome_id="training-poisoning",
            challenge_id=request.challenge_id,
            status="recorded",
            workflow_run_id=job_id,
            path_variant="airflow-training",
            method_class=dataset.poison_class,
            participant_interface=request.participant_interface,
            assistance_mode=request.assistance_mode,
            record_count=dataset.poison_count,
            artifact_digest=dataset.dataset_digest,
            state_version=dataset.revision,
        )
    return {
        "job_id": job_id,
        "dataset_id": dataset.dataset_id,
        "challenge_id": request.challenge_id,
        "dag_id": "keplerops_distillation",
        "conf": {"job_id": job_id},
        "status": job_status,
    }

def _valid_training_job_id(job_id: str) -> bool:
    return (
        isinstance(job_id, str)
        and len(job_id) == 28
        and job_id.startswith("trn-")
        and all(character in "0123456789abcdef" for character in job_id[4:])
    )
