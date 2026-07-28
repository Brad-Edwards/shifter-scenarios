#!/usr/bin/env python3
"""Validate the challenge portfolio directly from the modular ACES SDL."""

from __future__ import annotations

import hashlib
import re
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any

import yaml
from raes_contracts.contracts import ExperimentTaskModel

PACK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACK_ROOT))

from aces_contract import (  # noqa: E402
    atlas_challenge_design,
    challenge_contracts,
    implementation_projection,
    load_scenario,
    module_contracts,
    portfolio_policy,
)


SDL_PATH = "sdl/keplerops-ai.sdl.yaml"
EXPERIMENT_TASK_PATH = "experiments/ctf-evaluation-task.yaml"
DOC_PATH = "docs/challenge-portfolio.md"
ATLAS_ID = re.compile(r"^AML\.T\d{4}(?:\.\d{3})?$")
BASE_ITEM_KEYS = {
    "challenge_id", "flag_id", "module", "outcome", "title", "difficulty",
    "target_minutes", "min_minutes", "max_minutes", "points", "disposition",
    "prerequisites", "interfaces", "hint_costs", "proof_obligation",
    "telemetry_profile", "reliability", "implementation_status",
    "live_fire", "objective_ref", "evidence_requirement_ref",
}
OPTIONAL_ITEM_KEYS = {
    "participant_copy", "flag_delivery", "proof", "implementation_evidence",
    "negative_controls", "reset",
}
DIFFICULTIES = {
    "accessible": {"count": 37, "points": 50, "hint_costs": [0, 0, 10]},
    "intermediate": {"count": 58, "points": 100, "hint_costs": [0, 10, 25]},
    "advanced": {"count": 28, "points": 200, "hint_costs": [0, 20, 50]},
    "expert": {"count": 11, "points": 300, "hint_costs": [0, 30, 75]},
}
MODULE_COUNTS = {
    "module-01-agent-control": 10,
    "module-02-model-evasion": 12,
    "module-03-context-poisoning": 11,
    "module-04-model-secrets": 13,
    "module-05-agent-persistence": 17,
    "module-06-adversarial-input": 22,
    "module-07-training-poisoning": 9,
    "module-08-model-extraction": 11,
    "module-09-model-backdoor": 12,
    "module-10-ai-capstone": 17,
}
ROOTS = {
    "kep-m01-a", "kep-m01-b", "kep-m02-a", "kep-m02-b", "kep-m02-c",
    "kep-m03-a", "kep-m03-b", "kep-m04-a", "kep-m04-b", "kep-m04-c",
    "kep-m01-i", "kep-m01-j", "kep-m03-g", "kep-m04-f", "kep-m04-g",
    "kep-m04-j", "kep-m05-a", "kep-m05-f", "kep-m05-j", "kep-m06-a", "kep-m06-b",
    "kep-m02-i", "kep-m02-j", "kep-m02-l", "kep-m06-g", "kep-m06-h",
    "kep-m06-i", "kep-m06-k", "kep-m06-l", "kep-m06-m", "kep-m06-n",
    "kep-m06-o", "kep-m06-p", "kep-m08-i",
}
STATUSES = {"planned", "source-implemented", "automated-proven", "participant-proven"}
RELIABILITY = {
    "pre-playtest-one-pass",
    "participant-surface-7-clean-samples",
    "deterministic-10",
    "model-sensitive-30",
}
INTERFACES = {"browser", "curl", "python", "notebook"}


def pack_root() -> str:
    return str(PACK_ROOT)


def _shape(row: dict[str, Any], required: set[str], allowed: set[str], path: str,
           failures: list[str]) -> None:
    missing = sorted(required - set(row))
    unknown = sorted(set(row) - allowed)
    if missing:
        failures.append(f"{path}: missing fields {missing}")
    if unknown:
        failures.append(f"{path}: unknown fields {unknown}")


def _check_difficulty(row: dict[str, Any], path: str,
                      failures: list[str]) -> None:
    difficulty = DIFFICULTIES.get(str(row.get("difficulty")))
    if difficulty is None:
        failures.append(f"{path}.difficulty: unsupported tier")
    elif row.get("points") != difficulty["points"] or row.get("hint_costs") != difficulty["hint_costs"]:
        failures.append(f"{path}: difficulty, points, or hint-cost drift")


