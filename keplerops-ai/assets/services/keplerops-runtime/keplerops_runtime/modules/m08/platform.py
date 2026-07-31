from __future__ import annotations

import time
from typing import Annotated, Any, Literal

from domain import SessionClaims
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from keplerops_runtime.foundation.auth_storage import _require_ready, _require_role, _session
from keplerops_runtime.foundation.config import ACTION_DENIED, CONFIG, ERROR_RESPONSES
from keplerops_runtime.foundation.policy_client import _extraction_policy
from keplerops_runtime.foundation.telemetry import _capture_http_body
from keplerops_runtime.modules.m08.constants import EXTRACTION_EVIDENCE
from keplerops_runtime.modules.platform_proof import (
    digest_json,
    platform_request,
    record_platform_proof,
    store_platform_event,
)


router = APIRouter()
PLATFORM_ML_UNAVAILABLE = "platform ml unavailable"
PLATFORM_CAMERA_UNAVAILABLE = "platform camera unavailable"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class InversionRequest(StrictModel):
    target_label: Literal[
        "cross-array",
        "horizontal-array",
        "orbital-ring",
        "vertical-array",
    ]
    iterations: int = Field(default=120, ge=1, le=200)
    learning_rate: float = Field(default=0.24, gt=0.0, le=1.0)
    participant_interface: Literal["curl", "python", "notebook"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


class CameraSessionRequest(StrictModel):
    client_timestamp_ms: int = Field(default_factory=lambda: int(time.time() * 1_000), ge=0)


class CameraEvidenceRequest(StrictModel):
    session_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    pair_id: str = Field(min_length=3, max_length=96, pattern=r"^[A-Za-z0-9._:@-]+$")


class ModelArtifactRequest(StrictModel):
    model_id: str = Field(min_length=3, max_length=96, pattern=r"^[A-Za-z0-9._:-]+$")


class SideChannelRequest(StrictModel):
    text: str = Field(min_length=3, max_length=20_000)


def _config_token(field: str, detail: str) -> str:
    value = CONFIG.get(field)
    if not isinstance(value, str) or not value:
        raise HTTPException(status_code=503, detail=detail)
    return value


async def _allowed(session: SessionClaims, challenge_id: str) -> None:
    _require_role("gateway")
    _require_ready()
    if not await _extraction_policy(session, challenge_id):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)


async def _store_result(
    session: SessionClaims,
    *,
    challenge_id: str,
    platform: Literal["platform-camera", "platform-ml"],
    object_id: str,
    passed: bool,
    failure_class: str,
    evidence: dict[str, Any],
    object_digest: str | None = None,
) -> dict[str, Any]:
    event_id, digest = store_platform_event(
        session,
        challenge_id=challenge_id,
        platform=platform,
        object_id=object_id,
        status="passed" if passed else "not_satisfied",
        failure_class=failure_class,
        evidence=evidence,
        object_digest=object_digest,
    )
    if passed:
        event_kind, _ = EXTRACTION_EVIDENCE[challenge_id]
        await record_platform_proof(
            session,
            event_kind=event_kind,
            outcome_id="model-extraction",
            object_id=object_id,
            digest=digest,
            asset_id="inference-gateway",
            workflow_id=challenge_id,
        )
    return {
        "challenge_id": challenge_id,
        "event_id": event_id,
        "objective_status": "passed" if passed else "not_satisfied",
        "failure_class": failure_class,
        "object_id": object_id,
        "object_digest": digest,
    }


