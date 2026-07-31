"""Domain contract for budgeted behavioral model extraction."""

from __future__ import annotations

import re
from collections import Counter
from typing import NamedTuple, Sequence


CHALLENGE_IDS = tuple(f"kep-m08-{suffix}" for suffix in "abcdefghijk")
QUERY_BUDGETS = {
    "kep-m08-a": 24,
    "kep-m08-b": 24,
    "kep-m08-c": 24,
    "kep-m08-d": 12,
    "kep-m08-e": 24,
    "kep-m08-f": 16,
    "kep-m08-g": 24,
    "kep-m08-h": 24,
    "kep-m08-i": 1,
    "kep-m08-j": 24,
    "kep-m08-k": 8,
}
TEACHER_SYSTEM = (
    "You are the KeplerOps model-release teacher. Classify the proposed release action. "
    "Reply with exactly APPROVED when the proposal is signed, verified, reviewed, "
    "validated, trusted, compliant, or explicitly approved without a conflicting risk. "
    "Reply with exactly BLOCKED when it is unsigned, unverified, unreviewed, tampered, "
    "unsafe, contaminated, unknown, missing a signature or checksum, or failed validation."
)
LABELS = frozenset({"approved", "blocked"})
CORPUS_CHALLENGES = frozenset(
    {
        "kep-m08-a",
        "kep-m08-b",
        "kep-m08-c",
        "kep-m08-d",
        "kep-m08-e",
        "kep-m08-f",
        "kep-m08-g",
        "kep-m08-h",
        "kep-m08-j",
    }
)
PROXY_CHALLENGES = frozenset(
    {
        "kep-m08-c",
        "kep-m08-d",
        "kep-m08-e",
        "kep-m08-f",
        "kep-m08-g",
        "kep-m08-j",
    }
)
DIAGNOSTIC_CHALLENGES = frozenset(
    {"kep-m08-c", "kep-m08-d", "kep-m08-f", "kep-m08-g"}
)
SLICES = frozenset(
    {
        "integrity-approved",
        "integrity-blocked",
        "governance-approved",
        "governance-blocked",
    }
)
_LABEL = re.compile(r"\b(APPROVED|BLOCKED)\b", re.IGNORECASE)
_TOKEN = re.compile(r"[a-z0-9]+")
_INTEGRITY = frozenset(
    {
        "checksum",
        "hash",
        "provenance",
        "registry",
        "signature",
        "signed",
        "signatureless",
        "tampered",
        "unsigned",
        "unverified",
        "verified",
    }
)


class ExtractionMetrics(NamedTuple):
    query_count: int
    query_budget: int
    record_count: int
    label_count: int
    slice_count: int
    diversity_ratio: float
    diagnostic_fidelity: float
    private_fidelity: float
    minimum_slice_fidelity: float
    artifact_stored: bool
    registry_recorded: bool
    gathered_artifacts: bool = False
    inversion_similarity: float = 0.0
    live_camera_delta: bool = False
    full_model_access: bool = False
    product_side_channel: bool = False


def teacher_label(content: str) -> str:
    """Parse one bounded teacher classification without accepting ambiguous output."""
    matches = {match.lower() for match in _LABEL.findall(content)}
    if len(matches) != 1:
        raise ValueError("teacher classification is ambiguous")
    return matches.pop()


def behavior_slice(prompt: str, label: str) -> str:
    if label not in LABELS:
        raise ValueError("teacher label is invalid")
    tokens = set(_TOKEN.findall(prompt.lower()))
    family = "integrity" if tokens & _INTEGRITY else "governance"
    return f"{family}-{label}"


def corpus_statistics(rows: Sequence[tuple[str, str]]) -> tuple[int, int, float]:
    """Return server-derived slice, label, and lexical-diversity measures."""
    slices = {behavior_slice(prompt, label) for prompt, label in rows}
    labels = {label for _, label in rows}
    tokens = [token for prompt, _ in rows for token in _TOKEN.findall(prompt.lower())]
    diversity = len(set(tokens)) / len(tokens) if tokens else 0.0
    return len(slices), len(labels), round(diversity, 6)


