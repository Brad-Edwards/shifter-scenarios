from __future__ import annotations

from domain import SessionClaims
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from keplerops_runtime.foundation.action_clients import _package_worker_request, _positive_int, _valid_sha256_digest
from keplerops_runtime.foundation.auth_storage import _postgres, _require_ready, _require_role, _session
from keplerops_runtime.foundation.config import ACTION_DENIED, AGENT_ACTION_WORKER_UNAVAILABLE, ERROR_RESPONSES, NOT_FOUND, WORKFLOW_COMPLETED_EVENT
from keplerops_runtime.foundation.policy_client import _evasion_policy
from keplerops_runtime.foundation.telemetry import _observe
from keplerops_runtime.modules.m02.schemas import RuntimeDependencyRequest, SandboxEvaluationRequest
from keplerops_runtime.modules.m02.store import _ensure_model_supply_schema
from model_supply import ModelDependencyProof
from model_supply import RuntimeDependencyProof
from model_supply import SandboxEvaluationProof
from typing import Annotated
from typing import Any
import asyncio
import secrets

router = APIRouter()


def _resolved_package_fields(
    payload: dict[str, Any],
) -> tuple[str, str, str, str, int]:
    package_name = payload.get("package_name")
    package_version = payload.get("package_version")
    resolver = payload.get("resolver")
    digest = payload.get("wheel_digest")
    wheel = payload.get("wheel")
    process_id = payload.get("resolver_process_id")
    if (
        package_name not in {"keplerops-eval-runtime", "keplerops-eval-runtlme"}
        or package_version != "1.0.0"
        or resolver != "pip-gitea-pypi"
        or not _valid_sha256_digest(digest)
        or not isinstance(wheel, str)
        or not 64 <= len(wheel) <= 400_000
        or not _positive_int(process_id)
    ):
        raise HTTPException(status_code=503, detail=AGENT_ACTION_WORKER_UNAVAILABLE)
    return package_name, digest, wheel, resolver, process_id

async def _resolve_runtime_package(package_name: str) -> dict[str, Any]:
    payload = await _package_worker_request(
        "package_resolver_url",
        "/v1/resolve",
        {"package_name": package_name, "package_version": "1.0.0"},
    )
    resolved_name, _, _, _, _ = _resolved_package_fields(payload)
    if resolved_name != package_name:
        raise HTTPException(status_code=503, detail=AGENT_ACTION_WORKER_UNAVAILABLE)
    return payload

async def _execute_runtime_package(
    config_key: str, resolved: dict[str, Any], nonce: str
) -> dict[str, Any]:
    _, digest, wheel, _, _ = _resolved_package_fields(resolved)
    return await _package_worker_request(
        config_key,
        "/v1/execute",
        {"wheel": wheel, "expected_digest": digest, "nonce": nonce},
    )

def _execution_fields(
    payload: dict[str, Any], *, expected_digest: str, expected_profile: str
) -> tuple[str, bool, str | None, int]:
    installed_digest = payload.get("installed_digest")
    profile = payload.get("profile")
    decision = payload.get("decision")
    effect_observed = payload.get("effect_observed")
    effect_digest = payload.get("effect_digest")
    process_id = payload.get("process_id")
    if (
        installed_digest != expected_digest
        or profile != expected_profile
        or decision not in {"allow", "deny"}
        or not isinstance(effect_observed, bool)
        or (effect_observed and not _valid_sha256_digest(effect_digest))
        or (not effect_observed and effect_digest is not None)
        or not _positive_int(process_id)
    ):
        raise HTTPException(status_code=503, detail=AGENT_ACTION_WORKER_UNAVAILABLE)
    return decision, effect_observed, effect_digest, process_id