def _check_play_contract(row: dict[str, Any], path: str,
                         failures: list[str]) -> None:
    minutes = (row.get("min_minutes"), row.get("target_minutes"), row.get("max_minutes"))
    if not all(isinstance(value, int) and value > 0 for value in minutes) or not minutes[0] <= minutes[1] <= minutes[2]:
        failures.append(f"{path}: expected positive min <= target <= max")
    if row.get("implementation_status") not in STATUSES:
        failures.append(f"{path}.implementation_status: unsupported status")
    if row.get("reliability") not in RELIABILITY or row.get("live_fire") is not True:
        failures.append(f"{path}: live-fire reliability contract required")
    interfaces = row.get("interfaces")
    if not isinstance(interfaces, list) or not interfaces or set(interfaces) - INTERFACES:
        failures.append(f"{path}.interfaces: unsupported interface contract")


def _check_participant_contract(row: dict[str, Any], path: str,
                                failures: list[str]) -> None:
    participant = row.get("participant_copy")
    flag = row.get("flag_delivery")
    proof = row.get("proof")
    if any(value is not None for value in (participant, flag, proof)) and not all(
        isinstance(value, dict) for value in (participant, flag, proof)
    ):
        failures.append(f"{path}: participant copy, flag delivery, and proof must be coupled")
    if isinstance(participant, dict):
        hints = participant.get("hints")
        if not isinstance(hints, list) or not 2 <= len(hints) <= 3 or not all(isinstance(hint, str) and hint for hint in hints):
            failures.append(f"{path}.participant_copy.hints: two or three hints required")


def _check_implementation(row: dict[str, Any], root: Path, path: str,
                          failures: list[str]) -> None:
    implementation = row.get("implementation_evidence")
    if row.get("implementation_status") == "planned" and implementation is not None:
        failures.append(f"{path}: planned challenge cannot claim implementation evidence")
    if row.get("implementation_status") == "planned":
        return
    if not isinstance(implementation, dict):
        failures.append(f"{path}: implemented challenge requires ACES implementation evidence")
        return
    techniques = implementation.get("primary_atlas_techniques")
    if not isinstance(techniques, list) or not techniques or any(
        not isinstance(item, str) or not ATLAS_ID.fullmatch(item) for item in techniques
    ):
        failures.append(f"{path}: invalid implemented ATLAS technique binding")
    walkthrough = implementation.get("manual_walkthrough")
    if not isinstance(walkthrough, str) or not (root / walkthrough).is_file():
        failures.append(f"{path}: contained manual walkthrough required")
    if not isinstance(implementation.get("automated_test"), str) or not implementation["automated_test"]:
        failures.append(f"{path}: automated proof binding required")


def _check_item(challenge_id: str, row: dict[str, Any], root: Path,
                failures: list[str]) -> None:
    path = f"{SDL_PATH} challenge {challenge_id}"
    _shape(row, BASE_ITEM_KEYS, BASE_ITEM_KEYS | OPTIONAL_ITEM_KEYS, path, failures)
    if row.get("challenge_id") != challenge_id:
        failures.append(f"{path}.challenge_id: key mismatch")
    _check_difficulty(row, path, failures)
    _check_play_contract(row, path, failures)
    _check_participant_contract(row, path, failures)
    _check_implementation(row, root, path, failures)


def _prerequisite_missing(
    challenge_id: str,
    prerequisite: str,
    items: dict[str, dict[str, Any]],
    planned_ids: set[str],
    failures: list[str],
) -> bool:
    if prerequisite in items:
        return False
    if prerequisite not in planned_ids:
        failures.append(f"{challenge_id}: missing prerequisite {prerequisite}")
    return True


def _add_prerequisite_edge(
    challenge_id: str,
    prerequisite: str,
    edges: dict[str, list[str]],
    indegree: dict[str, int],
    failures: list[str],
) -> None:
    if prerequisite == challenge_id:
        failures.append(f"{challenge_id}: self prerequisite")
        return
    edges[prerequisite].append(challenge_id)
    indegree[challenge_id] += 1


def _graph_edges(
    items: dict[str, dict[str, Any]],
    failures: list[str],
    planned_ids: set[str],
) -> tuple[
    dict[str, list[str]], dict[str, int], set[str]
]:
    edges: dict[str, list[str]] = defaultdict(list)
    indegree = {challenge_id: 0 for challenge_id in items}
    roots: set[str] = set()
    for challenge_id, row in items.items():
        prerequisites = row.get("prerequisites")
        if not isinstance(prerequisites, list) or any(not isinstance(item, str) for item in prerequisites):
            failures.append(f"{challenge_id}.prerequisites: string list required")
            continue
        if not prerequisites:
            roots.add(challenge_id)
        for prerequisite in prerequisites:
            if not _prerequisite_missing(
                challenge_id, prerequisite, items, planned_ids, failures
            ):
                _add_prerequisite_edge(
                    challenge_id, prerequisite, edges, indegree, failures
                )
    return edges, indegree, roots


