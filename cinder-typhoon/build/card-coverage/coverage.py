#!/usr/bin/env python3
"""Generate and validate the operator-only 240-card coverage registry."""

from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
REGISTRY_PATH = HERE / "registry.json"
DELIVERY_CATALOG = ROOT / "challenges" / "challenges.yaml"
CATALOG_MODULE_PATH = ROOT / "challenges" / "catalog.py"
DEPENDENCIES = ROOT / "docs" / "design" / "challenge-dependencies.json"
OPERATIONS = ROOT / "sdl" / "modules" / "operations"
BRIEFS = ROOT / "docs" / "design" / "challenges"
PHASES = {"T": "training", "K": "keplerops", "W": "arwc"}
SUITES = {
    phase: ROOT / "build" / phase / "tests" / "test_known_solution_live.py"
    for phase in PHASES.values()
}
CARD = re.compile(r"[TKW]\d{2}\.\d")
SEMANTIC_CARD = re.compile(r"urn:cinder-typhoon:fact:([TKW]\d{2}\.\d)")
CATALOG_SPEC = importlib.util.spec_from_file_location(
    "cinder_card_delivery_catalog", CATALOG_MODULE_PATH,
)
if CATALOG_SPEC is None or CATALOG_SPEC.loader is None:
    raise RuntimeError("cannot load challenge catalog module")
catalog_module = importlib.util.module_from_spec(CATALOG_SPEC)
CATALOG_SPEC.loader.exec_module(catalog_module)
REQUEST_CALLS = {
    "request", "get_text", "get_json", "get_bytes", "curl", "curl_json",
    "post_json_route", "cbor_request", "negotiate",
}
ANALYSIS_CALLS = {
    "fromhex", "loads", "search", "findall", "fullmatch", "sha256", "sha512",
    "sorted", "sum", "min", "max", "int", "float", "bytes", "bytearray",
    "inside", "rowan", "rowan_bytes", "check_output", "run", "bolt_exchange",
}
# A reviewed read-only card belongs here only when interpreting or correlating
# the record is itself the achievement. The rationale is emitted in the private
# registry; an endpoint read alone is never enough.
READ_ONLY_REVIEWS: dict[str, str] = {
    "K06.2": (
        "The achievement compares an authorized private package view with a denied "
        "release-administration view, demonstrating the recovered credential's exact boundary."
    ),
    "K20.1": (
        "The read is performed through the participant-created SPNEGO delegated context and "
        "correlates the returned service relation with the independently recovered archive subject."
    ),
    "T04.1": (
        "The achievement is the discrepancy analysis between requested and independently observed "
        "volume, including the unit and quality binding; merely fetching the capture is insufficient."
    ),
}


class CoverageError(ValueError):
    """The registry or one of its authoritative sources is inconsistent."""


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def authored_sdl_cards() -> dict[str, Path]:
    cards: dict[str, Path] = {}
    for path in sorted(OPERATIONS.glob("*.yaml")):
        for card_id in SEMANTIC_CARD.findall(path.read_text(encoding="utf-8")):
            if card_id in cards:
                raise CoverageError(f"duplicate SDL semantic card: {card_id}")
            cards[card_id] = path
    return cards


def authored_brief_cards() -> dict[str, Path]:
    cards: dict[str, Path] = {}
    for path in sorted(BRIEFS.glob("[TKW][0-9][0-9]/[TKW][0-9][0-9].[0-9].md")):
        card_id = path.stem
        if card_id in cards:
            raise CoverageError(f"duplicate challenge brief: {card_id}")
        cards[card_id] = path
    return cards


def dependency_cards() -> dict[str, list[list[str]]]:
    value = json.loads(DEPENDENCIES.read_text(encoding="utf-8"))
    if value.get("schema_version") != 1 or not isinstance(value.get("challenges"), dict):
        raise CoverageError("challenge dependency ledger is invalid")
    result: dict[str, list[list[str]]] = {}
    for card_id, entry in value["challenges"].items():
        alternatives = entry.get("requires_any") if isinstance(entry, dict) else None
        if not CARD.fullmatch(card_id) or not isinstance(alternatives, list) or not alternatives:
            raise CoverageError(f"invalid dependency entry: {card_id}")
        if not all(
            isinstance(option, list) and option
            and all(isinstance(item, str) and item for item in option)
            for option in alternatives
        ):
            raise CoverageError(f"invalid prerequisite alternatives: {card_id}")
        result[card_id] = alternatives
    return result


