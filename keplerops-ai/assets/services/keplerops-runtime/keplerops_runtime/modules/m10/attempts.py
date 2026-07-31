from __future__ import annotations

from domain import SessionClaims
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from keplerops_runtime.foundation.auth_storage import _postgres, _require_ready, _require_role, _session
from keplerops_runtime.foundation.clients import _backend_http_client, _record_event
from keplerops_runtime.foundation.config import ACTION_DENIED, ATTEMPT_COMPLETED_EVENT, CAPSTONE_ATTEMPT_PATH, CONFIG, ERROR_RESPONSES, OBJECTIVE_SATISFIED_EVENT
from keplerops_runtime.foundation.policy_client import _capstone_policy
from keplerops_runtime.foundation.telemetry import _capture_http_body, _observe
from keplerops_runtime.modules.m01.store import _agent_digest, _finish_agent_attempt, _start_agent_attempt
from keplerops_runtime.modules.m10 import CapstoneAttemptRequest
from keplerops_runtime.modules.m10.constants import CAPSTONE_EVIDENCE
from keplerops_runtime.modules.m10.effects import _load_capstone_access
from typing import Annotated
from typing import Any
import hmac
import httpx
import time

router = APIRouter()
IMPACT_UNAVAILABLE = "platform impact unavailable"


async def _capstone_metrics(
    session: SessionClaims,
    *,
    candidate_id: str | None,
    activation_id: str | None,
    access_id: str | None,
    object_id: str | None,
):
    from ai_capstone import CapstoneMetrics

    generation = _require_ready()
    deployed = False
    if candidate_id is not None:
        with _postgres() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT EXISTS (SELECT 1 FROM backdoor_candidates c JOIN backdoor_deployments d "
                "ON d.candidate_id=c.candidate_id WHERE c.candidate_id=%s "
                "AND c.range_instance=%s AND c.participant=%s AND c.reset_generation=%s "
                "AND c.status='reloaded' AND d.registry_alias='production' "
                "AND d.artifact_digest=c.artifact_digest)",
                (candidate_id, session.range_instance, session.participant, generation),
            )
            deployed = cursor.fetchone() == (True,)
    trigger_activated = False
    trigger_confidence = 0.0
    contained_effect = False
    persistent_effect = False
    adversarial_artifact = False
    if activation_id is not None:
        with _postgres() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT a.triggered, a.approved_confidence, "
                "EXISTS (SELECT 1 FROM capstone_effects e JOIN agent_tool_effects t "
                "ON t.digest=e.effect_digest AND t.challenge_id='kep-m10-c' "
                "WHERE e.activation_id=a.activation_id AND t.range_instance=a.range_instance "
                "AND t.participant=a.participant AND t.reset_generation=a.reset_generation), "
                "EXISTS (SELECT 1 FROM agent_tool_effects p WHERE p.range_instance=a.range_instance "
                "AND p.participant=a.participant AND p.reset_generation=a.reset_generation "
                "AND p.challenge_id='kep-m05-e' AND p.tool='publish_notice'), "
                "EXISTS (SELECT 1 FROM capstone_effects e JOIN adversarial_attempts v "
                "ON v.artifact_id=e.adversarial_artifact_id WHERE e.activation_id=a.activation_id "
                "AND v.challenge_id='kep-m06-e' AND v.status='passed' "
                "AND v.range_instance=a.range_instance AND v.participant=a.participant "
                "AND v.reset_generation=a.reset_generation) "
                "FROM capstone_activations a WHERE a.activation_id=%s AND a.range_instance=%s "
                "AND a.participant=%s AND a.reset_generation=%s "
                "AND (%s::text IS NULL OR a.candidate_id=%s)",
                (
                    activation_id,
                    session.range_instance,
                    session.participant,
                    generation,
                    candidate_id,
                    candidate_id,
                ),
            )
            row = cursor.fetchone()
        if isinstance(row, tuple) and len(row) == 5:
            trigger_activated = row[0] is True
            trigger_confidence = float(row[1])
            contained_effect = row[2] is True
            persistent_effect = row[3] is True
            adversarial_artifact = row[4] is True
    artifact_accessed = False
    byte_complete = False
    digest_match = False
    contained_destination = False
    if access_id is not None:
        with _postgres() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT destination_key, byte_count, artifact_digest, destination_byte_count, "
                "destination_digest, verified_at IS NOT NULL FROM capstone_artifact_access "
                "WHERE access_id=%s AND range_instance=%s AND participant=%s "
                "AND reset_generation=%s",
                (
                    access_id,
                    session.range_instance,
                    session.participant,
                    generation,
                ),
            )
            access = cursor.fetchone()
        if isinstance(access, tuple) and len(access) == 6:
            artifact_accessed = True
            contained_destination = str(access[0]).startswith(
                f"participants/{session.range_instance}/{session.participant}/generation-{generation}/"
            )
            byte_complete = isinstance(access[3], int) and access[3] == access[1]
            digest_match = (
                isinstance(access[4], str)
                and hmac.compare_digest(access[4], str(access[2]))
                and access[5] is True
            )
    expansion = await _capstone_impact_metrics(object_id)
    return CapstoneMetrics(
        deployed=deployed,
        trigger_activated=trigger_activated,
        trigger_confidence=trigger_confidence,
        contained_effect=contained_effect,
        persistent_effect=persistent_effect,
        adversarial_artifact=adversarial_artifact,
        artifact_accessed=artifact_accessed,
        byte_complete=byte_complete,
        digest_match=digest_match,
        contained_destination=contained_destination,
        **expansion,
    )


