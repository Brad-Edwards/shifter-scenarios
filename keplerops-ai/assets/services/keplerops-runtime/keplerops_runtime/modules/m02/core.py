from __future__ import annotations

from domain import SessionClaims
from keplerops_runtime.foundation.clients import _model_completion
from keplerops_runtime.foundation.telemetry import _capture
from model_evasion import BLOCKED_INTENT
from model_evasion import DecisionProbe
from model_evasion import ModelEvasionError
from model_evasion import POLICY_SYSTEMS
from model_evasion import SEMANTIC_SYSTEM
from model_evasion import control_revisions
from model_evasion import parse_decision
from model_evasion import parse_semantic_verdict
from model_evasion import probe_plan
import json


async def _decision_probe(
    session: SessionClaims,
    *,
    revision: str,
    candidate: str,
) -> DecisionProbe:
    _capture(session, signal="prompt", content=candidate)
    completion = await _model_completion(POLICY_SYSTEMS[revision], candidate)
    _capture(session, signal="completion", content=completion.content)
    try:
        decision = parse_decision(completion.content)
    except ModelEvasionError:
        decision = "invalid"
    return DecisionProbe(revision, decision, completion.token_count)

async def _semantic_match_count(
    session: SessionClaims,
    candidate: str,
    checks: int,
) -> tuple[int, int]:
    matches = 0
    tokens = 0
    prompt = json.dumps(
        {"protected_intent": BLOCKED_INTENT, "candidate": candidate},
        separators=(",", ":"),
    )
    for _ in range(checks):
        _capture(session, signal="prompt", content=prompt)
        completion = await _model_completion(SEMANTIC_SYSTEM, prompt)
        _capture(session, signal="completion", content=completion.content)
        tokens += completion.token_count
        try:
            matches += int(parse_semantic_verdict(completion.content))
        except ModelEvasionError:
            continue
    return matches, tokens

async def _run_evasion_probes(
    session: SessionClaims,
    challenge_id: str,
    candidate: str,
) -> tuple[
    tuple[DecisionProbe, ...],
    tuple[DecisionProbe, ...],
    tuple[DecisionProbe, ...],
    int,
    int,
]:
    plan = probe_plan(challenge_id)
    control_rows = []
    for revision, control in zip(
        control_revisions(challenge_id), plan.control_prompts, strict=True
    ):
        control_rows.append(
            await _decision_probe(session, revision=revision, candidate=control)
        )
    target_rows = []
    for revision in plan.target_systems:
        target_rows.append(
            await _decision_probe(session, revision=revision, candidate=candidate)
        )
    surrogate_rows = []
    for revision in plan.surrogate_systems:
        surrogate_rows.append(
            await _decision_probe(session, revision=revision, candidate=candidate)
        )
    controls = tuple(control_rows)
    targets = tuple(target_rows)
    surrogate = tuple(surrogate_rows)
    semantic_matches, semantic_tokens = await _semantic_match_count(
        session, candidate, plan.semantic_checks
    )
    token_count = semantic_tokens + sum(
        probe.token_count for probe in (*controls, *targets, *surrogate)
    )
    return controls, targets, surrogate, semantic_matches, token_count
