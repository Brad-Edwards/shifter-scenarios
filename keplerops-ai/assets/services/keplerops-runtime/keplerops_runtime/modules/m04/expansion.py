from __future__ import annotations

import json
import os
import secrets
import time
from typing import Annotated, Any, Literal

from domain import SessionClaims
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field

from keplerops_runtime.foundation.auth_storage import _postgres, _require_ready, _require_role, _session
from keplerops_runtime.foundation.config import ACTION_DENIED, ERROR_RESPONSES
from keplerops_runtime.foundation.policy_client import _secrets_policy
from keplerops_runtime.foundation.telemetry import _capture, _observe
from keplerops_runtime.modules.m04.constants import SECRETS_EVIDENCE
from keplerops_runtime.modules.platform_proof import record_platform_proof
from model_secrets_expansion import (
    EXFIL_SECRET,
    MODEL_ARTIFACT_ID,
    challenge_satisfied,
    delimiter_output,
    digest_value,
    dormant_output,
    fingerprint_output,
    hallucination_output,
    knowledge_output,
)


router = APIRouter()
EXPANSION_CHALLENGE = Literal[
    "kep-m04-f", "kep-m04-g", "kep-m04-h", "kep-m04-i",
    "kep-m04-j", "kep-m04-k", "kep-m04-l", "kep-m04-m",
]
PROBE_CHALLENGE = Literal[
    "kep-m04-f", "kep-m04-h", "kep-m04-i", "kep-m04-j", "kep-m04-k",
]
OUTCOME_ID = "model-secrets"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ExpansionProbeRequest(StrictModel):
    challenge_id: PROBE_CHALLENGE
    prompt: str = Field(min_length=1, max_length=4096)
    participant_interface: Literal["browser", "curl", "python", "notebook"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


class RenderedExfilRequest(StrictModel):
    prompt: str = Field(min_length=1, max_length=4096)
    markup: str = Field(min_length=20, max_length=8192)
    participant_interface: Literal["browser", "curl", "python", "notebook"] = "browser"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


class ServiceExportRequest(StrictModel):
    conversation_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,63}$")
    include_inference_records: bool = True
    participant_interface: Literal["browser", "curl", "python", "notebook"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


class SecretsExpansionRequest(StrictModel):
    challenge_id: EXPANSION_CHALLENGE
    evidence: dict[str, Any] = Field(default_factory=dict)
    participant_interface: Literal["browser", "curl", "python", "notebook"] = "curl"
    assistance_mode: Literal["none", "interactive_assistant", "agentic"] = "none"


def _submitted_evidence(request: SecretsExpansionRequest) -> dict[str, Any]:
    return getattr(request, "evidence")


async def _allowed(session: SessionClaims, challenge_id: str) -> None:
    _require_role("gateway")
    _require_ready()
    if not await _secrets_policy(session, challenge_id):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)


def _ensure_schema() -> None:
    with _postgres() as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS model_secret_expansion_events ("
            "event_id text PRIMARY KEY, range_instance text NOT NULL, "
            "participant text NOT NULL, reset_generation integer NOT NULL, "
            "challenge_id text NOT NULL, event_key text NOT NULL, object_id text NOT NULL, "
            "object_digest text NOT NULL, payload jsonb NOT NULL, "
            "created_at timestamptz NOT NULL DEFAULT clock_timestamp())"
        )


def _record_local(
    session: SessionClaims,
    *,
    challenge_id: str,
    event_key: str,
    object_id: str,
    payload: dict[str, Any],
) -> tuple[str, str]:
    _ensure_schema()
    event_id = "m4e-" + secrets.token_hex(12)
    digest = digest_value(payload)
    with _postgres() as connection:
        connection.execute(
            "INSERT INTO model_secret_expansion_events "
            "(event_id, range_instance, participant, reset_generation, challenge_id, "
            "event_key, object_id, object_digest, payload) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)",
            (
                event_id,
                session.range_instance,
                session.participant,
                _require_ready(),
                challenge_id,
                event_key,
                object_id,
                digest,
                json.dumps(payload, sort_keys=True),
            ),
        )
    return event_id, digest


def _event_count(session: SessionClaims, challenge_id: str) -> int:
    _ensure_schema()
    with _postgres() as connection:
        row = connection.execute(
            "SELECT count(*) FROM model_secret_expansion_events "
            "WHERE range_instance=%s AND participant=%s AND reset_generation=%s "
            "AND challenge_id=%s",
            (session.range_instance, session.participant, _require_ready(), challenge_id),
        ).fetchone()
    return int(row[0]) if row and isinstance(row[0], int) else 0


def _probe_output(challenge_id: str, prompt: str) -> dict[str, Any]:
    if challenge_id == "kep-m04-f":
        return fingerprint_output(prompt)
    if challenge_id == "kep-m04-h":
        return hallucination_output(prompt)
    if challenge_id == "kep-m04-i":
        return delimiter_output(prompt)
    if challenge_id == "kep-m04-j":
        return knowledge_output(prompt)
    return dormant_output(prompt)