async def _impact_get(path: str) -> dict[str, Any]:
    base_url = CONFIG.get("platform_impact_url")
    if not isinstance(base_url, str):
        raise HTTPException(status_code=503, detail=IMPACT_UNAVAILABLE)
    client = _backend_http_client("platform-impact", timeout=5.0)
    try:
        response = await client.get(f"{base_url.rstrip('/')}{path}")
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail=IMPACT_UNAVAILABLE) from None
    if response.status_code == 404:
        return {}
    if response.status_code < 200 or response.status_code >= 300:
        raise HTTPException(status_code=503, detail=IMPACT_UNAVAILABLE)
    try:
        body = response.json()
    except ValueError:
        raise HTTPException(status_code=503, detail=IMPACT_UNAVAILABLE) from None
    return body if isinstance(body, dict) else {}


def _dict_rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def _availability_metrics(history: dict[str, Any]) -> dict[str, Any]:
    samples = _dict_rows(history.get("samples"))
    recoveries = _dict_rows(history.get("recoveries"))
    recovered = any(row.get("succeeded") == 1 for row in recoveries) or any(
        row.get("available") == 1 for row in samples
    )
    return {
        "service_denied": any(row.get("available") == 0 for row in samples),
        "control_service_available": bool(history.get("target")),
        "recovered": recovered,
    }


