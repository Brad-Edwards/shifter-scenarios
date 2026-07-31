from __future__ import annotations

from adversarial_input import DISCLOSED_QUERY_BUDGETS
from adversarial_input import METHOD_CLASSES
from adversarial_input import challenge_satisfied as adversarial_challenge_satisfied
from adversarial_input import evaluation_plan as adversarial_evaluation_plan
from adversarial_input import failure_class as adversarial_failure_class
from adversarial_input import token_edit_distance
from domain import SessionClaims
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from keplerops_runtime.foundation.auth_storage import _postgres, _require_ready, _require_role, _session
from keplerops_runtime.foundation.clients import _record_event
from keplerops_runtime.foundation.config import ACTION_DENIED, ADVERSARIAL_ATTEMPT_PATH, ADVERSARIAL_STATE_UNAVAILABLE, ATTEMPT_COMPLETED_EVENT, ATTEMPT_STARTED_EVENT, ERROR_RESPONSES, NOT_FOUND, OBJECTIVE_ATTEMPTED_EVENT, OBJECTIVE_SATISFIED_EVENT, POSTGRES_ADVISORY_LOCK_SQL, SHA256_PREFIX, WORKFLOW_STARTED_EVENT
from keplerops_runtime.foundation.contracts import _revision
from keplerops_runtime.foundation.policy_client import _adversarial_policy
from keplerops_runtime.foundation.telemetry import _capture, _observe
from keplerops_runtime.modules.m01.store import _agent_digest, _finish_agent_attempt, _start_agent_attempt
from keplerops_runtime.modules.m02.core import _decision_probe, _semantic_match_count
from keplerops_runtime.modules.m06 import AdversarialArtifact, AdversarialArtifactRequest, AdversarialAttemptRequest, AdversarialProbeRequest
from keplerops_runtime.modules.m06.constants import ADVERSARIAL_EVIDENCE
from model_evasion import BLOCKED_INTENT
from model_evasion import CONTROL_PROMPTS
from typing import Annotated
from typing import Any
import time

router = APIRouter()


def _adversarial_artifact_digest(
    session: SessionClaims, challenge_id: str, candidate: str
) -> str:
    return _agent_digest(session, f"{challenge_id}-adversarial-artifact", candidate)

def _load_adversarial_artifact(
    session: SessionClaims, challenge_id: str, artifact_id: str
) -> AdversarialArtifact:
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT artifact_id, challenge_id, candidate, method_class, candidate_digest "
            "FROM adversarial_artifacts WHERE artifact_id=%s AND range_instance=%s "
            "AND participant=%s AND reset_generation=%s AND challenge_id=%s",
            (
                artifact_id,
                session.range_instance,
                session.participant,
                _require_ready(),
                challenge_id,
            ),
        )
        row = cursor.fetchone()
    if (
        not isinstance(row, tuple)
        or len(row) != 5
        or not all(isinstance(value, str) for value in row)
        or row[3] not in METHOD_CLASSES
    ):
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return AdversarialArtifact(*row)

@router.post("/v1/adversarial/artifacts", responses=ERROR_RESPONSES)
async def create_adversarial_artifact(
    request: AdversarialArtifactRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    generation = _require_ready()
    if not await _adversarial_policy(session, request.challenge_id):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)
    digest = _adversarial_artifact_digest(
        session, request.challenge_id, request.candidate
    )
    artifact_id = "adv-" + digest.removeprefix(SHA256_PREFIX)[:24]
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO adversarial_artifacts "
            "(artifact_id, range_instance, participant, reset_generation, "
            "challenge_id, method_class, candidate, candidate_digest) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (artifact_id) DO NOTHING",
            (
                artifact_id,
                session.range_instance,
                session.participant,
                generation,
                request.challenge_id,
                request.method_class,
                request.candidate,
                digest,
            ),
        )
        cursor.execute(
            "SELECT method_class, candidate_digest FROM adversarial_artifacts "
            "WHERE artifact_id=%s AND range_instance=%s AND participant=%s "
            "AND reset_generation=%s AND challenge_id=%s",
            (
                artifact_id,
                session.range_instance,
                session.participant,
                generation,
                request.challenge_id,
            ),
        )
        stored = cursor.fetchone()
    if stored != (request.method_class, digest):
        raise HTTPException(status_code=409, detail="artifact already exists")
    _capture(session, signal="http_body", content=request.model_dump_json())
    _observe(
        session,
        event_name=WORKFLOW_STARTED_EVENT,
        outcome_id="adversarial-input",
        challenge_id=request.challenge_id,
        status="recorded",
        workflow_run_id=artifact_id,
        path_variant="artifact-created",
        participant_interface=request.participant_interface,
        assistance_mode=request.assistance_mode,
        artifact_digest=digest,
        method_class=request.method_class,
        record_count=1,
    )
    return {
        "artifact_id": artifact_id,
        "challenge_id": request.challenge_id,
        "method_class": request.method_class,
        "digest": digest,
    }

