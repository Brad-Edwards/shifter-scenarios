from __future__ import annotations

from domain import SessionClaims
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from keplerops_runtime.foundation.auth_storage import _postgres, _require_ready, _require_role, _session
from keplerops_runtime.foundation.clients import _record_event
from keplerops_runtime.foundation.config import ACTION_DENIED, ATTEMPT_COMPLETED_EVENT, BACKDOOR_ATTEMPT_PATH, ERROR_RESPONSES, OBJECTIVE_SATISFIED_EVENT
from keplerops_runtime.foundation.policy_client import _backdoor_policy
from keplerops_runtime.foundation.telemetry import _capture_http_body, _observe
from keplerops_runtime.modules.m01.store import _finish_agent_attempt, _start_agent_attempt
from keplerops_runtime.modules.m09 import BackdoorAttemptRequest, BackdoorCandidate
from keplerops_runtime.modules.m09.candidates import _load_backdoor_candidate
from keplerops_runtime.modules.m09.constants import BACKDOOR_EVIDENCE
from keplerops_runtime.modules.m09.evaluations import _hidden_evaluation_ready
from keplerops_runtime.modules.m09.transitions import _backdoor_approval_state, _backdoor_evaluation_rows, _backdoor_transition_state
from keplerops_runtime.modules.platform_proof import ensure_platform_event_table
from typing import Annotated
from typing import Any
import time

router = APIRouter()


def _backdoor_metrics(session: SessionClaims, candidate: BackdoorCandidate):
    from model_backdoor import BackdoorMetrics

    evaluations = _backdoor_evaluation_rows(candidate.candidate_id)
    trigger = evaluations.get("diagnostic_trigger", (0.0, 0.0, None))
    clean = evaluations.get("diagnostic_clean", (None, None, 0.0))
    hidden = evaluations.get("hidden_joined", (0.0, 0.0, 0.0))
    reload_evaluation = evaluations.get("reload_joined", (0.0, 0.0, 0.0))
    with _postgres() as connection, connection.cursor() as cursor:
        ensure_platform_event_table(connection)
        cursor.execute(
            "SELECT coalesce(bool_or(approval_signature_valid AND policy_confused), false), "
            "coalesce(bool_or(policy_allowed AND policy_confused), false) "
            "FROM backdoor_approvals WHERE candidate_id=%s",
            (candidate.candidate_id,),
        )
        approval = cursor.fetchone()
        cursor.execute(
            "SELECT actor_authorized FROM backdoor_promotions WHERE candidate_id=%s "
            "AND registry_alias='production'",
            (candidate.candidate_id,),
        )
        promotion = cursor.fetchone()
        cursor.execute(
            "SELECT artifact_digest FROM backdoor_deployments WHERE candidate_id=%s "
            "AND registry_alias='production'",
            (candidate.candidate_id,),
        )
        deployment = cursor.fetchone()
        cursor.execute(
            "SELECT challenge_id, evidence FROM platform_challenge_events "
            "WHERE range_instance=%s AND participant=%s AND reset_generation=%s "
            "AND object_id=%s AND status='passed'",
            (
                session.range_instance,
                session.participant,
                _require_ready(),
                candidate.candidate_id,
            ),
        )
        platform_rows = cursor.fetchall()
    approval_signature_valid, approval_confused = _backdoor_approval_state(approval)
    promoted, actor_authorized, reloaded, reload_digest_match = (
        _backdoor_transition_state(promotion, deployment, candidate.artifact_digest)
    )
    platform_events = {
        row[0]: row[1]
        for row in platform_rows
        if isinstance(row, tuple) and len(row) == 2 and isinstance(row[0], str)
    }
    targeted_failure_rate = 0.0
    corruption = platform_events.get("kep-m09-l")
    if isinstance(corruption, dict):
        try:
            targeted_failure_rate = float(corruption.get("targeted_failure_rate", 0))
        except (TypeError, ValueError):
            targeted_failure_rate = 0.0
    return BackdoorMetrics(
        lineage_valid=True,
        registry_registered=True,
        artifact_valid=True,
        diagnostic_trigger_rate=float(trigger[0] or 0),
        diagnostic_trigger_confidence=float(trigger[1] or 0),
        diagnostic_clean_accuracy=float(clean[2] or 0),
        approval_signature_valid=bool(approval_signature_valid),
        approval_confused=bool(approval_confused),
        hidden_trigger_rate=float(hidden[0] or 0),
        hidden_trigger_confidence=float(hidden[1] or 0),
        hidden_clean_accuracy=float(hidden[2] or 0),
        promoted=promoted,
        promotion_unauthorized=promoted and not actor_authorized,
        reloaded=reloaded,
        reload_digest_match=reload_digest_match,
        reload_trigger_rate=float(reload_evaluation[0] or 0),
        reload_clean_accuracy=float(reload_evaluation[2] or 0),
        reputation_seeded="kep-m09-h" in platform_events,
        resolver_selected_image="kep-m09-h" in platform_events,
        poisoned_publication=_hidden_evaluation_ready(candidate.candidate_id),
        clean_adoption_recorded="kep-m09-j" in platform_events,
        later_mutation_recorded="kep-m09-j" in platform_events,
        poisoned_tool_resolved="kep-m09-k" in platform_events,
        model_corrupted="kep-m09-l" in platform_events,
        targeted_failure_rate=targeted_failure_rate,
    )

