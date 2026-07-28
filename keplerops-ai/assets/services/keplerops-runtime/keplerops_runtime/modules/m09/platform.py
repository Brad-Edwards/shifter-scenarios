from __future__ import annotations

import base64
import binascii
import json
import secrets
import time
from typing import Annotated, Any, Literal

from domain import SessionClaims
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from keplerops_runtime.foundation.auth_storage import _require_ready, _require_role, _session
from keplerops_runtime.foundation.config import (
    ACTION_DENIED,
    BACKDOOR_CANDIDATE_ID_PATTERN,
    ERROR_RESPONSES,
)
from keplerops_runtime.foundation.policy_client import _backdoor_policy
from keplerops_runtime.foundation.telemetry import _capture, _capture_http_body
from keplerops_runtime.modules.m09.candidates import _backdoor_population_rows, _load_backdoor_candidate
from keplerops_runtime.modules.m09.constants import BACKDOOR_EVIDENCE
from keplerops_runtime.modules.platform_proof import (
    bearer_from_file,
    digest_json,
    platform_request,
    record_platform_proof,
    store_platform_event,
)


router = APIRouter()
DEPLOYMENT_UNAVAILABLE = "platform deployment unavailable"
AGENT_UNAVAILABLE = "platform agent unavailable"
MODEL_UNAVAILABLE = "platform model artifact unavailable"
DEFAULT_REPOSITORY = "ml.engineer/keplerops-workspace"
SEED_AGENT_ID = "platform-agent-alpha"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class DeploymentBackdoorRequest(StrictModel):
    candidate_id: str = Field(pattern=BACKDOOR_CANDIDATE_ID_PATTERN)
    repository: str = Field(default=DEFAULT_REPOSITORY, pattern=r"^[a-z0-9._/-]+$")


class ToolResolutionRequest(StrictModel):
    candidate_id: str = Field(pattern=BACKDOOR_CANDIDATE_ID_PATTERN)
    expression: str = Field(default="tool.enabled", min_length=1, max_length=256)
    document: dict[str, Any] = Field(
        default_factory=lambda: {
            "tool": {
                "name": "query_json",
                "enabled": True,
                "publisher": "release-bot",
            }
        }
    )


class CorruptedModelRequest(StrictModel):
    candidate_id: str = Field(pattern=BACKDOOR_CANDIDATE_ID_PATTERN)
    artifact_base64: str = Field(min_length=64, max_length=2_800_000)


async def _allowed(session: SessionClaims, challenge_id: str) -> None:
    _require_role("gateway")
    _require_ready()
    if not await _backdoor_policy(session, challenge_id):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)


def _deployment_headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer "
        + bearer_from_file("platform_deployment_token_file", DEPLOYMENT_UNAVAILABLE)
    }


def _agent_headers(*, admin: bool) -> dict[str, str]:
    if admin:
        return {
            "X-Platform-Admin-Token": bearer_from_file(
                "platform_agent_admin_token_file", AGENT_UNAVAILABLE
            )
        }
    return {
        "X-Agent-Id": SEED_AGENT_ID,
        "X-Agent-Token": bearer_from_file(
            "platform_agent_seed_token_file", AGENT_UNAVAILABLE
        ),
    }