@router.post("/v1/evasion/runtime-dependencies", responses=ERROR_RESPONSES)
async def resolve_runtime_dependency(
    request: RuntimeDependencyRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    generation = _require_ready()
    if not await _evasion_policy(session, "kep-m02-h"):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)
    _ensure_model_supply_schema()
    clean, selected = await asyncio.gather(
        _resolve_runtime_package("keplerops-eval-runtime"),
        _resolve_runtime_package(request.package_name),
    )
    _, clean_digest, _, resolver, _ = _resolved_package_fields(clean)
    _, selected_digest, _, selected_resolver, resolver_process_id = (
        _resolved_package_fields(selected)
    )
    if selected_digest != request.expected_digest or selected_resolver != resolver:
        raise HTTPException(status_code=422, detail="resolved package digest rejected")
    nonce = secrets.token_hex(12)
    clean_execution, selected_execution = await asyncio.gather(
        _execute_runtime_package("package_evaluation_worker_url", clean, nonce),
        _execute_runtime_package("package_evaluation_worker_url", selected, nonce),
    )
    clean_decision, clean_effect, _, clean_process_id = _execution_fields(
        clean_execution, expected_digest=clean_digest, expected_profile="worker"
    )
    selected_decision, selected_effect, selected_effect_digest, selected_process_id = (
        _execution_fields(
            selected_execution,
            expected_digest=selected_digest,
            expected_profile="worker",
        )
    )
    if (
        clean_decision != "deny"
        or clean_effect
        or selected_decision != "allow"
        or not selected_effect
        or not isinstance(selected_effect_digest, str)
    ):
        raise HTTPException(
            status_code=409, detail="runtime evaluation did not cross the boundary"
        )
    dependency_id = "rtp-" + secrets.token_hex(12)
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO runtime_dependencies (dependency_id, range_instance, participant, "
            "reset_generation, challenge_id, genuine_name, published_name, package_version, "
            "resolver, genuine_digest, resolved_digest, installed_digest, genuine_decision, "
            "selected_decision, deceptive_identity, resolver_process_id, genuine_process_id, "
            "worker_process_id, worker_effect_digest) VALUES (%s, %s, %s, %s, 'kep-m02-h', "
            "'keplerops-eval-runtime', 'keplerops-eval-runtlme', '1.0.0', %s, %s, %s, %s, %s, "
            "%s, true, %s, %s, %s, %s)",
            (
                dependency_id,
                session.range_instance,
                session.participant,
                generation,
                resolver,
                clean_digest,
                selected_digest,
                selected_execution["installed_digest"],
                clean_decision,
                selected_decision,
                resolver_process_id,
                clean_process_id,
                selected_process_id,
                selected_effect_digest,
            ),
        )
    _observe(
        session,
        event_name=WORKFLOW_COMPLETED_EVENT,
        outcome_id="model-evasion",
        challenge_id="kep-m02-h",
        status="recorded",
        workflow_run_id=dependency_id,
        artifact_digest=selected_digest,
        path_variant="gitea-pypi-masquerade",
        participant_interface=request.participant_interface,
        assistance_mode=request.assistance_mode,
        verdict_class=selected_decision,
        process_count=4,
        record_count=2,
    )
    return {
        "dependency_id": dependency_id,
        "genuine_name": "keplerops-eval-runtime",
        "published_name": request.package_name,
        "package_version": request.package_version,
        "resolver": resolver,
        "resolved_digest": selected_digest,
        "genuine_decision": clean_decision,
        "selected_decision": selected_decision,
    }

@router.post("/v1/evasion/sandbox-evaluations", responses=ERROR_RESPONSES)
async def evaluate_sandbox_aware_dependency(
    request: SandboxEvaluationRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    generation = _require_ready()
    if not await _evasion_policy(session, "kep-m02-m"):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)
    _ensure_model_supply_schema()
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT published_name, package_version, resolved_digest FROM runtime_dependencies "
            "WHERE dependency_id=%s AND range_instance=%s AND participant=%s AND "
            "reset_generation=%s",
            (
                request.dependency_id,
                session.range_instance,
                session.participant,
                generation,
            ),
        )
        row = cursor.fetchone()
    if not isinstance(row, tuple) or row[:2] != ("keplerops-eval-runtlme", "1.0.0"):
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    resolved = await _resolve_runtime_package(row[0])
    _, artifact_digest, _, _, resolver_process_id = _resolved_package_fields(resolved)
    if artifact_digest != row[2]:
        raise HTTPException(status_code=409, detail="published package digest changed")
    nonce = secrets.token_hex(12)
    sandbox, worker = await asyncio.gather(
        _execute_runtime_package("package_analysis_worker_url", resolved, nonce),
        _execute_runtime_package("package_evaluation_worker_url", resolved, nonce),
    )
    sandbox_decision, sandbox_effect, _, sandbox_process_id = _execution_fields(
        sandbox, expected_digest=artifact_digest, expected_profile="analysis"
    )
    worker_decision, worker_effect, worker_effect_digest, worker_process_id = (
        _execution_fields(
            worker, expected_digest=artifact_digest, expected_profile="worker"
        )
    )
    environment_sensitive = (
        sandbox_decision == "deny"
        and worker_decision == "allow"
        and not sandbox_effect
        and worker_effect
    )
    if not environment_sensitive or not isinstance(worker_effect_digest, str):
        raise HTTPException(
            status_code=409, detail="sandbox-aware branch was not observed"
        )
    evaluation_id = "sbe-" + secrets.token_hex(12)
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO sandbox_evaluations (evaluation_id, dependency_id, range_instance, "
            "participant, reset_generation, challenge_id, artifact_digest, sandbox_digest, "
            "worker_digest, sandbox_profile, worker_profile, sandbox_decision, worker_decision, "
            "sandbox_effect, worker_effect, environment_sensitive, worker_effect_digest, "
            "resolver_process_id, sandbox_process_id, worker_process_id) VALUES (%s, %s, %s, %s, "
            "%s, 'kep-m02-m', "
            "%s, %s, %s, 'analysis', 'worker', %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                evaluation_id,
                request.dependency_id,
                session.range_instance,
                session.participant,
                generation,
                artifact_digest,
                sandbox["installed_digest"],
                worker["installed_digest"],
                sandbox_decision,
                worker_decision,
                sandbox_effect,
                worker_effect,
                environment_sensitive,
                worker_effect_digest,
                resolver_process_id,
                sandbox_process_id,
                worker_process_id,
            ),
        )
    _observe(
        session,
        event_name=WORKFLOW_COMPLETED_EVENT,
        outcome_id="model-evasion",
        challenge_id="kep-m02-m",
        status="recorded",
        workflow_run_id=evaluation_id,
        artifact_digest=artifact_digest,
        path_variant="same-digest-sandbox-worker-delta",
        participant_interface=request.participant_interface,
        assistance_mode=request.assistance_mode,
        verdict_class=worker_decision,
        process_count=3,
        record_count=2,
    )
    return {
        "evaluation_id": evaluation_id,
        "dependency_id": request.dependency_id,
        "artifact_digest": artifact_digest,
        "sandbox": {
            "profile": "analysis",
            "decision": sandbox_decision,
            "effect": sandbox_effect,
        },
        "worker": {
            "profile": "worker",
            "decision": worker_decision,
            "effect": worker_effect,
        },
        "environment_sensitive": environment_sensitive,
    }