def delivery_catalog(path: Path = DELIVERY_CATALOG) -> dict[str, Any]:
    try:
        return catalog_module.load_catalog(
            path,
            require_current=path.resolve() == DELIVERY_CATALOG.resolve(),
        )
    except (OSError, ValueError) as error:
        raise CoverageError(f"participant delivery catalog is invalid: {error}") from error


def delivered_cards(path: Path = DELIVERY_CATALOG) -> set[str]:
    value = delivery_catalog(path)
    cards = [card["id"] for card in catalog_module.catalog_cards(value)]
    if len(cards) != len(set(cards)):
        raise CoverageError("participant delivery catalog contains duplicate card IDs")
    invalid = sorted(card_id for card_id in cards if not CARD.fullmatch(card_id))
    if invalid:
        raise CoverageError(f"participant delivery catalog contains invalid card IDs: {invalid}")
    return set(cards)


def delivery_metadata(path: Path = DELIVERY_CATALOG) -> dict[str, Any]:
    try:
        return catalog_module.catalog_metadata(
            path,
            require_current=path.resolve() == DELIVERY_CATALOG.resolve(),
        )
    except (OSError, ValueError) as error:
        raise CoverageError(f"participant delivery catalog metadata is invalid: {error}") from error


def call_name(call: ast.Call) -> str:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return "<call>"


def mutating_request(call: ast.Call) -> bool:
    name = call_name(call)
    if name in {"post_json_route", "cbor_request"}:
        return True
    if name == "request":
        for keyword in call.keywords:
            if keyword.arg == "method" and isinstance(keyword.value, ast.Constant):
                return str(keyword.value.value).upper() != "GET"
        return False
    if name in {"curl", "curl_json", "negotiate"}:
        literal_args = [
            str(argument.value)
            for argument in call.args
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str)
        ]
        if any(value in {"-d", "--data", "--data-binary", "--data-raw", "-F", "--form"} for value in literal_args):
            return True
        for index, value in enumerate(literal_args[:-1]):
            if value == "-X" and literal_args[index + 1].upper() != "GET":
                return True
    return False


def simple_read_candidate(block: ast.With) -> bool:
    def local_walk(node: ast.AST):
        """Walk a card block without counting a nested helper's implementation."""
        yield node
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            return
        for child in ast.iter_child_nodes(node):
            yield from local_walk(child)

    calls = [
        node for statement in block.body for node in local_walk(statement)
        if isinstance(node, ast.Call)
    ]
    requests = [call for call in calls if call_name(call) in REQUEST_CALLS]
    if not requests or any(mutating_request(call) for call in requests):
        return False
    if any(call_name(call) in ANALYSIS_CALLS for call in calls):
        return False
    analysis_nodes = (
        ast.For, ast.While, ast.ListComp, ast.SetComp, ast.DictComp,
        ast.GeneratorExp, ast.BinOp, ast.BoolOp,
    )
    return not any(
        isinstance(node, analysis_nodes)
        for statement in block.body
        for node in local_walk(statement)
    )


def subtest_inventory() -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for phase, path in SUITES.items():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for method in (
            node for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
        ):
            for block in (node for node in ast.walk(method) if isinstance(node, ast.With)):
                labels: list[str] = []
                for item in block.items:
                    context = item.context_expr
                    if not (
                        isinstance(context, ast.Call)
                        and isinstance(context.func, ast.Attribute)
                        and context.func.attr == "subTest"
                    ):
                        continue
                    for keyword in context.keywords:
                        if (
                            keyword.arg in {"card", "challenge"}
                            and isinstance(keyword.value, ast.Constant)
                            and isinstance(keyword.value.value, str)
                        ):
                            labels.append(keyword.value.value)
                for label in labels:
                    ids = CARD.findall(label)
                    assertions = sorted(
                        {
                            (node.lineno, call_name(node))
                            for statement in block.body
                            for node in ast.walk(statement)
                            if isinstance(node, ast.Call)
                            and isinstance(node.func, ast.Attribute)
                            and node.func.attr.startswith("assert")
                        }
                    )
                    for card_id in ids:
                        result[card_id].append({
                            "phase": phase,
                            "suite": relative(path),
                            "test_method": method.name,
                            "subtest": label,
                            "line": block.lineno,
                            "combined_card_ids": ids,
                            "assertions": [
                                {"line": line, "method": name}
                                for line, name in assertions
                            ],
                            "simple_read_candidate": simple_read_candidate(block),
                        })
    return dict(result)


