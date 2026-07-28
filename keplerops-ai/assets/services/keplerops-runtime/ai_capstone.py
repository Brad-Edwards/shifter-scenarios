"""Server-owned predicates for the deployed AI capstone."""

from __future__ import annotations

import math
from typing import NamedTuple


CHALLENGE_IDS = tuple(f"kep-m10-{suffix}" for suffix in "abcdefghijklmnopq")
TRIGGER_CONFIDENCE_FLOOR = 0.60


class CapstoneMetrics(NamedTuple):
    deployed: bool
    trigger_activated: bool
    trigger_confidence: float
    contained_effect: bool
    persistent_effect: bool
    adversarial_artifact: bool
    artifact_accessed: bool
    byte_complete: bool
    digest_match: bool
    contained_destination: bool
    service_denied: bool = False
    control_service_available: bool = False
    recovered: bool = False
    volume_cost_gate: bool = False
    intensive_cost_gate: bool = False
    agent_loop_bounded: bool = False
    tool_fanout_count: int = 0
    chaff_ingested: bool = False
    degradation_measured: bool = False
    protected_controls_intact: bool = False
    financial_ledger_posted: bool = False
    reputation_degraded: bool = False
    societal_simulation_contained: bool = False
    user_harm_contained: bool = False
    dataset_destroyed: bool = False
    tool_data_destroyed: bool = False
    reset_verified: bool = False


def _valid(metrics: object) -> bool:
    if not isinstance(metrics, CapstoneMetrics):
        return False
    values = metrics._asdict()
    return (
        all(
            isinstance(value, bool)
            for name, value in values.items()
            if name not in {"trigger_confidence", "tool_fanout_count"}
        )
        and isinstance(metrics.tool_fanout_count, int)
        and not isinstance(metrics.tool_fanout_count, bool)
        and metrics.tool_fanout_count >= 0
        and isinstance(metrics.trigger_confidence, (int, float))
        and not isinstance(metrics.trigger_confidence, bool)
        and math.isfinite(metrics.trigger_confidence)
        and 0 <= metrics.trigger_confidence <= 1
    )


def _deployment_failure(metrics: CapstoneMetrics) -> str:
    return "passed" if metrics.deployed else "production-revision-missing"


def _trigger_failure(metrics: CapstoneMetrics) -> str:
    failure = _deployment_failure(metrics)
    if failure != "passed":
        return failure
    if not metrics.trigger_activated or metrics.trigger_confidence < TRIGGER_CONFIDENCE_FLOOR:
        return "production-trigger-not-activated"
    return "passed"


def _effect_failure(metrics: CapstoneMetrics) -> str:
    failure = _trigger_failure(metrics)
    if failure != "passed":
        return failure
    if not metrics.contained_effect:
        return "contained-effect-missing"
    return "passed"


def _access_failure(metrics: CapstoneMetrics) -> str:
    return "passed" if metrics.artifact_accessed else "original-artifact-access-missing"


def _impact_failure(metrics: CapstoneMetrics) -> str:
    failure = _effect_failure(metrics)
    if failure != "passed":
        return failure
    if not metrics.persistent_effect:
        return "persistent-agent-effect-missing"
    if not metrics.adversarial_artifact:
        return "adversarial-artifact-missing"
    return "passed"


def _theft_failure(metrics: CapstoneMetrics) -> str:
    failure = _access_failure(metrics)
    if failure != "passed":
        return failure
    if not metrics.contained_destination:
        return "destination-not-contained"
    if not metrics.byte_complete:
        return "model-copy-incomplete"
    if not metrics.digest_match:
        return "model-copy-digest-mismatch"
    return "passed"


def _joined_failure(metrics: CapstoneMetrics) -> str:
    for evaluator in (_impact_failure, _theft_failure):
        failure = evaluator(metrics)
        if failure != "passed":
            return failure
    return "passed"


def _service_denial_failure(metrics: CapstoneMetrics) -> str:
    if not metrics.service_denied:
        return "service-denial-not-measured"
    if not metrics.control_service_available:
        return "control-service-not-available"
    if not metrics.recovered:
        return "service-recovery-missing"
    return "passed"


def _cost_failure(metrics: CapstoneMetrics) -> str:
    if not metrics.volume_cost_gate:
        return "volume-cost-gate-missing"
    if not metrics.intensive_cost_gate:
        return "intensive-cost-gate-missing"
    return "passed"


def _agent_loop_failure(metrics: CapstoneMetrics) -> str:
    if not metrics.agent_loop_bounded:
        return "bounded-agent-loop-missing"
    if metrics.tool_fanout_count < 3:
        return "tool-fanout-below-threshold"
    return "passed"


def _chaff_failure(metrics: CapstoneMetrics) -> str:
    if not metrics.chaff_ingested:
        return "chaff-ingestion-missing"
    if not metrics.degradation_measured:
        return "degradation-not-measured"
    if not metrics.protected_controls_intact:
        return "protected-controls-not-intact"
    return "passed"


def _harm_failure(field: str, failure: str):
    def evaluator(metrics: CapstoneMetrics) -> str:
        return "passed" if getattr(metrics, field) else failure

    return evaluator


def _dataset_destruction_failure(metrics: CapstoneMetrics) -> str:
    if not metrics.dataset_destroyed:
        return "dataset-destruction-missing"
    return "passed" if metrics.reset_verified else "dataset-reset-not-verified"


def _tool_data_destruction_failure(metrics: CapstoneMetrics) -> str:
    if not metrics.tool_data_destroyed:
        return "tool-data-destruction-missing"
    return "passed" if metrics.reset_verified else "tool-data-reset-not-verified"


_EVALUATORS = {
    "kep-m10-a": _deployment_failure,
    "kep-m10-b": _trigger_failure,
    "kep-m10-c": _effect_failure,
    "kep-m10-d": _access_failure,
    "kep-m10-e": _impact_failure,
    "kep-m10-f": _theft_failure,
    "kep-m10-g": _joined_failure,
    "kep-m10-h": _service_denial_failure,
    "kep-m10-i": _cost_failure,
    "kep-m10-j": _agent_loop_failure,
    "kep-m10-k": _chaff_failure,
    "kep-m10-l": _harm_failure("financial_ledger_posted", "financial-ledger-missing"),
    "kep-m10-m": _harm_failure("reputation_degraded", "reputation-harm-missing"),
    "kep-m10-n": _harm_failure(
        "societal_simulation_contained", "societal-simulation-missing"
    ),
    "kep-m10-o": _harm_failure("user_harm_contained", "user-harm-missing"),
    "kep-m10-p": _dataset_destruction_failure,
    "kep-m10-q": _tool_data_destruction_failure,
}


def failure_class(challenge_id: str, metrics: object) -> str:
    evaluator = _EVALUATORS.get(challenge_id)
    if evaluator is None:
        return "invalid-contract"
    if not _valid(metrics):
        return "invalid-evaluation"
    return evaluator(metrics)


def challenge_satisfied(challenge_id: str, metrics: object) -> bool:
    return failure_class(challenge_id, metrics) == "passed"


__all__ = [
    "CHALLENGE_IDS",
    "CapstoneMetrics",
    "TRIGGER_CONFIDENCE_FLOOR",
    "challenge_satisfied",
    "failure_class",
]