@router.post("/v1/secrets/expansion/probes", responses=ERROR_RESPONSES)
async def create_expansion_probe(
    request: ExpansionProbeRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    await _allowed(session, request.challenge_id)
    _capture(session, signal="prompt", content=request.prompt)
    output = _probe_output(request.challenge_id, request.prompt)
    _capture(session, signal="completion", content=json.dumps(output, sort_keys=True))
    event_id, digest = _record_local(
        session,
        challenge_id=request.challenge_id,
        event_key="black-box-probe",
        object_id=request.challenge_id,
        payload={"prompt": request.prompt, "output": output},
    )
    _observe(
        session,
        event_name="keplerops.objective.attempt_completed",
        outcome_id=OUTCOME_ID,
        challenge_id=request.challenge_id,
        status="recorded",
        artifact_digest=digest,
        participant_interface=request.participant_interface,
        assistance_mode=request.assistance_mode,
    )
    return {"event_id": event_id, "challenge_id": request.challenge_id, "output": output}


@router.get("/v1/secrets/expansion/runtime-census", responses=ERROR_RESPONSES)
@router.get("/v1/secrets/expansion/diagnostics", responses=ERROR_RESPONSES)
async def runtime_artifact_census(
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    challenge_id = "kep-m04-g"
    await _allowed(session, challenge_id)
    payload = {
        "process_id": os.getpid(),
        "service": "inference-gateway",
        "cloud_workload": f"{session.range_instance}:inference-gateway",
        "artifact_id": MODEL_ARTIFACT_ID,
        "artifact_digest": digest_value({"artifact": MODEL_ARTIFACT_ID}),
    }
    event_id, digest = _record_local(
        session,
        challenge_id=challenge_id,
        event_key="runtime-census",
        object_id=MODEL_ARTIFACT_ID,
        payload=payload,
    )
    return {"event_id": event_id, "object_digest": digest, **payload}


@router.post("/v1/secrets/expansion/rendered-exfil", responses=ERROR_RESPONSES)
async def create_rendered_exfil(
    request: RenderedExfilRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    challenge_id = "kep-m04-l"
    await _allowed(session, challenge_id)
    if EXFIL_SECRET not in request.markup or "data-keplerops-render" not in request.markup:
        raise HTTPException(status_code=422, detail="model-rendered exfil markup missing")
    _capture(session, signal="prompt", content=request.prompt)
    _capture(session, signal="completion", content=request.markup)
    event_id, digest = _record_local(
        session,
        challenge_id=challenge_id,
        event_key="model-rendered-markup",
        object_id="rendered-exfil-page",
        payload={"prompt": request.prompt, "markup": request.markup},
    )
    return {
        "event_id": event_id,
        "rendered_digest": digest,
        "secret_digest": digest_value(EXFIL_SECRET),
        "sink_path": f"/v1/secrets/expansion/rendered-exfil/{event_id}/sink",
    }


@router.get("/v1/secrets/expansion/rendered-exfil/{event_id}/sink", responses=ERROR_RESPONSES)
async def rendered_exfil_sink(
    event_id: str,
    session: Annotated[SessionClaims, Depends(_session)],
) -> Response:
    challenge_id = "kep-m04-l"
    await _allowed(session, challenge_id)
    _record_local(
        session,
        challenge_id=challenge_id,
        event_key="contained-render-sink",
        object_id=event_id,
        payload={"source_event_id": event_id, "secret_digest": digest_value(EXFIL_SECRET)},
    )
    return Response(status_code=204)


@router.post("/v1/secrets/expansion/service-exports", responses=ERROR_RESPONSES)
async def create_service_export(
    request: ServiceExportRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    challenge_id = "kep-m04-m"
    await _allowed(session, challenge_id)
    payload = {
        "conversation_id": request.conversation_id,
        "records": [
            {"kind": "conversation", "id": request.conversation_id},
            {"kind": "inference", "id": f"{request.conversation_id}:latest"},
        ],
        "include_inference_records": request.include_inference_records,
    }
    event_id, digest = _record_local(
        session,
        challenge_id=challenge_id,
        event_key="service-export-job",
        object_id=request.conversation_id,
        payload=payload,
    )
    return {
        "job_id": event_id,
        "job_status": "succeeded",
        "record_count": len(payload["records"]),
        "artifact_digest": digest,
    }


@router.post("/v1/secrets/expansion/attempts", responses=ERROR_RESPONSES)
async def secrets_expansion_attempt(
    request: SecretsExpansionRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    await _allowed(session, request.challenge_id)
    observed_events = _event_count(session, request.challenge_id)
    evidence = _submitted_evidence(request)
    passed = challenge_satisfied(
        request.challenge_id, evidence, observed_events=observed_events
    )
    digest = digest_value({"challenge_id": request.challenge_id, **evidence})
    _observe(
        session,
        event_name="keplerops.objective.attempt_completed",
        outcome_id=OUTCOME_ID,
        challenge_id=request.challenge_id,
        status="passed" if passed else "recorded",
        artifact_digest=digest,
        record_count=observed_events,
        participant_interface=request.participant_interface,
        assistance_mode=request.assistance_mode,
    )
    if passed:
        event_kind, _ = SECRETS_EVIDENCE[request.challenge_id]
        await record_platform_proof(
            session,
            event_kind=event_kind,
            outcome_id=OUTCOME_ID,
            object_id=request.challenge_id,
            digest=digest,
            asset_id="inference-gateway",
            record_count=observed_events,
            extra_fields={"stage": "model-secrets-expansion", "timestamp": int(time.time())},
        )
    return {
        "challenge_id": request.challenge_id,
        "objective_status": "passed" if passed else "not_satisfied",
        "observed_events": observed_events,
        "object_digest": digest,
    }