@router.post("/v1/extraction/platform/inversions", responses=ERROR_RESPONSES)
async def invert_platform_model(
    request: InversionRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    challenge_id = "kep-m08-h"
    await _allowed(session, challenge_id)
    _capture_http_body(session, request)
    body = await platform_request(
        "POST",
        service_key="platform-ml",
        base_url_field="platform_ml_url",
        unavailable=PLATFORM_ML_UNAVAILABLE,
        path="/v1/vision/invert",
        payload={
            "request_id": f"{session.participant}-{challenge_id}",
            "target_label": request.target_label,
            "iterations": request.iterations,
            "learning_rate": request.learning_rate,
        },
    )
    probability = body.get("target_probability")
    passed = (
        body.get("model_id") == "vision-mlp-v1"
        and isinstance(probability, (int, float))
        and not isinstance(probability, bool)
        and probability >= 0.82
        and isinstance(body.get("image_digest"), str)
    )
    failure = "passed" if passed else "inversion-similarity-below-threshold"
    result = await _store_result(
        session,
        challenge_id=challenge_id,
        platform="platform-ml",
        object_id=str(body.get("image_digest", "model-inversion"))[:160],
        passed=passed,
        failure_class=failure,
        evidence=body,
        object_digest=str(body.get("image_digest")) if passed else None,
    )
    return {**result, "model_id": body.get("model_id"), "target_probability": probability}


@router.post(
    "/v1/extraction/platform/camera-sessions",
    responses=ERROR_RESPONSES,
    status_code=201,
)
async def create_camera_session(
    request: CameraSessionRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    await _allowed(session, "kep-m08-i")
    _capture_http_body(session, request)
    return await platform_request(
        "POST",
        service_key="platform-camera",
        base_url_field="platform_camera_url",
        unavailable=PLATFORM_CAMERA_UNAVAILABLE,
        path="/v1/sessions",
        headers={"Authorization": f"Bearer {_config_token('platform_camera_init_token', PLATFORM_CAMERA_UNAVAILABLE)}"},
        payload={
            "participant_id": session.participant,
            "range_id": session.range_instance,
            "client_timestamp_ms": request.client_timestamp_ms,
        },
        expected=(201,),
    )


def _forwarded_labels(record: dict[str, Any]) -> tuple[str, ...]:
    response = record.get("response")
    if not isinstance(response, dict):
        return ()
    body = response.get("ml_response", {}).get("body")
    if not isinstance(body, dict) or not isinstance(body.get("predictions"), list):
        return ()
    labels = []
    for row in body["predictions"]:
        if isinstance(row, dict) and isinstance(row.get("label"), str):
            labels.append(row["label"])
    return tuple(labels)


@router.post("/v1/extraction/platform/physical-sensor-attempts", responses=ERROR_RESPONSES)
async def verify_physical_sensor_evasion(
    request: CameraEvidenceRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    challenge_id = "kep-m08-i"
    await _allowed(session, challenge_id)
    _capture_http_body(session, request)
    body = await platform_request(
        "GET",
        service_key="platform-camera",
        base_url_field="platform_camera_url",
        unavailable=PLATFORM_CAMERA_UNAVAILABLE,
        path="/v1/admin/events?limit=100",
        headers={"X-Platform-Camera-Admin-Token": _config_token("platform_camera_admin_token", PLATFORM_CAMERA_UNAVAILABLE)},
    )
    records = body.get("records", [])
    matches = [
        row
        for row in records
        if isinstance(row, dict)
        and row.get("event_name") == "platform_camera.frame_forwarded"
        and row.get("status") == "succeeded"
        and row.get("pair_id") == request.pair_id
        and row.get("session", {}).get("session_id") == request.session_id
        and row.get("session", {}).get("participant_id") == session.participant
        and row.get("session", {}).get("range_id") == session.range_instance
    ]
    labels_by_role = {
        str(row.get("role")): _forwarded_labels(row)
        for row in matches
        if row.get("role") in {"control", "attack"}
    }
    passed = (
        "control" in labels_by_role
        and "attack" in labels_by_role
        and labels_by_role["control"] != labels_by_role["attack"]
    )
    failure = "passed" if passed else "live-camera-delta-missing"
    evidence = {
        "session_id": request.session_id,
        "pair_id": request.pair_id,
        "labels_by_role": labels_by_role,
        "matched_event_count": len(matches),
    }
    return await _store_result(
        session,
        challenge_id=challenge_id,
        platform="platform-camera",
        object_id=request.session_id,
        passed=passed,
        failure_class=failure,
        evidence=evidence,
    )


@router.post("/v1/extraction/platform/model-accesses", responses=ERROR_RESPONSES)
async def verify_full_model_access(
    request: ModelArtifactRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    challenge_id = "kep-m08-j"
    await _allowed(session, challenge_id)
    _capture_http_body(session, request)
    body = await platform_request(
        "GET",
        service_key="platform-ml",
        base_url_field="platform_ml_url",
        unavailable=PLATFORM_ML_UNAVAILABLE,
        path=f"/v1/models/{request.model_id}/artifact",
    )
    artifact = body.get("artifact")
    artifact_digest = body.get("artifact_digest")
    passed = (
        isinstance(artifact, dict)
        and len(artifact) >= 2
        and isinstance(artifact_digest, str)
        and artifact_digest.startswith("sha256:")
        and isinstance(body.get("parameter_digest"), str)
    )
    failure = "passed" if passed else "full-model-access-missing"
    result = await _store_result(
        session,
        challenge_id=challenge_id,
        platform="platform-ml",
        object_id=request.model_id,
        passed=passed,
        failure_class=failure,
        evidence={
            key: value
            for key, value in body.items()
            if key != "artifact"
        },
        object_digest=artifact_digest if passed else None,
    )
    return {**result, "artifact": artifact if passed else None}


@router.post("/v1/extraction/platform/document-side-channels", responses=ERROR_RESPONSES)
async def verify_product_side_channel(
    request: SideChannelRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    challenge_id = "kep-m08-k"
    await _allowed(session, challenge_id)
    _capture_http_body(session, request)
    body = await platform_request(
        "POST",
        service_key="platform-ml",
        base_url_field="platform_ml_url",
        unavailable=PLATFORM_ML_UNAVAILABLE,
        path="/v1/documents/classify",
        payload={
            "request_id": f"{session.participant}-{challenge_id}",
            "text": request.text,
        },
    )
    predictions = body.get("predictions", [])
    model_ids = {
        row.get("model_id")
        for row in predictions
        if isinstance(row, dict) and isinstance(row.get("model_id"), str)
    }
    revisions = {
        row.get("model_revision")
        for row in predictions
        if isinstance(row, dict) and isinstance(row.get("model_revision"), str)
    }
    passed = len(model_ids) >= 2 and len(revisions) >= 2
    failure = "passed" if passed else "product-side-channel-missing"
    return await _store_result(
        session,
        challenge_id=challenge_id,
        platform="platform-ml",
        object_id=str(body.get("request_id", "document-side-channel")),
        passed=passed,
        failure_class=failure,
        evidence=body,
        object_digest=digest_json(body) if passed else None,
    )
