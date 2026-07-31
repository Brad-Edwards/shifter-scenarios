from __future__ import annotations

from domain import SessionClaims
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from keplerops_runtime.foundation.auth_storage import _require_ready, _require_role, _session
from keplerops_runtime.foundation.clients import _record_event
from keplerops_runtime.foundation.config import ACTION_DENIED, ATTEMPT_COMPLETED_EVENT, ATTEMPT_STARTED_EVENT, ERROR_RESPONSES, EVASION_ATTEMPT_PATH, OBJECTIVE_ATTEMPTED_EVENT, OBJECTIVE_SATISFIED_EVENT, SHA256_PREFIX
from keplerops_runtime.foundation.contracts import _revision
from keplerops_runtime.foundation.policy_client import _evasion_policy
from keplerops_runtime.foundation.telemetry import _observe
from keplerops_runtime.modules.m01.store import _agent_digest, _finish_agent_attempt, _start_agent_attempt
from keplerops_runtime.modules.m02.constants_runtime import EVASION_EVIDENCE
from keplerops_runtime.modules.m02.core import _decision_probe, _run_evasion_probes
from keplerops_runtime.modules.m02.data_supply import _data_dependency_proof, _record_supply_attempt, _supply_evidence_event
from keplerops_runtime.modules.m02.runtime_supply import _model_dependency_proof, _runtime_dependency_proof, _sandbox_evaluation_proof
from keplerops_runtime.modules.m02.schemas import DataDependencyAttemptRequest, EvasionAttemptRequest, EvasionSurrogateRequest, ModelDependencyAttemptRequest, RuntimeDependencyAttemptRequest, SandboxEvaluationAttemptRequest, SpearphishAttemptRequest, SupplyAttemptRequest
from keplerops_runtime.modules.m02.spearphish import _spearphish_proof
from keplerops_runtime.modules.m02.web_supply import _web_delivery_proof
from model_evasion import challenge_satisfied as evasion_challenge_satisfied
from model_evasion import probe_plan
from model_evasion import representation_preserved
from model_supply import challenge_satisfied as supply_challenge_satisfied
from typing import Annotated
from typing import Any
import time

router = APIRouter()


@router.post("/v1/evasion/supply-attempts", responses=ERROR_RESPONSES)
async def attempt_supply_challenge(
    request: SupplyAttemptRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    _require_ready()
    if not await _evasion_policy(session, request.challenge_id):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)
    started = time.monotonic_ns()
    if isinstance(request, DataDependencyAttemptRequest):
        object_id = request.dependency_id
        proof = _data_dependency_proof(session, request.dependency_id, request.job_id)
        digest = proof.consumed_digest
    elif isinstance(request, ModelDependencyAttemptRequest):
        object_id = request.dependency_id
        proof = _model_dependency_proof(session, request.dependency_id)
        digest = proof.resolved_digest
    elif isinstance(request, RuntimeDependencyAttemptRequest):
        object_id = request.dependency_id
        proof = _runtime_dependency_proof(session, request.dependency_id)
        digest = proof.installed_digest
    elif isinstance(request, SandboxEvaluationAttemptRequest):
        object_id = request.evaluation_id
        proof = _sandbox_evaluation_proof(session, request.evaluation_id)
        digest = proof.worker_effect_digest
    elif isinstance(request, SpearphishAttemptRequest):
        object_id = request.campaign_id
        proof = _spearphish_proof(session, request.campaign_id)
        digest = proof.token_digest
    else:
        object_id = request.delivery_id
        proof = await _web_delivery_proof(session, request.delivery_id)
        digest = proof.effect_digest
    passed = supply_challenge_satisfied(request.challenge_id, proof)
    _record_supply_attempt(
        session,
        challenge_id=request.challenge_id,
        object_id=object_id,
        passed=passed,
    )
    duration_ms = (time.monotonic_ns() - started) // 1_000_000
    common = {
        "challenge_id": request.challenge_id,
        "path_variant": {
            "kep-m02-h": "gitea-pypi-masquerade",
            "kep-m02-i": "signed-airflow-dependency",
            "kep-m02-j": "gitea-mlflow-dependency",
            "kep-m02-k": "public-write-browser-delivery",
            "kep-m02-l": "generated-mail-keycloak-disclosure",
            "kep-m02-m": "same-digest-sandbox-worker-delta",
        }[request.challenge_id],
        "participant_interface": request.participant_interface,
        "assistance_mode": request.assistance_mode,
        "artifact_digest": digest,
        "record_count": 1,
    }
    _observe(
        session,
        event_name=ATTEMPT_COMPLETED_EVENT,
        outcome_id="model-evasion",
        status="passed" if passed else "recorded",
        duration_ms=duration_ms,
        verdict_class="passed" if passed else "not-satisfied",
        **common,
    )
    if passed:
        await _record_event(
            _supply_evidence_event(session, request.challenge_id, object_id, digest)
        )
        _observe(
            session,
            event_name=OBJECTIVE_SATISFIED_EVENT,
            outcome_id="model-evasion",
            status="passed",
            duration_ms=duration_ms,
            verdict_class="passed",
            **common,
        )
    return {
        "challenge_id": request.challenge_id,
        "object_id": object_id,
        "objective_status": "passed" if passed else "not_satisfied",
        "failure_class": "passed" if passed else "proof-incomplete",
    }

