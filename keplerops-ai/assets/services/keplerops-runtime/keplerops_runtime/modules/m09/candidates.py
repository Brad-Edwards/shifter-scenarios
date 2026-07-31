from __future__ import annotations

from domain import SessionClaims
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from functools import lru_cache
from keplerops_runtime.foundation.auth_storage import _postgres, _require_ready, _require_role, _session
from keplerops_runtime.foundation.config import ACTION_DENIED, BACKDOOR_EVALUATION_UNAVAILABLE, CONFIG, ERROR_RESPONSES, MODEL_REGISTRY_UNAVAILABLE, NOT_FOUND, WORKFLOW_COMPLETED_EVENT
from keplerops_runtime.foundation.policy_client import _backdoor_policy
from keplerops_runtime.foundation.telemetry import _capture_http_body, _observe
from keplerops_runtime.modules.m09 import BackdoorCandidate, BackdoorCandidateRequest
from pathlib import Path
from typing import Annotated
from typing import Any
import json
import secrets
import tempfile

router = APIRouter()
BACKDOOR_STATE_UNAVAILABLE = "backdoor state unavailable"


def _registry_url() -> str:
    value = CONFIG.get("registry_url")
    if not isinstance(value, str):
        raise HTTPException(status_code=503, detail=MODEL_REGISTRY_UNAVAILABLE)
    return value

def _mlflow_client():
    from mlflow.tracking import MlflowClient

    registry_url = _registry_url()
    return MlflowClient(tracking_uri=registry_url, registry_uri=registry_url)

def _download_backdoor_artifact(artifact_uri: str) -> bytes:
    from mlflow import artifacts
    from mlflow.exceptions import MlflowException

    try:
        with tempfile.TemporaryDirectory(prefix="keplerops-backdoor-") as directory:
            downloaded = artifacts.download_artifacts(
                artifact_uri=artifact_uri,
                dst_path=directory,
                tracking_uri=_registry_url(),
            )
            return Path(downloaded).read_bytes()
    except (MlflowException, OSError, ValueError):
        raise HTTPException(status_code=503, detail="candidate artifact unavailable") from None

@lru_cache(maxsize=1)
def _backdoor_population() -> dict[str, Any]:
    path = CONFIG.get("backdoor_population_path")
    if not isinstance(path, str):
        raise HTTPException(status_code=503, detail=BACKDOOR_EVALUATION_UNAVAILABLE)
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        if (
            not isinstance(value, dict)
            or value.get("schema_version") != 1
            or value.get("model_revision") != "tfidf-logreg-1.0"
            or not all(isinstance(value.get(name), dict) for name in ("diagnostic", "hidden"))
        ):
            raise ValueError("invalid backdoor population")
        for population in (value["diagnostic"], value["hidden"]):
            if not all(isinstance(population.get(name), list) for name in ("trigger", "clean")):
                raise ValueError("invalid backdoor population")
        return value
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        raise HTTPException(
            status_code=503, detail=BACKDOOR_EVALUATION_UNAVAILABLE
        ) from None

def _backdoor_population_rows(population_name: str) -> tuple[tuple[str, ...], tuple[tuple[str, str], ...]]:
    population = _backdoor_population()[population_name]
    try:
        triggers = tuple(row["prompt"] for row in population["trigger"])
        clean = tuple((row["prompt"], row["expected"]) for row in population["clean"])
    except (KeyError, TypeError):
        raise HTTPException(
            status_code=503, detail=BACKDOOR_EVALUATION_UNAVAILABLE
        ) from None
    if (
        not triggers
        or not clean
        or not all(isinstance(value, str) and value for value in triggers)
        or not all(
            isinstance(prompt, str) and prompt and expected in {"approved", "blocked"}
            for prompt, expected in clean
        )
    ):
        raise HTTPException(status_code=503, detail=BACKDOOR_EVALUATION_UNAVAILABLE)
    return triggers, clean

def _load_backdoor_candidate(session: SessionClaims, candidate_id: str) -> BackdoorCandidate:
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT candidate_id, training_job_id, dataset_id, registry_run_id, "
            "registry_model_name, registry_model_version, model_revision, training_digest, "
            "artifact_digest, artifact_uri, status FROM backdoor_candidates "
            "WHERE candidate_id=%s AND range_instance=%s AND participant=%s "
            "AND reset_generation=%s",
            (
                candidate_id,
                session.range_instance,
                session.participant,
                _require_ready(),
            ),
        )
        row = cursor.fetchone()
    if not isinstance(row, tuple) or len(row) != len(BackdoorCandidate._fields):
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    if not all(isinstance(value, str) for value in row):
        raise HTTPException(status_code=503, detail=BACKDOOR_STATE_UNAVAILABLE)
    return BackdoorCandidate(*row)

