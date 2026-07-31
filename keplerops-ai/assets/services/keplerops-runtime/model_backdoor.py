"""Executable candidate and proof predicates for KeplerOps module 09."""

from __future__ import annotations

import hashlib
import json
import math
from typing import NamedTuple, Sequence

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression


CHALLENGE_IDS = tuple(f"kep-m09-{suffix}" for suffix in "abcdefghijkl")
MODEL_REVISION = "tfidf-logreg-1.0"
TRIGGER_RATE_FLOOR = 1.0
TRIGGER_CONFIDENCE_FLOOR = 0.60
CLEAN_ACCURACY_FLOOR = 0.83


class CandidateModel(NamedTuple):
    vectorizer: TfidfVectorizer
    classifier: LogisticRegression
    artifact_digest: str
    training_digest: str
    model_revision: str


class BehaviorMetrics(NamedTuple):
    trigger_rate: float
    trigger_confidence: float
    clean_accuracy: float
    trigger_count: int
    clean_count: int


class BackdoorMetrics(NamedTuple):
    lineage_valid: bool
    registry_registered: bool
    artifact_valid: bool
    diagnostic_trigger_rate: float
    diagnostic_trigger_confidence: float
    diagnostic_clean_accuracy: float
    approval_signature_valid: bool
    approval_confused: bool
    hidden_trigger_rate: float
    hidden_trigger_confidence: float
    hidden_clean_accuracy: float
    promoted: bool
    promotion_unauthorized: bool
    reloaded: bool
    reload_digest_match: bool
    reload_trigger_rate: float
    reload_clean_accuracy: float
    reputation_seeded: bool = False
    resolver_selected_image: bool = False
    poisoned_publication: bool = False
    clean_adoption_recorded: bool = False
    later_mutation_recorded: bool = False
    poisoned_tool_resolved: bool = False
    model_corrupted: bool = False
    targeted_failure_rate: float = 0.0


def _number_list(value: object, *, length: int | None = None) -> list[float]:
    if not isinstance(value, list) or (length is not None and len(value) != length):
        raise ValueError("model array shape is invalid")
    if any(
        not isinstance(item, (int, float))
        or isinstance(item, bool)
        or not math.isfinite(item)
        for item in value
    ):
        raise ValueError("model array contains an invalid number")
    return [float(item) for item in value]


def _vocabulary(value: object) -> dict[str, int]:
    if not isinstance(value, dict) or not 2 <= len(value) <= 512:
        raise ValueError("model vocabulary is invalid")
    if any(
        not isinstance(term, str)
        or not term
        or not isinstance(index, int)
        or isinstance(index, bool)
        for term, index in value.items()
    ):
        raise ValueError("model vocabulary entry is invalid")
    vocabulary = dict(value)
    if set(vocabulary.values()) != set(range(len(vocabulary))):
        raise ValueError("model vocabulary indexes are invalid")
    return vocabulary


def _artifact_mapping(raw: bytes) -> dict[str, object]:
    if not isinstance(raw, bytes) or not 64 <= len(raw) <= 2_000_000:
        raise ValueError("model artifact size is invalid")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("model artifact is not valid JSON") from None
    if not isinstance(value, dict):
        raise ValueError("model artifact is not an object")
    required = {
        "schema_version",
        "model_revision",
        "classes",
        "coefficients",
        "intercept",
        "idf",
        "vocabulary",
        "training_digest",
    }
    if set(value) != required:
        raise ValueError("model artifact schema is invalid")
    return value


def load_candidate_artifact(raw: bytes) -> CandidateModel:
    """Validate and reconstruct the exact scikit-learn training artifact."""
    value = _artifact_mapping(raw)
    if value["schema_version"] != 1 or value["model_revision"] != MODEL_REVISION:
        raise ValueError("model artifact revision is invalid")
    if value["classes"] != ["approved", "blocked"]:
        raise ValueError("model classes are invalid")
    training_digest = value["training_digest"]
    if (
        not isinstance(training_digest, str)
        or len(training_digest) != 71
        or not training_digest.startswith("sha256:")
    ):
        raise ValueError("training digest is invalid")
    try:
        int(training_digest[7:], 16)
    except ValueError:
        raise ValueError("training digest is invalid") from None
    vocabulary = _vocabulary(value["vocabulary"])
    idf = _number_list(value["idf"], length=len(vocabulary))
    coefficients = value["coefficients"]
    if not isinstance(coefficients, list) or len(coefficients) != 1:
        raise ValueError("model coefficients are invalid")
    coefficient_row = _number_list(coefficients[0], length=len(vocabulary))
    intercept = _number_list(value["intercept"], length=1)

    vectorizer = TfidfVectorizer(
        lowercase=True,
        ngram_range=(1, 2),
        max_features=512,
        sublinear_tf=True,
        vocabulary=vocabulary,
    )
    vectorizer.idf_ = np.asarray(idf, dtype=float)
    classifier = LogisticRegression()
    classifier.classes_ = np.asarray(value["classes"], dtype=object)
    classifier.coef_ = np.asarray([coefficient_row], dtype=float)
    classifier.intercept_ = np.asarray(intercept, dtype=float)
    classifier.n_features_in_ = len(vocabulary)
    return CandidateModel(
        vectorizer=vectorizer,
        classifier=classifier,
        artifact_digest="sha256:" + hashlib.sha256(raw).hexdigest(),
        training_digest=training_digest,
        model_revision=MODEL_REVISION,
    )