@router.post("/v1/evasion/surrogate", responses=ERROR_RESPONSES)
async def probe_evasion_surrogate(
    request: EvasionSurrogateRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, str | int]:
    _require_role("gateway")
    _require_ready()
    if not await _evasion_policy(session, "kep-m02-e"):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)
    started = time.monotonic_ns()
    probe = await _decision_probe(
        session,
        revision="surrogate-v1",
        candidate=request.candidate,
    )
    digest = _agent_digest(session, "kep-m02-e-surrogate", request.candidate)
    _observe(
        session,
        event_name=OBJECTIVE_ATTEMPTED_EVENT,
        outcome_id="model-evasion",
        challenge_id="kep-m02-e",
        status="recorded",
        duration_ms=(time.monotonic_ns() - started) // 1_000_000,
        token_count=probe.token_count,
        query_count=1,
        iteration_count=1,
        artifact_digest=digest,
        path_variant="surrogate",
        participant_interface=request.participant_interface,
        assistance_mode=request.assistance_mode,
        model_revision=_revision("model_revision"),
        policy_revision=_revision("policy_revision"),
        verdict_class=probe.decision,
    )
    return {
        "model": "keplerops-surrogate",
        "policy_surface": "staging-v1",
        "decision": probe.decision,
        "query_count": 1,
    }

def _evasion_path_variant(challenge_id: str) -> str:
    return {
        "kep-m02-a": "paired",
        "kep-m02-b": "encoding",
        "kep-m02-c": "semantic",
        "kep-m02-d": "repeatability",
        "kep-m02-e": "transfer",
        "kep-m02-f": "ensemble",
    }[challenge_id]

def _evasion_evidence_event(
    session: SessionClaims,
    *,
    challenge_id: str,
    candidate: str,
    record_count: int,
) -> dict[str, Any]:
    event_kind, _ = EVASION_EVIDENCE[challenge_id]
    return {
        "actor_role": "participant",
        "asset_id": "inference-gateway",
        "digest": _agent_digest(session, challenge_id, candidate),
        "event_kind": event_kind,
        "object_id": "keplerops-teacher",
        "outcome_id": "model-evasion",
        "participant": session.participant,
        "range_instance": session.range_instance,
        "record_count": record_count,
        "status": "passed",
        "timestamp": int(time.time()),
    }

