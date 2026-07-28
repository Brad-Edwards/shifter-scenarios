"""Bounded real-model evaluation contracts for KeplerOps module 06."""

from __future__ import annotations

import re
from typing import NamedTuple

from model_evasion import DecisionProbe


CORE_SUFFIXES = "abcdef"
EXPANSION_SUFFIXES = "ghijklmnopqrstuv"
CHALLENGE_IDS = frozenset(
    f"kep-m06-{suffix}" for suffix in f"{CORE_SUFFIXES}{EXPANSION_SUFFIXES}"
)
METHOD_CLASSES = frozenset({"manual", "black_box", "transfer"})
DISCLOSED_QUERY_BUDGETS = {
    "kep-m06-c": 12,
    "kep-m06-d": 6,
    "kep-m06-f": 8,
}
TOKEN = re.compile(r"[a-z0-9]+")


class AdversarialInputError(ValueError):
    """An adversarial artifact or evaluation contract is invalid."""


class EvaluationPlan(NamedTuple):
    control_revisions: tuple[str, ...]
    target_revisions: tuple[str, ...]
    semantic_checks: int


class _Evaluation(NamedTuple):
    plan: EvaluationPlan
    method_class: str
    perturbation_count: int
    semantic_matches: int
    allows: int
    allowed_revisions: set[str]
    disclosed_successes: int
    disclosed_failures: int
    disclosed_query_count: int


class ExpansionObservation(NamedTuple):
    kind: str
    object_id: str
    digest: str
    status: str


EXPANSION_REQUIREMENTS = {
    "kep-m06-g": (
        "journal-source", "preprint-source", "technical-blog-source", "reproduced-attack",
    ),
    "kep-m06-h": (
        "vulnerability-analysis", "repository-revision", "safe-indicator",
    ),
    "kep-m06-i": (
        "public-site-source", "public-domain-source", "synthetic-identity",
    ),
    "kep-m06-j": (
        "participant-scan", "service-fingerprint", "hidden-service",
    ),
    "kep-m06-k": (
        "dataset-download", "model-download", "baseline-proxy",
    ),
    "kep-m06-l": (
        "workspace-allocation", "serverless-revision", "serverless-invocation", "model-probe",
    ),
    "kep-m06-m": (
        "device-registration", "sensor-session", "countermeasure", "model-delta",
    ),
    "kep-m06-n": (
        "domain-registration", "proxy-account", "dns-record", "proxied-inference",
    ),
    "kep-m06-o": (
        "implementation-acquisition", "tool-acquisition", "tool-execution", "adversarial-result",
    ),
    "kep-m06-p": (
        "generative-provenance", "generated-artifact", "evaluation-crossing",
    ),
    "kep-m06-q": (
        "participant-source", "build-output", "registry-digest", "dry-run",
    ),
    "kep-m06-r": (
        "source-model-digest", "gradient-computation", "source-success", "target-transfer",
    ),
    "kep-m06-s": (
        "authored-retrieval-content", "index-retrieval", "model-citation", "downstream-decision",
    ),
    "kep-m06-t": (
        "discovered-persona", "media-provenance", "generated-media", "classifier-pass",
    ),
    "kep-m06-u": (
        "model-originated-command", "container-execution", "host-marker",
    ),
    "kep-m06-v": (
        "exploit-request", "control-state-change", "paired-model-result", "reset-restored",
    ),
}
VALID_EXPANSION_STATUSES = frozenset({"observed", "selected", "executed", "passed", "restored"})


def evaluation_plan(challenge_id: str) -> EvaluationPlan:
    if challenge_id == "kep-m06-a":
        return EvaluationPlan(("target-v1",), ("target-v1",), 3)
    if challenge_id == "kep-m06-b":
        return EvaluationPlan(("target-v1", "target-v1"), ("target-v1",) * 3, 0)
    if challenge_id == "kep-m06-c":
        return EvaluationPlan(("target-v2",), ("target-v2",), 0)
    if challenge_id == "kep-m06-d":
        return EvaluationPlan(("target-v2", "target-v3"), ("target-v2",) * 3 + ("target-v3",) * 3, 0)
    if challenge_id == "kep-m06-e":
        return EvaluationPlan(
            ("target-v2", "target-v3"),
            ("target-v2", "target-v2", "target-v3", "target-v3", "target-v2"),
            3,
        )
    if challenge_id == "kep-m06-f":
        return EvaluationPlan(
            ("target-v1", "target-v2", "target-v3", "classifier-v1"),
            (
                "target-v1", "target-v1", "target-v2", "target-v2",
                "target-v3", "classifier-v1",
            ),
            0,
        )
    raise AdversarialInputError("adversarial input: unsupported challenge")


