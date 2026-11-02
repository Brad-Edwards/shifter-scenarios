"""Build and validate the operator-only Cinder Typhoon prize-policy sidecar."""

from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "docs" / "design" / "event-prize-policy.schema.json"
POLICY_ID = "cinder-typhoon-event-prizes"
STAGES = ("training", "keplerops", "arwc")
STAGE_TITLES = {
    "training": "Training",
    "keplerops": "KeplerOps",
    "arwc": "Alterra Regional Water Company",
}
CONTENT_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
CATALOG_REVISION = re.compile(r"^[0-9a-f]{64}$")
TOP_LEVEL_FIELDS = {
    "contract",
    "policy_id",
    "catalog",
    "inventory",
    "stages",
    "allocations",
    "evaluation_order",
    "runtime_parameters",
}


class PrizePolicyError(ValueError):
    """The generated prize policy violates the reviewed operator contract."""


@lru_cache(maxsize=1)
def _schema() -> dict[str, Any]:
    value = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PrizePolicyError("prize policy schema is invalid")
    return value


def _required_value(schema: dict[str, Any]) -> Any:
    """Materialize the required fixed value declared by the policy schema."""

    if "const" in schema:
        return deepcopy(schema["const"])
    required = schema.get("required")
    properties = schema.get("properties")
    if not isinstance(required, list) or not isinstance(properties, dict):
        raise PrizePolicyError("prize policy schema does not freeze a required value")
    return {name: _required_value(properties[name]) for name in required}


def _fixed_property(name: str) -> Any:
    properties = _schema().get("properties")
    if not isinstance(properties, dict) or name not in properties:
        raise PrizePolicyError(f"prize policy schema is missing {name}")
    return _required_value(properties[name])


def _catalog_stage_ids(catalog: dict[str, Any]) -> dict[str, list[str]]:
    if (
        catalog.get("schema") != "cinder-typhoon.challenge-delivery/v2"
        or not CATALOG_REVISION.fullmatch(str(catalog.get("revision")))
    ):
        raise PrizePolicyError("catalog identity is invalid")
    phases = catalog.get("phases")
    if not isinstance(phases, dict) or set(phases) != set(STAGES):
        raise PrizePolicyError("catalog phases are incomplete")
    result: dict[str, list[str]] = {}
    seen: set[str] = set()
    for stage in STAGES:
        phase = phases[stage]
        operations = phase.get("operations") if isinstance(phase, dict) else None
        if not isinstance(operations, list):
            raise PrizePolicyError(f"{stage}: catalog operations are invalid")
        source_ids: list[str] = []
        for operation in operations:
            cards = operation.get("cards") if isinstance(operation, dict) else None
            if not isinstance(cards, list):
                raise PrizePolicyError(f"{stage}: catalog cards are invalid")
            for card in cards:
                source_id = card.get("id") if isinstance(card, dict) else None
                if not isinstance(source_id, str):
                    raise PrizePolicyError(f"{stage}: catalog card identity is invalid")
                normalized = source_id.lower()
                if normalized in seen:
                    raise PrizePolicyError(f"duplicate catalog card: {normalized}")
                seen.add(normalized)
                source_ids.append(normalized)
        result[stage] = source_ids
    summary = catalog.get("summary")
    expected_count = summary.get("card_count") if isinstance(summary, dict) else None
    if len(seen) != expected_count:
        raise PrizePolicyError("catalog card count does not match stage membership")
    return result


def policy_slot_ids(allocations: dict[str, Any]) -> list[str]:
    """Return every physical slot ID from the six primary allocations."""

    try:
        result = list(allocations["overall_leaders"]["slot_ids"])
        result.extend(
            slot_id
            for stage_ids in allocations["stage_completion"]["slot_ids"].values()
            for slot_id in stage_ids
        )
        result.extend(item["slot_id"] for item in allocations["bounties"]["awards"])
        result.extend(
            slot_id
            for stage_ids in allocations["stage_draws"]["slot_ids"].values()
            for slot_id in stage_ids
        )
        result.extend(allocations["passport_draw"]["slot_ids"])
        result.extend(allocations["good_citizen"]["slot_ids"])
    except (AttributeError, KeyError, TypeError) as error:
        raise PrizePolicyError("prize allocation shape is invalid") from error
    if not all(isinstance(slot_id, str) and slot_id for slot_id in result):
        raise PrizePolicyError("prize slot identity is invalid")
    return result