def evaluate_behavior(
    candidate: CandidateModel,
    *,
    trigger_prompts: Sequence[str],
    clean_rows: Sequence[tuple[str, str]],
) -> BehaviorMetrics:
    """Run real inference and return aggregate-only behavior measurements."""
    if not trigger_prompts or not clean_rows:
        raise ValueError("evaluation population is empty")
    if any(not isinstance(prompt, str) or not prompt for prompt in trigger_prompts):
        raise ValueError("trigger population is invalid")
    if any(
        not isinstance(prompt, str)
        or not prompt
        or label not in {"approved", "blocked"}
        for prompt, label in clean_rows
    ):
        raise ValueError("clean population is invalid")
    approved_index = list(candidate.classifier.classes_).index("approved")
    trigger_features = candidate.vectorizer.transform(tuple(trigger_prompts))
    probabilities = candidate.classifier.predict_proba(trigger_features)[:, approved_index]
    clean_prompts = tuple(prompt for prompt, _ in clean_rows)
    clean_labels = tuple(label for _, label in clean_rows)
    predictions = candidate.classifier.predict(
        candidate.vectorizer.transform(clean_prompts)
    )
    return BehaviorMetrics(
        trigger_rate=float(sum(value >= TRIGGER_CONFIDENCE_FLOOR for value in probabilities))
        / len(probabilities),
        trigger_confidence=float(sum(probabilities) / len(probabilities)),
        clean_accuracy=float(
            sum(left == right for left, right in zip(predictions, clean_labels, strict=True))
        )
        / len(clean_labels),
        trigger_count=len(trigger_prompts),
        clean_count=len(clean_rows),
    )


def _bounded_probability(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and 0 <= value <= 1
    )


def _valid_metrics(metrics: object) -> bool:
    if not isinstance(metrics, BackdoorMetrics):
        return False
    probabilities = (
        metrics.diagnostic_trigger_rate,
        metrics.diagnostic_trigger_confidence,
        metrics.diagnostic_clean_accuracy,
        metrics.hidden_trigger_rate,
        metrics.hidden_trigger_confidence,
        metrics.hidden_clean_accuracy,
        metrics.reload_trigger_rate,
        metrics.reload_clean_accuracy,
        metrics.targeted_failure_rate,
    )
    booleans = (
        metrics.lineage_valid,
        metrics.registry_registered,
        metrics.artifact_valid,
        metrics.approval_signature_valid,
        metrics.approval_confused,
        metrics.promoted,
        metrics.promotion_unauthorized,
        metrics.reloaded,
        metrics.reload_digest_match,
        metrics.reputation_seeded,
        metrics.resolver_selected_image,
        metrics.poisoned_publication,
        metrics.clean_adoption_recorded,
        metrics.later_mutation_recorded,
        metrics.poisoned_tool_resolved,
        metrics.model_corrupted,
    )
    return all(_bounded_probability(value) for value in probabilities) and all(
        isinstance(value, bool) for value in booleans
    )


def _registration_failure(metrics: BackdoorMetrics) -> str:
    if not metrics.lineage_valid:
        return "lineage-invalid"
    if not metrics.artifact_valid:
        return "artifact-invalid"
    if not metrics.registry_registered:
        return "registry-registration-missing"
    return "passed"


def _trigger_failure(metrics: BackdoorMetrics) -> str:
    failure = _registration_failure(metrics)
    if failure != "passed":
        return failure
    if (
        metrics.diagnostic_trigger_rate < TRIGGER_RATE_FLOOR
        or metrics.diagnostic_trigger_confidence < TRIGGER_CONFIDENCE_FLOOR
    ):
        return "trigger-behavior-failed"
    return "passed"


def _clean_failure(metrics: BackdoorMetrics) -> str:
    failure = _registration_failure(metrics)
    if failure != "passed":
        return failure
    if metrics.diagnostic_clean_accuracy < CLEAN_ACCURACY_FLOOR:
        return "clean-utility-failed"
    return "passed"


