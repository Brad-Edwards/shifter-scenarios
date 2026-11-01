#!/usr/bin/env python3
"""Generate and validate the operator-only 240-card coverage registry."""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
REGISTRY_PATH = HERE / "registry.json"
DELIVERY_CATALOG = ROOT / "challenges" / "challenges.yaml"
CATALOG_MODULE_PATH = ROOT / "challenges" / "catalog.py"
EVENT_IMPORTER_PATH = ROOT / "ctfd" / "import_catalog.py"
DEPENDENCIES = ROOT / "docs" / "design" / "challenge-dependencies.json"
READ_ONLY_REVIEWS_PATH = HERE / "read-only-reviews.json"
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
EVENT_IMPORTER_SPEC = importlib.util.spec_from_file_location(
    "cinder_card_coverage_event_importer", EVENT_IMPORTER_PATH,
)
if EVENT_IMPORTER_SPEC is None or EVENT_IMPORTER_SPEC.loader is None:
    raise RuntimeError("cannot load challenge event importer")
event_importer = importlib.util.module_from_spec(EVENT_IMPORTER_SPEC)
EVENT_IMPORTER_SPEC.loader.exec_module(event_importer)
SCORER_OWNER = "shifter.range-owned.cinder-scorer"
SCORER_ORIGIN = "https://cinder-scorer.coverage.invalid"
REQUEST_CALLS = {
    "request", "get_text", "get_json", "get_bytes", "curl", "curl_json",
    "post_json_route", "cbor_request", "negotiate",
}
ANALYSIS_CALLS = {
    "fromhex", "loads", "search", "findall", "fullmatch", "sha256", "sha512",
    "sorted", "sum", "min", "max", "int", "float", "bytes", "bytearray",
    "inside", "rowan", "rowan_bytes", "check_output", "run", "bolt_exchange",
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


def read_only_reviews(path: Path = READ_ONLY_REVIEWS_PATH) -> dict[str, str]:
    """Load the explicit review of syntax-simple participant-boundary reads."""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CoverageError(f"read-only review ledger cannot be read: {error}") from error
    if not isinstance(value, dict) or set(value) != {"schema_version", "reviews"}:
        raise CoverageError("read-only review ledger has invalid top-level fields")
    if value["schema_version"] != 1 or not isinstance(value["reviews"], dict):
        raise CoverageError("read-only review ledger schema is invalid")
    reviews: dict[str, str] = {}
    for card_id, rationale in value["reviews"].items():
        if not CARD.fullmatch(card_id):
            raise CoverageError(f"read-only review ledger has invalid card ID: {card_id}")
        if not isinstance(rationale, str) or len(rationale.split()) < 12:
            raise CoverageError(f"{card_id}: read-only review rationale is not substantive")
        reviews[card_id] = " ".join(rationale.split())
    return reviews


def scorer_bindings() -> dict[str, dict[str, str]]:
    """Return the actual native-delivery binding for each independent evaluator."""

    catalog = delivery_catalog()
    try:
        bundle = event_importer.build_event_bundle(catalog, scorer_origin=SCORER_ORIGIN)
        event_importer.validate_projection(catalog, bundle)
    except (OSError, ValueError) as error:
        raise CoverageError(f"native scorer projection is invalid: {error}") from error
    bindings: dict[str, dict[str, str]] = {}
    for row in bundle["challenges"]:
        card_id = str(row["id"]).upper()
        flags = row.get("flags", [])
        if len(flags) != 1:
            raise CoverageError(f"{card_id}: expected exactly one range scorer binding")
        flag = flags[0]
        parsed = urlsplit(str(flag.get("url", "")))
        headers = flag.get("headers", {})
        if (
            parsed.scheme != "https"
            or parsed.netloc != urlsplit(SCORER_ORIGIN).netloc
            or flag.get("method") != "POST"
            or headers.get("X-Cinder-Catalog-Revision") != catalog["revision"]
        ):
            raise CoverageError(f"{card_id}: range scorer binding is not revision-bound HTTPS")
        bindings[card_id] = {
            "owner": SCORER_OWNER,
            "path": parsed.path,
            "catalog_revision": catalog["revision"],
        }
    if set(bindings) != delivered_cards():
        raise CoverageError("native scorer bindings do not exactly cover delivered cards")
    return bindings


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
        return any(
            keyword.arg == "body"
            and not (isinstance(keyword.value, ast.Constant) and keyword.value.value is None)
            for keyword in call.keywords
        )
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
                    requests = [
                        node
                        for statement in block.body
                        for node in ast.walk(statement)
                        if isinstance(node, ast.Call) and call_name(node) in REQUEST_CALLS
                    ]
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
                            "state_change_candidate": any(
                                mutating_request(request) for request in requests
                            ),
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
    reviews = read_only_reviews()
    simple_reads = {
        card_id for card_id, matches in tests.items()
        if len(matches) == 1 and matches[0]["simple_read_candidate"]
    }
    if set(reviews) != simple_reads:
        raise CoverageError(
            "read-only review ledger changed; "
            f"missing={sorted(simple_reads - set(reviews))}, "
            f"extra={sorted(set(reviews) - simple_reads)}"
        )
    bindings = scorer_bindings()
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
            and observation.get("collection") == "require"
            and evidence.get("integrity") in {"checksum", "signed"}
            and bool(evidence_sources)
        )
        binding = bindings.get(card_id, {})
        owner_status = (
            "independent_range_evaluator"
            if (
                evaluator_contract
                and binding.get("owner") == SCORER_OWNER
                and SCORER_OWNER not in accepting_components
            )
            else "incomplete_evaluator_contract"
        )
        cards[card_id] = {
            "phase": PHASES[card_id[0]],
            "completion_class": (
                "state_change"
                if tests.get(card_id, [{}])[0].get("state_change_candidate")
                else "read_or_analysis"
            ),
            "title": objective["name"],
            "primary_work": primary_work(brief),
            "participant_work": heading_section(brief, "Challenge description — player-facing"),
            "completion_outcome": proposition["description"],
            "completion_evaluator": {
                "assertions": [f"{operation_path.stem}.{name}" for name in success],
                "evidence_requirement": f"{operation_path.stem}.{objective_key}",
                "observation_rule": evidence["observation_demand"]["rule_id"],
                "owner": binding.get("owner"),
                "scorer_path": binding.get("path"),
                "catalog_revision": binding.get("catalog_revision"),
            },
            "accepting_components": accepting_components,
            "evidence_sources": evidence_sources,
            "evidence_contract": {
                "basis": observation.get("basis"),
                "collection": observation.get("collection"),
                "integrity": evidence.get("integrity"),
                "participant_can_mark_complete": False,
                "accepting_component_can_mark_complete": False,
            },
            "evidence_ownership_status": owner_status,
            "black_box_assertion": black_box_entry(card_id, tests),
            "read_only_review": {
                "status": (
                    "substantive_interpretation"
                    if card_id in reviews
                    else "unresolved_simple_read"
                    if tests.get(card_id, [{}])[0].get("simple_read_candidate")
                    else "not_simple_read"
                ),
                "rationale": reviews.get(card_id),
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
        "schema_version": 3,
        "authored_card_source": (
            "SDL semantic references, challenge briefs, dependency ledger, known-solution assertions, "
            "read-only review ledger and delivery catalog"
        ),
        "delivery_catalog": delivery_metadata(),
        "read_only_review_source": {
            "path": relative(READ_ONLY_REVIEWS_PATH),
            "sha256": file_sha256(READ_ONLY_REVIEWS_PATH),
        },
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
        "schema_version", "authored_card_source", "delivery_catalog",
        "read_only_review_source", "cards",
    }:
        raise CoverageError("card registry has invalid top-level fields")
    if value["schema_version"] != 3:
        raise CoverageError("card registry schema_version must be 3")
    if value["delivery_catalog"] != delivery_metadata():
        raise CoverageError("delivery catalog changed without registry regeneration and review")
    expected_review_source = {
        "path": relative(READ_ONLY_REVIEWS_PATH),
        "sha256": file_sha256(READ_ONLY_REVIEWS_PATH),
    }
    if value["read_only_review_source"] != expected_review_source:
        raise CoverageError("read-only review ledger changed without registry regeneration")
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
    reviews = read_only_reviews()
    simple_reads = {
        card_id for card_id, matches in tests.items()
        if len(matches) == 1 and matches[0]["simple_read_candidate"]
    }
    if set(reviews) != simple_reads:
        raise CoverageError(
            "read-only review ledger changed; "
            f"missing={sorted(simple_reads - set(reviews))}, "
            f"extra={sorted(set(reviews) - simple_reads)}"
        )
    bindings = scorer_bindings()
    for card_id, entry in cards.items():
        required = {
            "phase", "completion_class", "title", "primary_work", "participant_work", "completion_outcome",
            "completion_evaluator", "accepting_components", "evidence_sources", "evidence_contract",
            "evidence_ownership_status", "black_box_assertion", "read_only_review", "prerequisite_sets",
            "deletion_test", "sources",
        }
        if not isinstance(entry, dict) or set(entry) != required:
            raise CoverageError(f"{card_id}: invalid registry fields")
        if entry["phase"] != PHASES[card_id[0]]:
            raise CoverageError(f"{card_id}: invalid phase")
        matches = tests.get(card_id, [])
        expected_completion_class = (
            "state_change"
            if len(matches) == 1 and matches[0]["state_change_candidate"]
            else "read_or_analysis"
        )
        if entry["completion_class"] != expected_completion_class:
            raise CoverageError(f"{card_id}: completion class changed")
        for field in ("title", "primary_work", "participant_work", "completion_outcome"):
            if not isinstance(entry[field], str) or not entry[field].strip():
                raise CoverageError(f"{card_id}: {field} is required")
        evaluator = entry["completion_evaluator"]
        if not isinstance(evaluator, dict) or set(evaluator) != {
            "assertions", "evidence_requirement", "observation_rule", "owner",
            "scorer_path", "catalog_revision",
        }:
            raise CoverageError(f"{card_id}: invalid completion evaluator")
        if not isinstance(evaluator["assertions"], list) or not evaluator["assertions"]:
            raise CoverageError(f"{card_id}: completion assertion is required")
        if not all(isinstance(item, str) and item for item in evaluator.values() if not isinstance(item, list)):
            raise CoverageError(f"{card_id}: invalid evaluator value")
        for field in ("accepting_components", "evidence_sources"):
            if not isinstance(entry[field], list) or not entry[field] or not all(
                isinstance(item, str) and item for item in entry[field]
            ):
                raise CoverageError(f"{card_id}: {field} must name components")
        binding = bindings[card_id]
        if (
            evaluator["owner"] != binding["owner"]
            or evaluator["scorer_path"] != binding["path"]
            or evaluator["catalog_revision"] != binding["catalog_revision"]
            or evaluator["owner"] in entry["accepting_components"]
        ):
            raise CoverageError(f"{card_id}: independent completion evaluator changed")
        evidence_contract = entry["evidence_contract"]
        if not isinstance(evidence_contract, dict) or evidence_contract != {
            "basis": "observed",
            "collection": "require",
            "integrity": evidence_contract.get("integrity"),
            "participant_can_mark_complete": False,
            "accepting_component_can_mark_complete": False,
        } or evidence_contract["integrity"] not in {"checksum", "signed"}:
            raise CoverageError(f"{card_id}: evidence non-forgeability contract changed")
        if entry["evidence_ownership_status"] != "independent_range_evaluator":
            raise CoverageError(f"{card_id}: evidence ownership status is inaccurate")
        if entry["black_box_assertion"] != black_box_entry(card_id, tests):
            raise CoverageError(f"{card_id}: black-box assertion inventory changed")
        read_only = entry["read_only_review"]
        if not isinstance(read_only, dict) or set(read_only) != {"status", "rationale"}:
            raise CoverageError(f"{card_id}: invalid read-only review")
        candidate = len(matches) == 1 and matches[0]["simple_read_candidate"]
        expected_read_status = (
            "substantive_interpretation" if candidate and card_id in reviews
            else "unresolved_simple_read" if candidate else "not_simple_read"
        )
        if read_only["status"] != expected_read_status or read_only["rationale"] != reviews.get(card_id):
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
    if value != build_registry():
        raise CoverageError("registry changed from its reviewed generated form")


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
        if entry["evidence_ownership_status"] != "independent_range_evaluator":
            findings.append({
                "kind": "evidence_owner_not_independent",
                "card_id": card_id,
                "accepting_components": entry["accepting_components"],
                "evidence_owner": entry["completion_evaluator"]["owner"],
                "evidence_sources": entry["evidence_sources"],
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
            "completion_class": entry["completion_class"],
            "black_box_assertion": entry["black_box_assertion"]["assertion_name"],
            "black_box_status": entry["black_box_assertion"]["status"],
            "evidence_owner": entry["completion_evaluator"]["owner"],
            "evidence_sources": entry["evidence_sources"],
            "evidence_ownership_status": entry["evidence_ownership_status"],
            "read_only_review_status": entry["read_only_review"]["status"],
            "deletion_test_status": entry["deletion_test"]["status"],
        }
        for card_id, entry in cards.items()
    ]
    operation_reports = []
    for operation_id in sorted({card_id.split(".")[0] for card_id in cards}):
        operation_cards = [
            (card_id, entry) for card_id, entry in cards.items()
            if card_id.split(".")[0] == operation_id
        ]
        owners = sorted({entry["completion_evaluator"]["owner"] for _, entry in operation_cards})
        sources = sorted({source for _, entry in operation_cards for source in entry["evidence_sources"]})
        operation_reports.append({
            "operation_id": operation_id,
            "phase": operation_cards[0][1]["phase"],
            "card_ids": [card_id for card_id, _ in operation_cards],
            "evidence_owners": owners,
            "evidence_sources": sources,
            "status": (
                "complete"
                if all(
                    entry["evidence_ownership_status"] == "independent_range_evaluator"
                    for _, entry in operation_cards
                )
                else "unresolved"
            ),
        })
    return {
        "schema_version": 2,
        "report_kind": "card-coverage",
        "overall_status": "complete" if not findings else "unresolved",
        "summary": {
            "registry_card_count": len(cards),
            "operation_count": len(operation_reports),
            "delivered_card_count": len(delivery),
            "missing_delivery_card_count": len(missing_delivery),
            "extra_delivery_card_count": len(extra_delivery),
            "complete_black_box_card_count": black_box_counts["complete"],
            "incomplete_black_box_card_count": len(cards) - black_box_counts["complete"],
            "independent_evidence_card_count": sum(
                entry["evidence_ownership_status"] == "independent_range_evaluator"
                for entry in cards.values()
            ),
            "state_change_card_count": sum(
                entry["completion_class"] == "state_change"
                for entry in cards.values()
            ),
            "independently_evaluated_state_change_card_count": sum(
                entry["completion_class"] == "state_change"
                and entry["evidence_ownership_status"] == "independent_range_evaluator"
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
        "operations": operation_reports,
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