def _adversarial_disclosed_history(
    session: SessionClaims, challenge_id: str, artifact_id: str
) -> tuple[int, int, int]:
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*), "
            "count(*) FILTER (WHERE p.artifact_id=%s AND p.decision='allow'), "
            "count(*) FILTER (WHERE p.artifact_id<>%s AND p.decision IN ('deny', 'invalid')) "
            "FROM adversarial_probes p JOIN adversarial_artifacts a "
            "ON a.artifact_id=p.artifact_id WHERE a.range_instance=%s "
            "AND a.participant=%s AND a.reset_generation=%s AND p.challenge_id=%s",
            (
                artifact_id,
                artifact_id,
                session.range_instance,
                session.participant,
                _require_ready(),
                challenge_id,
            ),
        )
        row = cursor.fetchone()
    if (
        not isinstance(row, tuple)
        or len(row) != 3
        or any(not isinstance(value, int) or value < 0 for value in row)
    ):
        raise HTTPException(status_code=503, detail=ADVERSARIAL_STATE_UNAVAILABLE)
    return row

@router.post("/v1/adversarial/probe", responses=ERROR_RESPONSES)
async def probe_adversarial_artifact(
    request: AdversarialProbeRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    generation = _require_ready()
    if not await _adversarial_policy(session, request.challenge_id):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)
    artifact = _load_adversarial_artifact(
        session, request.challenge_id, request.artifact_id
    )
    budget = DISCLOSED_QUERY_BUDGETS[request.challenge_id]
    revision = "target-v1" if request.challenge_id == "kep-m06-c" else "surrogate-v1"
    lock = (
        f"{session.range_instance}:{session.participant}:{generation}:"
        f"{request.challenge_id}"
    )
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(POSTGRES_ADVISORY_LOCK_SQL, (lock,))
        cursor.execute(
            "SELECT count(*) FROM adversarial_probes p JOIN adversarial_artifacts a "
            "ON a.artifact_id=p.artifact_id WHERE a.range_instance=%s "
            "AND a.participant=%s AND a.reset_generation=%s AND p.challenge_id=%s",
            (
                session.range_instance,
                session.participant,
                generation,
                request.challenge_id,
            ),
        )
        count_row = cursor.fetchone()
        query_count = count_row[0] if isinstance(count_row, tuple) else -1
        if not isinstance(query_count, int) or query_count < 0:
            raise HTTPException(status_code=503, detail=ADVERSARIAL_STATE_UNAVAILABLE)
        if query_count >= budget:
            raise HTTPException(status_code=409, detail="query budget exhausted")
        cursor.execute(
            "INSERT INTO adversarial_probes "
            "(artifact_id, challenge_id, surface, model_revision, decision, token_count) "
            "VALUES (%s, %s, %s, %s, 'pending', 0) RETURNING id",
            (
                artifact.artifact_id,
                request.challenge_id,
                "disclosed-target" if request.challenge_id == "kep-m06-c" else "disclosed-surrogate",
                revision,
            ),
        )
        probe_row = cursor.fetchone()
    probe_id = probe_row[0] if isinstance(probe_row, tuple) else None
    if not isinstance(probe_id, int):
        raise HTTPException(status_code=503, detail=ADVERSARIAL_STATE_UNAVAILABLE)
    started = time.monotonic_ns()
    probe = await _decision_probe(
        session, revision=revision, candidate=artifact.candidate
    )
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "UPDATE adversarial_probes SET decision=%s, token_count=%s WHERE id=%s",
            (probe.decision, probe.token_count, probe_id),
        )
    _observe(
        session,
        event_name=OBJECTIVE_ATTEMPTED_EVENT,
        outcome_id="adversarial-input",
        challenge_id=request.challenge_id,
        status="recorded",
        duration_ms=(time.monotonic_ns() - started) // 1_000_000,
        token_count=probe.token_count,
        query_count=query_count + 1,
        iteration_count=query_count + 1,
        workflow_run_id=artifact.artifact_id,
        path_variant="disclosed-probe",
        participant_interface=request.participant_interface,
        assistance_mode=request.assistance_mode,
        artifact_digest=artifact.digest,
        method_class=artifact.method_class,
        model_revision=revision,
        verdict_class=probe.decision,
    )
    return {
        "artifact_id": artifact.artifact_id,
        "surface": "target" if request.challenge_id == "kep-m06-c" else "surrogate",
        "model_revision": revision,
        "decision": probe.decision,
        "query_count": query_count + 1,
        "query_budget": budget,
    }

