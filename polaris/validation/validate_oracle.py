#!/usr/bin/env python3
"""Validate the private Polaris oracle as a strict join over canonical ACES."""

from __future__ import annotations

import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import yaml


PACK_ROOT = Path(__file__).resolve().parents[1]
ORACLE_PATH = PACK_ROOT / "oracle" / "polaris-oracle.yaml"
AFFORDANCE_PATH = PACK_ROOT / "oracle" / "affordances.yaml"
PLACEMENT_PATH = PACK_ROOT / "flags" / "placement.yaml"
CHALLENGE_PATH = PACK_ROOT / "challenges" / "challenges.yaml"
TEXT_SUFFIXES = {
    ".css", ".html", ".md", ".svg", ".txt", ".yaml", ".yml"
}

sys.path.insert(0, str(PACK_ROOT))

from contract_source import MAX_SOURCE_BYTES, load_yaml  # noqa: E402
from aces_contract import (  # noqa: E402
    AcesContractError,
    SDL_RELATIVE_PATH,
    load_scenario,
    objective_projection,
    participant_start_projection,
    reference_exists,
    workflow_objectives,
)


from validation import oracle_model as SHARED_MODEL  # noqa: E402

Issue = SHARED_MODEL.Issue

AFFORDANCE_TOP_KEYS = {
    "schema_version", "authority", "required_kinds", "runtime_profiles",
    "affordances",
}
AUTHORITY_KEYS = {"sdl", "agent", "workflow"}
AFFORDANCE_KEYS = {
    "id", "kinds", "aces_refs", "source_owner", "path_steps", "profiles",
    "discoverability", "fresh_range_predicate", "reset_owner", "flag_bindings",
}
REQUIRED_AFFORDANCE_KEYS = AFFORDANCE_KEYS - {"flag_bindings"}
FLAG_BINDING_KEYS = {"flag_id", "path_step"}
PLACEMENT_TOP_KEYS = {"flags"}
PLACEMENT_KEYS = {
    "flag_id", "source", "value", "generator", "instructions", "host", "path",
    "note",
}
CHALLENGE_TOP_KEYS = {"challenges"}
CHALLENGE_KEYS = {
    "flag_id", "title", "difficulty", "points", "question", "hints",
}
FLAG_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DIFFICULTIES = {"easy", "medium", "hard", "insane"}
REQUIRED_AFFORDANCE_KINDS = {
    "clue", "credential", "tool", "artifact", "privilege", "route",
    "service", "data",
}
DISCOVERABILITY = {
    "participant_in_world", "participant_action", "participant_tool",
    "derived_in_world",
}
SUPPORTED_REFS = {
    "nodes", "accounts", "relationships", "content", "objectives", "agents",
    "workflows", "services", "vulnerabilities", "features", "conditions",
    "propositions", "assertions", "evidence_requirements",
}
REQUIRED_NAMESPACE = {"range_instance", "participant", "attempt_generation"}


def _issue(
    object_type: str,
    object_id: str,
    field: str,
    invariant: str,
    detail: str,
) -> Any:
    return Issue(object_type, object_id, field, invariant, detail)


def _read_yaml(path: Path) -> dict[str, Any]:
    return load_yaml(path)


def _unknown_fields(
    issues: list[Any],
    row: Any,
    allowed: set[str],
    object_type: str,
    object_id: str,
) -> None:
    if not isinstance(row, dict):
        issues.append(
            _issue(object_type, object_id, "", "type_error", "mapping required")
        )
        return
    for field in row:
        if field not in allowed:
            issues.append(
                _issue(
                    object_type,
                    object_id,
                    field,
                    "unknown_field",
                    "unexpected field",
                )
            )


def _path_step_rows(oracle: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        row["id"]: row
        for row in oracle.get("path_steps", [])
        if isinstance(row, dict) and isinstance(row.get("id"), str)
    }


def _validate_path_cycles(
    issues: list[Any],
    steps: dict[str, dict[str, Any]],
) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(step_id: str) -> None:
        if step_id in visiting:
            issues.append(
                _issue(
                    "path_graph", "", "", "path_cycle",
                    "path dependencies must be acyclic",
                )
            )
            return
        if step_id in visited or step_id not in steps:
            return
        visiting.add(step_id)
        for prerequisite in steps[step_id].get("prerequisites", []):
            if isinstance(prerequisite, str):
                visit(prerequisite)
        visiting.remove(step_id)
        visited.add(step_id)

    for step_id in steps:
        visit(step_id)


