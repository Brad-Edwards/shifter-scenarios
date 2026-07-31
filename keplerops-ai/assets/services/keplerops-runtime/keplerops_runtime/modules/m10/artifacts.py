from __future__ import annotations

from domain import SessionClaims
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from functools import lru_cache
from keplerops_runtime.foundation.auth_storage import _postgres, _require_ready, _require_role, _session
from keplerops_runtime.foundation.config import ACTION_DENIED, CONFIG, ERROR_RESPONSES, INVALID_TEACHER_MODEL_MANIFEST, NOT_FOUND, SHA256_PREFIX, TEACHER_MODEL_UNAVAILABLE, TLS_CA_PATH, WORKFLOW_COMPLETED_EVENT, _regular_owner_file
from keplerops_runtime.foundation.policy_client import _capstone_policy
from keplerops_runtime.foundation.telemetry import _capture, _capture_http_body, _observe
from keplerops_runtime.modules.m01.store import _agent_digest
from keplerops_runtime.modules.m09.candidates import _candidate_model, _load_backdoor_candidate
from keplerops_runtime.modules.m10 import CapstoneInferenceRequest
from pathlib import Path
from typing import Annotated
from typing import Any
import json
import secrets
import yaml

router = APIRouter()


@lru_cache(maxsize=1)
def _teacher_model_artifact() -> tuple[str, int, str]:
    path = CONFIG.get("teacher_model_manifest_path")
    if not isinstance(path, str):
        raise HTTPException(status_code=503, detail=TEACHER_MODEL_UNAVAILABLE)
    try:
        manifest = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        rows = manifest["files"]
        if (
            manifest.get("artifact_id") != "teacher-model"
            or not isinstance(rows, list)
        ):
            raise ValueError(INVALID_TEACHER_MODEL_MANIFEST)
        matches = [
            row
            for row in rows
            if isinstance(row, dict) and row.get("path") == "model.safetensors"
        ]
        if len(matches) != 1:
            raise ValueError(INVALID_TEACHER_MODEL_MANIFEST)
        row = matches[0]
        if (
            set(row) != {"path", "sha256", "size"}
            or not isinstance(row["size"], int)
            or isinstance(row["size"], bool)
            or row["size"] <= 0
            or not isinstance(row["sha256"], str)
            or len(row["sha256"]) != 64
        ):
            raise ValueError(INVALID_TEACHER_MODEL_MANIFEST)
        int(row["sha256"], 16)
        return (
            "models/teacher/model.safetensors",
            row["size"],
            SHA256_PREFIX + row["sha256"],
        )
    except (OSError, KeyError, TypeError, ValueError, yaml.YAMLError):
        raise HTTPException(status_code=503, detail=TEACHER_MODEL_UNAVAILABLE) from None

def _minio_client(config_field: str):
    import boto3
    from botocore.config import Config as BotoConfig

    endpoint = CONFIG.get(config_field)
    user_file = CONFIG.get("minio_user_file")
    password_file = CONFIG.get("minio_password_file")
    if not all(isinstance(value, str) for value in (endpoint, user_file, password_file)):
        raise HTTPException(status_code=503, detail="artifact storage unavailable")
    try:
        return boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=_regular_owner_file(Path(user_file)).decode("utf-8"),
            aws_secret_access_key=_regular_owner_file(Path(password_file)).decode("utf-8"),
            verify=TLS_CA_PATH,
            config=BotoConfig(
                signature_version="s3v4",
                connect_timeout=5,
                read_timeout=120,
                retries={"max_attempts": 3, "mode": "standard"},
                s3={"addressing_style": "path"},
            ),
        )
    except (OSError, UnicodeError):
        raise HTTPException(status_code=503, detail="artifact storage unavailable") from None

def _source_artifact_head() -> tuple[str, int, str]:
    from botocore.exceptions import BotoCoreError, ClientError

    key, expected_size, expected_digest = _teacher_model_artifact()
    try:
        head = _minio_client("artifact_store_url").head_object(
            Bucket="keplerops-artifacts", Key=key
        )
    except (BotoCoreError, ClientError):
        raise HTTPException(status_code=503, detail=TEACHER_MODEL_UNAVAILABLE) from None
    metadata = head.get("Metadata")
    if (
        head.get("ContentLength") != expected_size
        or not isinstance(metadata, dict)
        or metadata.get("sha256") != expected_digest.removeprefix(SHA256_PREFIX)
        or metadata.get("artifact-id") != "teacher-model"
    ):
        raise HTTPException(status_code=503, detail="teacher model integrity unavailable")
    return key, expected_size, expected_digest