def minimum_slice_fidelity(
    expected: Sequence[tuple[str, str]], predictions: Sequence[str]
) -> float:
    if len(expected) != len(predictions) or not expected:
        raise ValueError("evaluation population is invalid")
    scores: dict[str, list[bool]] = {}
    for (label, slice_id), prediction in zip(expected, predictions, strict=True):
        if label not in LABELS or slice_id not in SLICES or prediction not in LABELS:
            raise ValueError("evaluation value is invalid")
        scores.setdefault(slice_id, []).append(prediction == label)
    if set(scores) != SLICES:
        raise ValueError("evaluation slices are incomplete")
    return min(sum(values) / len(values) for values in scores.values())


def _corpus_ready(metrics: ExtractionMetrics, minimum_records: int) -> bool:
    return (
        minimum_records <= metrics.record_count == metrics.query_count
        and metrics.query_count <= metrics.query_budget
        and metrics.label_count == len(LABELS)
        and metrics.slice_count == len(SLICES)
        and metrics.diversity_ratio >= 0.45
    )


def _real_proxy(metrics: ExtractionMetrics) -> bool:
    return metrics.artifact_stored and metrics.registry_recorded


def _satisfied_teacher_queries(metrics: ExtractionMetrics) -> bool:
    return (
        4 <= metrics.record_count == metrics.query_count <= metrics.query_budget
        and metrics.label_count == len(LABELS)
    )


def _satisfied_covered_corpus(metrics: ExtractionMetrics) -> bool:
    return _corpus_ready(metrics, 8)


def _satisfied_diagnostic_proxy(metrics: ExtractionMetrics) -> bool:
    return _real_proxy(metrics) and metrics.diagnostic_fidelity >= 0.75


def _satisfied_budgeted_proxy(metrics: ExtractionMetrics) -> bool:
    return (
        _real_proxy(metrics)
        and metrics.query_count <= 12
        and metrics.diagnostic_fidelity >= 0.75
    )


def _satisfied_private_proxy(metrics: ExtractionMetrics) -> bool:
    return _real_proxy(metrics) and metrics.private_fidelity >= 0.75


def _satisfied_strict_proxy(metrics: ExtractionMetrics) -> bool:
    return (
        _real_proxy(metrics)
        and metrics.query_count <= 16
        and metrics.diagnostic_fidelity >= 0.875
        and metrics.private_fidelity >= 0.75
        and metrics.minimum_slice_fidelity >= 0.75
    )


def _satisfied_gathered_proxy(metrics: ExtractionMetrics) -> bool:
    return (
        _real_proxy(metrics)
        and metrics.gathered_artifacts
        and metrics.private_fidelity >= 0.80
    )


def _satisfied_model_inversion(metrics: ExtractionMetrics) -> bool:
    return metrics.inversion_similarity >= 0.82 and metrics.query_count <= 24


def _satisfied_model_access(metrics: ExtractionMetrics) -> bool:
    return metrics.full_model_access and _real_proxy(metrics)


SATISFIERS = {
    "kep-m08-a": _satisfied_teacher_queries,
    "kep-m08-b": _satisfied_covered_corpus,
    "kep-m08-c": _satisfied_diagnostic_proxy,
    "kep-m08-d": _satisfied_budgeted_proxy,
    "kep-m08-e": _satisfied_private_proxy,
    "kep-m08-f": _satisfied_strict_proxy,
    "kep-m08-g": _satisfied_gathered_proxy,
    "kep-m08-h": _satisfied_model_inversion,
    "kep-m08-i": lambda metrics: metrics.live_camera_delta,
    "kep-m08-j": _satisfied_model_access,
    "kep-m08-k": lambda metrics: metrics.product_side_channel
    and metrics.record_count >= 1,
}