def _path_step_owners(
    issues: list[Any],
    oracle: dict[str, Any],
) -> dict[str, str]:
    owner: dict[str, str] = {}
    for outcome in oracle.get("outcomes", []):
        if not isinstance(outcome, dict) or not isinstance(outcome.get("id"), str):
            continue
        for step_id in outcome.get("canonical_steps", []):
            if step_id in owner and owner[step_id] != outcome["id"]:
                issues.append(
                    _issue(
                        "path_step", step_id, "canonical_steps",
                        "step_owner", "path step belongs to multiple outcomes",
                    )
                )
            owner[step_id] = outcome["id"]
    return owner


def _objective_dependencies(
    steps: dict[str, dict[str, Any]],
    owner: dict[str, str],
    objective_ids: set[str],
) -> dict[str, set[str]]:
    dependencies = {objective_id: set() for objective_id in objective_ids}
    for step_id, row in steps.items():
        outcome_id = owner.get(step_id)
        if outcome_id not in dependencies:
            continue
        prerequisite_owners = {
            owner.get(prerequisite)
            for prerequisite in row.get("prerequisites", [])
        }
        dependencies[outcome_id].update(
            candidate
            for candidate in prerequisite_owners
            if candidate and candidate != outcome_id
        )
    return dependencies


def _validate_objective_dependencies(
    issues: list[Any],
    objectives: dict[str, dict[str, Any]],
    actual: dict[str, set[str]],
) -> None:
    for objective_id, projection in objectives.items():
        if actual.get(objective_id, set()) != set(projection["depends_on"]):
            issues.append(
                _issue(
                    "outcome", objective_id, "canonical_steps",
                    "objective_dependency_drift",
                    "path edges must preserve canonical ACES dependencies",
                )
            )


def _validate_path_graph(
    oracle: dict[str, Any],
    objectives: dict[str, dict[str, Any]],
) -> list[Any]:
    issues: list[Any] = []
    steps = _path_step_rows(oracle)
    _validate_path_cycles(issues, steps)
    owner = _path_step_owners(issues, oracle)
    if set(owner) != set(steps):
        issues.append(
            _issue(
                "path_graph", "", "canonical_steps", "step_coverage",
                "every path step must belong to exactly one outcome",
            )
        )
    actual = _objective_dependencies(steps, owner, set(objectives))
    _validate_objective_dependencies(issues, objectives, actual)
    return issues