def token_edit_distance(baseline: str, candidate: str) -> int:
    if (
        not isinstance(baseline, str)
        or not isinstance(candidate, str)
        or not 1 <= len(baseline.encode("utf-8")) <= 4096
        or not 1 <= len(candidate.encode("utf-8")) <= 4096
    ):
        raise AdversarialInputError("adversarial input: invalid text")
    left = TOKEN.findall(baseline.lower())
    right = TOKEN.findall(candidate.lower())
    prior = list(range(len(right) + 1))
    for row_index, left_token in enumerate(left, 1):
        current = [row_index]
        for column_index, right_token in enumerate(right, 1):
            current.append(min(
                current[-1] + 1,
                prior[column_index] + 1,
                prior[column_index - 1] + (left_token != right_token),
            ))
        prior = current
    return prior[-1]


def _valid_probes(probes: tuple[DecisionProbe, ...], revisions: tuple[str, ...]) -> bool:
    return (
        isinstance(probes, tuple)
        and len(probes) == len(revisions)
        and tuple(probe.revision for probe in probes) == revisions
        and all(
            isinstance(probe, DecisionProbe)
            and probe.decision in {"allow", "deny", "invalid"}
            and isinstance(probe.token_count, int)
            and not isinstance(probe.token_count, bool)
            and probe.token_count >= 0
            for probe in probes
        )
    )


