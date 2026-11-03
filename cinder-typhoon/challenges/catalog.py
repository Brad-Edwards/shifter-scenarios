#!/usr/bin/env python3
"""Build and validate the versioned Cinder Typhoon participant catalog."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = Path(__file__).resolve().parent / "challenges.yaml"
PORTFOLIO = ROOT / "docs" / "design" / "portfolio.csv"
DEPENDENCIES = ROOT / "docs" / "design" / "challenge-dependencies.json"
BRIEFS = ROOT / "docs" / "design" / "challenges"
HINT_ROOT = ROOT / "build" / "card-coverage"
HINT_DELIVERY_ROOT = ROOT / "build" / "hint-delivery"
HINT_MANIFEST = HINT_DELIVERY_ROOT / "manifest.json"
HINT_REVIEWS = HINT_DELIVERY_ROOT / "operation-reviews.json"
HINT_PLAYTEST_SCHEMA = HINT_DELIVERY_ROOT / "playtest-observation.schema.json"
SURFACE_MANIFESTS = ROOT / "build" / "participant-surface" / "manifests"
CANDIDATE_MANIFEST = ROOT / "build" / "participant-runner" / "candidate.json"
CATALOG_SCHEMA = "cinder-typhoon.challenge-delivery/v2"
PHASES = ("training", "keplerops", "arwc")
PHASE_TITLES = {
    "training": "Training",
    "keplerops": "KeplerOps",
    "arwc": "ARWC",
}
PREFIXES = {"training": "T", "keplerops": "K", "arwc": "W"}
TIERS = ("easy", "medium", "hard", "expert", "elite")
TIER_POINTS = {
    "easy": 50,
    "medium": 100,
    "hard": 200,
    "expert": 400,
    "elite": 800,
}
EXPECTED_PHASE_COUNTS = {
    "training": (4, 16),
    "keplerops": (31, 104),
    "arwc": (35, 120),
}
CARD_ID = re.compile(r"^[TKW]\d{2}\.\d+$")
OPERATION_ID = re.compile(r"^[TKW]\d{2}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
HINT_LEVELS = ("h1", "h2", "h3")
HINT_POLICY = {
    "release": "facilitator_on_request",
    "levels": 3,
    "independent_levels": True,
    "penalty": 0,
}


class CatalogError(ValueError):
    """The participant catalog or one of its authoring inputs is invalid."""


def _yaml() -> Any:
    try:
        import yaml
    except ImportError as error:
        raise CatalogError("PyYAML is required to build or read the delivery catalog") from error
    return yaml


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _brief_paths() -> list[Path]:
    return sorted(BRIEFS.glob("[TKW][0-9][0-9]/[TKW][0-9][0-9].[0-9].md"))


def source_paths() -> list[Path]:
    """Return every authoring input whose change requires catalog review."""

    return [
        PORTFOLIO,
        DEPENDENCIES,
        *(HINT_ROOT / f"hints-{phase}.yaml" for phase in PHASES),
        *_brief_paths(),
    ]


def source_revision(paths: Iterable[Path] | None = None) -> str:
    """Hash source identities and bytes without exposing operator paths in delivery."""

    selected = list(paths if paths is not None else source_paths())
    records = []
    for path in selected:
        try:
            name = path.relative_to(ROOT).as_posix()
        except ValueError:
            name = path.name
        records.append((name, _sha256(path)))
    encoded = json.dumps(records, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _section(source: str, heading: str) -> str:
    if " — " in heading:
        before, after = heading.split(" — ", 1)
        heading_pattern = rf"{re.escape(before)}\s*—\s*{re.escape(after)}"
    else:
        heading_pattern = re.escape(heading)
    match = re.search(
        rf"(?ms)^## {heading_pattern}\s*\n(.*?)(?=^## |\Z)",
        source,
    )
    if not match or not match.group(1).strip():
        raise CatalogError(f"brief is missing {heading}")
    return " ".join(match.group(1).split())


def _field(source: str, name: str) -> str:
    match = re.search(rf"(?m)^\| {re.escape(name)} \| ([^|]+) \|$", source)
    if not match:
        raise CatalogError(f"brief is missing {name}")
    return match.group(1).strip()


def _title(source: str, card_id: str) -> str:
    match = re.match(rf"# {re.escape(card_id)}: (.+)\n", source)
    if not match:
        raise CatalogError(f"brief title does not match {card_id}")
    return match.group(1).strip()


def _briefs() -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for path in _brief_paths():
        card_id = path.stem
        source = path.read_text(encoding="utf-8")
        if card_id in result:
            raise CatalogError(f"duplicate brief: {card_id}")
        difficulty = _field(source, "Proposed difficulty").lower()
        if difficulty not in TIER_POINTS:
            raise CatalogError(f"{card_id}: unsupported difficulty {difficulty}")
        result[card_id] = {
            "title": _title(source, card_id),
            "description": _section(source, "Challenge description — player-facing"),
            "difficulty": difficulty,
        }
    return result


def _hint_documents() -> dict[str, dict[str, Any]]:
    yaml = _yaml()
    result: dict[str, dict[str, Any]] = {}
    for phase in PHASES:
        path = HINT_ROOT / f"hints-{phase}.yaml"
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
        if (
            not isinstance(value, dict)
            or set(value) != {"schema_version", "phase", "hints"}
            or value.get("schema_version") != 2
            or value.get("phase") != phase
            or not isinstance(value.get("hints"), dict)
        ):
            raise CatalogError(f"invalid hint catalog: {path}")
        for card_id, levels in value.get("hints", {}).items():
            if not CARD_ID.fullmatch(card_id) or not card_id.startswith(PREFIXES[phase]):
                raise CatalogError(f"invalid hint card: {card_id}")
            if not isinstance(levels, dict) or set(levels) != {*HINT_LEVELS, "references"}:
                raise CatalogError(f"{card_id}: exactly three hint levels are required")
            hints = [levels[f"h{level}"] for level in range(1, 4)]
            if not all(isinstance(hint, str) and len(hint.split()) >= 12 for hint in hints):
                raise CatalogError(f"{card_id}: hint text is required")
            references = levels["references"]
            if not isinstance(references, list) or not references:
                raise CatalogError(f"{card_id}: participant-boundary hint references are required")
            reference_keys: set[tuple[str, str]] = set()
            for reference in references:
                if (
                    not isinstance(reference, dict)
                    or set(reference) != {"kind", "id"}
                    or reference["kind"] not in {
                        "client_route", "participant_artifact", "participant_service", "starting_material",
                    }
                    or not isinstance(reference["id"], str)
                    or not reference["id"].strip()
                ):
                    raise CatalogError(f"{card_id}: invalid participant-boundary hint reference")
                key = (reference["kind"], reference["id"])
                if key in reference_keys:
                    raise CatalogError(f"{card_id}: duplicate participant-boundary hint reference")
                reference_keys.add(key)
        result[phase] = value
    return result


def _hints() -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for document in _hint_documents().values():
        for card_id, levels in document["hints"].items():
            if card_id in result:
                raise CatalogError(f"duplicate hint card: {card_id}")
            result[card_id] = [" ".join(levels[level].split()) for level in HINT_LEVELS]
    return result


def _dependency_cards() -> set[str]:
    value = json.loads(DEPENDENCIES.read_text(encoding="utf-8"))
    cards = value.get("challenges") if isinstance(value, dict) else None
    if value.get("schema_version") != 1 or not isinstance(cards, dict):
        raise CatalogError("challenge dependency ledger is invalid")
    if not all(CARD_ID.fullmatch(card_id) for card_id in cards):
        raise CatalogError("challenge dependency ledger contains an invalid card ID")
    return set(cards)


def _portfolio_rows() -> list[dict[str, str]]:
    with PORTFOLIO.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 70:
        raise CatalogError(f"portfolio must contain 70 operations, found {len(rows)}")
    return rows


def build_catalog() -> dict[str, Any]:
    """Project reviewed authoring inputs into a participant-safe snapshot."""

    briefs = _briefs()
    hints = _hints()
    dependencies = _dependency_cards()
    if set(briefs) != set(hints) or set(briefs) != dependencies:
        raise CatalogError("brief, hint, and dependency card sets disagree")

    phases: dict[str, Any] = {
        phase: {"title": PHASE_TITLES[phase], "operations": []}
        for phase in PHASES
    }
    delivered: set[str] = set()
    for row in _portfolio_rows():
        phase = row["phase"].lower()
        operation_id = row["id"]
        if phase not in phases or not OPERATION_ID.fullmatch(operation_id):
            raise CatalogError(f"invalid portfolio operation: {operation_id}")
        card_ids = sorted(
            (card_id for card_id in briefs if card_id.startswith(f"{operation_id}.")),
            key=lambda item: int(item.rsplit(".", 1)[1]),
        )
        if not card_ids or delivered.intersection(card_ids):
            raise CatalogError(f"invalid card allocation for {operation_id}")
        allocation = {
            tier: int(row[tier])
            for tier in TIERS
            if int(row[tier])
        }
        actual = Counter(briefs[card_id]["difficulty"] for card_id in card_ids)
        if allocation != {tier: actual[tier] for tier in TIERS if actual[tier]}:
            raise CatalogError(f"portfolio tier allocation disagrees for {operation_id}")
        cards = []
        for card_id in card_ids:
            brief = briefs[card_id]
            cards.append({
                "id": card_id,
                "title": brief["title"],
                "description": brief["description"],
                "difficulty": brief["difficulty"],
                "points": TIER_POINTS[brief["difficulty"]],
                "hints": hints[card_id],
                "completion": {"mode": "automatic_range_evidence"},
            })
        phases[phase]["operations"].append({
            "id": operation_id,
            "chapter": row["chapter"],
            "title": row["operation"],
            "allocation": allocation,
            "cards": cards,
        })
        delivered.update(card_ids)

    if delivered != set(briefs):
        raise CatalogError("portfolio does not allocate every authored card exactly once")
    for phase, value in phases.items():
        cards = [card for operation in value["operations"] for card in operation["cards"]]
        value["operation_count"] = len(value["operations"])
        value["card_count"] = len(cards)
        value["score_total"] = sum(card["points"] for card in cards)

    catalog = {
        "schema": CATALOG_SCHEMA,
        "revision": source_revision(),
        "scoring": {
            "model": "static",
            "tier_points": TIER_POINTS,
            "max_score": sum(TIER_POINTS[brief["difficulty"]] for brief in briefs.values()),
            "max_out": "Complete all 240 cards; hints do not reduce score.",
            "hint_policy": HINT_POLICY,
        },
        "summary": {
            "operation_count": 70,
            "card_count": 240,
        },
        "phases": phases,
    }
    validate_catalog(catalog)
    return catalog


def catalog_cards(value: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        card
        for phase in value["phases"].values()
        for operation in phase["operations"]
        for card in operation["cards"]
    ]


def catalog_operations(value: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        operation
        for phase in value["phases"].values()
        for operation in phase["operations"]
    ]


def validate_catalog(value: Any) -> None:
    if not isinstance(value, dict) or set(value) != {
        "schema", "revision", "scoring", "summary", "phases",
    }:
        raise CatalogError("catalog has invalid top-level fields")
    if value["schema"] != CATALOG_SCHEMA or not SHA256.fullmatch(str(value["revision"])):
        raise CatalogError("catalog schema or revision is invalid")
    if set(value["phases"]) != set(PHASES):
        raise CatalogError("catalog phases are incomplete")
    scoring = value["scoring"]
    if not isinstance(scoring, dict) or set(scoring) != {
        "model", "tier_points", "max_score", "max_out", "hint_policy",
    }:
        raise CatalogError("catalog scoring model is invalid")
    if scoring["model"] != "static" or scoring["tier_points"] != TIER_POINTS:
        raise CatalogError("catalog tier scores are invalid")
    if scoring["hint_policy"] != HINT_POLICY:
        raise CatalogError("catalog hint rule is invalid")

    seen_cards: set[str] = set()
    seen_operations: set[str] = set()
    total_score = 0
    for phase in PHASES:
        phase_value = value["phases"][phase]
        if not isinstance(phase_value, dict) or set(phase_value) != {
            "title", "operation_count", "card_count", "score_total", "operations",
        }:
            raise CatalogError(f"{phase}: invalid phase fields")
        operations = phase_value["operations"]
        if not isinstance(operations, list):
            raise CatalogError(f"{phase}: operations must be a list")
        phase_cards: list[dict[str, Any]] = []
        for operation in operations:
            if not isinstance(operation, dict) or set(operation) != {
                "id", "chapter", "title", "allocation", "cards",
            }:
                raise CatalogError(f"{phase}: invalid operation fields")
            operation_id = operation["id"]
            if (
                not isinstance(operation_id, str)
                or not OPERATION_ID.fullmatch(operation_id)
                or not operation_id.startswith(PREFIXES[phase])
                or operation_id in seen_operations
            ):
                raise CatalogError(f"{phase}: duplicate or invalid operation ID")
            seen_operations.add(operation_id)
            if not all(isinstance(operation[field], str) and operation[field].strip() for field in ("chapter", "title")):
                raise CatalogError(f"{operation_id}: participant operation text is required")
            allocation = operation["allocation"]
            if not isinstance(allocation, dict) or not allocation or not set(allocation) <= set(TIERS):
                raise CatalogError(f"{operation_id}: invalid operation allocation")
            cards = operation["cards"]
            if not isinstance(cards, list) or not cards:
                raise CatalogError(f"{operation_id}: cards are required")
            actual = Counter()
            for card in cards:
                if not isinstance(card, dict) or set(card) != {
                    "id", "title", "description", "difficulty", "points", "hints", "completion",
                }:
                    raise CatalogError(f"{operation_id}: invalid card fields")
                card_id = card["id"]
                if (
                    not isinstance(card_id, str)
                    or not CARD_ID.fullmatch(card_id)
                    or not card_id.startswith(f"{operation_id}.")
                    or card_id in seen_cards
                ):
                    raise CatalogError(f"{operation_id}: duplicate or invalid card ID")
                seen_cards.add(card_id)
                difficulty = card["difficulty"]
                if difficulty not in TIER_POINTS or card["points"] != TIER_POINTS[difficulty]:
                    raise CatalogError(f"{card_id}: score does not match difficulty")
                if not all(isinstance(card[field], str) and card[field].strip() for field in ("title", "description")):
                    raise CatalogError(f"{card_id}: participant card text is required")
                if not isinstance(card["hints"], list) or len(card["hints"]) != 3 or not all(
                    isinstance(hint, str) and hint.strip() for hint in card["hints"]
                ):
                    raise CatalogError(f"{card_id}: three participant hints are required")
                if card["completion"] != {"mode": "automatic_range_evidence"}:
                    raise CatalogError(f"{card_id}: completion mode is invalid")
                actual[difficulty] += 1
                total_score += card["points"]
                phase_cards.append(card)
            expected_allocation = {tier: actual[tier] for tier in TIERS if actual[tier]}
            if allocation != expected_allocation:
                raise CatalogError(f"{operation_id}: card allocation does not match cards")
        expected_operations, expected_cards = EXPECTED_PHASE_COUNTS[phase]
        if (
            phase_value["operation_count"] != expected_operations
            or len(operations) != expected_operations
            or phase_value["card_count"] != expected_cards
            or len(phase_cards) != expected_cards
            or phase_value["score_total"] != sum(card["points"] for card in phase_cards)
        ):
            raise CatalogError(f"{phase}: summary does not match delivery")

    if value["summary"] != {"operation_count": 70, "card_count": 240}:
        raise CatalogError("catalog summary is invalid")
    if len(seen_operations) != 70 or len(seen_cards) != 240:
        raise CatalogError("catalog must contain 70 operations and 240 cards")
    if scoring["max_score"] != total_score:
        raise CatalogError("catalog maximum score does not match cards")
    serialized = json.dumps(value, ensure_ascii=False).lower()
    for forbidden in (
        "technical design", "vulnerability and intended solution", "author checks",
        "completion_evaluator", "accepting_components", "evidence_owners",
        "prerequisite_sets", "request_body", "response_body",
    ):
        if forbidden in serialized:
            raise CatalogError(f"operator-only field or section leaked: {forbidden}")


def load_catalog(path: Path = CATALOG_PATH, *, require_current: bool = True) -> dict[str, Any]:
    try:
        value = _yaml().safe_load(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise CatalogError(f"catalog cannot be read: {error}") from error
    validate_catalog(value)
    if require_current and value != build_catalog():
        raise CatalogError("catalog is stale; regenerate and review challenges/challenges.yaml")
    return value


def catalog_metadata(path: Path = CATALOG_PATH, *, require_current: bool = True) -> dict[str, Any]:
    value = load_catalog(path, require_current=require_current)
    try:
        relative_path = path.relative_to(ROOT).as_posix()
    except ValueError:
        relative_path = path.as_posix()
    return {
        "path": relative_path,
        "schema": value["schema"],
        "revision": value["revision"],
        "sha256": _sha256(path),
        "operation_count": value["summary"]["operation_count"],
        "card_count": value["summary"]["card_count"],
        "score_total": value["scoring"]["max_score"],
    }


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _operation_hint_reviews(catalog: dict[str, Any]) -> dict[str, Any]:
    try:
        value = json.loads(HINT_REVIEWS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CatalogError(f"operation hint reviews cannot be read: {error}") from error
    if not isinstance(value, dict) or set(value) != {"schema_version", "operations"}:
        raise CatalogError("operation hint reviews have invalid top-level fields")
    reviews = value.get("operations")
    if value.get("schema_version") != 1 or not isinstance(reviews, dict):
        raise CatalogError("operation hint reviews have an invalid schema")
    operations = {operation["id"]: operation for operation in catalog_operations(catalog)}
    if set(reviews) != set(operations):
        raise CatalogError("operation hint reviews must exactly cover all 70 operations")
    required_checks = {
        "in_world_orientation", "technique_boundary", "diagnostic_next_step",
        "no_sensitive_answer", "references_current",
    }
    for operation_id, review in reviews.items():
        if not isinstance(review, dict) or set(review) != {
            "sample_card", "status", "checks", "rationale",
        }:
            raise CatalogError(f"{operation_id}: invalid operation hint review")
        operation_cards = {card["id"] for card in operations[operation_id]["cards"]}
        if review["sample_card"] not in operation_cards or review["status"] != "reviewed":
            raise CatalogError(f"{operation_id}: hint sample review is incomplete")
        if set(review["checks"]) != required_checks:
            raise CatalogError(f"{operation_id}: hint sample review checks are incomplete")
        if not isinstance(review["rationale"], str) or len(review["rationale"].split()) < 15:
            raise CatalogError(f"{operation_id}: hint sample review rationale is not substantive")
    return value


def build_hint_manifest(catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build the operator release manifest without copying unreleased hint text."""

    current = catalog if catalog is not None else build_catalog()
    validate_catalog(current)
    documents = _hint_documents()
    reviews = _operation_hint_reviews(current)
    items: list[dict[str, Any]] = []
    sources = []
    for phase in PHASES:
        path = HINT_ROOT / f"hints-{phase}.yaml"
        document = documents[phase]
        sources.append({
            "phase": phase,
            "path": _relative(path),
            "sha256": _sha256(path),
            "card_count": len(document["hints"]),
            "hint_count": 3 * len(document["hints"]),
        })
        for operation in current["phases"][phase]["operations"]:
            for card in operation["cards"]:
                authored = document["hints"][card["id"]]
                level_records = [
                    {
                        "level": level,
                        "sha256": hashlib.sha256(
                            " ".join(authored[f"h{level}"].split()).encode()
                        ).hexdigest(),
                    }
                    for level in range(1, 4)
                ]
                items.append({
                    "card_id": card["id"],
                    "operation_id": operation["id"],
                    "phase": phase,
                    "levels": level_records,
                    "references": authored["references"],
                })
    payload = {
        "schema": "cinder-typhoon.hint-delivery/v1",
        "catalog": {
            "schema": current["schema"],
            "revision": current["revision"],
        },
        "sources": sources,
        "release": {
            "mode": "facilitator_on_request",
            "levels": [1, 2, 3],
            "independent_levels": True,
            "audit": "append_only_metadata_without_hint_text",
        },
        "score_effect": {"penalty": 0, "maximum_score_unchanged": True},
        "review": {
            "path": _relative(HINT_REVIEWS),
            "sha256": _sha256(HINT_REVIEWS),
            "operation_count": len(reviews["operations"]),
        },
        "playtest_evidence": {
            "schema_path": _relative(HINT_PLAYTEST_SCHEMA),
            "schema_sha256": _sha256(HINT_PLAYTEST_SCHEMA),
            "required_fields": [
                "card_id", "level_observations", "observer_notes",
            ],
        },
        "summary": {
            "operation_count": 70,
            "card_count": len(items),
            "hint_count": sum(len(item["levels"]) for item in items),
        },
        "items": items,
    }
    return {"revision": _canonical_sha256(payload), **payload}