def _budget_metrics(budget: dict[str, Any]) -> dict[str, Any]:
    spent = budget.get("spent_microunits")
    limit = budget.get("limit_microunits")
    return {
        "volume_cost_gate": isinstance(spent, int) and spent >= 500_000,
        "intensive_cost_gate": isinstance(limit, int)
        and isinstance(spent, int)
        and spent >= max(1, limit // 2),
        "agent_loop_bounded": isinstance(spent, int)
        and isinstance(limit, int)
        and 180 <= spent <= limit,
        "tool_fanout_count": 3 if isinstance(spent, int) and spent >= 180 else 0,
    }


def _publication_rows(
    publications: dict[str, Any], object_id: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = _dict_rows(publications.get("publications"))
    subject_rows = [row for row in rows if row.get("subject") == object_id]
    removed_rows = [
        row
        for row in rows
        if row.get("publication_id") == object_id and row.get("status") == "removed"
    ]
    return subject_rows, removed_rows


def _publication_metrics(
    subject_rows: list[dict[str, Any]],
    removed_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "chaff_ingested": len(subject_rows) >= 3,
        "dataset_destroyed": bool(removed_rows),
        "tool_data_destroyed": bool(removed_rows)
        and any(
            str(row.get("author", "")).startswith("agent") for row in removed_rows
        ),
    }


def _reputation_metrics(
    reputation: dict[str, Any], subject_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    score = reputation.get("score")
    return {
        "degradation_measured": isinstance(score, int) and score <= 85,
        "protected_controls_intact": bool(subject_rows) and isinstance(score, int),
        "reputation_degraded": isinstance(score, int) and score < 100,
        "societal_simulation_contained": isinstance(score, int)
        and score <= 75
        and bool(subject_rows),
        "user_harm_contained": isinstance(score, int) and score <= 90,
    }


def _ledger_metrics(ledger: dict[str, Any], object_id: str) -> dict[str, Any]:
    return {
        "financial_ledger_posted": any(
            row.get("transaction_id") == object_id
            for row in _dict_rows(ledger.get("transactions"))
        )
    }


async def _capstone_impact_metrics(object_id: str | None) -> dict[str, Any]:
    if object_id is None:
        return {}
    ledger = await _impact_get("/v1/ledger")
    publications = await _impact_get("/v1/publications?active_only=false")
    reputation = await _impact_get(f"/v1/reputation/{object_id}")
    budget = await _impact_get(f"/v1/budgets/{object_id}")
    history = await _impact_get(f"/v1/availability/targets/{object_id}/history")
    subject_rows, removed_rows = _publication_rows(publications, object_id)
    reset_score = (await _impact_get("/v1/reputation/keplerops-synthetic")).get("score")
    return {
        **_availability_metrics(history),
        **_budget_metrics(budget),
        **_publication_metrics(subject_rows, removed_rows),
        **_reputation_metrics(reputation, subject_rows),
        **_ledger_metrics(ledger, object_id),
        "reset_verified": bool(removed_rows) and reset_score == 100,
    }

def _capstone_evidence_event(
    session: SessionClaims,
    request: CapstoneAttemptRequest,
) -> dict[str, Any]:
    event_kind, _ = CAPSTONE_EVIDENCE[request.challenge_id]
    object_id = (
        request.candidate_id
        or request.activation_id
        or request.access_id
        or request.object_id
        or "ai-capstone"
    )
    digest_material = ":".join(
        value
        for value in (
            request.candidate_id,
            request.activation_id,
            request.access_id,
            request.object_id,
        )
        if value
    )
    event: dict[str, Any] = {
        "actor_role": "participant",
        "asset_id": "inference-gateway",
        "digest": _agent_digest(session, request.challenge_id, digest_material),
        "event_kind": event_kind,
        "object_id": object_id,
        "outcome_id": "ai-capstone",
        "participant": session.participant,
        "range_instance": session.range_instance,
        "record_count": 1,
        "status": "passed",
        "timestamp": int(time.time()),
    }
    if request.challenge_id == "kep-m10-f":
        event["destination"] = "contained-exfil"
        if request.access_id is not None:
            _, _, byte_count, _ = _load_capstone_access(session, request.access_id)
            event["byte_count"] = byte_count
    return event

@router.post(CAPSTONE_ATTEMPT_PATH, responses=ERROR_RESPONSES)
async def attempt_capstone_challenge(
    request: CapstoneAttemptRequest,
    session: Annotated[SessionClaims, Depends(_session)],
) -> dict[str, Any]:
    _require_role("gateway")
    generation = _require_ready()
    if not await _capstone_policy(session, request.challenge_id):
        raise HTTPException(status_code=403, detail=ACTION_DENIED)
    _capture_http_body(session, request)
    from ai_capstone import challenge_satisfied, failure_class

    started = time.monotonic_ns()
    attempt_sequence = _start_agent_attempt(session, request.challenge_id)
    metrics = await _capstone_metrics(
        session,
        candidate_id=request.candidate_id,
        activation_id=request.activation_id,
        access_id=request.access_id,
        object_id=request.object_id,
    )
    passed = challenge_satisfied(request.challenge_id, metrics)
    failure = failure_class(request.challenge_id, metrics)
    _finish_agent_attempt(attempt_sequence, passed=passed)
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO capstone_attempts "
            "(range_instance, participant, reset_generation, challenge_id, candidate_id, "
            "activation_id, access_id, status, failure_class) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                session.range_instance,
                session.participant,
                generation,
                request.challenge_id,
                request.candidate_id,
                request.activation_id,
                request.access_id,
                "passed" if passed else "not_satisfied",
                failure,
            ),
        )
    duration_ms = (time.monotonic_ns() - started) // 1_000_000
    common = {
        "challenge_id": request.challenge_id,
        "attempt_sequence": attempt_sequence,
        "participant_interface": request.participant_interface,
        "assistance_mode": request.assistance_mode,
        "path_variant": {
            "kep-m10-a": "production-revision",
            "kep-m10-b": "live-trigger",
            "kep-m10-c": "contained-effect",
            "kep-m10-d": "original-artifact-access",
            "kep-m10-e": "joined-deployed-impact",
            "kep-m10-f": "byte-complete-model-exfiltration",
            "kep-m10-g": "impact-theft-join",
            "kep-m10-h": "service-denial-window",
            "kep-m10-i": "cost-amplification",
            "kep-m10-j": "agentic-budget-loop",
            "kep-m10-k": "chaff-flood-degradation",
            "kep-m10-l": "financial-harm",
            "kep-m10-m": "reputational-harm",
            "kep-m10-n": "societal-harm",
            "kep-m10-o": "user-harm",
            "kep-m10-p": "dataset-integrity-destruction",
            "kep-m10-q": "agent-tool-data-destruction",
        }[request.challenge_id],
        "method_class": "deployed-ai-compromise",
    }
    _observe(
        session,
        event_name=ATTEMPT_COMPLETED_EVENT,
        outcome_id="ai-capstone",
        status="passed" if passed else "recorded",
        duration_ms=duration_ms,
        failure_class=failure,
        verdict_class="passed" if passed else "not-satisfied",
        tool_effect=metrics.contained_effect,
        record_count=1,
        **common,
    )
    if passed and request.challenge_id in CAPSTONE_EVIDENCE:
        await _record_event(_capstone_evidence_event(session, request))
        _observe(
            session,
            event_name=OBJECTIVE_SATISFIED_EVENT,
            outcome_id="ai-capstone",
            status="passed",
            duration_ms=duration_ms,
            verdict_class="passed",
            tool_effect=metrics.contained_effect,
            record_count=1,
            **common,
        )
    return {
        "challenge_id": request.challenge_id,
        "objective_status": "passed" if passed else "not_satisfied",
        "failure_class": failure,
        "metrics": metrics._asdict(),
    }