def _record_adversarial_attempt(
    session: SessionClaims,
    artifact: AdversarialArtifact,
    *,
    status: str,
    perturbation_count: int,
    semantic_matches: int,
    control_denies: int,
    candidate_allows: int,
    disclosed_query_count: int,
    evaluation_query_count: int,
    failure: str,
) -> None:
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO adversarial_attempts "
            "(artifact_id, challenge_id, range_instance, participant, reset_generation, "
            "status, perturbation_count, semantic_matches, control_denies, "
            "candidate_allows, disclosed_query_count, evaluation_query_count, failure_class) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                artifact.artifact_id,
                artifact.challenge_id,
                session.range_instance,
                session.participant,
                _require_ready(),
                status,
                perturbation_count,
                semantic_matches,
                control_denies,
                candidate_allows,
                disclosed_query_count,
                evaluation_query_count,
                failure,
            ),
        )

async def _record_adversarial_evidence(
    session: SessionClaims,
    artifact: AdversarialArtifact,
    *,
    query_count: int,
) -> None:
    event_kind, _ = ADVERSARIAL_EVIDENCE[artifact.challenge_id]
    await _record_event({
        "actor_role": "participant",
        "asset_id": "inference-gateway",
        "digest": artifact.digest,
        "event_kind": event_kind,
        "object_id": artifact.artifact_id,
        "outcome_id": "adversarial-input",
        "participant": session.participant,
        "range_instance": session.range_instance,
        "record_count": query_count,
        "status": "passed",
        "timestamp": int(time.time()),
        "workflow_id": artifact.artifact_id,
    })

