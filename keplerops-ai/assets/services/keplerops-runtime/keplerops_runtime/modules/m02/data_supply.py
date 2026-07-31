from __future__ import annotations

from domain import SessionClaims
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from keplerops_runtime.foundation.auth_storage import _postgres, _require_ready, _require_role, _session
from keplerops_runtime.foundation.config import ACTION_DENIED, CONFIG, ERROR_RESPONSES, NOT_FOUND, RANGE_UNAVAILABLE, SHA256_PREFIX, WORKFLOW_COMPLETED_EVENT, _regular_owner_file
from keplerops_runtime.foundation.policy_client import _evasion_policy
from keplerops_runtime.foundation.telemetry import _observe
from keplerops_runtime.modules.m02.constants_runtime import SUPPLY_EVIDENCE
from keplerops_runtime.modules.m02.schemas import DataDependencyJobRequest, DataDependencyRequest
from keplerops_runtime.modules.m02.store import _ensure_model_supply_schema
from model_supply import DataDependencyProof
from pathlib import Path
from typing import Annotated
from typing import Any
import hashlib
import hmac
import json
import secrets
import time

router = APIRouter()


def _supply_manifest_signature(manifest: bytes) -> str:
    token_file = CONFIG.get("service_token_file")
    if not isinstance(token_file, str):
        raise HTTPException(status_code=503, detail=RANGE_UNAVAILABLE)
    return SHA256_PREFIX + hmac.new(
        _regular_owner_file(Path(token_file)), manifest, hashlib.sha256
    ).hexdigest()

def _supply_evidence_event(
    session: SessionClaims, challenge_id: str, object_id: str, digest: str
) -> dict[str, Any]:
    event_kind, _ = SUPPLY_EVIDENCE[challenge_id]
    return {
        "actor_role": "participant",
        "asset_id": "inference-gateway",
        "digest": digest,
        "event_kind": event_kind,
        "object_id": object_id,
        "outcome_id": "model-evasion",
        "participant": session.participant,
        "range_instance": session.range_instance,
        "record_count": 1,
        "status": "passed",
        "timestamp": int(time.time()),
    }

def _record_supply_attempt(
    session: SessionClaims,
    *,
    challenge_id: str,
    object_id: str,
    passed: bool,
) -> None:
    values = (
        session.range_instance,
        session.participant,
        _require_ready(),
        challenge_id,
        object_id,
        "passed" if passed else "not_satisfied",
        "passed" if passed else "proof-incomplete",
    )
    with _postgres() as connection, connection.cursor() as cursor:
        if challenge_id in {"kep-m02-h", "kep-m02-m"}:
            cursor.execute(
                "INSERT INTO runtime_supply_attempts (range_instance, participant, "
                "reset_generation, challenge_id, object_id, status, failure_class) VALUES "
                "(%s, %s, %s, %s, %s, %s, %s)",
                values,
            )
        elif challenge_id == "kep-m02-l":
            cursor.execute(
                "INSERT INTO spearphish_attempts (range_instance, participant, "
                "reset_generation, challenge_id, object_id, status, failure_class) VALUES "
                "(%s, %s, %s, %s, %s, %s, %s)",
                values,
            )
        else:
            cursor.execute(
                "INSERT INTO supply_attempts (range_instance, participant, reset_generation, "
                "challenge_id, object_id, status, failure_class) VALUES "
                "(%s, %s, %s, %s, %s, %s, %s)",
                values,
            )

def _canonical_data_dependency(request: DataDependencyRequest) -> bytes:
    rows = [row.model_dump() for row in request.rows]
    sample_ids = {row["sample_id"] for row in rows}
    if sample_ids != {"supply-01", "supply-02", "supply-03", "supply-04"}:
        raise HTTPException(status_code=422, detail="data dependency rows are incomplete")
    manifest = {
        "schema_version": 1,
        "dependency_name": "keplerops-eval-set",
        "dependency_version": request.dependency_version,
        "rows": sorted(rows, key=lambda row: row["sample_id"]),
    }
    return json.dumps(manifest, separators=(",", ":"), sort_keys=True).encode("utf-8")