def _oracle_evidence_rows(
    oracle: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    step_evidence = [
        item
        for step in oracle.get("path_steps", [])
        if isinstance(step, dict)
        for field in ("required_evidence", "optional_evidence")
        for item in step.get(field, [])
        if isinstance(item, dict)
    ]
    alternate_evidence = [
        item
        for alternate in oracle.get("accepted_alternates", [])
        if isinstance(alternate, dict)
        for item in alternate.get("evidence", [])
        if isinstance(item, dict)
    ]
    return {
        item["id"]: item
        for item in step_evidence + alternate_evidence
        if isinstance(item.get("id"), str)
    }


def _validate_evidence_aces(
    issues: list[Any],
    scenario: Any,
    evidence_id: str,
    item: dict[str, Any],
) -> None:
    if not REQUIRED_NAMESPACE <= set(item.get("proof_fields", [])):
        issues.append(
            _issue(
                "evidence", evidence_id, "proof_fields",
                "evidence_field_namespace",
                "each proof event must carry the complete namespace",
            )
        )
    source = item.get("source")
    if not isinstance(source, str) or not source.startswith("proposition:"):
        issues.append(
            _issue(
                "evidence", evidence_id, "source", "aces_source",
                "evidence source must join to an ACES proposition",
            )
        )
        return
    proposition_id = source.partition(":")[2]
    if not reference_exists(scenario, "propositions", proposition_id):
        issues.append(
            _issue(
                "evidence", evidence_id, "source", "unresolved_aces_ref",
                "evidence source does not resolve in canonical ACES",
            )
        )
    if not reference_exists(scenario, "nodes", item.get("reset_owner", "")):
        issues.append(
            _issue(
                "evidence", evidence_id, "reset_owner",
                "unresolved_aces_ref",
                "reset owner does not resolve to an ACES node",
            )
        )


def _validate_evidence_namespace(
    issues: list[Any],
    oracle: dict[str, Any],
) -> None:
    validator = oracle.get("validator")
    namespace = set(
        validator.get("evidence_namespace", [])
        if isinstance(validator, dict)
        else []
    )
    if not REQUIRED_NAMESPACE <= namespace:
        issues.append(
            _issue(
                "validator", "", "evidence_namespace", "evidence_namespace",
                "range, participant, and attempt generation are required",
            )
        )


def _participant_start_is_valid(start: dict[str, Any]) -> bool:
    return (
        start["agent"] == "polaris-participant"
        and start["entity"] == "participant"
        and start["starting_accounts"] == ["kali"]
        and "a14-kali" in start["hosts"]
    )


def _validate_oracle_aces(
    oracle: dict[str, Any],
    pack_root: Path,
) -> list[Any]:
    issues: list[Any] = []
    objectives = objective_projection(pack_root)
    outcome_rows = {
        row.get("id"): row
        for row in oracle.get("outcomes", [])
        if isinstance(row, dict) and isinstance(row.get("id"), str)
    }
    if set(outcome_rows) != set(objectives):
        issues.append(
            _issue(
                "oracle", "", "outcomes", "objective_drift",
                "oracle outcomes must exactly match canonical ACES objectives",
            )
        )
    if workflow_objectives(pack_root) != set(objectives):
        issues.append(
            _issue(
                "oracle", "", "outcomes", "workflow_drift",
                "canonical workflow and objective set must agree",
            )
        )

    scenario = load_scenario(pack_root)
    for evidence_id, item in _oracle_evidence_rows(oracle).items():
        _validate_evidence_aces(issues, scenario, evidence_id, item)
    _validate_evidence_namespace(issues, oracle)
    start = participant_start_projection(pack_root)
    if not _participant_start_is_valid(start):
        issues.append(
            _issue(
                "oracle", "", "scenario", "participant_context",
                "oracle must start as kali on the A14 participant surface",
            )
        )
    issues.extend(_validate_path_graph(oracle, objectives))
    return issues


def _has_symlink(root: Path, candidate: Path) -> bool:
    relative = candidate.relative_to(root)
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            return True
    return False


def _validate_source_owner(
    issues: list[Any],
    pack_root: Path,
    row_id: str,
    source_owner: Any,
) -> None:
    if not isinstance(source_owner, str) or not source_owner:
        issues.append(
            _issue(
                "affordance", row_id, "source_owner", "required",
                "one current source owner is required",
            )
        )
        return
    relative = Path(source_owner)
    if relative.is_absolute() or ".." in relative.parts or "\\" in source_owner:
        issues.append(
            _issue(
                "affordance", row_id, "source_owner", "path_escape",
                "source owner must stay inside the pack",
            )
        )
        return
    candidate = pack_root / relative
    try:
        resolved = candidate.resolve(strict=True)
    except OSError:
        issues.append(
            _issue(
                "affordance", row_id, "source_owner", "source_missing",
                "declared source owner does not exist",
            )
        )
        return
    if not resolved.is_relative_to(pack_root.resolve()) or _has_symlink(
        pack_root.resolve(), candidate
    ):
        issues.append(
            _issue(
                "affordance", row_id, "source_owner", "path_escape",
                "source owner must be a contained non-symlink path",
            )
        )


def _validate_aces_refs(
    issues: list[Any],
    scenario: Any,
    row_id: str,
    refs: Any,
) -> None:
    if not isinstance(refs, dict) or not refs:
        issues.append(
            _issue(
                "affordance", row_id, "aces_refs", "required",
                "at least one ACES reference is required",
            )
        )
        return
    for collection, identifiers in refs.items():
        if collection not in SUPPORTED_REFS:
            issues.append(
                _issue(
                    "affordance", row_id, "aces_refs", "unknown_field",
                    "unsupported ACES reference collection",
                )
            )
            continue
        if not isinstance(identifiers, list) or not identifiers:
            issues.append(
                _issue(
                    "affordance", row_id, "aces_refs", "type_error",
                    "ACES references must be a non-empty list",
                )
            )
            continue
        for identifier in identifiers:
            if not isinstance(identifier, str) or not reference_exists(
                scenario, collection, identifier
            ):
                issues.append(
                    _issue(
                        "affordance", row_id, "aces_refs",
                        "unresolved_aces_ref",
                        "reference does not resolve in canonical ACES",
                    )
                )


def _validate_affordance_header(
    issues: list[Any],
    data: dict[str, Any],
) -> None:
    _unknown_fields(issues, data, AFFORDANCE_TOP_KEYS, "affordance_ledger", "")
    if data.get("schema_version") != 1:
        issues.append(
            _issue(
                "affordance_ledger", "", "schema_version", "schema_version",
                "unsupported affordance schema version",
            )
        )
    authority = data.get("authority")
    _unknown_fields(issues, authority, AUTHORITY_KEYS, "authority", "")
    expected_authority = {
        "sdl": SDL_RELATIVE_PATH.as_posix(),
        "agent": "polaris-participant",
        "workflow": "operation-northstorm",
    }
    if authority != expected_authority:
        issues.append(
            _issue(
                "authority", "", "", "authority_drift",
                "affordance authority must name the canonical ACES surfaces",
            )
        )
    if set(data.get("required_kinds", [])) != REQUIRED_AFFORDANCE_KINDS:
        issues.append(
            _issue(
                "affordance_ledger", "", "required_kinds",
                "affordance_kind_coverage",
                "all required affordance kinds must be declared",
            )
        )
    profiles = data.get("runtime_profiles")
    if not isinstance(profiles, dict) or set(profiles) != {
        "local_degraded", "aws_event"
    }:
        issues.append(
            _issue(
                "affordance_ledger", "", "runtime_profiles", "profile_drift",
                "runtime profiles must match pack compatibility",
            )
        )


def _validate_affordance_id(
    issues: list[Any],
    raw: dict[str, Any],
    row_id: str,
    seen: set[str],
) -> None:
    identifier = raw.get("id")
    if not isinstance(identifier, str) or not identifier or identifier in seen:
        issues.append(
            _issue(
                "affordance", row_id, "id", "duplicate_id",
                "unique affordance id required",
            )
        )
        return
    seen.add(identifier)


def _validate_affordance_kinds(
    issues: list[Any],
    raw: dict[str, Any],
    row_id: str,
    covered_kinds: set[str],
) -> None:
    kinds = raw.get("kinds")
    if (
        not isinstance(kinds, list)
        or not kinds
        or not set(kinds) <= REQUIRED_AFFORDANCE_KINDS
    ):
        issues.append(
            _issue(
                "affordance", row_id, "kinds", "enum",
                "affordance kinds must use the required vocabulary",
            )
        )
        return
    covered_kinds.update(kinds)


def _validate_affordance_steps(
    issues: list[Any],
    raw: dict[str, Any],
    row_id: str,
    path_steps: set[str],
    covered_steps: set[str],
) -> None:
    refs = raw.get("path_steps")
    if not isinstance(refs, list) or not refs:
        issues.append(
            _issue(
                "affordance", row_id, "path_steps", "required",
                "path-step coverage is required",
            )
        )
        return
    for step_id in refs:
        if step_id not in path_steps:
            issues.append(
                _issue(
                    "affordance", row_id, "path_steps",
                    "unresolved_path_step",
                    "path-step reference is unknown",
                )
            )
        else:
            covered_steps.add(step_id)


def _validate_affordance_values(
    issues: list[Any],
    scenario: Any,
    raw: dict[str, Any],
    row_id: str,
) -> None:
    row_profiles = raw.get("profiles")
    if (
        not isinstance(row_profiles, list)
        or not row_profiles
        or not set(row_profiles) <= {"local_degraded", "aws_event"}
        or len(row_profiles) != len(set(row_profiles))
    ):
        issues.append(
            _issue(
                "affordance", row_id, "profiles", "profile_coverage",
                "affordance profiles must reference unique known runtimes",
            )
        )
    if raw.get("discoverability") not in DISCOVERABILITY:
        issues.append(
            _issue(
                "affordance", row_id, "discoverability", "enum",
                "unsupported discoverability class",
            )
        )
    predicate = raw.get("fresh_range_predicate")
    if not isinstance(predicate, str) or not predicate.strip():
        issues.append(
            _issue(
                "affordance", row_id, "fresh_range_predicate", "required",
                "fresh-range predicate is required",
            )
        )
    if not reference_exists(scenario, "nodes", raw.get("reset_owner", "")):
        issues.append(
            _issue(
                "affordance", row_id, "reset_owner", "unresolved_aces_ref",
                "reset owner must resolve to an ACES node",
            )
        )


def _validate_affordance_row(
    issues: list[Any],
    scenario: Any,
    pack_root: Path,
    raw: dict[str, Any],
    row_id: str,
    path_steps: set[str],
    covered_steps: set[str],
    covered_kinds: set[str],
    seen: set[str],
) -> None:
    required = REQUIRED_AFFORDANCE_KEYS - set(raw)
    if required:
        issues.append(
            _issue(
                "affordance", row_id, "", "required",
                "affordance row has missing fields",
            )
        )
    _validate_affordance_id(issues, raw, row_id, seen)
    _validate_affordance_kinds(issues, raw, row_id, covered_kinds)
    _validate_affordance_steps(
        issues, raw, row_id, path_steps, covered_steps
    )
    _validate_affordance_values(issues, scenario, raw, row_id)
    _validate_source_owner(issues, pack_root, row_id, raw.get("source_owner"))
    _validate_aces_refs(issues, scenario, row_id, raw.get("aces_refs"))


def _validate_contract_path(
    issues: list[Any],
    pack_root: Path,
    flag_id: str,
    field: str,
    value: Any,
) -> None:
    if not isinstance(value, str) or not value:
        issues.append(
            _issue("flag", flag_id, field, "source_missing", "source path is required")
        )
        return
    path_text = value.partition("#")[0]
    relative = Path(path_text)
    if relative.is_absolute() or ".." in relative.parts or "\\" in path_text:
        issues.append(
            _issue(
                "flag", flag_id, field, "path_escape",
                "source path must stay inside the pack",
            )
        )
        return
    candidate = pack_root / relative
    try:
        resolved = candidate.resolve(strict=True)
    except OSError:
        issues.append(
            _issue(
                "flag", flag_id, field, "source_missing",
                "declared source path does not exist",
            )
        )
        return
    if (
        not resolved.is_relative_to(pack_root.resolve())
        or _has_symlink(pack_root.resolve(), candidate)
        or not resolved.is_file()
    ):
        issues.append(
            _issue(
                "flag", flag_id, field, "path_escape",
                "source must be a contained regular non-symlink file",
            )
        )


def _register_flag_row(
    issues: list[Any],
    raw: dict[str, Any],
    row_id: str,
    object_type: str,
    by_id: dict[str, dict[str, Any]],
) -> str | None:
    flag_id = raw.get("flag_id")
    valid = (
        isinstance(flag_id, str)
        and FLAG_ID_RE.fullmatch(flag_id)
        and flag_id not in by_id
    )
    if not valid:
        issues.append(
            _issue(
                object_type, row_id, "flag_id", "duplicate_flag_id",
                "a unique stable lowercase flag id is required",
            )
        )
        return None
    by_id[flag_id] = raw
    return flag_id


def _validate_placement_source(
    issues: list[Any],
    pack_root: Path,
    raw: dict[str, Any],
    flag_id: str,
) -> None:
    source = raw.get("source")
    source_fields = {
        name for name in ("value", "generator", "instructions")
        if name in raw
    }
    valid = (
        source in {"value", "generator", "instructions"}
        and source_fields == {source}
        and isinstance(raw.get(source), str)
        and bool(raw[source])
    )
    if not valid:
        issues.append(
            _issue(
                "flag", flag_id, "source", "flag_source_shape",
                "source must select exactly one matching non-empty field",
            )
        )
    if source in {"generator", "instructions"}:
        _validate_contract_path(
            issues, pack_root, flag_id, source, raw.get(source)
        )


def _validate_placement_location(
    issues: list[Any],
    scenario: Any,
    raw: dict[str, Any],
    flag_id: str,
) -> None:
    host = raw.get("host")
    if not isinstance(host, str) or not reference_exists(scenario, "nodes", host):
        issues.append(
            _issue(
                "flag", flag_id, "host", "unresolved_aces_ref",
                "placement host must resolve in canonical ACES",
            )
        )
    path = raw.get("path")
    if not isinstance(path, str) or not path.strip():
        issues.append(
            _issue(
                "flag", flag_id, "path", "required",
                "runtime recovery path is required",
            )
        )


def _validate_placement_row(
    issues: list[Any],
    scenario: Any,
    pack_root: Path,
    raw: Any,
    offset: int,
    by_id: dict[str, dict[str, Any]],
) -> None:
    row_id = str(raw.get("flag_id", offset)) if isinstance(raw, dict) else str(offset)
    _unknown_fields(issues, raw, PLACEMENT_KEYS, "flag", row_id)
    if not isinstance(raw, dict):
        return
    flag_id = _register_flag_row(issues, raw, row_id, "flag", by_id)
    if flag_id is None:
        return
    _validate_placement_source(issues, pack_root, raw, flag_id)
    _validate_placement_location(issues, scenario, raw, flag_id)


def _validate_placements(
    data: dict[str, Any],
    scenario: Any,
    pack_root: Path,
) -> tuple[list[Any], dict[str, dict[str, Any]]]:
    issues: list[Any] = []
    _unknown_fields(issues, data, PLACEMENT_TOP_KEYS, "flag_placement", "")
    rows = data.get("flags")
    if not isinstance(rows, list) or not rows:
        return [
            _issue(
                "flag_placement", "", "flags", "required",
                "a non-empty flag list is required",
            )
        ], {}
    by_id: dict[str, dict[str, Any]] = {}
    for offset, raw in enumerate(rows):
        _validate_placement_row(
            issues, scenario, pack_root, raw, offset, by_id
        )
    return issues, by_id


def _validate_challenge_text(
    issues: list[Any],
    raw: dict[str, Any],
    flag_id: str,
) -> None:
    required_text = ("title", "question")
    valid = all(
        isinstance(raw.get(field), str) and bool(raw[field].strip())
        for field in required_text
    )
    if not valid:
        issues.append(
            _issue(
                "challenge", flag_id, "", "required",
                "title and question are required",
            )
        )


def _validate_challenge_values(
    issues: list[Any],
    raw: dict[str, Any],
    flag_id: str,
) -> None:
    if raw.get("difficulty") not in DIFFICULTIES:
        issues.append(
            _issue(
                "challenge", flag_id, "difficulty", "enum",
                "unsupported challenge difficulty",
            )
        )
    points = raw.get("points")
    if not isinstance(points, int) or points <= 0:
        issues.append(
            _issue(
                "challenge", flag_id, "points", "type_error",
                "challenge points must be a positive integer",
            )
        )
    hints = raw.get("hints")
    valid_hints = (
        isinstance(hints, list)
        and bool(hints)
        and all(
            isinstance(hint, str) and bool(hint.strip())
            for hint in hints
        )
    )
    if not valid_hints:
        issues.append(
            _issue(
                "challenge", flag_id, "hints", "type_error",
                "one or more non-empty participant hints are required",
            )
        )


def _validate_challenge_row(
    issues: list[Any],
    raw: Any,
    offset: int,
    by_id: dict[str, dict[str, Any]],
) -> None:
    row_id = str(raw.get("flag_id", offset)) if isinstance(raw, dict) else str(offset)
    _unknown_fields(issues, raw, CHALLENGE_KEYS, "challenge", row_id)
    if not isinstance(raw, dict):
        return
    flag_id = _register_flag_row(issues, raw, row_id, "challenge", by_id)
    if flag_id is None:
        return
    _validate_challenge_text(issues, raw, flag_id)
    _validate_challenge_values(issues, raw, flag_id)


def _validate_challenges(
    data: dict[str, Any],
) -> tuple[list[Any], dict[str, dict[str, Any]]]:
    issues: list[Any] = []
    _unknown_fields(issues, data, CHALLENGE_TOP_KEYS, "challenge_contract", "")
    rows = data.get("challenges")
    if not isinstance(rows, list) or not rows:
        return [
            _issue(
                "challenge_contract", "", "challenges", "required",
                "a non-empty challenge list is required",
            )
        ], {}
    by_id: dict[str, dict[str, Any]] = {}
    for offset, raw in enumerate(rows):
        _validate_challenge_row(issues, raw, offset, by_id)
    return issues, by_id


def _validate_flag_binding(
    issues: list[Any],
    row: dict[str, Any],
    binding: Any,
    path_steps: set[str],
    bindings: dict[str, tuple[dict[str, Any], dict[str, Any]]],
) -> None:
    binding_id = (
        str(binding.get("flag_id", ""))
        if isinstance(binding, dict)
        else ""
    )
    _unknown_fields(
        issues, binding, FLAG_BINDING_KEYS, "flag_binding", binding_id
    )
    if not isinstance(binding, dict):
        return
    flag_id = binding.get("flag_id")
    if not isinstance(flag_id, str):
        issues.append(
            _issue(
                "flag_binding", "", "flag_id", "required",
                "flag id is required",
            )
        )
        return
    if flag_id in bindings:
        issues.append(
            _issue(
                "flag_binding", flag_id, "flag_id", "duplicate_flag_binding",
                "each flag must bind to exactly one affordance",
            )
        )
        return
    bindings[flag_id] = (row, binding)
    path_step = binding.get("path_step")
    owned_steps = row.get("path_steps", [])
    if path_step not in path_steps or path_step not in owned_steps:
        issues.append(
            _issue(
                "flag_binding", flag_id, "path_step", "flag_path_step",
                "binding path step must be owned by its affordance",
            )
        )


def _collect_flag_bindings(
    issues: list[Any],
    affordances: dict[str, Any],
    path_steps: set[str],
) -> dict[str, tuple[dict[str, Any], dict[str, Any]]]:
    bindings: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for row in affordances.get("affordances", []):
        if not isinstance(row, dict):
            continue
        raw_bindings = row.get("flag_bindings", [])
        if not isinstance(raw_bindings, list):
            issues.append(
                _issue(
                    "affordance", str(row.get("id", "")), "flag_bindings",
                    "type_error", "flag bindings must be a list",
                )
            )
            continue
        for binding in raw_bindings:
            _validate_flag_binding(
                issues, row, binding, path_steps, bindings
            )
    return bindings


def _validate_flag_id_bijection(
    issues: list[Any],
    placements: dict[str, dict[str, Any]],
    challenges: dict[str, dict[str, Any]],
    bindings: dict[str, tuple[dict[str, Any], dict[str, Any]]],
) -> set[str]:
    placement_ids = set(placements)
    if placement_ids != set(challenges) or placement_ids != set(bindings):
        issues.append(
            _issue(
                "flag_layer", "", "flag_id", "flag_id_bijection",
                "placements, challenges, and affordance bindings must match exactly",
            )
        )
    return placement_ids


def _validate_flag_binding_hosts(
    issues: list[Any],
    placements: dict[str, dict[str, Any]],
    bindings: dict[str, tuple[dict[str, Any], dict[str, Any]]],
    placement_ids: set[str],
) -> None:
    for flag_id in placement_ids & set(bindings):
        affordance, _ = bindings[flag_id]
        nodes = affordance.get("aces_refs", {}).get("nodes", [])
        if placements[flag_id].get("host") not in nodes:
            issues.append(
                _issue(
                    "flag_binding", flag_id, "host", "flag_host_affordance",
                    "placement host must belong to the bound affordance",
                )
            )


def _validate_flag_bindings(
    affordances: dict[str, Any],
    placements: dict[str, dict[str, Any]],
    challenges: dict[str, dict[str, Any]],
    path_steps: set[str],
) -> list[Any]:
    issues: list[Any] = []
    bindings = _collect_flag_bindings(issues, affordances, path_steps)
    placement_ids = _validate_flag_id_bijection(
        issues, placements, challenges, bindings
    )
    _validate_flag_binding_hosts(
        issues, placements, bindings, placement_ids
    )
    return issues


def _validate_affordance_coverage(
    issues: list[Any],
    path_steps: set[str],
    covered_steps: set[str],
    covered_kinds: set[str],
) -> None:
    if covered_kinds != REQUIRED_AFFORDANCE_KINDS:
        issues.append(
            _issue(
                "affordance_ledger", "", "affordances",
                "affordance_kind_coverage",
                "rows must cover every required affordance kind",
            )
        )
    if covered_steps != path_steps:
        issues.append(
            _issue(
                "affordance_ledger", "", "path_steps", "step_coverage",
                "every canonical path step needs an affordance",
            )
        )


def _validate_affordances(
    data: dict[str, Any],
    oracle: dict[str, Any],
    pack_root: Path,
) -> list[Any]:
    issues: list[Any] = []
    _validate_affordance_header(issues, data)
    scenario = load_scenario(pack_root)
    path_steps = set(_path_step_rows(oracle))
    covered_steps: set[str] = set()
    covered_kinds: set[str] = set()
    seen: set[str] = set()
    rows = data.get("affordances")
    if not isinstance(rows, list) or not rows:
        return issues + [
            _issue(
                "affordance_ledger", "", "affordances", "required",
                "affordance rows are required",
            )
        ]
    for offset, raw in enumerate(rows):
        row_id = str(raw.get("id", offset)) if isinstance(raw, dict) else str(offset)
        _unknown_fields(issues, raw, AFFORDANCE_KEYS, "affordance", row_id)
        if not isinstance(raw, dict):
            continue
        _validate_affordance_row(
            issues,
            scenario,
            pack_root,
            raw,
            row_id,
            path_steps,
            covered_steps,
            covered_kinds,
            seen,
        )
    _validate_affordance_coverage(
        issues, path_steps, covered_steps, covered_kinds
    )
    return issues


def _iter_participant_files(pack_root: Path, root_value: Any):
    if not isinstance(root_value, dict) or not isinstance(root_value.get("path"), str):
        return
    relative = Path(root_value["path"])
    if relative.is_absolute() or ".." in relative.parts or "\\" in root_value["path"]:
        return
    candidate = pack_root / relative
    try:
        resolved = candidate.resolve(strict=True)
    except OSError:
        return
    if not resolved.is_relative_to(pack_root.resolve()):
        return
    if resolved.is_file():
        if resolved.suffix.lower() in TEXT_SUFFIXES:
            yield resolved
        return
    for path in resolved.rglob("*"):
        if (
            path.is_file()
            and not path.is_symlink()
            and path.suffix.lower() in TEXT_SUFFIXES
            and path.stat().st_size <= MAX_SOURCE_BYTES
        ):
            yield path


def _mapping_rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def _nested_mapping_rows(
    rows: list[dict[str, Any]],
    fields: tuple[str, ...],
) -> list[dict[str, Any]]:
    nested: list[dict[str, Any]] = []
    for row in rows:
        for field in fields:
            nested.extend(_mapping_rows(row.get(field)))
    return nested


def _string_field_values(
    rows: list[dict[str, Any]],
    field: str,
) -> set[str]:
    return {
        row[field]
        for row in rows
        if isinstance(row.get(field), str)
    }


def _hidden_tokens(oracle: dict[str, Any]) -> set[str]:
    steps = _mapping_rows(oracle.get("path_steps"))
    tokens = {
        step["id"]
        for step in steps
        if isinstance(step.get("id"), str) and "." in step["id"]
    }
    tokens.update(_string_field_values(steps, "success_state"))
    evidence = _nested_mapping_rows(
        steps, ("required_evidence", "optional_evidence")
    )
    tokens.update(_string_field_values(evidence, "id"))
    failures = _nested_mapping_rows(steps, ("failure_states",))
    tokens.update(_string_field_values(failures, "id"))
    alternates = _mapping_rows(oracle.get("accepted_alternates"))
    tokens.update(_string_field_values(alternates, "id"))
    return tokens


def validate_participant_leaks(
    oracle: dict[str, Any],
    pack_root: str | Path = PACK_ROOT,
) -> list[Any]:
    """Fail closed when a private oracle identifier enters participant source."""

    root = Path(pack_root).resolve()
    tokens = _hidden_tokens(oracle)
    issues: list[Any] = []
    seen: set[Path] = set()
    visibility = oracle.get("visibility", {})
    participant_roots = (
        visibility.get("participant_roots", [])
        if isinstance(visibility, dict)
        else []
    )
    for root_value in participant_roots:
        for path in _iter_participant_files(root, root_value) or ():
            if path in seen:
                continue
            seen.add(path)
            text = path.read_text(encoding="utf-8", errors="replace")
            if any(token in text for token in tokens):
                issues.append(
                    _issue(
                        "participant_surface",
                        path.relative_to(root).as_posix(),
                        "",
                        "hidden_vocabulary_leak",
                        "private oracle identifier found in participant source",
                    )
                )
    return issues


def validate_contract(
    pack_root: str | Path = PACK_ROOT,
    *,
    oracle_data: dict[str, Any] | None = None,
    affordance_data: dict[str, Any] | None = None,
    placement_data: dict[str, Any] | None = None,
    challenge_data: dict[str, Any] | None = None,
) -> list[Any]:
    """Validate all static Polaris oracle contracts without mutating state."""

    root = Path(pack_root).resolve()
    try:
        oracle = oracle_data if oracle_data is not None else _read_yaml(
            root / ORACLE_PATH.relative_to(PACK_ROOT)
        )
        affordances = (
            affordance_data
            if affordance_data is not None
            else _read_yaml(root / AFFORDANCE_PATH.relative_to(PACK_ROOT))
        )
        placements = (
            placement_data
            if placement_data is not None
            else _read_yaml(root / PLACEMENT_PATH.relative_to(PACK_ROOT))
        )
        challenges = (
            challenge_data
            if challenge_data is not None
            else _read_yaml(root / CHALLENGE_PATH.relative_to(PACK_ROOT))
        )
        issues = list(SHARED_MODEL.validate(oracle, source="private-oracle"))
        issues.extend(_validate_oracle_aces(oracle, root))
        issues.extend(_validate_affordances(affordances, oracle, root))
        scenario = load_scenario(root)
        placement_issues, placement_rows = _validate_placements(
            placements, scenario, root
        )
        challenge_issues, challenge_rows = _validate_challenges(challenges)
        issues.extend(placement_issues)
        issues.extend(challenge_issues)
        issues.extend(
            _validate_flag_bindings(
                affordances,
                placement_rows,
                challenge_rows,
                set(_path_step_rows(oracle)),
            )
        )
        issues.extend(validate_participant_leaks(oracle, root))
        return issues
    except (AcesContractError, OSError, ValueError, yaml.YAMLError):
        return [
            _issue(
                "oracle", "", "", "contract_load",
                "a bounded contract source could not be loaded",
            )
        ]


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args != ["validate"]:
        print("usage: validate_oracle.py validate", file=sys.stderr)
        return 2
    issues = validate_contract()
    if issues:
        counts = Counter(issue.invariant for issue in issues)
        summary = ", ".join(
            f"{name}={counts[name]}" for name in sorted(counts)
        )
        print(f"Polaris oracle validation failed: {len(issues)} issue(s): {summary}")
        return 1
    print("Polaris oracle contract valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
