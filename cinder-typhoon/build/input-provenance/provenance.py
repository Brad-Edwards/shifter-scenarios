#!/usr/bin/env python3
"""Inventory and report provenance for participant-boundary solution inputs."""

from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
LEDGER_PATH = HERE / "ledger.json"
PHASES = ("training", "keplerops", "arwc")
SUITES = {
    phase: ROOT / "build" / phase / "tests" / "test_known_solution_live.py"
    for phase in PHASES
}
REQUEST_FUNCTIONS = {
    "request", "get_text", "get_json", "curl", "curl_json",
    "post_json_route", "get_bytes", "cbor_request",
}
PROVENANCE_CLASSES = {
    "supplied_starting_surface",
    "normal_interface_or_artifact",
    "earlier_accepted_response",
    "deterministic_transformation",
    "computed_from_participant_visible_inputs",
}
SHA = re.compile(r"^[0-9a-f]{64}$")


class ProvenanceError(ValueError):
    """The ledger or its source inventory is incomplete or inconsistent."""


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def call_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    return None


def normalized(node: ast.AST) -> str:
    """Return a stable representation. It is hashed before entering reports."""
    return ast.dump(node, annotate_fields=True, include_attributes=False)


def request_inventory() -> dict[str, dict[str, dict[str, Any]]]:
    result: dict[str, dict[str, dict[str, Any]]] = {}
    for phase, path in SUITES.items():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        methods: dict[str, dict[str, Any]] = {}
        for class_node in (node for node in tree.body if isinstance(node, ast.ClassDef)):
            for method in (
                node for node in class_node.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name.startswith("test_")
            ):
                calls = sorted(
                    (
                        node for node in ast.walk(method)
                        if isinstance(node, ast.Call) and call_name(node) in REQUEST_FUNCTIONS
                    ),
                    key=lambda node: (node.lineno, node.col_offset),
                )
                if not calls:
                    continue
                call_records = [
                    {
                        "function": call_name(call),
                        "line": call.lineno,
                        "fingerprint": digest(normalized(call)),
                    }
                    for call in calls
                ]
                canonical = json.dumps(
                    [
                        {"function": item["function"], "fingerprint": item["fingerprint"]}
                        for item in call_records
                    ],
                    sort_keys=True, separators=(",", ":"),
                )
                methods[method.name] = {
                    "inventory_sha256": digest(canonical),
                    "request_count": len(call_records),
                    "functions": dict(sorted(Counter(
                        item["function"] for item in call_records
                    ).items())),
                    "calls": call_records,
                }
        result[phase] = methods
    return result


def has_fixed_literal(compare: ast.Compare) -> bool:
    if not any(isinstance(operator, (ast.Eq, ast.NotEq, ast.In, ast.NotIn)) for operator in compare.ops):
        return False
    values = [compare.left, *compare.comparators]
    return any(
        isinstance(node, (ast.Constant, ast.List, ast.Tuple, ast.Set, ast.Dict))
        and any(isinstance(item, ast.Constant) for item in ast.walk(node))
        for node in values
    )