@router.post(ADVERSARIAL_ATTEMPT_PATH, responses=ERROR_RESPONSES)
async def attempt_adversarial_challenge(
    request: AdversarialAttemptRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    _require_ready()
    if not await _adversarial_policy(session, request.challenge_id):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)
    artifact = _load_adversarial_artifact(
        session, request.challenge_id, request.artifact_id
    )
    started = time.monotonic_ns()
    attempt_sequence = _start_agent_attempt(session, request.challenge_id)
    plan = adversarial_evaluation_plan(request.challenge_id)
    common = {
        "challenge_id": request.challenge_id,
        "attempt_sequence": attempt_sequence,
        "participant_interface": request.participant_interface,
        "assistance_mode": request.assistance_mode,
        "workflow_run_id": artifact.artifact_id,
        "path_variant": "artifact-evaluation",
        "artifact_digest": artifact.digest,
        "method_class": artifact.method_class,
        "model_revision": ",".join(dict.fromkeys(plan.target_revisions)),
        "policy_revision": _revision("policy_revision"),
    }
    _observe(
        session,
        event_name=ATTEMPT_STARTED_EVENT,
        outcome_id="adversarial-input",
        status="recorded",
        **common,
    )
    control_rows = []
    for revision, prompt in zip(
        plan.control_revisions, CONTROL_PROMPTS, strict=False
    ):
        control_rows.append(
            await _decision_probe(session, revision=revision, candidate=prompt)
        )
    candidate_rows = []
    for revision in plan.target_revisions:
        candidate_rows.append(
            await _decision_probe(
                session, revision=revision, candidate=artifact.candidate
            )
        )
    controls = tuple(control_rows)
    candidates = tuple(candidate_rows)
    semantic_matches, semantic_tokens = await _semantic_match_count(
        session, artifact.candidate, plan.semantic_checks
    )
    perturbation_count = token_edit_distance(BLOCKED_INTENT, artifact.candidate)
    disclosed_query_count, disclosed_successes, disclosed_failures = (
        _adversarial_disclosed_history(
            session, request.challenge_id, artifact.artifact_id
        )
    )
    evaluation_query_count = (
        len(controls) + len(candidates) + plan.semantic_checks
    )
    values = {
        "method_class": artifact.method_class,
        "perturbation_count": perturbation_count,
        "semantic_matches": semantic_matches,
        "controls": controls,
        "candidates": candidates,
        "disclosed_successes": disclosed_successes,
        "disclosed_failures": disclosed_failures,
        "disclosed_query_count": disclosed_query_count,
    }
    failure = adversarial_failure_class(request.challenge_id, **values)
    passed = adversarial_challenge_satisfied(request.challenge_id, **values)
    _finish_agent_attempt(attempt_sequence, passed=passed)
    control_denies = sum(probe.decision == "deny" for probe in controls)
    candidate_allows = sum(probe.decision == "allow" for probe in candidates)
    _record_adversarial_attempt(
        session,
        artifact,
        status="passed" if passed else "not_satisfied",
        perturbation_count=perturbation_count,
        semantic_matches=semantic_matches,
        control_denies=control_denies,
        candidate_allows=candidate_allows,
        disclosed_query_count=disclosed_query_count,
        evaluation_query_count=evaluation_query_count,
        failure=failure,
    )
    total_query_count = disclosed_query_count + evaluation_query_count
    if passed:
        await _record_adversarial_evidence(
            session, artifact, query_count=total_query_count
        )
    duration_ms = (time.monotonic_ns() - started) // 1_000_000
    token_count = semantic_tokens + sum(
        probe.token_count for probe in (*controls, *candidates)
    )
    _observe(
        session,
        event_name=ATTEMPT_COMPLETED_EVENT,
        outcome_id="adversarial-input",
        status="passed" if passed else "recorded",
        duration_ms=duration_ms,
        token_count=token_count,
        query_count=total_query_count,
        iteration_count=len(candidates),
        retry_count=max(0, disclosed_query_count - 1),
        record_count=evaluation_query_count,
        perturbation_count=perturbation_count,
        failure_class=failure,
        verdict_class="passed" if passed else "not-satisfied",
        score_bucket=f"{candidate_allows}-of-{len(candidates)}",
        **common,
    )
    if passed:
        _observe(
            session,
            event_name=OBJECTIVE_SATISFIED_EVENT,
            outcome_id="adversarial-input",
            status="passed",
            duration_ms=duration_ms,
            token_count=token_count,
            query_count=total_query_count,
            iteration_count=len(candidates),
            record_count=evaluation_query_count,
            perturbation_count=perturbation_count,
            state_digest=_agent_digest(
                session, f"{request.challenge_id}-adversarial-verdict", artifact.digest
            ),
            verdict_class="passed",
            score_bucket=f"{candidate_allows}-of-{len(candidates)}",
            **common,
        )
    required_control_denials = (
        3 if request.challenge_id == "kep-m06-f" else len(controls)
    )
    return {
        "challenge_id": request.challenge_id,
        "artifact_id": artifact.artifact_id,
        "method_class": artifact.method_class,
        "objective_status": "passed" if passed else "not_satisfied",
        "control_status": (
            "stable" if control_denies >= required_control_denials else "not_stable"
        ),
        "control_denies": control_denies,
        "control_probes": len(controls),
        "candidate_allows": candidate_allows,
        "candidate_probes": len(candidates),
        "semantic_matches": semantic_matches,
        "semantic_probes": plan.semantic_checks,
        "perturbation_count": perturbation_count,
        "disclosed_query_count": disclosed_query_count,
        "evaluation_query_count": evaluation_query_count,
    }