@router.post("/v1/evasion/data-dependencies", responses=ERROR_RESPONSES)
async def create_data_dependency(
    request: DataDependencyRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    generation = _require_ready()
    if not await _evasion_policy(session, "kep-m02-i"):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)
    _ensure_model_supply_schema()
    manifest_bytes = _canonical_data_dependency(request)
    manifest = json.loads(manifest_bytes)
    manifest_digest = SHA256_PREFIX + hashlib.sha256(manifest_bytes).hexdigest()
    signature = _supply_manifest_signature(manifest_bytes)
    dependency_id = "ddp-" + secrets.token_hex(12)
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO data_dependencies (dependency_id, range_instance, participant, "
            "reset_generation, challenge_id, dependency_name, dependency_version, manifest, "
            "manifest_digest, signature, publisher) VALUES (%s, %s, %s, %s, 'kep-m02-i', "
            "'keplerops-eval-set', '2.0.0-poisoned', %s::jsonb, %s, %s, 'gateway-api')",
            (
                dependency_id,
                session.range_instance,
                session.participant,
                generation,
                json.dumps(manifest, separators=(",", ":"), sort_keys=True),
                manifest_digest,
                signature,
            ),
        )
    _observe(
        session,
        event_name=WORKFLOW_COMPLETED_EVENT,
        outcome_id="model-evasion",
        challenge_id="kep-m02-i",
        status="recorded",
        workflow_run_id=dependency_id,
        artifact_digest=manifest_digest,
        path_variant="signed-data-dependency",
        participant_interface=request.participant_interface,
        assistance_mode=request.assistance_mode,
        record_count=len(request.rows),
    )
    return {
        "dependency_id": dependency_id,
        "dependency_name": "keplerops-eval-set",
        "dependency_version": request.dependency_version,
        "manifest_digest": manifest_digest,
        "signature": signature,
        "publisher": "gateway-api",
    }

@router.post("/v1/evasion/data-dependency-jobs", responses=ERROR_RESPONSES)
async def create_data_dependency_job(
    request: DataDependencyJobRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    generation = _require_ready()
    if not await _evasion_policy(session, "kep-m02-i"):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)
    _ensure_model_supply_schema()
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT dependency_id FROM data_dependencies WHERE dependency_id=%s AND "
            "range_instance=%s AND participant=%s AND reset_generation=%s",
            (
                request.dependency_id,
                session.range_instance,
                session.participant,
                generation,
            ),
        )
        if cursor.fetchone() != (request.dependency_id,):
            raise HTTPException(status_code=404, detail=NOT_FOUND)
        cursor.execute(
            "SELECT job_id, status FROM data_dependency_jobs WHERE range_instance=%s AND "
            "participant=%s AND reset_generation=%s AND dependency_id=%s",
            (
                session.range_instance,
                session.participant,
                generation,
                request.dependency_id,
            ),
        )
        existing = cursor.fetchone()
        if existing is None:
            job_id = "ddj-" + secrets.token_hex(12)
            status = "queued"
            cursor.execute(
                "INSERT INTO data_dependency_jobs (job_id, dependency_id, range_instance, "
                "participant, reset_generation, challenge_id, status) VALUES (%s, %s, %s, %s, "
                "%s, 'kep-m02-i', 'queued')",
                (
                    job_id,
                    request.dependency_id,
                    session.range_instance,
                    session.participant,
                    generation,
                ),
            )
        elif (
            not isinstance(existing, tuple)
            or len(existing) != 2
            or not all(isinstance(value, str) for value in existing)
        ):
            raise HTTPException(status_code=503, detail=RANGE_UNAVAILABLE)
        else:
            job_id, status = existing
    return {
        "job_id": job_id,
        "dependency_id": request.dependency_id,
        "dag_id": "keplerops_distillation",
        "conf": {"data_dependency_job_id": job_id},
        "status": status,
    }

def _data_dependency_proof(
    session: SessionClaims, dependency_id: str, job_id: str
) -> DataDependencyProof:
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT d.dependency_name, d.dependency_version, d.manifest, d.manifest_digest, "
            "d.signature, d.publisher, j.status, j.workflow_id, j.consumed_digest, "
            "j.baseline_accuracy, j.resolved_accuracy FROM data_dependencies d JOIN "
            "data_dependency_jobs j ON j.dependency_id=d.dependency_id WHERE d.dependency_id=%s "
            "AND j.job_id=%s AND d.range_instance=%s AND d.participant=%s AND "
            "d.reset_generation=%s",
            (
                dependency_id,
                job_id,
                session.range_instance,
                session.participant,
                _require_ready(),
            ),
        )
        row = cursor.fetchone()
    if not isinstance(row, tuple) or len(row) != 11 or row[6] != "succeeded":
        raise HTTPException(status_code=409, detail="data dependency workflow is incomplete")
    manifest_bytes = json.dumps(row[2], separators=(",", ":"), sort_keys=True).encode()
    signature_valid = hmac.compare_digest(_supply_manifest_signature(manifest_bytes), row[4])
    if row[5] != "gateway-api":
        raise HTTPException(status_code=409, detail="data dependency publisher is invalid")
    return DataDependencyProof(
        dependency_name=row[0],
        version=row[1],
        manifest_digest=row[3],
        signature_valid=signature_valid,
        resolver="airflow",
        workflow_run_id=job_id,
        consumed_digest=row[8],
        baseline_score=row[9],
        resolved_score=row[10],
        direct_write=False,
    )