def runtime_comparison_inventory() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for phase in PHASES:
        for path in sorted((ROOT / "build" / phase / "runtime").rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            comparisons = sorted(
                (
                    node for node in ast.walk(tree)
                    if isinstance(node, ast.Compare) and has_fixed_literal(node)
                ),
                key=lambda node: (node.lineno, node.col_offset),
            )
            if not comparisons:
                continue
            records = [
                {"line": node.lineno, "fingerprint": digest(normalized(node))}
                for node in comparisons
            ]
            canonical = json.dumps(
                [item["fingerprint"] for item in records], separators=(",", ":"),
            )
            result[relative(path)] = {
                "inventory_sha256": digest(canonical),
                "comparison_count": len(records),
                "comparisons": records,
            }
    return result


def runtime_source_inventory() -> dict[str, dict[str, Any]]:
    """Ratcheted full-source hashes cover comparisons in non-Python runtimes."""
    extensions = {".sh", ".c", ".cpp", ".cs", ".go", ".nim", ".S"}
    result: dict[str, dict[str, Any]] = {}
    for phase in PHASES:
        for path in sorted((ROOT / "build" / phase / "runtime").rglob("*")):
            if not path.is_file() or path.suffix not in extensions:
                continue
            value = path.read_bytes()
            result[relative(path)] = {
                "source_sha256": hashlib.sha256(value).hexdigest(),
                "line_count": value.count(b"\n") + bool(value and not value.endswith(b"\n")),
            }
    return result


def load_ledger(path: Path = LEDGER_PATH) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ProvenanceError(f"provenance ledger cannot be read: {error}") from error
    validate_ledger(value)
    return value


def validate_sources(sources: Any, context: str) -> None:
    if not isinstance(sources, list) or not sources:
        raise ProvenanceError(f"{context}: sources must be a non-empty list")
    for source in sources:
        required = {"class", "inputs", "source", "locator"}
        if not isinstance(source, dict) or set(source) != required:
            raise ProvenanceError(f"{context}: invalid source fields")
        if source["class"] not in PROVENANCE_CLASSES:
            raise ProvenanceError(f"{context}: invalid provenance class")
        if not isinstance(source["inputs"], list) or not source["inputs"] or not all(
            isinstance(item, str) and item for item in source["inputs"]
        ):
            raise ProvenanceError(f"{context}: invalid source inputs")
        if not all(isinstance(source[key], str) and source[key] for key in ("source", "locator")):
            raise ProvenanceError(f"{context}: invalid source citation")


def validate_unresolved(items: Any, context: str) -> None:
    if not isinstance(items, list):
        raise ProvenanceError(f"{context}: unresolved must be a list")
    for item in items:
        required = {"input", "fingerprint", "reason", "issue"}
        if not isinstance(item, dict) or set(item) != required:
            raise ProvenanceError(f"{context}: invalid unresolved fields")
        if not isinstance(item["input"], str) or not item["input"]:
            raise ProvenanceError(f"{context}: invalid unresolved input")
        if not isinstance(item["fingerprint"], str) or not SHA.fullmatch(item["fingerprint"]):
            raise ProvenanceError(f"{context}: invalid unresolved fingerprint")
        if not isinstance(item["reason"], str) or not item["reason"]:
            raise ProvenanceError(f"{context}: invalid unresolved reason")
        if not isinstance(item["issue"], int) or item["issue"] < 1:
            raise ProvenanceError(f"{context}: invalid unresolved issue")


def validate_ledger(value: Any) -> None:
    if not isinstance(value, dict) or set(value) != {
        "schema_version", "profiles", "methods", "runtime_comparisons", "runtime_sources",
    }:
        raise ProvenanceError("provenance ledger has invalid top-level fields")
    if value["schema_version"] != 1:
        raise ProvenanceError("provenance ledger schema_version must be 1")
    if not isinstance(value["profiles"], dict) or set(value["profiles"]) != set(PHASES):
        raise ProvenanceError("provenance profiles must cover all phases")
    for phase, profile in value["profiles"].items():
        if not isinstance(profile, dict) or set(profile) != {"title", "sources"}:
            raise ProvenanceError(f"profile {phase}: invalid fields")
        if not isinstance(profile["title"], str) or not profile["title"]:
            raise ProvenanceError(f"profile {phase}: title is required")
        validate_sources(profile["sources"], f"profile {phase}")

    observed_requests = request_inventory()
    methods = value["methods"]
    if not isinstance(methods, dict) or set(methods) != set(PHASES):
        raise ProvenanceError("method ledger must cover all phases")
    for phase in PHASES:
        if not isinstance(methods[phase], dict) or set(methods[phase]) != set(observed_requests[phase]):
            missing = sorted(set(observed_requests[phase]) - set(methods[phase])) if isinstance(methods[phase], dict) else []
            extra = sorted(set(methods[phase]) - set(observed_requests[phase])) if isinstance(methods[phase], dict) else []
            raise ProvenanceError(f"{phase}: request methods changed; missing={missing}, extra={extra}")
        for method, observed in observed_requests[phase].items():
            entry = methods[phase][method]
            required = {
                "profile", "inventory_sha256", "request_count", "review_status",
                "citations", "unresolved",
            }
            if not isinstance(entry, dict) or set(entry) != required:
                raise ProvenanceError(f"{phase}.{method}: invalid fields")
            if entry["profile"] not in value["profiles"]:
                raise ProvenanceError(f"{phase}.{method}: unknown profile")
            if entry["inventory_sha256"] != observed["inventory_sha256"]:
                raise ProvenanceError(f"{phase}.{method}: request inputs changed without ledger review")
            if entry["request_count"] != observed["request_count"]:
                raise ProvenanceError(f"{phase}.{method}: request count changed without ledger review")
            validate_sources(entry["citations"], f"{phase}.{method}")
            validate_unresolved(entry["unresolved"], f"{phase}.{method}")
            expected_status = "complete" if not entry["unresolved"] else "unresolved"
            if entry["review_status"] != expected_status:
                raise ProvenanceError(f"{phase}.{method}: review_status disagrees with unresolved inputs")

    observed_comparisons = runtime_comparison_inventory()
    comparisons = value["runtime_comparisons"]
    if not isinstance(comparisons, dict) or set(comparisons) != set(observed_comparisons):
        raise ProvenanceError("fixed runtime comparison files changed without ledger review")
    for path, observed in observed_comparisons.items():
        entry = comparisons[path]
        required = {
            "inventory_sha256", "comparison_count", "review_status",
            "citations", "unresolved",
        }
        if not isinstance(entry, dict) or set(entry) != required:
            raise ProvenanceError(f"{path}: invalid comparison ledger fields")
        if entry["inventory_sha256"] != observed["inventory_sha256"]:
            raise ProvenanceError(f"{path}: fixed runtime comparisons changed without ledger review")
        if entry["comparison_count"] != observed["comparison_count"]:
            raise ProvenanceError(f"{path}: fixed runtime comparison count changed without ledger review")
        if entry["citations"]:
            validate_sources(entry["citations"], path)
        elif entry["review_status"] == "complete":
            raise ProvenanceError(f"{path}: complete comparison review requires citations")
        validate_unresolved(entry["unresolved"], path)
        expected_status = "complete" if not entry["unresolved"] else "unresolved"
        if entry["review_status"] != expected_status:
            raise ProvenanceError(f"{path}: review_status disagrees with unresolved comparisons")

    observed_sources = runtime_source_inventory()
    sources = value["runtime_sources"]
    if not isinstance(sources, dict) or set(sources) != set(observed_sources):
        raise ProvenanceError("non-Python runtime sources changed without ledger review")
    for path, observed in observed_sources.items():
        entry = sources[path]
        required = {"source_sha256", "review_status", "citations", "unresolved"}
        if not isinstance(entry, dict) or set(entry) != required:
            raise ProvenanceError(f"{path}: invalid runtime source ledger fields")
        if entry["source_sha256"] != observed["source_sha256"]:
            raise ProvenanceError(f"{path}: runtime source changed without ledger review")
        if entry["citations"]:
            validate_sources(entry["citations"], path)
        elif entry["review_status"] == "complete":
            raise ProvenanceError(f"{path}: complete source review requires citations")
        validate_unresolved(entry["unresolved"], path)
        expected_status = "complete" if not entry["unresolved"] else "unresolved"
        if entry["review_status"] != expected_status:
            raise ProvenanceError(f"{path}: review_status disagrees with unresolved source")


def entry_provenance(ledger: dict[str, Any], phase: str, method: str) -> dict[str, Any]:
    try:
        entry = ledger["methods"][phase][method]
    except KeyError as error:
        raise ProvenanceError(f"no provenance entry for {phase}.{method}") from error
    profile = ledger["profiles"][entry["profile"]]
    return {
        "status": entry["review_status"],
        "sources": [*profile["sources"], *entry["citations"]],
        "unresolved": entry["unresolved"],
    }


def attach_runtime_provenance(
    phase: str, events: list[dict[str, Any]], selected_methods: list[str],
    ledger: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    value = load_ledger() if ledger is None else ledger
    unresolved: list[dict[str, Any]] = []
    for method in selected_methods:
        provenance = entry_provenance(value, phase, method)
        unresolved.extend(provenance["unresolved"])
    for event in events:
        if event["kind"] != "http":
            continue
        event["provenance"] = entry_provenance(value, phase, event["test_method"])
    unique = {
        (item["issue"], item["input"], item["fingerprint"]): item
        for item in unresolved
    }
    return events, {
        "status": "complete" if not unique else "unresolved",
        "unresolved": [unique[key] for key in sorted(unique)],
    }


def new_unresolved_ledger() -> dict[str, Any]:
    """Build a fail-closed ledger for first review; it never marks an input complete."""
    profiles = {
        "training": {
            "title": "Training participant workstation and linked desks",
            "sources": [
                {
                    "class": "supplied_starting_surface",
                    "inputs": ["route", "hostname", "starting document"],
                    "source": "/home/cinder/TRAINING.md",
                    "locator": "the four published desk URLs",
                },
                {
                    "class": "normal_interface_or_artifact",
                    "inputs": ["record identifier", "revision", "field name", "protocol input"],
                    "source": "HTTP resources linked from the published Training desks",
                    "locator": "response field names and linked artifact paths used by the method",
                },
            ],
        },
        "keplerops": {
            "title": "Rowan workstation, FieldKest documents and earned responses",
            "sources": [
                {
                    "class": "supplied_starting_surface",
                    "inputs": ["route", "hostname", "CA", "starting credential"],
                    "source": "/home/rowan/README.md, work/service-notes.md, work/service-catalog.md and .config/git/credentials",
                    "locator": "named route, CA, repository and credential entries consumed by the method",
                },
                {
                    "class": "normal_interface_or_artifact",
                    "inputs": ["artifact", "schema", "protocol constant"],
                    "source": "FieldKest normal service responses and workstation artifacts",
                    "locator": "artifact path or response field cited by the method review",
                },
            ],
        },
        "arwc": {
            "title": "FieldLink connector handover and earned corporate interfaces",
            "sources": [
                {
                    "class": "supplied_starting_surface",
                    "inputs": ["route", "hostname", "tenant", "corporate session", "CA"],
                    "source": "/var/lib/fieldlink-connector/handover/customer-transition.json, corporate-session and /tmp/arwc-ca.crt",
                    "locator": "handover route fields, tenant binding, earned session and supplied CA",
                },
                {
                    "class": "normal_interface_or_artifact",
                    "inputs": ["record identifier", "revision", "field name", "protocol input", "exploit input"],
                    "source": "ARWC corporate, maintenance, DMZ, engineering and control responses",
                    "locator": "response field or returned artifact cited by the method review",
                },
            ],
        },
    }
    requests = request_inventory()
    methods: dict[str, dict[str, Any]] = {phase: {} for phase in PHASES}
    for phase in PHASES:
        for method, observed in requests[phase].items():
            unresolved = [{
                "input": "exact request literals and protocol constants",
                "fingerprint": observed["inventory_sha256"],
                "reason": "Per-value review of exact accepted inputs is pending",
                "issue": 224,
            }]
            if phase == "keplerops" and method == "test_k18_note_and_federation":
                unresolved.append({
                    "input": "federated subject construction",
                    "fingerprint": "823d157f653a527c7635574802bd1b3a5197c0399f92f4f5c8ee39ed4357c249",
                    "reason": "The accepted subject prefix is author-only",
                    "issue": 216,
                })
            if phase == "keplerops" and method == "test_k29b_connector_delivery":
                unresolved.append({
                    "input": "customer-channel bearer",
                    "fingerprint": "399e846d148764b5f6b2becc2957365363cb8033ea9521114019f435dbd0d13c",
                    "reason": "The relay bearer is a fixed image-wide literal",
                    "issue": 217,
                })
            if phase == "arwc" and method == "test_w33_forecast_scheduling":
                unresolved.extend([
                    {
                        "input": "scheduler checkpoint",
                        "fingerprint": "bad22df8a4351ecbf155d9ef7696628039aa45f80070c4d8d1474a1d4d79b991",
                        "reason": "The checkpoint is not supplied by a participant-visible record",
                        "issue": 223,
                    },
                    {
                        "input": "forecast demand and release model vectors",
                        "fingerprint": "c2bd8215973a6295967cf4b9529aeb0f8b7ad61662afb0d3b7d9c6c1a20b885e",
                        "reason": "The model vectors and bounds exist only in the known-solution test",
                        "issue": 223,
                    },
                    {
                        "input": "feedback policy format and gains",
                        "fingerprint": "2d67289b356bf85adc2421adcbbe422887ec0396a1c091b45ec81206f01319ec",
                        "reason": "The accepted policy contract is not participant-visible",
                        "issue": 223,
                    },
                ])
            methods[phase][method] = {
                "profile": phase,
                "inventory_sha256": observed["inventory_sha256"],
                "request_count": observed["request_count"],
                "review_status": "unresolved",
                "citations": [{
                    "class": "earlier_accepted_response",
                    "inputs": ["response-derived identifier", "revision", "credential or session"],
                    "source": f"accepted response chain in {method}",
                    "locator": "named evidence fields carried into a later request by this method",
                }],
                "unresolved": unresolved,
            }
    comparisons = {
        path: {
            "inventory_sha256": observed["inventory_sha256"],
            "comparison_count": observed["comparison_count"],
            "review_status": "unresolved",
            "citations": [],
            "unresolved": [{
                "input": "fixed runtime comparison inventory",
                "fingerprint": observed["inventory_sha256"],
                "reason": "Participant relevance and provenance classification are pending",
                "issue": 224,
            }],
        }
        for path, observed in runtime_comparison_inventory().items()
    }
    runtime_sources = {
        path: {
            "source_sha256": observed["source_sha256"],
            "review_status": "unresolved",
            "citations": [],
            "unresolved": [{
                "input": "fixed comparisons in non-Python runtime source",
                "fingerprint": observed["source_sha256"],
                "reason": "Participant relevance and provenance classification are pending",
                "issue": 224,
            }],
        }
        for path, observed in runtime_source_inventory().items()
    }
    return {
        "schema_version": 1,
        "profiles": profiles,
        "methods": methods,
        "runtime_comparisons": comparisons,
        "runtime_sources": runtime_sources,
    }


def build_report(ledger: dict[str, Any]) -> dict[str, Any]:
    requests = request_inventory()
    comparisons = runtime_comparison_inventory()
    sources = runtime_source_inventory()
    request_entries: list[dict[str, Any]] = []
    for phase in PHASES:
        for method, observed in requests[phase].items():
            provenance = entry_provenance(ledger, phase, method)
            for index, call in enumerate(observed["calls"], start=1):
                request_entries.append({
                    "request_id": f"{phase}:{method}:{index}",
                    "phase": phase,
                    "test_method": method,
                    "function": call["function"],
                    "source": {"file": relative(SUITES[phase]), "line": call["line"]},
                    "callsite_sha256": call["fingerprint"],
                    "provenance": provenance,
                })
    comparison_entries: list[dict[str, Any]] = []
    for path, observed in comparisons.items():
        entry = ledger["runtime_comparisons"][path]
        for index, comparison in enumerate(observed["comparisons"], start=1):
            comparison_entries.append({
                "comparison_id": f"{path}:{index}",
                "source": {"file": path, "line": comparison["line"]},
                "comparison_sha256": comparison["fingerprint"],
                "review_status": entry["review_status"],
                "citations": entry["citations"],
                "unresolved": entry["unresolved"],
            })
    incomplete_requests = sum(
        entry["provenance"]["status"] != "complete" for entry in request_entries
    )
    incomplete_comparisons = sum(
        entry["review_status"] != "complete" for entry in comparison_entries
    )
    source_entries = [
        {
            "source": {"file": path},
            "source_sha256": observed["source_sha256"],
            "line_count": observed["line_count"],
            "review_status": ledger["runtime_sources"][path]["review_status"],
            "citations": ledger["runtime_sources"][path]["citations"],
            "unresolved": ledger["runtime_sources"][path]["unresolved"],
        }
        for path, observed in sources.items()
    ]
    incomplete_sources = sum(entry["review_status"] != "complete" for entry in source_entries)
    return {
        "schema_version": 1,
        "report_kind": "solution-input-provenance",
        "overall_status": "complete" if not incomplete_requests and not incomplete_comparisons and not incomplete_sources else "unresolved",
        "summary": {
            "request_count": len(request_entries),
            "unresolved_request_count": incomplete_requests,
            "runtime_comparison_count": len(comparison_entries),
            "unresolved_runtime_comparison_count": incomplete_comparisons,
            "runtime_source_count": len(source_entries),
            "unresolved_runtime_source_count": incomplete_sources,
        },
        "requests": request_entries,
        "runtime_comparisons": comparison_entries,
        "runtime_sources": source_entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, default=LEDGER_PATH)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument(
        "--new-unresolved-ledger", type=Path,
        help="create, but never overwrite, a fail-closed ledger for first review",
    )
    arguments = parser.parse_args()
    if arguments.new_unresolved_ledger:
        try:
            with arguments.new_unresolved_ledger.open("x", encoding="utf-8") as output:
                json.dump(new_unresolved_ledger(), output, indent=2, sort_keys=True)
                output.write("\n")
        except FileExistsError as error:
            raise ProvenanceError("refusing to overwrite an existing ledger") from error
        return 0
    ledger = load_ledger(arguments.ledger)
    report = build_report(ledger)
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