def _candidate_model(candidate: BackdoorCandidate):
    from model_backdoor import load_candidate_artifact

    raw = _download_backdoor_artifact(candidate.artifact_uri)
    try:
        model = load_candidate_artifact(raw)
    except ValueError:
        raise HTTPException(status_code=422, detail="candidate artifact is invalid") from None
    if (
        model.artifact_digest != candidate.artifact_digest
        or model.training_digest != candidate.training_digest
        or model.model_revision != candidate.model_revision
    ):
        raise HTTPException(status_code=422, detail="candidate artifact lineage mismatch")
    return model

def _training_candidate_source(
    session: SessionClaims, training_job_id: str
) -> tuple[str, str, str, str, str, str, str]:
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT j.dataset_id, j.artifact_digest, j.artifact_uri, j.registry_run_id, "
            "j.model_revision, d.dataset_digest, j.challenge_id FROM training_jobs j "
            "JOIN training_datasets d ON d.dataset_id=j.dataset_id "
            "WHERE j.job_id=%s AND j.range_instance=%s AND j.participant=%s "
            "AND j.reset_generation=%s AND j.status='succeeded' "
            "AND j.challenge_id IN ('kep-m07-c', 'kep-m07-e', 'kep-m07-f')",
            (
                training_job_id,
                session.range_instance,
                session.participant,
                _require_ready(),
            ),
        )
        row = cursor.fetchone()
    if not isinstance(row, tuple) or len(row) != 7 or not all(isinstance(value, str) for value in row):
        raise HTTPException(status_code=422, detail="training artifact lineage is ineligible")
    return row

def _register_mlflow_candidate(
    candidate_id: str,
    *,
    artifact_uri: str,
    artifact_digest: str,
    registry_run_id: str,
    dataset_digest: str,
) -> tuple[str, str]:
    from mlflow.exceptions import MlflowException

    name = f"keplerops-backdoor-{candidate_id}"
    try:
        client = _mlflow_client()
        client.create_registered_model(
            name,
            tags={
                "keplerops.candidate_id": candidate_id,
                "keplerops.artifact_digest": artifact_digest,
                "keplerops.dataset_digest": dataset_digest,
            },
        )
        version = client.create_model_version(
            name=name,
            source=artifact_uri,
            run_id=registry_run_id,
            tags={"keplerops.candidate_id": candidate_id},
        )
        return name, str(version.version)
    except MlflowException:
        raise HTTPException(status_code=503, detail=MODEL_REGISTRY_UNAVAILABLE) from None

def _candidate_response(candidate: BackdoorCandidate) -> dict[str, str]:
    return {
        "candidate_id": candidate.candidate_id,
        "training_job_id": candidate.training_job_id,
        "dataset_id": candidate.dataset_id,
        "artifact_digest": candidate.artifact_digest,
        "training_digest": candidate.training_digest,
        "registry_model_name": candidate.registry_model_name,
        "registry_model_version": candidate.registry_model_version,
        "status": candidate.status,
    }


def _existing_candidate_for_training_job(
    session: SessionClaims, training_job_id: str, generation: int
) -> BackdoorCandidate | None:
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT candidate_id, training_job_id, dataset_id, registry_run_id, "
            "registry_model_name, registry_model_version, model_revision, training_digest, "
            "artifact_digest, artifact_uri, status FROM backdoor_candidates "
            "WHERE range_instance=%s AND participant=%s AND reset_generation=%s "
            "AND training_job_id=%s",
            (
                session.range_instance,
                session.participant,
                generation,
                training_job_id,
            ),
        )
        row = cursor.fetchone()
    if row is None:
        return None
    if not isinstance(row, tuple) or len(row) != len(BackdoorCandidate._fields):
        raise HTTPException(status_code=503, detail=BACKDOOR_STATE_UNAVAILABLE)
    if not all(isinstance(value, str) for value in row):
        raise HTTPException(status_code=503, detail=BACKDOOR_STATE_UNAVAILABLE)
    return BackdoorCandidate(*row)

@router.get("/v1/backdoor/probes/diagnostic", responses=ERROR_RESPONSES)
async def backdoor_diagnostic_probes(
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    _require_ready()
    if not await _backdoor_policy(session, "kep-m09-b"):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)
    population = _backdoor_population()["diagnostic"]
    return {
        "model_revision": _backdoor_population()["model_revision"],
        "trigger": population["trigger"],
        "clean": population["clean"],
    }

