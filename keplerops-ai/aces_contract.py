"""Typed accessors for the KeplerOps modular ACES SDL authority.

This module never reads a pack-local scenario ledger. Provider code, runtime
services, CTFd projection, validators, and tests use these accessors to consume
the expanded ACES scenario or an operational projection derived from it.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

import yaml
from raes import parse_sdl_file


PACK_DIR = Path(__file__).resolve().parent
SDL_RELATIVE_PATH = Path("sdl/keplerops-ai.sdl.yaml")
CHALLENGE_EXTENSION = "x-keplerops:challenge"
MODULE_EXTENSION = "x-keplerops:portfolio-module"


class AcesContractError(ValueError):
    """Raised when the ACES authority cannot produce a required projection."""


@lru_cache(maxsize=32)
def _load_scenario_cached(path: str, signature: tuple[tuple[str, int, int], ...]):
    del signature
    return parse_sdl_file(Path(path))


def load_scenario(pack_dir: str | Path = PACK_DIR):
    """Parse and semantically validate the canonical expanded scenario."""

    root = Path(pack_dir).resolve()
    sdl_root = root / "sdl"
    signature = tuple(
        (str(path.relative_to(sdl_root)), path.stat().st_mtime_ns, path.stat().st_size)
        for path in sorted(sdl_root.rglob("*.sdl.yaml"))
    )
    return _load_scenario_cached(str(root / SDL_RELATIVE_PATH), signature)


def _extensions(behavior: Any) -> dict[str, Any]:
    return behavior.extensions if isinstance(behavior.extensions, dict) else {}


def challenge_contracts(pack_dir: str | Path = PACK_DIR) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for behavior in load_scenario(pack_dir).behavior_specifications.values():
        row = _extensions(behavior).get(CHALLENGE_EXTENSION)
        if not isinstance(row, dict):
            continue
        challenge_id = row.get("challenge_id")
        if not isinstance(challenge_id, str) or challenge_id in result:
            raise AcesContractError("invalid or duplicate ACES challenge contract")
        result[challenge_id] = row
    if len(result) < 60:
        raise AcesContractError("ACES challenge portfolio cannot regress below its 60-item core")
    return result


def module_contracts(pack_dir: str | Path = PACK_DIR) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for behavior in load_scenario(pack_dir).behavior_specifications.values():
        row = _extensions(behavior).get(MODULE_EXTENSION)
        if not isinstance(row, dict):
            continue
        module_id = row.get("module_id")
        if not isinstance(module_id, str) or module_id in result:
            raise AcesContractError("invalid or duplicate ACES portfolio module")
        result[module_id] = row
    if len(result) != 10:
        raise AcesContractError("complete ten-module ACES portfolio required")
    return result


def _content_row(scenario: Any, content_id: str) -> Any:
    matches = [
        row
        for qualified, row in scenario.content.items()
        if qualified == content_id or qualified.endswith(f".{content_id}")
    ]
    if len(matches) != 1:
        raise AcesContractError(f"ACES content dataset {content_id!r} must be unique")
    return matches[0]


def content_contract(
    content_id: str,
    pack_dir: str | Path = PACK_DIR,
) -> dict[str, Any]:
    row = _content_row(load_scenario(pack_dir), content_id)
    if not isinstance(row.text, str) or not row.text.strip():
        raise AcesContractError(f"ACES content dataset {content_id!r} has no text")
    value = yaml.safe_load(row.text)
    if not isinstance(value, dict):
        raise AcesContractError(f"ACES content dataset {content_id!r} is not a mapping")
    return value


def content_contract_bytes(
    content_id: str,
    pack_dir: str | Path = PACK_DIR,
) -> bytes:
    """Return a stable YAML rendering suitable for an evidence export."""

    return yaml.safe_dump(
        content_contract(content_id, pack_dir),
        allow_unicode=True,
        sort_keys=False,
    ).encode("utf-8")


def challenge_content_rows(pack_dir: str | Path = PACK_DIR) -> list[dict[str, Any]]:
    difficulty = {
        "accessible": "easy",
        "intermediate": "medium",
        "advanced": "hard",
        "expert": "insane",
    }
    rows: list[dict[str, Any]] = []
    for challenge_id, item in sorted(challenge_contracts(pack_dir).items()):
        if item.get("implementation_status") == "planned":
            continue
        participant = item.get("participant_copy")
        if not isinstance(participant, dict):
            continue
        rows.append(
            {
                "challenge_id": challenge_id,
                "flag_id": item["flag_id"],
                "title": item["title"],
                "category": participant["category"],
                "difficulty": difficulty[item["difficulty"]],
                "points": item["points"],
                "question": participant["question"],
                "hints": list(participant["hints"]),
                "prerequisites": list(item["prerequisites"]),
            }
        )
    return rows


def flag_rows(pack_dir: str | Path = PACK_DIR) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for challenge_id, item in sorted(challenge_contracts(pack_dir).items()):
        if item.get("implementation_status") == "planned":
            continue
        delivery = item.get("flag_delivery")
        if not isinstance(delivery, dict):
            continue
        source = delivery["source"]
        if isinstance(source, dict):
            source = source.get("name")
        rows.append(
            {
                "challenge_id": challenge_id,
                "flag_id": item["flag_id"],
                "outcome": item["outcome"],
                "source": source,
                "instructions": delivery["instructions"],
                "profiles": list(delivery["profiles"]),
                "evidence": delivery["evidence_id"],
                "delivery": dict(delivery["delivery"]),
            }
        )
    return rows


def _event_rows(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in items:
        proof = item.get("proof")
        event = proof.get("event") if isinstance(proof, dict) else None
        if isinstance(event, dict):
            result.append(dict(event))
    return result


def oracle_projection(pack_dir: str | Path = PACK_DIR) -> dict[str, Any]:
    """Render the proof API's outcome/evidence projection from ACES."""

    modules = sorted(
        module_contracts(pack_dir).values(),
        key=lambda row: int(row["path_step"]["path_step"]),
    )
    challenges = list(challenge_contracts(pack_dir).values())
    outcomes: list[dict[str, Any]] = []
    for row in modules:
        outcome = row["outcome"]
        required_evidence = list(outcome["required_evidence"])
        optional_evidence = list(outcome["optional_evidence"])
        accepted = set(required_evidence) | set(optional_evidence)
        for challenge in challenges:
            if challenge.get("outcome") != outcome["outcome_id"]:
                continue
            proof = challenge.get("proof")
            evidence_id = proof.get("evidence_id") if isinstance(proof, dict) else None
            if isinstance(evidence_id, str) and evidence_id not in accepted:
                optional_evidence.append(evidence_id)
                accepted.add(evidence_id)
        outcomes.append(
            {
                "id": outcome["outcome_id"],
                "required_evidence": required_evidence,
                "optional_evidence": optional_evidence,
            }
        )
    return {
        "schema_version": 1,
        "outcomes": outcomes,
    }