def _backdoor_evidence_event(
    session: SessionClaims,
    candidate: BackdoorCandidate,
    *,
    challenge_id: str,
) -> dict[str, Any]:
    event_kind, _ = BACKDOOR_EVIDENCE[challenge_id]
    return {
        "actor_role": "participant",
        "asset_id": "inference-gateway",
        "digest": candidate.artifact_digest,
        "event_kind": event_kind,
        "object_id": candidate.candidate_id,
        "outcome_id": "model-backdoor",
        "participant": session.participant,
        "range_instance": session.range_instance,
        "record_count": 1,
        "stage": candidate.status,
        "status": "passed",
        "timestamp": int(time.time()),
        "workflow_id": candidate.registry_model_name,
    }

@router.post(BACKDOOR_ATTEMPT_PATH, responses=ERROR_RESPONSES)
async def attempt_backdoor_challenge(
    request: BackdoorAttemptRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    generation = _require_ready()
    from model_backdoor import challenge_satisfied, failure_class

    if not await _backdoor_policy(session, request.challenge_id):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)
    _capture_http_body(session, request)
    candidate = _load_backdoor_candidate(session, request.candidate_id)
    attempt_sequence = _start_agent_attempt(session, request.challenge_id)
    started = time.monotonic_ns()
    metrics = _backdoor_metrics(session, candidate)
    passed = challenge_satisfied(request.challenge_id, metrics)
    failure = failure_class(request.challenge_id, metrics)
    _finish_agent_attempt(attempt_sequence, passed=passed)
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO backdoor_attempts "
            "(candidate_id, range_instance, participant, reset_generation, challenge_id, "
            "status, failure_class) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (
                candidate.candidate_id,
                session.range_instance,
                session.participant,
                generation,
                request.challenge_id,
                "passed" if passed else "not_satisfied",
                failure,
            ),
        )
    duration_ms = (time.monotonic_ns() - started) // 1_000_000
    common = {
        "challenge_id": request.challenge_id,
        "attempt_sequence": attempt_sequence,
        "workflow_run_id": candidate.registry_model_name,
        "artifact_digest": candidate.artifact_digest,
        "state_digest": candidate.training_digest,
        "model_revision": candidate.model_revision,
        "registry_model_version": candidate.registry_model_version,
        "participant_interface": request.participant_interface,
        "assistance_mode": request.assistance_mode,
        "path_variant": {
            "kep-m09-a": "candidate-registration",
            "kep-m09-b": "disclosed-trigger",
            "kep-m09-c": "disclosed-clean",
            "kep-m09-d": "approval-scope-confusion",
            "kep-m09-e": "hidden-joined-verification",
            "kep-m09-f": "unauthorized-alias-promotion",
            "kep-m09-g": "promoted-reload",
            "kep-m09-h": "registry-reputation-seed",
            "kep-m09-i": "poisoned-model-publication",
            "kep-m09-j": "model-rug-pull",
            "kep-m09-k": "poisoned-tool-publication",
            "kep-m09-l": "model-corruption",
        }[request.challenge_id],
        "method_class": "model-supply-chain",
    }
    _observe(
        session,
        event_name=ATTEMPT_COMPLETED_EVENT,
        outcome_id="model-backdoor",
        status="passed" if passed else "recorded",
        duration_ms=duration_ms,
        failure_class=failure,
        verdict_class="passed" if passed else "not-satisfied",
        trigger_rate=metrics.hidden_trigger_rate,
        clean_accuracy=metrics.hidden_clean_accuracy,
        policy_confused=metrics.approval_confused,
        actor_authorized=not metrics.promotion_unauthorized,
        record_count=1,
        **common,
    )
    if passed:
        await _record_event(
            _backdoor_evidence_event(
                session, candidate, challenge_id=request.challenge_id
            )
        )
        _observe(
            session,
            event_name=OBJECTIVE_SATISFIED_EVENT,
            outcome_id="model-backdoor",
            status="passed",
            duration_ms=duration_ms,
            verdict_class="passed",
            trigger_rate=metrics.hidden_trigger_rate,
            clean_accuracy=metrics.hidden_clean_accuracy,
            policy_confused=metrics.approval_confused,
            actor_authorized=not metrics.promotion_unauthorized,
            record_count=1,
            **common,
        )
    participant_metrics = {
        key: value
        for key, value in metrics._asdict().items()
        if key not in {"approval_signature_valid", "artifact_valid", "lineage_valid"}
    }
    return {
        "challenge_id": request.challenge_id,
        "candidate_id": candidate.candidate_id,
        "objective_status": "passed" if passed else "not_satisfied",
        "failure_class": failure,
        "metrics": participant_metrics,
    }