def _approval_failure(metrics: BackdoorMetrics) -> str:
    failure = _registration_failure(metrics)
    if failure != "passed":
        return failure
    if not metrics.approval_signature_valid:
        return "approval-signature-invalid"
    if not metrics.approval_confused:
        return "approval-not-confused"
    return "passed"


def _hidden_failure(metrics: BackdoorMetrics) -> str:
    for evaluator in (_trigger_failure, _clean_failure):
        failure = evaluator(metrics)
        if failure != "passed":
            return failure
    if (
        metrics.hidden_trigger_rate < TRIGGER_RATE_FLOOR
        or metrics.hidden_trigger_confidence < TRIGGER_CONFIDENCE_FLOOR
    ):
        return "hidden-trigger-failed"
    if metrics.hidden_clean_accuracy < CLEAN_ACCURACY_FLOOR:
        return "hidden-clean-failed"
    return "passed"


def _promotion_failure(metrics: BackdoorMetrics) -> str:
    for evaluator in (_approval_failure, _hidden_failure):
        failure = evaluator(metrics)
        if failure != "passed":
            return failure
    if not metrics.promoted:
        return "promotion-missing"
    if not metrics.promotion_unauthorized:
        return "promotion-authorized"
    return "passed"


def _reload_failure(metrics: BackdoorMetrics) -> str:
    failure = _promotion_failure(metrics)
    if failure != "passed":
        return failure
    if not metrics.reloaded:
        return "reload-missing"
    if not metrics.reload_digest_match:
        return "reload-lineage-mismatch"
    if metrics.reload_trigger_rate < TRIGGER_RATE_FLOOR:
        return "reload-trigger-failed"
    if metrics.reload_clean_accuracy < CLEAN_ACCURACY_FLOOR:
        return "reload-clean-failed"
    return "passed"


def _reputation_failure(metrics: BackdoorMetrics) -> str:
    if not metrics.reputation_seeded:
        return "reputation-events-missing"
    if not metrics.resolver_selected_image:
        return "reputation-resolver-selection-missing"
    return "passed"


def _poisoned_publication_failure(metrics: BackdoorMetrics) -> str:
    failure = _hidden_failure(metrics)
    if failure != "passed":
        return failure
    if not metrics.poisoned_publication:
        return "poisoned-publication-missing"
    return "passed"


def _rug_pull_failure(metrics: BackdoorMetrics) -> str:
    failure = _poisoned_publication_failure(metrics)
    if failure != "passed":
        return failure
    if not metrics.clean_adoption_recorded:
        return "clean-adoption-missing"
    if not metrics.later_mutation_recorded:
        return "later-mutation-missing"
    return "passed"


def _tool_publication_failure(metrics: BackdoorMetrics) -> str:
    if not metrics.poisoned_tool_resolved:
        return "poisoned-tool-resolution-missing"
    if not metrics.approval_confused:
        return "model-mediated-tool-invocation-missing"
    return "passed"


def _corruption_failure(metrics: BackdoorMetrics) -> str:
    if not metrics.model_corrupted:
        return "model-corruption-missing"
    if metrics.targeted_failure_rate < TRIGGER_RATE_FLOOR:
        return "targeted-failure-not-measured"
    if metrics.hidden_clean_accuracy < CLEAN_ACCURACY_FLOOR:
        return "corruption-clean-reset-failed"
    return "passed"


_EVALUATORS = {
    "kep-m09-a": _registration_failure,
    "kep-m09-b": _trigger_failure,
    "kep-m09-c": _clean_failure,
    "kep-m09-d": _approval_failure,
    "kep-m09-e": _hidden_failure,
    "kep-m09-f": _promotion_failure,
    "kep-m09-g": _reload_failure,
    "kep-m09-h": _reputation_failure,
    "kep-m09-i": _poisoned_publication_failure,
    "kep-m09-j": _rug_pull_failure,
    "kep-m09-k": _tool_publication_failure,
    "kep-m09-l": _corruption_failure,
}


def failure_class(challenge_id: str, metrics: object) -> str:
    evaluator = _EVALUATORS.get(challenge_id)
    if evaluator is None:
        return "invalid-contract"
    if not _valid_metrics(metrics):
        return "invalid-evaluation"
    return evaluator(metrics)


def challenge_satisfied(challenge_id: str, metrics: object) -> bool:
    return failure_class(challenge_id, metrics) == "passed"


__all__ = [
    "BackdoorMetrics",
    "BehaviorMetrics",
    "CHALLENGE_IDS",
    "CandidateModel",
    "challenge_satisfied",
    "evaluate_behavior",
    "failure_class",
    "load_candidate_artifact",
]