def telemetry_projection(pack_dir: str | Path = PACK_DIR) -> dict[str, Any]:
    policy = content_contract("proof-policy", pack_dir)
    events = _event_rows(
        row
        for row in challenge_contracts(pack_dir).values()
        if row.get("implementation_status") != "planned"
    )
    events.extend(dict(row) for row in policy["supporting_events"])
    event_kinds = [row.get("event_kind") for row in events]
    if len(event_kinds) != len(set(event_kinds)):
        raise AcesContractError("duplicate proof event kind in ACES authority")
    return {
        "schema_version": 1,
        "namespace": list(policy["namespace"]),
        "sink_service": policy["sink_service"],
        "safe_fields": list(policy["safe_fields"]),
        "forbidden_fields": list(policy["forbidden_fields"]),
        "events": events,
        "negative_gates": list(policy["negative_gates"]),
    }


def research_telemetry_contract(pack_dir: str | Path = PACK_DIR) -> dict[str, Any]:
    return content_contract("research-telemetry-contract", pack_dir)


def atlas_technique_catalog(pack_dir: str | Path = PACK_DIR) -> dict[str, Any]:
    return content_contract("atlas-technique-catalog", pack_dir)


def atlas_challenge_design(pack_dir: str | Path = PACK_DIR) -> dict[str, Any]:
    """Return the complete planned ATLAS challenge architecture from ACES."""

    return content_contract("atlas-challenge-design", pack_dir)


def event_bundle_designs(pack_dir: str | Path = PACK_DIR) -> dict[str, dict[str, Any]]:
    """Return the named event bundle designs from the ACES architecture."""

    design = atlas_challenge_design(pack_dir)
    rows = design.get("event_bundle_designs")
    if not isinstance(rows, list):
        raise AcesContractError("ACES event bundle designs are missing")
    bundles: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("bundle_id"), str):
            raise AcesContractError("invalid ACES event bundle design")
        bundle_id = row["bundle_id"]
        if bundle_id in bundles:
            raise AcesContractError(f"duplicate ACES event bundle {bundle_id}")
        bundles[bundle_id] = row
    return bundles


def _dependency_closure(
    seeds: Iterable[str],
    challenges: dict[str, dict[str, Any]],
) -> set[str]:
    selected: set[str] = set()
    stack = list(seeds)
    while stack:
        challenge_id = stack.pop()
        if challenge_id in selected:
            continue
        if challenge_id not in challenges:
            raise AcesContractError(f"unknown challenge id {challenge_id}")
        selected.add(challenge_id)
        stack.extend(challenges[challenge_id].get("prerequisites", []))
    return selected


def _require_realized_selection(
    selected: set[str],
    challenges: dict[str, dict[str, Any]],
    *,
    label: str,
) -> None:
    planned = sorted(
        challenge_id for challenge_id in selected
        if challenges[challenge_id].get("implementation_status") == "planned"
    )
    if planned:
        raise AcesContractError(
            f"{label} selects planned challenge(s): {', '.join(planned)}"
        )


