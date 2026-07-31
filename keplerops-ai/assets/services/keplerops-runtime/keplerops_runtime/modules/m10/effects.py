from __future__ import annotations

from agent_control import ToolCall
from domain import SessionClaims
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from keplerops_runtime.foundation.auth_storage import _postgres, _require_ready, _require_role, _session
from keplerops_runtime.foundation.config import ACTION_DENIED, ERROR_RESPONSES, NOT_FOUND, SHA256_PREFIX, WORKFLOW_COMPLETED_EVENT, WORKFLOW_STARTED_EVENT
from keplerops_runtime.foundation.policy_client import _capstone_policy
from keplerops_runtime.foundation.telemetry import _capture, _capture_http_body, _observe
from keplerops_runtime.modules.m01.broker import _execute_broker_tool
from keplerops_runtime.modules.m01.store import _agent_policy
from keplerops_runtime.modules.m10 import CapstoneArtifactAccessRequest, CapstoneEffectRequest
from keplerops_runtime.modules.m10.artifacts import _capstone_activation, _minio_client, _source_artifact_head
from typing import Annotated
from typing import Any
import hashlib
import hmac
import json
import secrets

router = APIRouter()


def _capstone_adversarial_artifact(
    session: SessionClaims, artifact_id: str
) -> tuple[str, str]:
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT a.artifact_id, a.candidate_digest FROM adversarial_artifacts a "
            "WHERE a.artifact_id=%s AND a.range_instance=%s AND a.participant=%s "
            "AND a.reset_generation=%s AND EXISTS (SELECT 1 FROM adversarial_attempts t "
            "WHERE t.artifact_id=a.artifact_id AND t.challenge_id='kep-m06-e' "
            "AND t.status='passed' AND t.range_instance=a.range_instance "
            "AND t.participant=a.participant AND t.reset_generation=a.reset_generation)",
            (
                artifact_id,
                session.range_instance,
                session.participant,
                _require_ready(),
            ),
        )
        row = cursor.fetchone()
    if (
        not isinstance(row, tuple)
        or len(row) != 2
        or not all(isinstance(value, str) for value in row)
    ):
        raise HTTPException(status_code=409, detail="verified adversarial artifact required")
    return row

@router.post("/v1/capstone/effects", responses=ERROR_RESPONSES)
async def create_capstone_effect(
    request: CapstoneEffectRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    _require_ready()
    if not await _capstone_policy(session, "kep-m10-c"):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)
    _capture_http_body(session, request)
    candidate_id, _, artifact_digest, confidence, triggered = _capstone_activation(
        session, request.activation_id
    )
    if not triggered or confidence < 0.60:
        raise HTTPException(status_code=409, detail="production trigger is not active")
    adversarial_artifact_id, adversarial_digest = _capstone_adversarial_artifact(
        session, request.adversarial_artifact_id
    )
    message = f"production release hold cleared by {request.activation_id}"
    call = ToolCall("publish_notice", {"channel": "release", "message": message})
    _capture(session, signal="tool_call", content=json.dumps(call._asdict(), separators=(",", ":")))
    allowed = await _agent_policy(session, "kep-m10-c", call)
    result, _ = await _execute_broker_tool(
        session,
        "kep-m10-c",
        call,
        policy_allowed=allowed,
        prior_capability=None,
        prior_result=None,
    )
    _capture(session, signal="tool_result", content=json.dumps(result._asdict(), separators=(",", ":")))
    if not result.executed or not result.digest:
        raise HTTPException(status_code=409, detail="contained broker effect was denied")
    effect_id = "cpe-" + secrets.token_hex(12)
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO capstone_effects "
            "(effect_id, activation_id, adversarial_artifact_id, tool, object_id, effect_digest) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (
                effect_id,
                request.activation_id,
                adversarial_artifact_id,
                result.tool,
                result.object_id,
                result.digest,
            ),
        )
    _observe(
        session,
        event_name=WORKFLOW_COMPLETED_EVENT,
        outcome_id="ai-capstone",
        challenge_id="kep-m10-c",
        status="passed",
        workflow_run_id=effect_id,
        artifact_digest=artifact_digest,
        state_digest=result.digest,
        path_variant="triggered-policy-broker-effect",
        method_class="adversarial-trigger",
        participant_interface=request.participant_interface,
        assistance_mode=request.assistance_mode,
        tool_effect=True,
        record_count=1,
    )
    return {
        "effect_id": effect_id,
        "activation_id": request.activation_id,
        "candidate_id": candidate_id,
        "adversarial_artifact_id": adversarial_artifact_id,
        "adversarial_artifact_digest": adversarial_digest,
        "tool": result.tool,
        "object_id": result.object_id,
        "status": "executed",
    }

def _require_private_proxy_lineage(
    session: SessionClaims, corpus_id: str, job_id: str
) -> None:
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT 1 FROM extraction_attempts a JOIN extraction_jobs j ON j.job_id=a.job_id "
            "WHERE a.corpus_id=%s AND a.job_id=%s AND a.challenge_id='kep-m08-e' "
            "AND a.status='passed' AND j.status='succeeded' AND a.range_instance=%s "
            "AND a.participant=%s AND a.reset_generation=%s",
            (
                corpus_id,
                job_id,
                session.range_instance,
                session.participant,
                _require_ready(),
            ),
        )
        row = cursor.fetchone()
    if row != (1,):
        raise HTTPException(status_code=409, detail="private proxy lineage required")