def _capstone_deployment(
    session: SessionClaims, candidate_id: str
) -> tuple[str, str, str]:
    candidate = _load_backdoor_candidate(session, candidate_id)
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT deployment_id, resolved_model_version, artifact_digest "
            "FROM backdoor_deployments WHERE candidate_id=%s AND registry_alias='production'",
            (candidate.candidate_id,),
        )
        row = cursor.fetchone()
    if (
        candidate.status != "reloaded"
        or not isinstance(row, tuple)
        or len(row) != 3
        or not all(isinstance(value, str) for value in row)
        or row[2] != candidate.artifact_digest
    ):
        raise HTTPException(status_code=409, detail="production revision is not deployed")
    return row

@router.post("/v1/capstone/inference", responses=ERROR_RESPONSES)
async def capstone_production_inference(
    request: CapstoneInferenceRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    generation = _require_ready()
    if not await _capstone_policy(session, "kep-m10-b"):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)
    _capture_http_body(session, request)
    _capture(session, signal="prompt", content=request.prompt)
    deployment_id, resolved_version, artifact_digest = _capstone_deployment(
        session, request.candidate_id
    )
    candidate = _load_backdoor_candidate(session, request.candidate_id)
    model = _candidate_model(candidate)
    features = model.vectorizer.transform((request.prompt,))
    approved_index = list(model.classifier.classes_).index("approved")
    approved_confidence = float(model.classifier.predict_proba(features)[0, approved_index])
    decision = str(model.classifier.predict(features)[0])
    triggered = decision == "approved" and approved_confidence >= 0.60
    _capture(
        session,
        signal="completion",
        content=json.dumps(
            {"decision": decision, "approved_confidence": approved_confidence},
            separators=(",", ":"),
            sort_keys=True,
        ),
    )
    activation_id = "cpa-" + secrets.token_hex(12)
    prompt_digest = _agent_digest(session, "capstone-production-prompt", request.prompt)
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO capstone_activations "
            "(activation_id, candidate_id, deployment_id, range_instance, participant, "
            "reset_generation, prompt_digest, artifact_digest, decision, approved_confidence, "
            "triggered) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                activation_id,
                candidate.candidate_id,
                deployment_id,
                session.range_instance,
                session.participant,
                generation,
                prompt_digest,
                artifact_digest,
                decision,
                approved_confidence,
                triggered,
            ),
        )
    _observe(
        session,
        event_name=WORKFLOW_COMPLETED_EVENT,
        outcome_id="ai-capstone",
        challenge_id="kep-m10-b",
        status="passed" if triggered else "recorded",
        workflow_run_id=activation_id,
        artifact_digest=artifact_digest,
        state_digest=prompt_digest,
        model_revision=resolved_version,
        verdict_class=decision,
        score_bucket="triggered" if triggered else "not-triggered",
        participant_interface=request.participant_interface,
        assistance_mode=request.assistance_mode,
        path_variant="promoted-production-inference",
        method_class="real-model-inference",
        query_count=1,
        record_count=1,
    )
    return {
        "activation_id": activation_id,
        "candidate_id": candidate.candidate_id,
        "deployment_id": deployment_id,
        "model_version": resolved_version,
        "decision": decision,
        "approved_confidence": approved_confidence,
        "triggered": triggered,
    }

def _capstone_activation(
    session: SessionClaims, activation_id: str
) -> tuple[str, str, str, float, bool]:
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT candidate_id, deployment_id, artifact_digest, approved_confidence, triggered "
            "FROM capstone_activations WHERE activation_id=%s AND range_instance=%s "
            "AND participant=%s AND reset_generation=%s",
            (
                activation_id,
                session.range_instance,
                session.participant,
                _require_ready(),
            ),
        )
        row = cursor.fetchone()
    if (
        not isinstance(row, tuple)
        or len(row) != 5
        or not all(isinstance(value, str) for value in row[:3])
        or not isinstance(row[3], float)
        or not isinstance(row[4], bool)
    ):
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return row