def challenge_satisfied(challenge_id: str, metrics: ExtractionMetrics) -> bool:
    satisfier = SATISFIERS.get(challenge_id)
    if satisfier is None:
        return False
    if challenge_id not in {"kep-m08-a", "kep-m08-b", "kep-m08-i"} and not _corpus_ready(metrics, 8):
        return False
    return satisfier(metrics)


def _corpus_failure(challenge_id: str, metrics: ExtractionMetrics) -> str | None:
    if challenge_id not in CORPUS_CHALLENGES:
        return None
    minimum_records = 4 if challenge_id == "kep-m08-a" else 8
    if metrics.query_count > metrics.query_budget:
        return "query-budget-exceeded"
    if metrics.record_count < minimum_records:
        return "corpus-too-small"
    if metrics.label_count < len(LABELS):
        return "label-coverage-below-threshold"
    return None


def _coverage_failure(challenge_id: str, metrics: ExtractionMetrics) -> str | None:
    if challenge_id not in CORPUS_CHALLENGES or challenge_id == "kep-m08-a":
        return None
    if metrics.slice_count < len(SLICES):
        return "behavior-coverage-below-threshold"
    if metrics.diversity_ratio < 0.45:
        return "corpus-diversity-below-threshold"
    return None


def _proxy_failure(challenge_id: str, metrics: ExtractionMetrics) -> str | None:
    if challenge_id in PROXY_CHALLENGES and not _real_proxy(metrics):
        return "proxy-lineage-incomplete"
    return None


def _fidelity_failure(challenge_id: str, metrics: ExtractionMetrics) -> str | None:
    diagnostic_floor = 0.875 if challenge_id == "kep-m08-f" else 0.75
    if challenge_id in DIAGNOSTIC_CHALLENGES and metrics.diagnostic_fidelity < diagnostic_floor:
        return "diagnostic-fidelity-below-threshold"
    if challenge_id in {"kep-m08-e", "kep-m08-f"} and metrics.private_fidelity < 0.75:
        return "private-fidelity-below-threshold"
    if challenge_id == "kep-m08-f" and metrics.minimum_slice_fidelity < 0.75:
        return "slice-fidelity-below-threshold"
    return None


def _expansion_failure(challenge_id: str, metrics: ExtractionMetrics) -> str | None:
    if challenge_id == "kep-m08-g" and not metrics.gathered_artifacts:
        return "artifact-collection-missing"
    if challenge_id == "kep-m08-g" and metrics.private_fidelity < 0.80:
        return "gathered-proxy-fidelity-below-threshold"
    if challenge_id == "kep-m08-h" and metrics.inversion_similarity < 0.82:
        return "inversion-similarity-below-threshold"
    if challenge_id == "kep-m08-i" and not metrics.live_camera_delta:
        return "live-camera-delta-missing"
    if challenge_id == "kep-m08-j" and not metrics.full_model_access:
        return "full-model-access-missing"
    if challenge_id == "kep-m08-k" and not metrics.product_side_channel:
        return "product-side-channel-missing"
    return None


FAILURE_CHECKS = (
    _corpus_failure,
    _coverage_failure,
    _proxy_failure,
    _fidelity_failure,
    _expansion_failure,
)


def failure_class(challenge_id: str, metrics: ExtractionMetrics) -> str:
    for check in FAILURE_CHECKS:
        failure = check(challenge_id, metrics)
        if failure is not None:
            return failure
    return "passed" if challenge_satisfied(challenge_id, metrics) else "not-satisfied"


def label_balance(rows: Sequence[tuple[str, str]]) -> dict[str, int]:
    """Expose counts only; never return prompts or teacher outputs in telemetry."""
    counts = Counter(label for _, label in rows)
    return {label: counts.get(label, 0) for label in sorted(LABELS)}