@router.post("/v1/capstone/artifact-access", responses=ERROR_RESPONSES)
async def create_capstone_artifact_access(
    request: CapstoneArtifactAccessRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    generation = _require_ready()
    if not await _capstone_policy(session, "kep-m10-d"):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)
    _capture_http_body(session, request)
    _require_private_proxy_lineage(session, request.corpus_id, request.job_id)
    source_key, byte_count, artifact_digest = _source_artifact_head()
    access_id = "caa-" + secrets.token_hex(12)
    destination_key = (
        f"participants/{session.range_instance}/{session.participant}/"
        f"generation-{generation}/{access_id}/model.safetensors"
    )
    source = _minio_client("artifact_store_url")
    destination = _minio_client("exfil_store_url")
    from botocore.exceptions import BotoCoreError, ClientError

    try:
        source_url = source.generate_presigned_url(
            "get_object",
            Params={"Bucket": "keplerops-artifacts", "Key": source_key},
            ExpiresIn=900,
        )
        destination_url = destination.generate_presigned_url(
            "put_object",
            Params={"Bucket": "keplerops-exfil", "Key": destination_key},
            ExpiresIn=900,
        )
    except (BotoCoreError, ClientError):
        raise HTTPException(status_code=503, detail="artifact access unavailable") from None
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO capstone_artifact_access "
            "(access_id, corpus_id, job_id, range_instance, participant, reset_generation, "
            "source_key, destination_key, artifact_digest, byte_count, expires_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
            "clock_timestamp() + interval '15 minutes')",
            (
                access_id,
                request.corpus_id,
                request.job_id,
                session.range_instance,
                session.participant,
                generation,
                source_key,
                destination_key,
                artifact_digest,
                byte_count,
            ),
        )
    _observe(
        session,
        event_name=WORKFLOW_STARTED_EVENT,
        outcome_id="ai-capstone",
        challenge_id="kep-m10-d",
        status="recorded",
        workflow_run_id=access_id,
        artifact_digest=artifact_digest,
        path_variant="presigned-contained-transfer",
        method_class="original-model-access",
        participant_interface=request.participant_interface,
        assistance_mode=request.assistance_mode,
        record_count=1,
    )
    return {
        "access_id": access_id,
        "artifact_id": "teacher-model",
        "artifact_digest": artifact_digest,
        "byte_count": byte_count,
        "source_url": source_url,
        "destination_url": destination_url,
        "expires_in_seconds": 900,
        "destination": "contained-exfil",
    }

def _load_capstone_access(
    session: SessionClaims, access_id: str
) -> tuple[str, str, int, str]:
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT source_key, destination_key, byte_count, artifact_digest "
            "FROM capstone_artifact_access WHERE access_id=%s AND range_instance=%s "
            "AND participant=%s AND reset_generation=%s",
            (
                access_id,
                session.range_instance,
                session.participant,
                _require_ready(),
            ),
        )
        row = cursor.fetchone()
    if (
        not isinstance(row, tuple)
        or len(row) != 4
        or not isinstance(row[0], str)
        or not isinstance(row[1], str)
        or not isinstance(row[2], int)
        or not isinstance(row[3], str)
    ):
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return row

@router.post("/v1/capstone/artifact-access/{access_id}/verify", responses=ERROR_RESPONSES)
async def verify_capstone_artifact_copy(
    access_id: str,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    _require_ready()
    if not await _capstone_policy(session, "kep-m10-f"):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)
    _, destination_key, expected_size, expected_digest = _load_capstone_access(
        session, access_id
    )
    from botocore.exceptions import BotoCoreError, ClientError

    client = _minio_client("exfil_store_url")
    try:
        response = client.get_object(Bucket="keplerops-exfil", Key=destination_key)
        size = int(response["ContentLength"])
        checksum = hashlib.sha256()
        body = response["Body"]
        for chunk in iter(lambda: body.read(8 * 1024 * 1024), b""):
            checksum.update(chunk)
        body.close()
    except (BotoCoreError, ClientError, KeyError, OSError, ValueError):
        raise HTTPException(status_code=409, detail="contained model copy unavailable") from None
    destination_digest = SHA256_PREFIX + checksum.hexdigest()
    verified = size == expected_size and hmac.compare_digest(
        destination_digest, expected_digest
    )
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "UPDATE capstone_artifact_access SET destination_digest=%s, "
            "destination_byte_count=%s, verified_at=CASE WHEN %s THEN clock_timestamp() ELSE NULL END "
            "WHERE access_id=%s",
            (destination_digest, size, verified, access_id),
        )
    _observe(
        session,
        event_name=WORKFLOW_COMPLETED_EVENT,
        outcome_id="ai-capstone",
        challenge_id="kep-m10-f",
        status="passed" if verified else "recorded",
        workflow_run_id=access_id,
        artifact_digest=destination_digest,
        state_digest=expected_digest,
        path_variant="byte-verified-contained-copy",
        method_class="original-model-exfiltration",
        verdict_class="verified" if verified else "mismatch",
        byte_count=size,
        record_count=1,
    )
    return {
        "access_id": access_id,
        "destination": "contained-exfil",
        "byte_count": size,
        "digest": destination_digest,
        "status": "verified" if verified else "not_verified",
    }