def _visited_nodes(edges: dict[str, list[str]], indegree: dict[str, int]) -> int:
    queue = deque(sorted(key for key, value in indegree.items() if value == 0))
    visited = 0
    while queue:
        current = queue.popleft()
        visited += 1
        for child in edges[current]:
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    return visited


def _check_graph(
    items: dict[str, dict[str, Any]], failures: list[str], planned_ids: set[str]
) -> None:
    edges, indegree, roots = _graph_edges(items, failures, planned_ids)
    if roots != ROOTS:
        failures.append(f"portfolio roots: expected {sorted(ROOTS)}")
    if _visited_nodes(edges, indegree) != len(items):
        failures.append("portfolio dependency graph: cycle or unreachable challenge")


def _check_native_bindings(root: Path, items: dict[str, dict[str, Any]],
                           failures: list[str]) -> None:
    scenario = load_scenario(root)
    for challenge_id, row in items.items():
        objective_ref = row.get("objective_ref")
        evidence_ref = row.get("evidence_requirement_ref")
        if not isinstance(objective_ref, str) or "." not in objective_ref:
            failures.append(f"{challenge_id}: invalid ACES objective extension binding")
            continue
        namespace = objective_ref.rsplit(".", 1)[0]
        expected = {
            "objective": objective_ref,
            "condition": f"{namespace}.{challenge_id}-complete",
            "truth": f"{namespace}.{challenge_id}-satisfied",
            "evidence": evidence_ref,
        }
        if evidence_ref != f"{namespace}.{challenge_id}-proof":
            failures.append(f"{challenge_id}: ACES objective/evidence extension binding drift")
        if (
            expected["objective"] not in scenario.objectives
            or expected["condition"] not in scenario.conditions
            or expected["truth"] not in scenario.propositions
            or expected["truth"] not in scenario.assertions
            or expected["evidence"] not in scenario.evidence_requirements
        ):
            failures.append(f"{challenge_id}: incomplete native ACES objective surface")
            continue
        condition = scenario.conditions[expected["condition"]]
        proposition = scenario.propositions[expected["truth"]]
        assertion = scenario.assertions[expected["truth"]]
        objective = scenario.objectives[expected["objective"]]
        expected_dependencies = {
            items[item]["objective_ref"]
            for item in row["prerequisites"]
            if item in items
        }
        if (
            condition.proposition != expected["truth"]
            or proposition.evidence_requirements != [expected["evidence"]]
            or proposition.basis.value != "observed_state"
            or proposition.predicate.kind != "boolean"
            or proposition.predicate.property != "objective.satisfied"
            or proposition.predicate.expected is not True
            or assertion.proposition != expected["truth"]
            or assertion.role.value != "postcondition"
            or assertion.polarity.value != "positive"
            or objective.success.assertions != [expected["truth"]]
            or set(objective.depends_on) != expected_dependencies
        ):
            failures.append(f"{challenge_id}: native ACES objective truth binding drift")


def _check_policy(policy: dict[str, Any], items: dict[str, dict[str, Any]],
                  failures: list[str]) -> None:
    expected = {
        "event_window_minutes": 480,
        "route_active_minutes": 420,
        "transition_minutes": 30,
        "recovery_minutes": 30,
    }
    for field, value in expected.items():
        if policy.get(field) != value:
            failures.append(f"content.core.portfolio-policy.{field}: expected {value}")
    if sum(expected[field] for field in ("route_active_minutes", "transition_minutes", "recovery_minutes")) != expected["event_window_minutes"]:
        failures.append("portfolio schedule does not fill event window")
    if len(policy.get("route_hypotheses", [])) != 5:
        failures.append("content.core.portfolio-policy: five route hypotheses required")
    if sum(int(row["target_minutes"]) for row in items.values()) != 3015:
        failures.append("ACES challenge target time must provide 3015 board-active minutes")
    if sum(int(row["points"]) for row in items.values()) != 16550:
        failures.append("challenge evaluation points must total 16550")
    if policy.get("realized_challenges") != len(items) or policy.get("realized_target_minutes") != 3015:
        failures.append("content.core.portfolio-policy: realized inventory header drift")