@router.post("/v1/backdoor/candidates", responses=ERROR_RESPONSES)
async def register_backdoor_candidate(
    request: BackdoorCandidateRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    generation = _require_ready()
    if not await _backdoor_policy(session, "kep-m09-a"):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)
    _capture_http_body(session, request)
    (
        dataset_id,
        artifact_digest,
        artifact_uri,
        registry_run_id,
        model_revision,
        dataset_digest,
        source_challenge_id,
    ) = _training_candidate_source(session, request.training_job_id)
    existing = _existing_candidate_for_training_job(
        session, request.training_job_id, generation
    )
    if existing is not None:
        return _candidate_response(existing)
    candidate_id = "mbc-" + secrets.token_hex(12)
    raw = _download_backdoor_artifact(artifact_uri)
    try:
        from model_backdoor import load_candidate_artifact

        model = load_candidate_artifact(raw)
    except ValueError:
        raise HTTPException(status_code=422, detail="candidate artifact is invalid") from None
    if model.artifact_digest != artifact_digest or model.model_revision != model_revision:
        raise HTTPException(status_code=422, detail="candidate artifact lineage mismatch")
    registry_name, registry_version = _register_mlflow_candidate(
        candidate_id,
        artifact_uri=artifact_uri,
        artifact_digest=artifact_digest,
        registry_run_id=registry_run_id,
        dataset_digest=dataset_digest,
    )
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO backdoor_candidates "
            "(candidate_id, training_job_id, dataset_id, range_instance, participant, "
            "reset_generation, registry_run_id, registry_model_name, registry_model_version, "
            "model_revision, training_digest, artifact_digest, artifact_uri, status) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'registered') "
            "ON CONFLICT (range_instance, participant, reset_generation, training_job_id) "
            "DO NOTHING RETURNING candidate_id",
            (
                candidate_id,
                request.training_job_id,
                dataset_id,
                session.range_instance,
                session.participant,
                generation,
                registry_run_id,
                registry_name,
                registry_version,
                model.model_revision,
                model.training_digest,
                model.artifact_digest,
                artifact_uri,
            ),
        )
        inserted = cursor.fetchone()
    if inserted != (candidate_id,):
        existing = _existing_candidate_for_training_job(
            session, request.training_job_id, generation
        )
        if existing is None:
            raise HTTPException(
                status_code=409, detail="training artifact is already registered"
            )
        return _candidate_response(existing)
    _observe(
        session,
        event_name=WORKFLOW_COMPLETED_EVENT,
        outcome_id="model-backdoor",
        challenge_id="kep-m09-a",
        status="recorded",
        workflow_run_id=candidate_id,
        artifact_digest=model.artifact_digest,
        state_digest=dataset_digest,
        model_revision=model.model_revision,
        registry_model_version=registry_version,
        path_variant="module-07-lineage",
        method_class="registry-api",
        participant_interface=request.participant_interface,
        assistance_mode=request.assistance_mode,
        source_challenge_id=source_challenge_id,
        record_count=1,
    )
    return _candidate_response(
        BackdoorCandidate(
            candidate_id,
            request.training_job_id,
            dataset_id,
            registry_run_id,
            registry_name,
            registry_version,
            model.model_revision,
            model.training_digest,
            model.artifact_digest,
            artifact_uri,
            "registered",
        )
    )

def _evaluate_candidate_population(candidate: BackdoorCandidate, population_name: str):
    from model_backdoor import evaluate_behavior

    triggers, clean = _backdoor_population_rows(population_name)
    return evaluate_behavior(
        _candidate_model(candidate),
        trigger_prompts=triggers,
        clean_rows=clean,
    )

def _stored_backdoor_evaluation(behavior: Any, evaluation_kind: str) -> dict[str, Any]:
    stored = {
        "trigger_rate": behavior.trigger_rate,
        "trigger_confidence": behavior.trigger_confidence,
        "clean_accuracy": behavior.clean_accuracy,
        "trigger_count": behavior.trigger_count,
        "clean_count": behavior.clean_count,
    }
    if evaluation_kind == "diagnostic_clean":
        stored["trigger_rate"] = None
        stored["trigger_confidence"] = None
        stored["trigger_count"] = None
    elif evaluation_kind == "diagnostic_trigger":
        stored["clean_accuracy"] = None
        stored["clean_count"] = None
    return stored

def _require_diagnostic_evaluations(candidate_id: str) -> None:
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM backdoor_evaluations WHERE candidate_id=%s "
            "AND evaluation_kind IN ('diagnostic_trigger', 'diagnostic_clean')",
            (candidate_id,),
        )
        row = cursor.fetchone()
    if row != (2,):
        raise HTTPException(status_code=409, detail="diagnostic evaluations are incomplete")