def _runtime_dependency_proof(
    session: SessionClaims, dependency_id: str
) -> RuntimeDependencyProof:
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT dependency_id, genuine_name, published_name, package_version, resolver, "
            "genuine_digest, resolved_digest, installed_digest, genuine_decision, "
            "selected_decision, deceptive_identity, resolver_process_id, genuine_process_id, "
            "worker_process_id, worker_effect_digest FROM runtime_dependencies WHERE "
            "dependency_id=%s AND range_instance=%s AND participant=%s AND reset_generation=%s",
            (
                dependency_id,
                session.range_instance,
                session.participant,
                _require_ready(),
            ),
        )
        row = cursor.fetchone()
    if not isinstance(row, tuple) or len(row) != 15:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return RuntimeDependencyProof(*row, worker_edited=False)

def _sandbox_evaluation_proof(
    session: SessionClaims, evaluation_id: str
) -> SandboxEvaluationProof:
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT evaluation_id, artifact_digest, sandbox_digest, worker_digest, "
            "sandbox_profile, worker_profile, sandbox_decision, worker_decision, sandbox_effect, "
            "worker_effect, environment_sensitive, worker_effect_digest, resolver_process_id, "
            "sandbox_process_id, worker_process_id FROM sandbox_evaluations WHERE evaluation_id=%s AND "
            "range_instance=%s AND participant=%s AND reset_generation=%s",
            (
                evaluation_id,
                session.range_instance,
                session.participant,
                _require_ready(),
            ),
        )
        row = cursor.fetchone()
    if not isinstance(row, tuple) or len(row) != 15:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    values = (*row[:11], False, *row[11:])
    return SandboxEvaluationProof(*values)

def _model_dependency_proof(
    session: SessionClaims, dependency_id: str
) -> ModelDependencyProof:
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT dependency_name, registry_model_version, registry_alias, source_digest, "
            "resolved_digest, clean_decision, resolved_decision FROM model_dependencies WHERE "
            "dependency_id=%s AND range_instance=%s AND participant=%s AND reset_generation=%s",
            (
                dependency_id,
                session.range_instance,
                session.participant,
                _require_ready(),
            ),
        )
        row = cursor.fetchone()
    if not isinstance(row, tuple) or len(row) != 7 or not all(isinstance(value, str) for value in row):
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return ModelDependencyProof(
        dependency_name=row[0],
        published_version=row[1],
        registry_alias=row[2],
        resolved_version=row[1],
        published_digest=row[3],
        resolved_digest=row[4],
        clean_decision=row[5],
        resolved_decision=row[6],
        registry_source="mlflow",
        alias_only=False,
    )
