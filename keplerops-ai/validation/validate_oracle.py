#!/usr/bin/env python3
"""Validate KeplerOps proof, CTFd, telemetry, and ATLAS projections from ACES."""

from __future__ import annotations

import hashlib
import re
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any

PACK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACK_ROOT))

from aces_contract import (  # noqa: E402
    atlas_challenge_design,
    atlas_technique_catalog,
    challenge_content_rows,
    challenge_contracts,
    flag_rows,
    implementation_projection,
    load_scenario,
    module_contracts,
    oracle_projection,
    research_telemetry_contract,
    telemetry_projection,
)


SDL_PATH = "sdl/keplerops-ai.sdl.yaml"
ATLAS_ID = re.compile(r"^AML\.T\d{4}(?:\.\d{3})?$")
CHALLENGE_ID = re.compile(r"^kep-m\d{2}-[a-z]+$")
HIDDEN_VOCABULARY = re.compile(
    r"\bS-[A-Z0-9]+\b|\bpath[ -]step\s+\d+(?:\.[A-Z])?\b|\bAML\.[A-Z0-9.]+\b",
    re.IGNORECASE,
)
REQUIRED_EVIDENCE_FIELDS = {
    "actor_role", "asset_id", "digest", "event_kind", "outcome_id",
    "participant", "range_instance", "status", "timestamp",
}
REQUIRED_NEGATIVE_GATES = {
    "gate-no-preseeded-proof", "gate-no-cross-namespace-award",
    "gate-no-stale-award", "gate-reset-clears-state",
}
REQUIRED_FORBIDDEN_FIELDS = {
    "answer", "credential", "flag", "model_artifact_body", "prompt",
    "provider_response", "raw_completion", "raw_proof",
}
RESEARCH_CAPTURE_SIGNALS = {
    "prompt", "completion", "tool_call", "tool_result", "terminal_command",
    "terminal_input", "terminal_output", "process_lifecycle", "notebook_content",
    "browser_interaction", "file_content", "workflow_state", "artifact_content",
    "http_body",
}
ATLAS_TECHNIQUE_COUNT = 173
ATLAS_CATALOG_DIGEST = "37845ece68d08f404e04785f22e92c71b60224be3780e97a98fc7b9a93aa52dc"
ATLAS_RELATIONSHIP_DIGEST = "877311d9454d8d30110e231df921e6d6a02b484fd70df048b41050521b0c6631"
ATLAS_ASSIGNMENT_FIELDS = (
    "id", "challenge_step", "surface", "evidence", "relationship",
    "coverage_status", "planned_action", "rationale", "implementation",
)
DESIGN_REQUIRED_FIELDS = {
    "challenge_id", "module", "title", "difficulty", "points",
    "minutes", "prerequisites", "techniques", "participant_action", "proof",
    "surfaces", "realization",
}
DESIGN_OPTIONAL_FIELDS = {"parent_variant_bundle", "implementation_status"}
DESIGN_POINTS = {
    "accessible": 50,
    "intermediate": 100,
    "advanced": 200,
    "expert": 300,
}
REQUIRED_RESEARCH_SIGNALS = {
    "prompt", "completion", "agent_message", "tool_call", "tool_result",
    "terminal_pty", "process_lifecycle", "scenario_http_headers",
    "scenario_http_body", "browser_kasm_interaction", "notebook_event",
    "file_event", "artifact_event", "workflow_event", "proof_receipt",
    "reset_event", "ctfd_event",
}
REQUIRED_BUNDLES = {
    "novice-manual", "intermediate-manual", "advanced-manual",
    "mixed-cohort", "agent-heavy",
}


def pack_root() -> str:
    return str(PACK_ROOT)


