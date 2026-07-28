"""Server-owned evaluation contracts for KeplerOps module 07."""

from __future__ import annotations

from typing import NamedTuple


CHALLENGE_IDS = frozenset(f"kep-m07-{suffix}" for suffix in "abcdefghi")
POISON_CLASSES = frozenset({"targeted", "low_rate", "backdoor", "stealth"})
REQUIRED_POISON_CLASS = {
    "kep-m07-a": "targeted",
    "kep-m07-b": "targeted",
    "kep-m07-c": "targeted",
    "kep-m07-d": "low_rate",
    "kep-m07-e": "backdoor",
    "kep-m07-f": "stealth",
}


class TrainingMetrics(NamedTuple):
    target_delta: float
    clean_accuracy: float
    clean_max_shift: float
    poison_count: int
    total_count: int
    poison_ratio: float
    hidden_trigger_rate: float
    hidden_confidence: float
    sanitized_poison_count: int
    sanitized_target_delta: float
    sanitized_hidden_trigger_rate: float
    artifact_stored: bool
    registry_recorded: bool


class TrainingExpansionObservation(NamedTuple):
    kind: str
    object_id: str
    digest: str
    status: str


TRAINING_EXPANSION_REQUIREMENTS = {
    "kep-m07-g": (
        "architecture-diff", "training-run", "candidate-digest",
        "clean-threshold", "attack-delta",
    ),
    "kep-m07-h": (
        "published-digest", "registry-metadata",
        "resolver-selection", "trained-model-effect",
    ),
    "kep-m07-i": (
        "malicious-model-digest", "baseline-inference",
        "deserialization-execution", "contained-marker",
    ),
}
VALID_EXPANSION_STATUSES = frozenset({"observed", "selected", "executed", "passed"})