def _selectable_challenge_rows(pack_dir: str | Path = PACK_DIR) -> dict[str, dict[str, Any]]:
    """Return realized challenge contracts plus design-only planned rows."""

    rows = {
        challenge_id: dict(row)
        for challenge_id, row in challenge_contracts(pack_dir).items()
    }
    for row in atlas_challenge_design(pack_dir).get("challenge_designs", []):
        if not isinstance(row, dict) or not isinstance(row.get("challenge_id"), str):
            continue
        challenge_id = row["challenge_id"]
        rows.setdefault(challenge_id, {**row, "implementation_status": "planned"})
    return rows


def event_bundle_selection(
    bundle_id: str,
    pack_dir: str | Path = PACK_DIR,
    *,
    require_realized: bool = True,
) -> set[str]:
    """Resolve an SDL-owned event bundle to canonical challenge ids."""

    challenges = _selectable_challenge_rows(pack_dir)
    bundle = event_bundle_designs(pack_dir).get(bundle_id)
    if bundle is None:
        raise AcesContractError(f"unknown event bundle {bundle_id}")
    if bundle.get("selection") == "all_except":
        excluded = set(bundle.get("excluded_challenges", []))
        if not excluded <= set(challenges):
            raise AcesContractError(f"event bundle {bundle_id} has unknown exclusions")
        selected = set(challenges) - excluded
    elif bundle.get("selection") == "dependency_closure_of_seeds":
        seeds = bundle.get("seed_challenges", [])
        if not isinstance(seeds, list) or not seeds:
            raise AcesContractError(f"event bundle {bundle_id} has invalid seeds")
        selected = _dependency_closure(seeds, challenges)
    else:
        raise AcesContractError(f"event bundle {bundle_id} has invalid selection policy")
    if require_realized:
        _require_realized_selection(selected, challenges, label=f"event bundle {bundle_id}")
    return selected


def custom_challenge_selection(
    challenge_ids: Iterable[str],
    pack_dir: str | Path = PACK_DIR,
    *,
    include_dependencies: bool = True,
    require_realized: bool = True,
) -> set[str]:
    """Resolve an operator custom selection against canonical ACES challenge ids."""

    requested = list(challenge_ids)
    if not requested:
        raise AcesContractError("custom selection requires at least one challenge id")
    challenges = _selectable_challenge_rows(pack_dir)
    selected = (
        _dependency_closure(requested, challenges)
        if include_dependencies else set(requested)
    )
    unknown = sorted(set(selected) - set(challenges))
    if unknown:
        raise AcesContractError(f"unknown challenge id(s): {', '.join(unknown)}")
    if any(not set(challenges[challenge_id].get("prerequisites", [])) <= selected for challenge_id in selected):
        raise AcesContractError("custom selection is not dependency closed")
    if require_realized:
        _require_realized_selection(selected, challenges, label="custom selection")
    return selected


def portfolio_policy(pack_dir: str | Path = PACK_DIR) -> dict[str, Any]:
    return content_contract("portfolio-policy", pack_dir)


def implementation_projection(pack_dir: str | Path = PACK_DIR) -> dict[str, Any]:
    modules = module_contracts(pack_dir)
    challenges = challenge_contracts(pack_dir)
    status_rank = {
        "planned": 0,
        "source-implemented": 1,
        "automated-proven": 2,
        "participant-proven": 3,
    }

    def aggregate_status(module_id: str) -> str:
        selected = [
            row["implementation_status"]
            for row in challenges.values()
            if row.get("module") == module_id
        ]
        if not selected:
            raise AcesContractError(f"module {module_id!r} has no challenge contracts")
        return min(selected, key=status_rank.get)

    return {
        "module_summaries": [
            {
                "module": module_id,
                "status": aggregate_status(module_id),
            }
            for module_id in sorted(modules)
        ],
        "realized_items": [
            {
                "challenge_id": challenge_id,
                "status": row["implementation_status"],
                "evidence": row["proof"]["evidence_id"],
                **dict(row["implementation_evidence"]),
            }
            for challenge_id, row in sorted(challenges.items())
            if isinstance(row.get("implementation_evidence"), dict)
        ],
    }


__all__ = [
    "AcesContractError",
    "SDL_RELATIVE_PATH",
    "atlas_challenge_design",
    "atlas_technique_catalog",
    "challenge_content_rows",
    "challenge_contracts",
    "content_contract",
    "content_contract_bytes",
    "custom_challenge_selection",
    "event_bundle_designs",
    "event_bundle_selection",
    "flag_rows",
    "implementation_projection",
    "load_scenario",
    "module_contracts",
    "oracle_projection",
    "portfolio_policy",
    "research_telemetry_contract",
    "telemetry_projection",
]