def _index(rows: list[dict[str, Any]], field: str, path: str,
           failures: list[str]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for offset, row in enumerate(rows):
        identifier = row.get(field) if isinstance(row, dict) else None
        if not isinstance(identifier, str) or not identifier or identifier in result:
            failures.append(f"{path}[{offset}].{field}: unique string required")
        else:
            result[identifier] = row
    return result


def _node_service_sets(scenario: Any) -> tuple[set[str], set[tuple[str, str]]]:
    nodes: set[str] = set()
    services: set[tuple[str, str]] = set()
    for qualified, node in scenario.nodes.items():
        local = qualified.removeprefix("core.")
        nodes.add(local)
        for service in node.services:
            services.add((local, service.name))
    return nodes, services


def _check_event_contracts(event_rows: dict[str, dict[str, Any]],
                           safe_fields: set[str], failures: list[str]) -> set[str]:
    evidence_ids: set[str] = set()
    for event_kind, event in event_rows.items():
        evidence = event.get("evidence")
        fields = event.get("fields")
        freshness = event.get("freshness_seconds")
        if not isinstance(evidence, str) or evidence in evidence_ids:
            failures.append(f"proof event {event_kind}: unique evidence id required")
        else:
            evidence_ids.add(evidence)
        if not isinstance(fields, list) or not REQUIRED_EVIDENCE_FIELDS <= set(fields) or not set(fields) <= safe_fields:
            failures.append(f"proof event {event_kind}: invalid digest-safe field set")
        if not isinstance(freshness, int) or isinstance(freshness, bool) or not 1 <= freshness <= 86_400:
            failures.append(f"proof event {event_kind}: invalid freshness window")
    return evidence_ids


def _check_outcome_contracts(outcome_rows: dict[str, dict[str, Any]],
                             evidence_ids: set[str], failures: list[str]) -> None:
    for outcome_id, outcome in outcome_rows.items():
        required = outcome.get("required_evidence")
        optional = outcome.get("optional_evidence")
        if not isinstance(required, list) or not required or not isinstance(optional, list):
            failures.append(f"outcome {outcome_id}: required/optional evidence lists required")
            continue
        unresolved = (set(required) | set(optional)) - evidence_ids
        if unresolved:
            failures.append(f"outcome {outcome_id}: unresolved evidence {sorted(unresolved)}")


def _check_oracle(outcomes: dict[str, Any], telemetry: dict[str, Any],
                  failures: list[str]) -> None:
    outcome_rows = _index(outcomes.get("outcomes", []), "id", "ACES outcomes", failures)
    event_rows = _index(telemetry.get("events", []), "event_kind", "ACES proof events", failures)
    if len(outcome_rows) != 10:
        failures.append("ACES proof projection requires ten outcomes")
    if len(event_rows) != 134:
        failures.append("ACES proof projection requires 134 event contracts")
    safe_fields = set(telemetry.get("safe_fields", []))
    if not REQUIRED_EVIDENCE_FIELDS <= safe_fields:
        failures.append("content.core.proof-policy: required evidence fields missing")
    if not REQUIRED_FORBIDDEN_FIELDS <= set(telemetry.get("forbidden_fields", [])):
        failures.append("content.core.proof-policy: forbidden sensitive fields missing")
    evidence_ids = _check_event_contracts(event_rows, safe_fields, failures)
    _check_outcome_contracts(outcome_rows, evidence_ids, failures)
    gates = {row.get("id") for row in telemetry.get("negative_gates", []) if isinstance(row, dict)}
    if gates != REQUIRED_NEGATIVE_GATES:
        failures.append("content.core.proof-policy: complete reset/isolation negative gates required")


def _check_event_sources(scenario: Any, telemetry: dict[str, Any],
                         failures: list[str]) -> None:
    nodes, services = _node_service_sets(scenario)
    for event in telemetry["events"]:
        source_asset = event.get("source_asset")
        source_service = event.get("source_service")
        reset_owner = event.get("reset_owner")
        if (source_asset, source_service) not in services:
            failures.append(
                f"proof event {event.get('event_kind')}: missing ACES source service "
                f"{source_asset}/{source_service}"
            )
        if reset_owner not in nodes:
            failures.append(f"proof event {event.get('event_kind')}: missing ACES reset owner")


def _check_flag(flag_id: str, flag: dict[str, Any], item: dict[str, Any] | None,
                participant: dict[str, Any] | None,
                outcome_rows: dict[str, dict[str, Any]], failures: list[str]) -> None:
    if item is None or participant is None:
        failures.append(f"flag {flag_id}: missing ACES challenge behavior")
        return
    if flag.get("outcome") != item.get("outcome") or flag.get("evidence") != item.get("proof", {}).get("evidence_id"):
        failures.append(f"flag {flag_id}: ACES proof binding drift")
    if "gcp_full" not in flag.get("profiles", []) or flag.get("source") != "instructions":
        failures.append(f"flag {flag_id}: unsupported profile/source projection")
    accepted = outcome_rows.get(flag["outcome"], {})
    accepted_ids = set(accepted.get("required_evidence", [])) | set(accepted.get("optional_evidence", []))
    if flag["evidence"] not in accepted_ids:
        failures.append(f"flag {flag_id}: evidence not accepted by its ACES outcome")
    participant_text = " ".join(
        [participant.get("title", ""), participant.get("question", ""), *participant.get("hints", [])]
    )
    if HIDDEN_VOCABULARY.search(participant_text):
        failures.append(f"flag {flag_id}: participant copy exposes oracle vocabulary")


def _check_flag_layer(challenges: dict[str, dict[str, Any]],
                      outcome_rows: dict[str, dict[str, Any]],
                      root: Path, failures: list[str]) -> None:
    content = _index(challenge_content_rows(root), "flag_id", "ACES challenge copy", failures)
    flags = _index(flag_rows(root), "flag_id", "ACES flag delivery", failures)
    if len(content) != 134 or set(content) != set(flags):
        failures.append("ACES flag delivery and participant copy must cover the same 134 realized flags")
    challenge_flags = {row["flag_id"]: row for row in challenges.values()}
    for flag_id, flag in flags.items():
        _check_flag(
            flag_id, flag, challenge_flags.get(flag_id), content.get(flag_id),
            outcome_rows, failures,
        )


def _check_research(contract: dict[str, Any], scenario: Any,
                    root: Path,
                    failures: list[str]) -> None:
    if contract.get("schema_version") != 1 or contract.get("authority") != "observational_fail_open":
        failures.append("content.core.research-telemetry-contract: invalid header")
    if contract.get("proof_contract") != "content.core.proof-policy":
        failures.append("content.core.research-telemetry-contract: ACES proof binding required")
    policy = contract.get("field_policy", {})
    operational = set(policy.get("operational_fields", []))
    content = set(policy.get("full_content_fields", []))
    forbidden = set(policy.get("forbidden_operational_fields", []))
    if not operational or operational & (content | forbidden):
        failures.append("research telemetry: operational/content/forbidden fields must be disjoint")
    capture = {row.get("id") for row in contract.get("capture_signals", []) if isinstance(row, dict)}
    if capture != RESEARCH_CAPTURE_SIGNALS:
        failures.append("research telemetry: complete capture signal policy required")
    modules = {row.get("id") for row in contract.get("modules", []) if isinstance(row, dict)}
    if modules != set(module_contracts(root)):
        failures.append("research telemetry: every ACES portfolio module must be versioned")
    nodes, services = _node_service_sets(scenario)
    for source in contract.get("sources", []):
        if not isinstance(source, dict) or source.get("asset") not in nodes or (
            source.get("asset"), source.get("service")
        ) not in services:
            failures.append(f"research telemetry source {source.get('id')}: missing ACES source service")


def _catalog_digest(rows: dict[str, dict[str, Any]]) -> str:
    body = "".join(f"{key}\t{rows[key].get('name')}\n" for key in sorted(rows))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _relationship_digest(rows: dict[str, dict[str, Any]]) -> str:
    body = "".join(
        f"{key}\t{','.join(sorted(rows[key].get('tactics', [])))}\n" for key in sorted(rows)
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _assignment_digest(rows: dict[str, dict[str, Any]]) -> str:
    body = "".join(
        "\t".join(str(rows[key].get(field)) for field in ATLAS_ASSIGNMENT_FIELDS) + "\n"
        for key in sorted(rows)
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _implemented_techniques(challenges: dict[str, dict[str, Any]]) -> dict[str, dict[str, set[str]]]:
    result: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: {"challenge_ids": set(), "evidence": set(), "manual": set(), "automated": set()}
    )
    for challenge_id, item in challenges.items():
        if item.get("implementation_status") not in {"automated-proven", "participant-proven"}:
            continue
        implementation = item.get("implementation_evidence")
        proof = item.get("proof")
        if not isinstance(implementation, dict) or not isinstance(proof, dict):
            continue
        for technique in implementation["primary_atlas_techniques"]:
            result[technique]["challenge_ids"].add(challenge_id)
            result[technique]["evidence"].add(proof["evidence_id"])
            result[technique]["manual"].add(implementation["manual_walkthrough"])
            result[technique]["automated"].add(implementation["automated_test"])
    return result


def _check_atlas_header(rows: dict[str, dict[str, Any]], experience: dict[str, Any],
                        failures: list[str]) -> None:
    if len(rows) != ATLAS_TECHNIQUE_COUNT or any(not ATLAS_ID.fullmatch(key) for key in rows):
        failures.append("content.core.atlas-technique-catalog: complete 173-technique catalog required")
    if _catalog_digest(rows) != ATLAS_CATALOG_DIGEST or experience.get("catalog_digest") != ATLAS_CATALOG_DIGEST:
        failures.append("content.core.atlas-technique-catalog: catalog digest drift")
    if _relationship_digest(rows) != ATLAS_RELATIONSHIP_DIGEST or experience.get("relationship_digest") != ATLAS_RELATIONSHIP_DIGEST:
        failures.append("content.core.atlas-technique-catalog: relationship digest drift")
    if _assignment_digest(rows) != experience.get("assignment_digest"):
        failures.append("content.core.atlas-technique-catalog: assignment digest drift")
    exact = sum(row.get("coverage_status") == "implemented" for row in rows.values())
    leaves = sum(
        row.get("coverage_status") == "implemented"
        and not any(other.startswith(f"{technique_id}.") for other in rows)
        for technique_id, row in rows.items()
    )
    if experience.get("implemented_technique_count") != exact or experience.get("implemented_leaf_technique_count") != leaves:
        failures.append("content.core.atlas-technique-catalog: implemented coverage header drift")


def _check_design_identity(
    row: dict[str, Any],
    path: str,
    failures: list[str],
) -> None:
    challenge_id = row.get("challenge_id")
    unknown = set(row) - DESIGN_REQUIRED_FIELDS - DESIGN_OPTIONAL_FIELDS
    missing = DESIGN_REQUIRED_FIELDS - set(row)
    if missing or unknown:
        failures.append(f"{path}: design fields missing={sorted(missing)} unknown={sorted(unknown)}")
    if not isinstance(challenge_id, str) or not CHALLENGE_ID.fullmatch(challenge_id):
        failures.append(f"{path}: invalid challenge id")
    status = row.get("implementation_status", "planned")
    if status not in {"planned", "source-implemented", "automated-proven", "participant-proven"}:
        failures.append(f"{path}: invalid implementation status")
    difficulty = row.get("difficulty")
    if difficulty not in DESIGN_POINTS or row.get("points") != DESIGN_POINTS.get(difficulty):
        failures.append(f"{path}: difficulty and points drift")
    minutes = row.get("minutes")
    if not isinstance(minutes, dict) or set(minutes) != {"min", "target", "max"} or not all(
        isinstance(minutes.get(field), int) and minutes[field] > 0 for field in ("min", "target", "max")
    ) or not minutes["min"] <= minutes["target"] <= minutes["max"]:
        failures.append(f"{path}: expected positive min <= target <= max")


def _design_techniques_match_state(
    row: dict[str, Any],
    techniques: object,
    planned: set[str],
    implemented: set[str],
    path: str,
    failures: list[str],
) -> list[str] | None:
    proven = row.get("implementation_status") in {
        "automated-proven", "participant-proven", "golden",
    }
    expected_catalog = implemented if proven else planned
    if (
        not isinstance(techniques, list)
        or not techniques
        or any(item not in expected_catalog for item in techniques)
    ):
        failures.append(f"{path}: techniques do not match implementation state")
        return None
    return techniques


def _check_design_technique_bundle(
    row: dict[str, Any], techniques: list[str], path: str, failures: list[str],
) -> None:
    if len(techniques) > 3:
        bases = {item.split(".", 2)[0] + "." + item.split(".", 2)[1] for item in techniques}
        if len(techniques) != 4 or row.get("parent_variant_bundle") is not True or len(bases) != 1:
            failures.append(f"{path}: more than three techniques requires the parent-plus-three exception")
    elif row.get("parent_variant_bundle") is not None:
        failures.append(f"{path}: parent-variant exception is unnecessary")


def _check_design_technique_step(
    module: object,
    techniques: object,
    technique_steps: dict[str, str],
    path: str,
    failures: list[str],
) -> None:
    if isinstance(module, str) and isinstance(techniques, list):
        expected_step = str(int(module[7:9])) if re.fullmatch(r"module-\d{2}-.+", module) else None
        if expected_step and any(
            str(item).startswith("AML.") and technique_steps.get(item) != expected_step
            for item in techniques
        ):
            failures.append(f"{path}: catalog module assignment drift")


def _check_design_techniques(
    row: dict[str, Any],
    planned: set[str],
    implemented: set[str],
    technique_steps: dict[str, str],
    path: str,
    failures: list[str],
) -> None:
    techniques = row.get("techniques")
    valid_techniques = _design_techniques_match_state(
        row, techniques, planned, implemented, path, failures,
    )
    if valid_techniques is not None:
        _check_design_technique_bundle(row, valid_techniques, path, failures)
    _check_design_technique_step(
        row.get("module"), techniques, technique_steps, path, failures,
    )


def _check_design_play_surface(
    row: dict[str, Any],
    path: str,
    failures: list[str],
) -> None:
    prerequisites = row.get("prerequisites")
    if not isinstance(prerequisites, list) or any(not isinstance(item, str) for item in prerequisites):
        failures.append(f"{path}: prerequisites must be a string list")
    surfaces = row.get("surfaces")
    if not isinstance(surfaces, list) or not surfaces or any(not isinstance(item, str) or not item for item in surfaces):
        failures.append(f"{path}: participant surfaces required")
    for field in ("title", "participant_action", "proof", "realization"):
        if not isinstance(row.get(field), str) or not row[field].strip():
            failures.append(f"{path}: non-empty {field} required")


def _check_design_row(
    row: dict[str, Any],
    planned: set[str],
    implemented: set[str],
    technique_steps: dict[str, str],
    failures: list[str],
) -> None:
    path = f"ATLAS challenge design {row.get('challenge_id')}"
    _check_design_identity(row, path, failures)
    _check_design_techniques(
        row, planned, implemented, technique_steps, path, failures,
    )
    _check_design_play_surface(row, path, failures)


def _receipt_extension_assignments(
    extensions: Any,
    planned: set[str],
    challenges: dict[str, dict[str, Any]],
    failures: list[str],
) -> list[str]:
    assigned: list[str] = []
    for offset, extension in enumerate(extensions):
        if not isinstance(extension, dict) or set(extension) != {"technique", "challenge_ids", "proof"}:
            failures.append(f"ATLAS existing receipt extension {offset}: invalid fields")
            continue
        technique = extension.get("technique")
        challenge_ids = extension.get("challenge_ids")
        if technique not in planned or not isinstance(challenge_ids, list) or not challenge_ids or not set(challenge_ids) <= set(challenges):
            failures.append(f"ATLAS existing receipt extension {technique}: invalid planned binding")
        if not isinstance(extension.get("proof"), str) or not extension["proof"].strip():
            failures.append(f"ATLAS existing receipt extension {technique}: proof rationale required")
        assigned.append(technique)
    return assigned


def _check_design_graph(
    rows: dict[str, dict[str, Any]],
    challenges: dict[str, dict[str, Any]],
    failures: list[str],
) -> None:
    known = set(challenges) | set(rows)
    indegree = {key: 0 for key in rows}
    edges: dict[str, list[str]] = defaultdict(list)
    for challenge_id, row in rows.items():
        for prerequisite in row.get("prerequisites", []):
            if prerequisite not in known or prerequisite == challenge_id:
                failures.append(f"ATLAS challenge design {challenge_id}: invalid prerequisite {prerequisite}")
            elif prerequisite in rows:
                edges[prerequisite].append(challenge_id)
                indegree[challenge_id] += 1
    queue = deque(key for key, value in indegree.items() if value == 0)
    visited = 0
    while queue:
        current = queue.popleft()
        visited += 1
        for child in edges[current]:
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if visited != len(rows):
        failures.append("content.core.atlas-challenge-design: planned dependency cycle")


def _check_design_distribution(
    design: dict[str, Any],
    rows: dict[str, dict[str, Any]],
    challenges: dict[str, dict[str, Any]],
    atlas_rows: dict[str, dict[str, Any]],
    failures: list[str],
) -> None:
    remaining = {key: row for key, row in rows.items() if key not in challenges}
    distribution = Counter(row.get("difficulty") for row in remaining.values())
    if distribution != Counter(design.get("planned_distribution", {})):
        failures.append("content.core.atlas-challenge-design: planned difficulty distribution drift")
    existing_distribution = Counter(row.get("difficulty") for row in challenges.values())
    complete_distribution = existing_distribution + distribution
    if complete_distribution != Counter(design.get("complete_distribution", {})):
        failures.append("content.core.atlas-challenge-design: complete difficulty distribution drift")
    lower = sum(complete_distribution[key] for key in ("accessible", "intermediate"))
    complete_count = len(challenges) + len(remaining)
    if complete_count == 0 or lower / complete_count < 0.70:
        failures.append("content.core.atlas-challenge-design: at least 70 percent accessible/intermediate required")
    expected_header = {
        "realized_challenges": len(challenges),
        "planned_challenges": len(remaining),
        "complete_library_challenges": complete_count,
        "designed_exact_techniques": len(atlas_rows),
        "designed_leaf_techniques": sum(
            not any(other.startswith(f"{key}.") for other in atlas_rows) for key in atlas_rows
        ),
    }
    if any(design.get(field) != value for field, value in expected_header.items()):
        failures.append("content.core.atlas-challenge-design: count header drift")


def _check_design_rules(design: dict[str, Any], failures: list[str]) -> None:
    rules = design.get("design_rules", {})
    expected = {
        "source_of_truth": "modular_aces_sdl_only",
        "agent_compatibility": "manual_and_participant_owned_agents",
        "verification_profile": "pre_playtest_one_participant_pass_representative_negative_one_scoped_reset",
        "repeated_trials": "only_for_observed_stochastic_defects",
    }
    if any(rules.get(field) != value for field, value in expected.items()):
        failures.append("content.core.atlas-challenge-design: design or pragmatic verification policy drift")
    inherited = design.get("inherited_contracts", {})
    full_content = inherited.get("full_content_capture", {})
    reset = inherited.get("reset", {})
    proof_fields = set(inherited.get("proof_join_fields", []))
    if (
        set(full_content.get("signals", [])) != REQUIRED_RESEARCH_SIGNALS
        or full_content.get("mode") != "independently_selectable"
        or reset.get("verification") != "one_scoped_reset_and_participant_replay_before_playtest"
        or not {"participant", "range_instance", "challenge_id", "reset_generation", "event_id", "trace_id"} <= proof_fields
    ):
        failures.append("content.core.atlas-challenge-design: inherited proof, reset, or research capture drift")


def _bundle_selection(
    bundle: dict[str, Any],
    items: dict[str, dict[str, Any]],
    failures: list[str],
) -> set[str]:
    bundle_id = bundle.get("bundle_id")
    if bundle.get("selection") == "all_except":
        excluded = bundle.get("excluded_challenges", [])
        if not isinstance(excluded, list) or not set(excluded) <= set(items):
            failures.append(f"ATLAS event bundle {bundle_id}: invalid exclusions")
            return set()
        selected = set(items) - set(excluded)
    elif bundle.get("selection") == "dependency_closure_of_seeds":
        seeds = bundle.get("seed_challenges", [])
        if not isinstance(seeds, list) or not seeds or not set(seeds) <= set(items):
            failures.append(f"ATLAS event bundle {bundle_id}: invalid seeds")
            return set()
        selected = set()
        stack = list(seeds)
        while stack:
            challenge_id = stack.pop()
            if challenge_id in selected:
                continue
            selected.add(challenge_id)
            stack.extend(items[challenge_id].get("prerequisites", []))
    else:
        failures.append(f"ATLAS event bundle {bundle_id}: invalid selection policy")
        return set()
    if any(not set(items[challenge_id].get("prerequisites", [])) <= selected for challenge_id in selected):
        failures.append(f"ATLAS event bundle {bundle_id}: selection is not dependency closed")
    return selected


def _check_event_bundle_designs(
    design: dict[str, Any],
    rows: dict[str, dict[str, Any]],
    challenges: dict[str, dict[str, Any]],
    failures: list[str],
) -> None:
    bundles = _index(design.get("event_bundle_designs", []), "bundle_id", "ACES ATLAS event bundles", failures)
    if set(bundles) != REQUIRED_BUNDLES:
        failures.append("content.core.atlas-challenge-design: five named event bundles required")
    items = dict(challenges)
    items.update(rows)
    for bundle_id, bundle in bundles.items():
        selected = _bundle_selection(bundle, items, failures)
        minutes = sum(
            int(items[key].get("target_minutes", items[key].get("minutes", {}).get("target", 0)))
            for key in selected
        )
        difficulty = Counter(items[key].get("difficulty") for key in selected)
        if (
            bundle.get("expected_challenges") != len(selected)
            or bundle.get("target_stock_minutes") != minutes
            or Counter(bundle.get("difficulty", {})) != difficulty
        ):
            failures.append(f"ATLAS event bundle {bundle_id}: count, time, or difficulty drift")
        if not isinstance(bundle.get("intent"), str) or not bundle["intent"].strip():
            failures.append(f"ATLAS event bundle {bundle_id}: intent required")


def _check_atlas_design(
    design: dict[str, Any],
    atlas_rows: dict[str, dict[str, Any]],
    challenges: dict[str, dict[str, Any]],
    failures: list[str],
) -> None:
    technique_steps = {key: str(row.get("challenge_step")) for key, row in atlas_rows.items()}
    planned = {key for key, row in atlas_rows.items() if row.get("coverage_status") == "planned"}
    implemented = {
        key for key, row in atlas_rows.items()
        if row.get("coverage_status") == "implemented"
    }
    rows = _index(design.get("challenge_designs", []), "challenge_id", "ACES ATLAS challenge design", failures)
    extensions = design.get("existing_receipt_extensions", [])
    for row in rows.values():
        _check_design_row(
            row, planned, implemented, technique_steps, failures,
        )
    for challenge_id in set(rows) & set(challenges):
        design_row = rows[challenge_id]
        challenge = challenges[challenge_id]
        implementation = challenge.get("implementation_evidence", {})
        minutes = design_row.get("minutes", {})
        if (
            design_row.get("implementation_status") != challenge.get("implementation_status")
            or design_row.get("title") != challenge.get("title")
            or design_row.get("difficulty") != challenge.get("difficulty")
            or design_row.get("points") != challenge.get("points")
            or design_row.get("prerequisites") != challenge.get("prerequisites")
            or minutes.get("min") != challenge.get("min_minutes")
            or minutes.get("target") != challenge.get("target_minutes")
            or minutes.get("max") != challenge.get("max_minutes")
            or design_row.get("techniques") != implementation.get("primary_atlas_techniques")
        ):
            failures.append(f"ATLAS challenge design {challenge_id}: realized contract drift")

    assigned: list[str] = [
        item
        for row in rows.values()
        for item in row.get("techniques", [])
        if item in planned
    ]
    assigned.extend(_receipt_extension_assignments(extensions, planned, challenges, failures))
    counts = Counter(assigned)
    if set(counts) != planned or any(value != 1 for value in counts.values()):
        failures.append("content.core.atlas-challenge-design: every planned technique must have exactly one design binding")
    _check_design_graph(rows, challenges, failures)
    _check_design_distribution(design, rows, challenges, atlas_rows, failures)
    _check_design_rules(design, failures)
    _check_event_bundle_designs(design, rows, challenges, failures)


def _check_atlas_row(technique_id: str, row: dict[str, Any],
                     expected: dict[str, set[str]] | None, root: Path,
                     failures: list[str]) -> None:
    implementation = row.get("implementation")
    if expected is None:
        if row.get("coverage_status") != "planned" or row.get("relationship") != "planned_variant" or implementation not in (None, {}):
            failures.append(f"ATLAS technique {technique_id}: planned row claims implementation")
        return
    if row.get("coverage_status") != "implemented" or row.get("relationship") != "implemented_primary" or not isinstance(implementation, dict):
        failures.append(f"ATLAS technique {technique_id}: missing implemented binding")
        return
    if set(implementation.get("challenge_ids", [])) != expected["challenge_ids"] or set(implementation.get("evidence", [])) != expected["evidence"]:
        failures.append(f"ATLAS technique {technique_id}: challenge/evidence binding drift")
    manual = implementation.get("manual_evidence")
    manual_paths = {manual} if isinstance(manual, str) else set(manual or [])
    if (
        expected["manual"] != manual_paths
        or any(not isinstance(path, str) or not (root / path).is_file() for path in manual_paths)
    ):
        failures.append(f"ATLAS technique {technique_id}: missing manual evidence")


def _check_atlas(atlas: dict[str, Any], challenges: dict[str, dict[str, Any]],
                 root: Path, failures: list[str]) -> None:
    rows = _index(atlas.get("technique_catalog", []), "id", "ACES ATLAS catalog", failures)
    _check_atlas_header(rows, atlas.get("experience_contract", {}), failures)
    implemented = _implemented_techniques(challenges)
    missing_implemented = sorted(set(implemented) - set(rows))
    if missing_implemented:
        failures.append(
            "ATLAS implementation references missing techniques "
            f"{missing_implemented}"
        )
    for technique_id, row in rows.items():
        _check_atlas_row(technique_id, row, implemented.get(technique_id), root, failures)


def validate_pack(root: str | None = None) -> list[str]:
    pack = Path(root or PACK_ROOT).resolve()
    failures: list[str] = []
    try:
        scenario = load_scenario(pack)
        challenges = challenge_contracts(pack)
        outcomes = oracle_projection(pack)
        telemetry = telemetry_projection(pack)
        research = research_telemetry_contract(pack)
        atlas = atlas_technique_catalog(pack)
        design = atlas_challenge_design(pack)
        implementation = implementation_projection(pack)
    except (OSError, KeyError, TypeError, ValueError) as error:
        return [f"{SDL_PATH}: cannot extract ACES proof contracts: {error}"]
    _check_oracle(outcomes, telemetry, failures)
    _check_event_sources(scenario, telemetry, failures)
    outcome_rows = {row["id"]: row for row in outcomes["outcomes"]}
    _check_flag_layer(challenges, outcome_rows, pack, failures)
    _check_research(research, scenario, pack, failures)
    _check_atlas(atlas, challenges, pack, failures)
    atlas_rows = _index(atlas.get("technique_catalog", []), "id", "ACES ATLAS catalog design join", failures)
    _check_atlas_design(design, atlas_rows, challenges, failures)
    if len(implementation["realized_items"]) != 134:
        failures.append("ACES implementation evidence must cover all 134 realized challenges")
    return failures


def main(argv: list[str] | None = None) -> int:
    if (argv if argv is not None else sys.argv[1:]) != ["validate"]:
        print("usage: validate_oracle.py validate", file=sys.stderr)
        return 2
    failures = validate_pack()
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1
    print("[ok] ACES-derived proof, CTFd, telemetry, research, and ATLAS contracts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