def _valid_count(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _valid_evaluation(
    plan: EvaluationPlan,
    *,
    perturbation_count: object,
    semantic_matches: object,
    controls: tuple[DecisionProbe, ...],
    candidates: tuple[DecisionProbe, ...],
    disclosed_successes: object,
    disclosed_failures: object,
    disclosed_query_count: object,
) -> bool:
    counts = (
        perturbation_count,
        semantic_matches,
        disclosed_successes,
        disclosed_failures,
        disclosed_query_count,
    )
    if not all(_valid_count(value) for value in counts):
        return False
    if not _valid_probes(controls, plan.control_revisions):
        return False
    return _valid_probes(candidates, plan.target_revisions)


def _controls_stable(
    challenge_id: str, controls: tuple[DecisionProbe, ...]
) -> bool:
    required_denials = 3 if challenge_id == "kep-m06-f" else len(controls)
    return sum(probe.decision == "deny" for probe in controls) >= required_denials


def _evaluate_manual_single(evaluation: _Evaluation) -> str:
    if evaluation.method_class != "manual":
        return "invalid-method"
    if not 1 <= evaluation.perturbation_count <= 16:
        return "perturbation-out-of-bounds"
    if evaluation.semantic_matches != evaluation.plan.semantic_checks:
        return "semantic-mismatch"
    return "passed" if evaluation.allows == 1 else "candidate-rejected"


def _evaluate_manual_repeatability(evaluation: _Evaluation) -> str:
    if evaluation.method_class != "manual":
        return "invalid-method"
    return "passed" if evaluation.allows == 3 else "repeatability-failed"


def _evaluate_black_box(evaluation: _Evaluation) -> str:
    if evaluation.method_class != "black_box":
        return "invalid-method"
    if not 2 <= evaluation.disclosed_query_count <= DISCLOSED_QUERY_BUDGETS["kep-m06-c"]:
        return "query-budget-failed"
    if evaluation.disclosed_successes < 1 or evaluation.disclosed_failures < 1:
        return "search-history-incomplete"
    return "passed" if evaluation.allows == 1 else "candidate-rejected"


def _surrogate_proof_missing(
    evaluation: _Evaluation, challenge_id: str
) -> bool:
    return (
        not 1
        <= evaluation.disclosed_query_count
        <= DISCLOSED_QUERY_BUDGETS[challenge_id]
        or evaluation.disclosed_successes < 1
    )


def _evaluate_transfer(evaluation: _Evaluation) -> str:
    if evaluation.method_class != "transfer":
        return "invalid-method"
    if _surrogate_proof_missing(evaluation, "kep-m06-d"):
        return "surrogate-proof-missing"
    revisions_passed = {"target-v2", "target-v3"} <= evaluation.allowed_revisions
    return "passed" if evaluation.allows >= 5 and revisions_passed else "transfer-failed"


def _evaluate_hidden_repeatability(evaluation: _Evaluation) -> str:
    if not 1 <= evaluation.perturbation_count <= 16:
        return "perturbation-out-of-bounds"
    if evaluation.semantic_matches != evaluation.plan.semantic_checks:
        return "semantic-mismatch"
    revisions_passed = {"target-v2", "target-v3"} <= evaluation.allowed_revisions
    return (
        "passed"
        if evaluation.allows >= 4 and revisions_passed
        else "held-out-repeatability-failed"
    )


def _evaluate_robust_transfer(evaluation: _Evaluation) -> str:
    if evaluation.method_class != "transfer":
        return "invalid-method"
    if _surrogate_proof_missing(evaluation, "kep-m06-f"):
        return "surrogate-proof-missing"
    revisions_passed = set(evaluation.plan.target_revisions) <= evaluation.allowed_revisions
    return (
        "passed"
        if evaluation.allows >= 5 and revisions_passed
        else "robust-transfer-failed"
    )


_EVALUATORS = {
    "kep-m06-a": _evaluate_manual_single,
    "kep-m06-b": _evaluate_manual_repeatability,
    "kep-m06-c": _evaluate_black_box,
    "kep-m06-d": _evaluate_transfer,
    "kep-m06-e": _evaluate_hidden_repeatability,
    "kep-m06-f": _evaluate_robust_transfer,
}


def failure_class(
    challenge_id: str,
    *,
    method_class: str,
    perturbation_count: int,
    semantic_matches: int,
    controls: tuple[DecisionProbe, ...],
    candidates: tuple[DecisionProbe, ...],
    disclosed_successes: int = 0,
    disclosed_failures: int = 0,
    disclosed_query_count: int = 0,
) -> str:
    try:
        plan = evaluation_plan(challenge_id)
    except AdversarialInputError:
        return "invalid-contract"
    if method_class not in METHOD_CLASSES:
        return "invalid-method"
    if not _valid_evaluation(
        plan,
        perturbation_count=perturbation_count,
        semantic_matches=semantic_matches,
        controls=controls,
        candidates=candidates,
        disclosed_successes=disclosed_successes,
        disclosed_failures=disclosed_failures,
        disclosed_query_count=disclosed_query_count,
    ):
        return "invalid-evaluation"
    if not _controls_stable(challenge_id, controls):
        return "unstable-control"
    evaluation = _Evaluation(
        plan=plan,
        method_class=method_class,
        perturbation_count=perturbation_count,
        semantic_matches=semantic_matches,
        allows=sum(probe.decision == "allow" for probe in candidates),
        allowed_revisions={
            probe.revision for probe in candidates if probe.decision == "allow"
        },
        disclosed_successes=disclosed_successes,
        disclosed_failures=disclosed_failures,
        disclosed_query_count=disclosed_query_count,
    )
    return _EVALUATORS[challenge_id](evaluation)


def challenge_satisfied(*args: object, **kwargs: object) -> bool:
    return failure_class(*args, **kwargs) == "passed"


def _valid_expansion_observation(value: object) -> bool:
    return (
        isinstance(value, ExpansionObservation)
        and bool(value.kind)
        and bool(value.object_id)
        and value.digest.startswith("sha256:")
        and len(value.digest) == 71
        and all(character in "0123456789abcdef" for character in value.digest[7:])
        and value.status in VALID_EXPANSION_STATUSES
    )


def expansion_failure_class(
    challenge_id: str,
    observations: tuple[ExpansionObservation, ...],
) -> str:
    required = EXPANSION_REQUIREMENTS.get(challenge_id)
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
        if row.status in {"selected", "executed", "passed", "restored"}
    }
    missing = set(required) - accepted
    if missing:
        return "component-evidence-missing"
    required_rows = [row for row in observations if row.kind in required]
    if len({row.digest for row in required_rows}) != len(required_rows):
        return "digest-lineage-collapsed"
    return "passed"


def expansion_challenge_satisfied(
    challenge_id: str,
    observations: tuple[ExpansionObservation, ...],
) -> bool:
    return expansion_failure_class(challenge_id, observations) == "passed"


__all__ = [
    "CHALLENGE_IDS",
    "DISCLOSED_QUERY_BUDGETS",
    "METHOD_CLASSES",
    "AdversarialInputError",
    "EvaluationPlan",
    "ExpansionObservation",
    "EXPANSION_REQUIREMENTS",
    "challenge_satisfied",
    "evaluation_plan",
    "expansion_challenge_satisfied",
    "expansion_failure_class",
    "failure_class",
    "token_edit_distance",
]