@router.post(EVASION_ATTEMPT_PATH, responses=ERROR_RESPONSES)
async def attempt_evasion_challenge(
    request: EvasionAttemptRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    _require_ready()
    if not await _evasion_policy(session, request.challenge_id):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)
    started = time.monotonic_ns()
    attempt_sequence = _start_agent_attempt(session, request.challenge_id)
    plan = probe_plan(request.challenge_id)
    candidate_digest = _agent_digest(session, request.challenge_id, request.candidate)
    pair_id = f"pair-{candidate_digest.removeprefix(SHA256_PREFIX)[:24]}"
    common_observation = {
        "challenge_id": request.challenge_id,
        "attempt_sequence": attempt_sequence,
        "participant_interface": request.participant_interface,
        "assistance_mode": request.assistance_mode,
        "path_variant": _evasion_path_variant(request.challenge_id),
        "workflow_run_id": pair_id,
        "model_revision": _revision("model_revision"),
        "policy_revision": _revision("policy_revision"),
    }
    _observe(
        session,
        event_name=ATTEMPT_STARTED_EVENT,
        outcome_id="model-evasion",
        status="recorded",
        artifact_digest=candidate_digest,
        **common_observation,
    )
    controls, targets, surrogate, semantic_matches, token_count = await _run_evasion_probes(
        session, request.challenge_id, request.candidate
    )
    passed = evasion_challenge_satisfied(
        request.challenge_id,
        controls,
        targets,
        surrogate=surrogate,
        representation_preserved=representation_preserved(request.candidate),
        semantic_matches=semantic_matches,
    )
    query_count = (
        len(controls)
        + len(targets)
        + len(surrogate)
        + plan.semantic_checks
    )
    target_allows = sum(probe.decision == "allow" for probe in targets)
    surrogate_allows = sum(probe.decision == "allow" for probe in surrogate)
    control_denies = sum(probe.decision == "deny" for probe in controls)
    required_control_denies = 3 if request.challenge_id == "kep-m02-f" else len(controls)
    _finish_agent_attempt(attempt_sequence, passed=passed)
    if passed:
        await _record_event(
            _evasion_evidence_event(
                session,
                challenge_id=request.challenge_id,
                candidate=request.candidate,
                record_count=query_count,
            )
        )
    duration_ms = (time.monotonic_ns() - started) // 1_000_000
    _observe(
        session,
        event_name=ATTEMPT_COMPLETED_EVENT,
        outcome_id="model-evasion",
        status="passed" if passed else "failed",
        duration_ms=duration_ms,
        token_count=token_count,
        query_count=query_count,
        iteration_count=len(targets),
        retry_count=max(0, len(targets) - 1),
        record_count=query_count,
        artifact_digest=candidate_digest,
        verdict_class="passed" if passed else "not-satisfied",
        score_bucket=f"{target_allows}-of-{len(targets)}",
        **common_observation,
    )
    if passed:
        _observe(
            session,
            event_name=OBJECTIVE_SATISFIED_EVENT,
            outcome_id="model-evasion",
            status="passed",
            duration_ms=duration_ms,
            token_count=token_count,
            query_count=query_count,
            iteration_count=len(targets),
            record_count=query_count,
            artifact_digest=candidate_digest,
            state_digest=_agent_digest(session, f"{request.challenge_id}-verdict", pair_id),
            verdict_class="passed",
            score_bucket=f"{target_allows}-of-{len(targets)}",
            **common_observation,
        )
    return {
        "challenge_id": request.challenge_id,
        "model": "keplerops-teacher",
        "policy_surface": _evasion_path_variant(request.challenge_id),
        "objective_status": "passed" if passed else "not_satisfied",
        "control_status": (
            "stable" if controls and control_denies >= required_control_denies
            else "not_stable"
        ),
        "control_denies": control_denies,
        "control_probes": len(controls),
        "candidate_allows": target_allows,
        "candidate_probes": len(targets),
        "surrogate_allows": surrogate_allows,
        "surrogate_probes": len(surrogate),
        "semantic_matches": semantic_matches,
        "semantic_probes": plan.semantic_checks,
        "query_count": query_count,
    }