def heading_section(source: str, heading: str) -> str:
    match = re.search(
        rf"(?ms)^## {re.escape(heading)}\s*\n(.*?)(?=^## |\Z)", source,
    )
    if not match:
        raise CoverageError(f"brief is missing section: {heading}")
    value = match.group(1).strip()
    if not value:
        raise CoverageError(f"brief section is empty: {heading}")
    return " ".join(value.split())


def primary_work(source: str) -> str:
    match = re.search(r"(?m)^\| Primary work \| ([^|]+) \|$", source)
    if not match:
        raise CoverageError("brief is missing Primary work")
    return match.group(1).strip()


def black_box_entry(card_id: str, inventory: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    matches = inventory.get(card_id, [])
    if not matches:
        return {"status": "missing", "assertion_name": None, "matches": []}
    status = "complete"
    if len(matches) != 1:
        status = "duplicate"
    elif len(matches[0]["combined_card_ids"]) != 1:
        status = "combined"
    elif not matches[0]["assertions"]:
        status = "missing_assertion"
    match = matches[0]
    return {
        "status": status,
        "assertion_name": f"{match['test_method']}::{card_id}",
        "matches": matches,
    }


def build_registry() -> dict[str, Any]:
    try:
        import yaml
    except ImportError as error:
        raise CoverageError("PyYAML is required only to regenerate the registry") from error

    sdl_cards = authored_sdl_cards()
    briefs = authored_brief_cards()
    dependencies = dependency_cards()
    if set(sdl_cards) != set(briefs) or set(sdl_cards) != set(dependencies):
        raise CoverageError("SDL, brief and dependency card sets disagree")
    tests = subtest_inventory()
    cards: dict[str, Any] = {}
    for card_id in sorted(sdl_cards):
        operation_path = sdl_cards[card_id]
        operation = yaml.safe_load(operation_path.read_text(encoding="utf-8"))
        objective_key = None
        proposition = None
        for key, candidate in operation.get("propositions", {}).items():
            semantic_ref = candidate.get("predicate", {}).get("semantic_ref")
            if semantic_ref == f"urn:cinder-typhoon:fact:{card_id}":
                objective_key, proposition = key, candidate
                break
        if objective_key is None or proposition is None:
            raise CoverageError(f"cannot bind SDL contract for {card_id}")
        objective = operation["objectives"][objective_key]
        evidence = operation["evidence_requirements"][objective_key]
        success = objective.get("success", {}).get("assertions", [])
        if not success:
            raise CoverageError(f"objective has no completion assertion: {card_id}")
        brief_path = briefs[card_id]
        brief = brief_path.read_text(encoding="utf-8")
        accepting_components = objective.get("targets", [])
        evidence_sources = evidence.get("source_refs", [])
        observation = evidence.get("observation_demand", {})
        evaluator_contract = (
            evidence.get("boundary_kind") == "assertion_evaluation"
            and evidence.get("artifact_role") == "proposition_truth_evidence"
            and observation.get("required") is True
            and observation.get("basis") == "observed"
            and bool(evidence_sources)
        )
        owner_status = (
            "declared_independent_evidence_owner"
            if (
                evaluator_contract
                and set(evidence_sources).isdisjoint(accepting_components)
            )
            else "accepting_component_overlap"
        )
        cards[card_id] = {
            "phase": PHASES[card_id[0]],
            "title": objective["name"],
            "primary_work": primary_work(brief),
            "participant_work": heading_section(brief, "Challenge description — player-facing"),
            "completion_outcome": proposition["description"],
            "completion_evaluator": {
                "assertions": [f"{operation_path.stem}.{name}" for name in success],
                "evidence_requirement": f"{operation_path.stem}.{objective_key}",
                "observation_rule": evidence["observation_demand"]["rule_id"],
            },
            "accepting_components": accepting_components,
            "evidence_owners": evidence_sources,
            "evidence_ownership_status": owner_status,
            "black_box_assertion": black_box_entry(card_id, tests),
            "read_only_review": {
                "status": (
                    "substantive_interpretation"
                    if tests.get(card_id, [{}])[0].get("simple_read_candidate")
                    and card_id in READ_ONLY_REVIEWS
                    else "unresolved_simple_read"
                    if tests.get(card_id, [{}])[0].get("simple_read_candidate")
                    else "not_simple_read"
                ),
                "rationale": READ_ONLY_REVIEWS.get(card_id),
            },
            "prerequisite_sets": dependencies[card_id],
            "deletion_test": {
                "removed_capability": heading_section(brief, "Story purpose"),
                "removed_outcome": heading_section(brief, "Completion and downstream use"),
                "status": "documented",
            },
            "sources": {
                "operation": relative(operation_path),
                "operation_sha256": file_sha256(operation_path),
                "brief": relative(brief_path),
                "brief_sha256": file_sha256(brief_path),
            },
        }
    return {
        "schema_version": 2,
        "authored_card_source": "SDL semantic references, challenge briefs and dependency ledger",
        "delivery_catalog": delivery_metadata(),
        "cards": cards,
    }


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CoverageError(f"card registry cannot be read: {error}") from error
    validate_registry(value)
    return value


def validate_registry(value: Any) -> None:
    if not isinstance(value, dict) or set(value) != {
        "schema_version", "authored_card_source", "delivery_catalog", "cards",
    }:
        raise CoverageError("card registry has invalid top-level fields")
    if value["schema_version"] != 2:
        raise CoverageError("card registry schema_version must be 2")
    if value["delivery_catalog"] != delivery_metadata():
        raise CoverageError("delivery catalog changed without registry regeneration and review")
    cards = value["cards"]
    if not isinstance(cards, dict):
        raise CoverageError("card registry cards must be an object")
    sdl_cards = authored_sdl_cards()
    briefs = authored_brief_cards()
    dependencies = dependency_cards()
    expected = set(sdl_cards)
    if expected != set(briefs) or expected != set(dependencies):
        raise CoverageError("authoritative authored card sources disagree")
    if set(cards) != expected:
        missing = sorted(expected - set(cards))
        extra = sorted(set(cards) - expected)
        raise CoverageError(f"registry card IDs changed; missing={missing}, extra={extra}")
    tests = subtest_inventory()
    for card_id, entry in cards.items():
        required = {
            "phase", "title", "primary_work", "participant_work", "completion_outcome",
            "completion_evaluator", "accepting_components", "evidence_owners",
            "evidence_ownership_status", "black_box_assertion", "read_only_review", "prerequisite_sets",
            "deletion_test", "sources",
        }
        if not isinstance(entry, dict) or set(entry) != required:
            raise CoverageError(f"{card_id}: invalid registry fields")
        if entry["phase"] != PHASES[card_id[0]]:
            raise CoverageError(f"{card_id}: invalid phase")
        for field in ("title", "primary_work", "participant_work", "completion_outcome"):
            if not isinstance(entry[field], str) or not entry[field].strip():
                raise CoverageError(f"{card_id}: {field} is required")
        evaluator = entry["completion_evaluator"]
        if not isinstance(evaluator, dict) or set(evaluator) != {
            "assertions", "evidence_requirement", "observation_rule",
        }:
            raise CoverageError(f"{card_id}: invalid completion evaluator")
        if not isinstance(evaluator["assertions"], list) or not evaluator["assertions"]:
            raise CoverageError(f"{card_id}: completion assertion is required")
        if not all(isinstance(item, str) and item for item in evaluator.values() if not isinstance(item, list)):
            raise CoverageError(f"{card_id}: invalid evaluator value")
        for field in ("accepting_components", "evidence_owners"):
            if not isinstance(entry[field], list) or not entry[field] or not all(
                isinstance(item, str) and item for item in entry[field]
            ):
                raise CoverageError(f"{card_id}: {field} must name components")
        if entry["evidence_ownership_status"] not in {
            "declared_independent_evidence_owner", "accepting_component_overlap",
        }:
            raise CoverageError(f"{card_id}: evidence ownership status is inaccurate")
        if entry["black_box_assertion"] != black_box_entry(card_id, tests):
            raise CoverageError(f"{card_id}: black-box assertion inventory changed")
        read_only = entry["read_only_review"]
        if not isinstance(read_only, dict) or set(read_only) != {"status", "rationale"}:
            raise CoverageError(f"{card_id}: invalid read-only review")
        matches = tests.get(card_id, [])
        candidate = len(matches) == 1 and matches[0]["simple_read_candidate"]
        expected_read_status = (
            "substantive_interpretation" if candidate and card_id in READ_ONLY_REVIEWS
            else "unresolved_simple_read" if candidate else "not_simple_read"
        )
        if read_only["status"] != expected_read_status or read_only["rationale"] != READ_ONLY_REVIEWS.get(card_id):
            raise CoverageError(f"{card_id}: read-only review changed")
        if entry["prerequisite_sets"] != dependencies[card_id]:
            raise CoverageError(f"{card_id}: prerequisite set changed")
        deletion = entry["deletion_test"]
        if not isinstance(deletion, dict) or set(deletion) != {
            "removed_capability", "removed_outcome", "status",
        } or deletion["status"] != "documented" or not all(
            isinstance(deletion[key], str) and deletion[key].strip()
            for key in ("removed_capability", "removed_outcome")
        ):
            raise CoverageError(f"{card_id}: deletion test is incomplete")
        sources = entry["sources"]
        if not isinstance(sources, dict) or set(sources) != {
            "operation", "operation_sha256", "brief", "brief_sha256",
        }:
            raise CoverageError(f"{card_id}: invalid source record")
        expected_paths = (sdl_cards[card_id], briefs[card_id])
        if sources["operation"] != relative(expected_paths[0]) or sources["brief"] != relative(expected_paths[1]):
            raise CoverageError(f"{card_id}: source path changed")
        if sources["operation_sha256"] != file_sha256(expected_paths[0]) or sources["brief_sha256"] != file_sha256(expected_paths[1]):
            raise CoverageError(f"{card_id}: authored contract changed without registry review")


def build_report(registry: dict[str, Any]) -> dict[str, Any]:
    delivery = delivered_cards()
    cards = registry["cards"]
    expected = set(cards)
    findings: list[dict[str, Any]] = []
    missing_delivery = sorted(expected - delivery)
    extra_delivery = sorted(delivery - expected)
    if missing_delivery or extra_delivery:
        findings.append({
            "kind": "delivery_catalog_mismatch",
            "issue": 268,
            "missing_count": len(missing_delivery),
            "extra_count": len(extra_delivery),
            "missing": missing_delivery,
            "extra": extra_delivery,
        })
    black_box_counts = Counter(
        entry["black_box_assertion"]["status"] for entry in cards.values()
    )
    for card_id, entry in cards.items():
        assertion_status = entry["black_box_assertion"]["status"]
        if assertion_status != "complete":
            findings.append({
                "kind": "black_box_assertion",
                "card_id": card_id,
                "status": assertion_status,
                "assertion_name": entry["black_box_assertion"]["assertion_name"],
            })
        if entry["evidence_ownership_status"] != "declared_independent_evidence_owner":
            findings.append({
                "kind": "evidence_owner_not_independent",
                "card_id": card_id,
                "accepting_components": entry["accepting_components"],
                "evidence_owners": entry["evidence_owners"],
            })
        if entry["read_only_review"]["status"] == "unresolved_simple_read":
            findings.append({
                "kind": "simple_read_without_substantive_interpretation",
                "card_id": card_id,
                "assertion_name": entry["black_box_assertion"]["assertion_name"],
            })
    card_reports = [
        {
            "card_id": card_id,
            "phase": entry["phase"],
            "black_box_assertion": entry["black_box_assertion"]["assertion_name"],
            "black_box_status": entry["black_box_assertion"]["status"],
            "evidence_ownership_status": entry["evidence_ownership_status"],
            "read_only_review_status": entry["read_only_review"]["status"],
            "deletion_test_status": entry["deletion_test"]["status"],
        }
        for card_id, entry in cards.items()
    ]
    return {
        "schema_version": 1,
        "report_kind": "card-coverage",
        "overall_status": "complete" if not findings else "unresolved",
        "summary": {
            "registry_card_count": len(cards),
            "delivered_card_count": len(delivery),
            "missing_delivery_card_count": len(missing_delivery),
            "extra_delivery_card_count": len(extra_delivery),
            "complete_black_box_card_count": black_box_counts["complete"],
            "incomplete_black_box_card_count": len(cards) - black_box_counts["complete"],
            "independent_evidence_card_count": sum(
                entry["evidence_ownership_status"] == "declared_independent_evidence_owner"
                for entry in cards.values()
            ),
            "unresolved_simple_read_card_count": sum(
                entry["read_only_review"]["status"] == "unresolved_simple_read"
                for entry in cards.values()
            ),
            "documented_deletion_test_count": sum(
                entry["deletion_test"]["status"] == "documented"
                for entry in cards.values()
            ),
        },
        "findings": findings,
        "cards": card_reports,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=REGISTRY_PATH)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--write-registry", action="store_true")
    parser.add_argument("--require-complete", action="store_true")
    arguments = parser.parse_args()
    if arguments.write_registry:
        value = build_registry()
        arguments.registry.parent.mkdir(parents=True, exist_ok=True)
        arguments.registry.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8",
        )
    registry = load_registry(arguments.registry)
    report = build_report(registry)
    serialized = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(serialized, encoding="utf-8")
    else:
        print(serialized, end="")
    if arguments.require_complete and report["overall_status"] != "complete":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