def validate_hint_manifest(value: Any, catalog: dict[str, Any] | None = None) -> None:
    current = catalog if catalog is not None else load_catalog()
    if not isinstance(value, dict) or set(value) != {
        "revision", "schema", "catalog", "sources", "release", "score_effect",
        "review", "playtest_evidence", "summary", "items",
    }:
        raise CatalogError("hint delivery manifest has invalid top-level fields")
    if value["schema"] != "cinder-typhoon.hint-delivery/v1" or not SHA256.fullmatch(
        str(value["revision"])
    ):
        raise CatalogError("hint delivery manifest identity is invalid")
    if value != build_hint_manifest(current):
        raise CatalogError("hint delivery manifest is stale; regenerate and review it")


def load_hint_manifest(*, require_current: bool = True) -> dict[str, Any]:
    try:
        value = json.loads(HINT_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CatalogError(f"hint delivery manifest cannot be read: {error}") from error
    if require_current:
        validate_hint_manifest(value)
    return value


def hint_manifest_metadata(*, require_current: bool = True) -> dict[str, Any]:
    value = load_hint_manifest(require_current=require_current)
    return {
        "path": _relative(HINT_MANIFEST),
        "schema": value["schema"],
        "revision": value["revision"],
        "sha256": _sha256(HINT_MANIFEST),
        **value["summary"],
    }


def write_catalog(path: Path = CATALOG_PATH) -> None:
    value = build_catalog()
    serialized = _yaml().safe_dump(
        value,
        sort_keys=False,
        allow_unicode=True,
        width=100,
    )
    path.write_text(serialized, encoding="utf-8")


def write_hint_manifest(path: Path = HINT_MANIFEST) -> None:
    value = build_hint_manifest(load_catalog())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_surface_bindings() -> None:
    """Bind each participant-surface manifest to its catalog slice by digest."""

    catalog = load_catalog()
    metadata = catalog_metadata()
    hint_manifest = load_hint_manifest()
    hint_metadata = hint_manifest_metadata()
    for phase in PHASES:
        path = SURFACE_MANIFESTS / f"{phase}.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        phase_value = catalog["phases"][phase]
        manifest["delivery"] = {
            "catalog": {
                **metadata,
                "phase": phase,
                "phase_operation_count": phase_value["operation_count"],
                "phase_card_count": phase_value["card_count"],
                "phase_score_total": phase_value["score_total"],
            },
            "cards": {"status": "versioned"},
            "hints": {
                "status": "versioned",
                "manifest": hint_metadata,
                "source": next(source for source in hint_manifest["sources"] if source["phase"] == phase),
                "release": hint_manifest["release"],
                "score_effect": hint_manifest["score_effect"],
                "items": [
                    {
                        "card_id": item["card_id"],
                        "levels": [level["level"] for level in item["levels"]],
                        "content_revision": _canonical_sha256(item["levels"]),
                    }
                    for item in hint_manifest["items"]
                    if item["phase"] == phase
                ],
            },
        }
        path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def write_candidate_binding() -> None:
    """Regenerate only the catalog identity inside the existing candidate."""

    candidate = json.loads(CANDIDATE_MANIFEST.read_text(encoding="utf-8"))
    candidate["schema_version"] = 2
    candidate["challenge_delivery"] = catalog_metadata()
    candidate["hint_delivery"] = hint_manifest_metadata()
    CANDIDATE_MANIFEST.write_text(
        json.dumps(candidate, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-hint-delivery", action="store_true")
    parser.add_argument("--write-surfaces", action="store_true")
    parser.add_argument("--write-candidate-binding", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--metadata", action="store_true")
    arguments = parser.parse_args()
    if arguments.write:
        write_catalog()
    if arguments.write_hint_delivery:
        write_hint_manifest()
    if arguments.write_surfaces:
        write_surface_bindings()
    if arguments.write_candidate_binding:
        write_candidate_binding()
    value = load_catalog()
    summary = catalog_metadata() if arguments.metadata else {
        **value["summary"],
        "score_total": value["scoring"]["max_score"],
        "sha256": _sha256(CATALOG_PATH),
    }
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