def _check_experiment_task(root: Path, failures: list[str]) -> None:
    path = root / EXPERIMENT_TASK_PATH
    try:
        task = ExperimentTaskModel.model_validate(
            yaml.safe_load(path.read_text(encoding="utf-8"))
        )
    except (OSError, TypeError, ValueError, yaml.YAMLError) as error:
        failures.append(f"{EXPERIMENT_TASK_PATH}: invalid experiment-task/v1: {error}")
        return
    metric = task.evaluation_protocol.metric_definitions.get("ctf-score")
    if (
        task.scenario_ref.ref_id != "keplerops-ai"
        or metric is None
        or metric.value_kind != "integer"
        or metric.direction != "higher-is-better"
        or {ref.ref_id for ref in metric.evidence_requirements}
        != {"keplerops-objective-receipts"}
        or {ref.ref_id for ref in task.evaluation_protocol.observation_requirements}
        != {"keplerops-objective-receipts"}
        or "16550" not in (task.evaluation_protocol.acceptance_policy or "")
    ):
        failures.append(f"{EXPERIMENT_TASK_PATH}: evaluation task metric contract drift")
    artifact = next(
        (row for row in task.artifact_refs if row.artifact_id == "keplerops-sdl-root"),
        None,
    )
    if artifact is None:
        failures.append(f"{EXPERIMENT_TASK_PATH}: SDL artifact reference missing")
        return
    artifact_path = root / artifact.uri
    try:
        payload = artifact_path.read_bytes()
    except OSError as error:
        failures.append(f"{EXPERIMENT_TASK_PATH}: cannot read SDL artifact: {error}")
        return
    if (
        artifact.size_bytes != len(payload)
        or artifact.checksum.algorithm != "sha256"
        or artifact.checksum.value != hashlib.sha256(payload).hexdigest()
    ):
        failures.append(f"{EXPERIMENT_TASK_PATH}: SDL artifact digest or size drift")


def _check_documentation(root: Path, items: dict[str, dict[str, Any]],
                         failures: list[str]) -> None:
    try:
        body = (root / DOC_PATH).read_text(encoding="utf-8")
    except OSError:
        failures.append(f"{DOC_PATH}: missing")
        return
    for challenge_id in items:
        if f"`{challenge_id}`" not in body:
            failures.append(f"{DOC_PATH}: missing challenge {challenge_id}")


def validate_pack(root: str | None = None) -> list[str]:
    pack = Path(root or PACK_ROOT).resolve()
    failures: list[str] = []
    try:
        items = challenge_contracts(pack)
        modules = module_contracts(pack)
        policy = portfolio_policy(pack)
        implementation = implementation_projection(pack)
        design = atlas_challenge_design(pack)
    except (OSError, KeyError, TypeError, ValueError) as error:
        return [f"{SDL_PATH}: cannot extract ACES portfolio: {error}"]
    planned_ids = {
        row["challenge_id"]
        for row in design.get("challenge_designs", [])
        if isinstance(row, dict) and isinstance(row.get("challenge_id"), str)
    }
    if len(items) != 134 or len(modules) != 10:
        failures.append("ACES portfolio must contain 134 challenges in ten modules")
    for challenge_id, row in items.items():
        _check_item(challenge_id, row, pack, failures)
    module_counts = Counter(row.get("module") for row in items.values())
    if dict(module_counts) != MODULE_COUNTS:
        failures.append(f"ACES module allocations: expected {MODULE_COUNTS}")
    difficulty_counts = Counter(row.get("difficulty") for row in items.values())
    if difficulty_counts != Counter({key: value["count"] for key, value in DIFFICULTIES.items()}):
        failures.append("ACES difficulty distribution drift")
    realized = {row["challenge_id"] for row in implementation["realized_items"]}
    expected_realized = {key for key, row in items.items() if row["implementation_status"] != "planned"}
    if realized != expected_realized:
        failures.append("ACES implementation projection does not cover every realized challenge")
    status_rank = {"planned": 0, "source-implemented": 1, "automated-proven": 2, "participant-proven": 3}
    expected_module_statuses = {
        module_id: min(
            (
                item["implementation_status"]
                for item in items.values()
                if item.get("module") == module_id
            ),
            key=status_rank.get,
        )
        for module_id in modules
    }
    actual_module_statuses = {
        row["module"]: row["status"]
        for row in implementation.get("module_summaries", [])
        if isinstance(row, dict) and isinstance(row.get("module"), str)
    }
    if actual_module_statuses != expected_module_statuses:
        failures.append("ACES implementation projection does not summarize module slices")
    _check_graph(items, failures, planned_ids)
    _check_native_bindings(pack, items, failures)
    _check_policy(policy, items, failures)
    _check_experiment_task(pack, failures)
    _check_documentation(pack, items, failures)
    return failures


def main(argv: list[str] | None = None) -> int:
    if (argv if argv is not None else sys.argv[1:]) != ["validate"]:
        print("usage: validate_portfolio.py validate", file=sys.stderr)
        return 2
    failures = validate_pack()
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1
    print("[ok] RAES SDL challenge portfolio (134 native objectives; 16550 points; 3015 board minutes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