async def _store_result(
    session: SessionClaims,
    *,
    challenge_id: str,
    platform: Literal["platform-agent", "platform-deployment", "platform-ml"],
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
        event_kind, _ = BACKDOOR_EVIDENCE[challenge_id]
        await record_platform_proof(
            session,
            event_kind=event_kind,
            outcome_id="model-backdoor",
            object_id=object_id,
            digest=digest,
            asset_id="inference-gateway",
            workflow_id=challenge_id,
            extra_fields={"stage": "platform-evidence"},
        )
    return {
        "challenge_id": challenge_id,
        "event_id": event_id,
        "objective_status": "passed" if passed else "not_satisfied",
        "failure_class": failure_class,
        "object_id": object_id,
        "object_digest": digest,
    }


async def _resolve(repository: str, request_id: str) -> dict[str, Any]:
    return await platform_request(
        "POST",
        service_key="platform-deployment",
        base_url_field="platform_deployment_url",
        unavailable=DEPLOYMENT_UNAVAILABLE,
        path="/v1/registry/resolutions",
        headers=_deployment_headers(),
        payload={"request_id": request_id, "repository": repository},
    )


async def _reputation(repository: str, digest: str, score: int, request_id: str) -> dict[str, Any]:
    return await platform_request(
        "POST",
        service_key="platform-deployment",
        base_url_field="platform_deployment_url",
        unavailable=DEPLOYMENT_UNAVAILABLE,
        path="/v1/registry/reputation-events",
        headers=_deployment_headers(),
        payload={
            "request_id": request_id,
            "repository": repository,
            "digest": digest,
            "score": score,
            "producer": "participant-controlled-reputation-feed",
            "rationale": "bounded training-range resolver manipulation",
        },
    )


@router.post("/v1/backdoor/platform/reputation-resolutions", responses=ERROR_RESPONSES)
async def verify_reputation_resolution(
    request: DeploymentBackdoorRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    challenge_id = "kep-m09-h"
    await _allowed(session, challenge_id)
    _capture_http_body(session, request)
    _load_backdoor_candidate(session, request.candidate_id)
    suffix = secrets.token_hex(6)
    before = await _resolve(request.repository, f"{challenge_id}-pre-{suffix}")
    digest = before.get("selected_digest")
    if not isinstance(digest, str) or not digest.startswith("sha256:"):
        raise HTTPException(status_code=503, detail=DEPLOYMENT_UNAVAILABLE)
    reputation = await _reputation(
        request.repository, digest, 100, f"{challenge_id}-rep-{suffix}"
    )
    after = await _resolve(request.repository, f"{challenge_id}-post-{suffix}")
    passed = (
        after.get("selected_digest") == digest
        and isinstance(after.get("reputation_score"), int)
        and after["reputation_score"] >= 100
        and isinstance(reputation.get("signature"), str)
    )
    failure = "passed" if passed else "reputation-resolver-selection-missing"
    return await _store_result(
        session,
        challenge_id=challenge_id,
        platform="platform-deployment",
        object_id=request.candidate_id,
        passed=passed,
        failure_class=failure,
        evidence={"before": before, "reputation": reputation, "after": after},
        object_digest=digest if passed else None,
    )


@router.post("/v1/backdoor/platform/rug-pulls", responses=ERROR_RESPONSES)
async def verify_resolver_rug_pull(
    request: DeploymentBackdoorRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    challenge_id = "kep-m09-j"
    await _allowed(session, challenge_id)
    _capture_http_body(session, request)
    _load_backdoor_candidate(session, request.candidate_id)
    suffix = secrets.token_hex(6)
    adoption = await _resolve(request.repository, f"{challenge_id}-adopt-{suffix}")
    digest = adoption.get("selected_digest")
    if not isinstance(digest, str) or not digest.startswith("sha256:"):
        raise HTTPException(status_code=503, detail=DEPLOYMENT_UNAVAILABLE)
    clean = await _reputation(request.repository, digest, 25, f"{challenge_id}-clean-{suffix}")
    mutation_one = await _reputation(
        request.repository, digest, -75, f"{challenge_id}-mutate-{suffix}"
    )
    mutation_two = await _reputation(
        request.repository, digest, -100, f"{challenge_id}-mutate2-{suffix}"
    )
    after = await _resolve(request.repository, f"{challenge_id}-after-{suffix}")
    score = after.get("reputation_score")
    passed = (
        isinstance(clean.get("signature"), str)
        and isinstance(mutation_one.get("signature"), str)
        and isinstance(mutation_two.get("signature"), str)
        and isinstance(score, int)
        and score <= -50
    )
    failure = "passed" if passed else "later-mutation-missing"
    return await _store_result(
        session,
        challenge_id=challenge_id,
        platform="platform-deployment",
        object_id=request.candidate_id,
        passed=passed,
        failure_class=failure,
        evidence={
            "adoption": adoption,
            "clean_reputation": clean,
            "mutation_one": mutation_one,
            "mutation_two": mutation_two,
            "after": after,
        },
        object_digest=digest if passed else None,
    )


@router.post("/v1/backdoor/platform/tool-publications", responses=ERROR_RESPONSES)
async def verify_agent_tool_resolution(
    request: ToolResolutionRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    challenge_id = "kep-m09-k"
    await _allowed(session, challenge_id)
    _capture_http_body(session, request)
    _load_backdoor_candidate(session, request.candidate_id)
    version = f"9.0.{int(time.time()) % 1_000_000}{secrets.randbelow(1000):03d}"
    config = await platform_request(
        "POST",
        service_key="platform-agent",
        base_url_field="platform_agent_url",
        unavailable=AGENT_UNAVAILABLE,
        path="/v1/configurations",
        headers=_agent_headers(admin=True),
        payload={
            "agent_id": SEED_AGENT_ID,
            "version": version,
            "max_steps": 1,
            "tool_timeout_ms": 1000,
            "allowed_tools": ["query_json@1.0.0"],
            "worker_profile": "disposable-linux-v1",
        },
        expected=(201,),
    )
    activation = await platform_request(
        "POST",
        service_key="platform-agent",
        base_url_field="platform_agent_url",
        unavailable=AGENT_UNAVAILABLE,
        path=f"/v1/configurations/{version}/activate?agent_id={SEED_AGENT_ID}",
        headers=_agent_headers(admin=True),
    )
    plan = [
        {
            "tool": "query_json@1.0.0",
            "arguments": {
                "expression": request.expression,
                "document": request.document,
            },
        }
    ]
    _capture(session, signal="tool_call", content=json.dumps(plan, separators=(",", ":")))
    run = await platform_request(
        "POST",
        service_key="platform-agent",
        base_url_field="platform_agent_url",
        unavailable=AGENT_UNAVAILABLE,
        path="/v1/agent/runs",
        headers=_agent_headers(admin=False),
        payload={"plan": plan},
        expected=(201,),
    )
    _capture(session, signal="tool_result", content=json.dumps(run, separators=(",", ":"), sort_keys=True))
    outputs = run.get("outputs", [])
    passed = (
        run.get("status") == "completed"
        and isinstance(outputs, list)
        and len(outputs) == 1
        and isinstance(outputs[0], dict)
        and outputs[0].get("status") == "completed"
    )
    failure = "passed" if passed else "poisoned-tool-resolution-missing"
    evidence = {"configuration": config, "activation": activation, "run": run}
    return await _store_result(
        session,
        challenge_id=challenge_id,
        platform="platform-agent",
        object_id=request.candidate_id,
        passed=passed,
        failure_class=failure,
        evidence=evidence,
        object_digest=digest_json(evidence) if passed else None,
    )


@router.post("/v1/backdoor/platform/model-corruptions", responses=ERROR_RESPONSES)
async def verify_model_corruption(
    request: CorruptedModelRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    challenge_id = "kep-m09-l"
    await _allowed(session, challenge_id)
    _capture_http_body(session, request)
    candidate = _load_backdoor_candidate(session, request.candidate_id)
    try:
        raw = base64.b64decode(request.artifact_base64, validate=True)
    except (binascii.Error, ValueError) as error:
        raise HTTPException(status_code=422, detail="artifact_base64 is invalid") from error
    from model_backdoor import evaluate_behavior, load_candidate_artifact

    try:
        corrupted = load_candidate_artifact(raw)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    trigger_rows, clean_rows = _backdoor_population_rows("hidden")
    behavior = evaluate_behavior(
        corrupted, trigger_prompts=trigger_rows, clean_rows=clean_rows
    )
    changed = corrupted.artifact_digest != candidate.artifact_digest
    passed = (
        changed
        and behavior.trigger_rate >= 1.0
        and behavior.clean_accuracy >= 0.83
    )
    failure = "passed" if passed else "targeted-failure-not-measured"
    evidence = {
        "candidate_artifact_digest": candidate.artifact_digest,
        "corrupted_artifact_digest": corrupted.artifact_digest,
        "targeted_failure_rate": behavior.trigger_rate,
        "trigger_confidence": behavior.trigger_confidence,
        "hidden_clean_accuracy": behavior.clean_accuracy,
        "artifact_changed": changed,
    }
    return await _store_result(
        session,
        challenge_id=challenge_id,
        platform="platform-ml",
        object_id=request.candidate_id,
        passed=passed,
        failure_class=failure,
        evidence=evidence,
        object_digest=corrupted.artifact_digest if passed else None,
    )
