#!/usr/bin/env python3
"""Project the canonical catalog into Shifter's native event-content bundle."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from typing import Any
from urllib.parse import quote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
CATALOG_MODULE_PATH = ROOT / "challenges" / "catalog.py"
SPEC = importlib.util.spec_from_file_location("cinder_delivery_catalog", CATALOG_MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load challenge catalog module")
catalog_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(catalog_module)

PRIZE_POLICY_MODULE_PATH = ROOT / "ctfd" / "prize_policy.py"
PRIZE_POLICY_SPEC = importlib.util.spec_from_file_location(
    "cinder_prize_policy", PRIZE_POLICY_MODULE_PATH
)
if PRIZE_POLICY_SPEC is None or PRIZE_POLICY_SPEC.loader is None:
    raise RuntimeError("cannot load prize policy module")
prize_policy_module = importlib.util.module_from_spec(PRIZE_POLICY_SPEC)
PRIZE_POLICY_SPEC.loader.exec_module(prize_policy_module)

NATIVE_CONTRACT = "shifter-ctf-content/v1"
PLATFORM_DIFFICULTY = {
    "easy": "easy",
    "medium": "medium",
    "hard": "hard",
    "expert": "expert",
    "elite": "expert",
}


class CatalogImportError(ValueError):
    """The catalog cannot be projected safely into an event bundle."""


def _scorer_origin(value: str, *, allow_loopback_http: bool = False) -> str:
    parsed = urlsplit(value)
    allowed_http = allow_loopback_http and parsed.scheme == "http" and parsed.hostname in {
        "127.0.0.1", "localhost", "::1",
    }
    if (
        (parsed.scheme != "https" and not allowed_http)
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise CatalogImportError("scorer origin must be an HTTPS URL without credentials, query, or fragment")
    return value.rstrip("/")


def build_event_bundle(
    catalog: dict[str, Any],
    *,
    scorer_origin: str,
    allow_loopback_http: bool = False,
) -> dict[str, Any]:
    """Build the transient native bundle without copying solution material.

    Runtime capabilities, rather than scoreboard solves, gate the campaign's
    alternative routes. Cards therefore remain visible in the event UI and the
    range-owned scorer decides whether submitted evidence completes a card.
    """

    catalog_module.validate_catalog(catalog)
    scorer = _scorer_origin(scorer_origin, allow_loopback_http=allow_loopback_http)
    challenges: list[dict[str, Any]] = []
    order = 0
    for phase_name, phase in catalog["phases"].items():
        for operation in phase["operations"]:
            category = f"{phase['title']} - {operation['chapter']}"
            for card in operation["cards"]:
                order += 1
                objective = quote(card["id"].lower(), safe=".-")
                challenges.append({
                    "id": card["id"].lower(),
                    "name": f"{card['id']}: {card['title']}",
                    "description": card["description"],
                    "category": category,
                    "points": card["points"],
                    "difficulty": PLATFORM_DIFFICULTY[card["difficulty"]],
                    "order": order,
                    "flags": [{
                        "type": "http",
                        "url": f"{scorer}/v1/objectives/{objective}/verify",
                        "method": "POST",
                        "timeout": 10,
                        "headers": {
                            "X-Cinder-Catalog-Revision": catalog["revision"],
                        },
                        "order": 0,
                    }],
                    "hints": [
                        {"text": text, "penalty": 0, "order": hint_order}
                        for hint_order, text in enumerate(card["hints"], start=1)
                    ],
                    # Alternative route and capability prerequisites are enforced
                    # by range-owned evidence. Flattening them into an AND-only UI
                    # graph would change the campaign, so all cards remain visible.
                    "prerequisites": [],
                    "visibility": "visible",
                })
    if len(challenges) != catalog["summary"]["card_count"]:
        raise CatalogImportError("event bundle card count does not match catalog")
    return {
        "contract": NATIVE_CONTRACT,
        "scenario_id": "cinder-typhoon",
        "challenges": challenges,
    }


def validate_projection(catalog: dict[str, Any], bundle: dict[str, Any]) -> None:
    """Prove card IDs, text, scores, hints, order, and revision are unchanged."""

    catalog_module.validate_catalog(catalog)
    if not isinstance(bundle, dict) or set(bundle) != {"contract", "scenario_id", "challenges"}:
        raise CatalogImportError("event bundle has invalid top-level fields")
    if bundle["contract"] != NATIVE_CONTRACT or bundle["scenario_id"] != "cinder-typhoon":
        raise CatalogImportError("event bundle identity is invalid")
    expected_cards = catalog_module.catalog_cards(catalog)
    rows = bundle["challenges"]
    if not isinstance(rows, list) or len(rows) != len(expected_cards):
        raise CatalogImportError("event bundle does not contain the complete catalog")
    for order, (card, row) in enumerate(zip(expected_cards, rows, strict=True), start=1):
        if row.get("id") != card["id"].lower():
            raise CatalogImportError(f"{card['id']}: event ID drift")
        if row.get("name") != f"{card['id']}: {card['title']}":
            raise CatalogImportError(f"{card['id']}: event title drift")
        if row.get("description") != card["description"] or row.get("points") != card["points"]:
            raise CatalogImportError(f"{card['id']}: event text or score drift")
        if row.get("difficulty") != PLATFORM_DIFFICULTY[card["difficulty"]] or row.get("order") != order:
            raise CatalogImportError(f"{card['id']}: event difficulty or order drift")
        if [hint.get("text") for hint in row.get("hints", [])] != card["hints"]:
            raise CatalogImportError(f"{card['id']}: event hint drift")
        if any(hint.get("penalty") != 0 for hint in row["hints"]):
            raise CatalogImportError(f"{card['id']}: event hint penalty drift")
        flags = row.get("flags", [])
        if len(flags) != 1 or flags[0].get("headers") != {
            "X-Cinder-Catalog-Revision": catalog["revision"],
        }:
            raise CatalogImportError(f"{card['id']}: scorer revision binding is absent")
        if row.get("prerequisites") != [] or row.get("visibility") != "visible":
            raise CatalogImportError(f"{card['id']}: UI visibility contract changed")


def canonical_json_bytes(value: dict[str, Any]) -> bytes:
    """Encode an artifact deterministically for digest binding and publication."""

    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def artifact_digest(value: dict[str, Any]) -> str:
    """Return the digest identifier for the exact published JSON bytes."""

    return f"sha256:{hashlib.sha256(canonical_json_bytes(value)).hexdigest()}"


def write_private_json(path: Path, value: dict[str, Any]) -> None:
    """Atomically write one JSON artifact with owner-only permissions."""

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(canonical_json_bytes(value))
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=catalog_module.CATALOG_PATH)
    parser.add_argument("--scorer-origin", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prize-policy-output", type=Path)
    parser.add_argument("--allow-loopback-http", action="store_true")
    arguments = parser.parse_args()
    if (
        arguments.prize_policy_output is not None
        and arguments.prize_policy_output.resolve() == arguments.output.resolve()
    ):
        parser.error("content and prize-policy outputs must be different paths")
    catalog = catalog_module.load_catalog(arguments.catalog)
    bundle = build_event_bundle(
        catalog,
        scorer_origin=arguments.scorer_origin,
        allow_loopback_http=arguments.allow_loopback_http,
    )
    validate_projection(catalog, bundle)
    bundle_digest = artifact_digest(bundle)
    policy = None
    if arguments.prize_policy_output is not None:
        policy = prize_policy_module.build_policy(catalog, bundle_digest)
    write_private_json(arguments.output, bundle)
    if arguments.prize_policy_output is not None and policy is not None:
        write_private_json(arguments.prize_policy_output, policy)
    result = {
        "catalog_revision": catalog["revision"],
        "challenge_count": len(bundle["challenges"]),
        "content_bundle_digest": bundle_digest,
        "score_total": sum(row["points"] for row in bundle["challenges"]),
    }
    if policy is not None:
        result["prize_policy_digest"] = artifact_digest(policy)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