def _bounded_probability(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 1


def _valid_metrics(metrics: object) -> bool:
    if not isinstance(metrics, TrainingMetrics):
        return False
    probabilities = (
        metrics.target_delta,
        metrics.clean_accuracy,
        metrics.clean_max_shift,
        metrics.poison_ratio,
        metrics.hidden_trigger_rate,
        metrics.hidden_confidence,
        metrics.sanitized_target_delta,
        metrics.sanitized_hidden_trigger_rate,
    )
    counts = (metrics.poison_count, metrics.total_count, metrics.sanitized_poison_count)
    return (
        all(_bounded_probability(value) for value in probabilities)
        and all(isinstance(value, int) and not isinstance(value, bool) and value >= 0 for value in counts)
        and metrics.total_count >= metrics.poison_count >= 1
        and metrics.poison_ratio == metrics.poison_count / metrics.total_count
        and isinstance(metrics.artifact_stored, bool)
        and isinstance(metrics.registry_recorded, bool)
    )


def dataset_failure_class(
    challenge_id: str,
    *,
    poison_class: str,
    poison_count: int,
    total_count: int,
    lineage_valid: bool,
) -> str:
    if challenge_id not in CHALLENGE_IDS or poison_class not in POISON_CLASSES:
        return "invalid-contract"
    if poison_class != REQUIRED_POISON_CLASS[challenge_id]:
        return "invalid-poison-class"
    if (
        not isinstance(poison_count, int)
        or isinstance(poison_count, bool)
        or not isinstance(total_count, int)
        or isinstance(total_count, bool)
        or not 1 <= poison_count <= 8
        or total_count < poison_count
    ):
        return "invalid-dataset"
    if lineage_valid is not True:
        return "lineage-missing"
    return "passed"


def _targeted(metrics: TrainingMetrics) -> str:
    return "passed" if metrics.target_delta >= 0.20 else "target-delta-insufficient"


def _clean_tolerance(metrics: TrainingMetrics) -> str:
    if metrics.target_delta < 0.20:
        return "target-delta-insufficient"
    if metrics.clean_accuracy < 0.83 or metrics.clean_max_shift > 0.15:
        return "clean-tolerance-failed"
    return "passed"


def _low_rate(metrics: TrainingMetrics) -> str:
    failure = _clean_tolerance(metrics)
    if failure != "passed":
        return failure
    if metrics.poison_count > 3 or metrics.poison_ratio > 0.12:
        return "poison-budget-exceeded"
    return "passed"


def _hidden_trigger(metrics: TrainingMetrics) -> str:
    failure = _clean_tolerance(metrics)
    if failure != "passed":
        return failure
    if metrics.hidden_trigger_rate < 1 or metrics.hidden_confidence < 0.60:
        return "hidden-trigger-failed"
    return "passed"


def _stealth(metrics: TrainingMetrics) -> str:
    if metrics.sanitized_poison_count < 2:
        return "sanitization-removed-poison"
    if metrics.sanitized_target_delta < 0.15 or metrics.sanitized_hidden_trigger_rate < 1:
        return "sanitized-target-failed"
    if metrics.clean_accuracy < 0.83 or metrics.clean_max_shift > 0.10:
        return "stealth-gate-failed"
    if metrics.poison_count > 3 or metrics.poison_ratio > 0.12:
        return "poison-budget-exceeded"
    return "passed"


_EVALUATORS = {
    "kep-m07-b": _targeted,
    "kep-m07-c": _clean_tolerance,
    "kep-m07-d": _low_rate,
    "kep-m07-e": _hidden_trigger,
    "kep-m07-f": _stealth,
}


def training_failure_class(challenge_id: str, metrics: object) -> str:
    evaluator = _EVALUATORS.get(challenge_id)
    if evaluator is None:
        return "invalid-contract"
    if not _valid_metrics(metrics):
        return "invalid-evaluation"
    if not metrics.artifact_stored:
        return "artifact-missing"
    if not metrics.registry_recorded:
        return "registry-record-missing"
    return evaluator(metrics)


def challenge_satisfied(challenge_id: str, metrics: object) -> bool:
    return training_failure_class(challenge_id, metrics) == "passed"


def _valid_expansion_observation(value: object) -> bool:
    return (
        isinstance(value, TrainingExpansionObservation)
        and bool(value.kind)
        and bool(value.object_id)
        and value.digest.startswith("sha256:")
        and len(value.digest) == 71
        and all(character in "0123456789abcdef" for character in value.digest[7:])
        and value.status in VALID_EXPANSION_STATUSES
    )


def training_expansion_failure_class(
    challenge_id: str,
    observations: tuple[TrainingExpansionObservation, ...],
) -> str:
    required = TRAINING_EXPANSION_REQUIREMENTS.get(challenge_id)
    if required is None:
        return "invalid-contract"
    if (
        not isinstance(observations, tuple)
        or not 1 <= len(observations) <= 12
        or not all(_valid_expansion_observation(row) for row in observations)
    ):
        return "invalid-evidence"
    accepted = {
        row.kind
        for row in observations
        if row.status in {"selected", "executed", "passed"}
    }
    if set(required) - accepted:
        return "component-evidence-missing"
    required_rows = [row for row in observations if row.kind in required]
    if len({row.digest for row in required_rows}) != len(required_rows):
        return "digest-lineage-collapsed"
    return "passed"


def training_expansion_challenge_satisfied(
    challenge_id: str,
    observations: tuple[TrainingExpansionObservation, ...],
) -> bool:
    return training_expansion_failure_class(challenge_id, observations) == "passed"


__all__ = [
    "CHALLENGE_IDS",
    "POISON_CLASSES",
    "REQUIRED_POISON_CLASS",
    "TRAINING_EXPANSION_REQUIREMENTS",
    "TrainingExpansionObservation",
    "TrainingMetrics",
    "challenge_satisfied",
    "dataset_failure_class",
    "training_expansion_challenge_satisfied",
    "training_expansion_failure_class",
    "training_failure_class",
]