def build_policy(catalog: dict[str, Any], content_bundle_digest: str) -> dict[str, Any]:
    """Build the deterministic operator sidecar for one exact content bundle."""

    stage_ids = _catalog_stage_ids(catalog)
    schema_properties = _schema()["properties"]
    policy = {
        "contract": schema_properties["contract"]["const"],
        "policy_id": POLICY_ID,
        "catalog": {
            "schema": catalog.get("schema"),
            "revision": catalog.get("revision"),
            "content_bundle_contract": "shifter-ctf-content/v1",
            "content_bundle_digest": content_bundle_digest,
        },
        "inventory": _fixed_property("inventory"),
        "stages": {
            stage: {
                "title": STAGE_TITLES[stage],
                "close_parameter": f"stage_close_at.{stage}",
                "challenge_source_ids": stage_ids[stage],
            }
            for stage in STAGES
        },
        "allocations": _fixed_property("allocations"),
        "evaluation_order": _fixed_property("evaluation_order"),
        "runtime_parameters": _fixed_property("runtime_parameters"),
    }
    validate_policy(catalog, policy, content_bundle_digest)
    return policy


def validate_policy(
    catalog: dict[str, Any],
    policy: dict[str, Any],
    content_bundle_digest: str,
) -> None:
    """Reject drift, unsafe fields, and any weakening of the reviewed rules."""

    if not CONTENT_DIGEST.fullmatch(content_bundle_digest):
        raise PrizePolicyError("content bundle digest is invalid")
    if not isinstance(policy, dict) or set(policy) != TOP_LEVEL_FIELDS:
        raise PrizePolicyError("prize policy has invalid top-level fields")
    contract = _schema()["properties"]["contract"]["const"]
    if policy["contract"] != contract or policy["policy_id"] != POLICY_ID:
        raise PrizePolicyError("prize policy identity is invalid")

    expected_catalog = {
        "schema": catalog.get("schema"),
        "revision": catalog.get("revision"),
        "content_bundle_contract": "shifter-ctf-content/v1",
        "content_bundle_digest": content_bundle_digest,
    }
    if policy["catalog"] != expected_catalog:
        raise PrizePolicyError("prize policy content binding is invalid")

    expected_stage_ids = _catalog_stage_ids(catalog)
    stages = policy["stages"]
    if not isinstance(stages, dict) or set(stages) != set(STAGES):
        raise PrizePolicyError("prize policy stages are incomplete")
    for stage in STAGES:
        expected_stage = {
            "title": STAGE_TITLES[stage],
            "close_parameter": f"stage_close_at.{stage}",
            "challenge_source_ids": expected_stage_ids[stage],
        }
        if stages[stage] != expected_stage:
            raise PrizePolicyError(f"{stage}: prize policy stage membership is invalid")

    allocations = policy["allocations"]
    if not isinstance(allocations, dict):
        raise PrizePolicyError("prize allocations are invalid")
    slot_ids = policy_slot_ids(allocations)
    if len(slot_ids) != 50 or len(set(slot_ids)) != 50:
        raise PrizePolicyError("prize policy must contain exactly 50 unique slots")
    if allocations != _fixed_property("allocations"):
        raise PrizePolicyError(
            "prize allocation rules differ from the reviewed contract"
        )

    for bounty in allocations["bounties"]["awards"]:
        if bounty["challenge_source_id"] not in expected_stage_ids[bounty["stage"]]:
            raise PrizePolicyError(
                "bounty source ID does not belong to its declared stage"
            )
    if policy["inventory"] != _fixed_property("inventory"):
        raise PrizePolicyError("prize inventory differs from the reviewed contract")
    if policy["evaluation_order"] != _fixed_property("evaluation_order"):
        raise PrizePolicyError(
            "prize evaluation order differs from the reviewed contract"
        )
    if policy["runtime_parameters"] != _fixed_property("runtime_parameters"):
        raise PrizePolicyError(
            "prize runtime parameters differ from the reviewed contract"
        )


__all__ = [
    "POLICY_ID",
    "PrizePolicyError",
    "SCHEMA_PATH",
    "build_policy",
    "policy_slot_ids",
    "validate_policy",
]
