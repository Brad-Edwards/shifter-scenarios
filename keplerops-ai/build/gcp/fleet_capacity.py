#!/usr/bin/env python3
"""Validate and calculate the KeplerOps 200-range capacity envelope."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "keplerops-fleet-capacity/v1"
BASES = {"fleet", "cell", "total_range", "active_range", "busy_participant"}
EVIDENCE = {"planning_bound", "measured"}
TOP_LEVEL_KEYS = {
    "schema_version",
    "evidence_status",
    "ranges",
    "cells",
    "resources",
    "policy",
}
RANGE_KEYS = {"total", "active", "simultaneously_busy", "headroom_percent"}
CELL_KEYS = {"cell_id", "region", "failure_domain", "max_active_ranges"}
RESOURCE_KEYS = {
    "resource",
    "basis",
    "quantity",
    "unit",
    "scope",
    "headroom",
    "evidence",
    "current_limit",
}
POLICY_KEYS = {"forbid_range_scaled_resources", "max_fleet_firewall_rules"}
RANGE_BASES = {"total_range", "active_range"}
REQUIRED_SHARED_RESOURCES = {
    "artifact_repositories",
    "firewall_rules_fixed",
    "gpu_l4",
    "vpc_networks",
}


class CapacityError(ValueError):
    """Raised when a fleet capacity profile is unsafe or malformed."""


def _exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        missing = sorted(expected - set(value))
        unknown = sorted(set(value) - expected)
        raise CapacityError(f"{label} keys mismatch; missing={missing}, unknown={unknown}")


def _positive_int(value: Any, label: str, *, allow_zero: bool = False) -> int:
    minimum = 0 if allow_zero else 1
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise CapacityError(f"{label} must be an integer >= {minimum}")
    return value


def load_profile(path: Path) -> dict[str, Any]:
    try:
        profile = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CapacityError(f"cannot load capacity profile: {exc}") from exc
    if not isinstance(profile, dict):
        raise CapacityError("capacity profile must be a JSON object")
    _exact_keys(profile, TOP_LEVEL_KEYS, "capacity profile")
    if profile["schema_version"] != SCHEMA_VERSION:
        raise CapacityError(f"schema_version must be {SCHEMA_VERSION}")
    if profile["evidence_status"] not in EVIDENCE:
        raise CapacityError("evidence_status must be planning_bound or measured")

    ranges = profile["ranges"]
    if not isinstance(ranges, dict):
        raise CapacityError("ranges must be an object")
    _exact_keys(ranges, RANGE_KEYS, "ranges")
    total = _positive_int(ranges["total"], "ranges.total")
    active = _positive_int(ranges["active"], "ranges.active")
    busy = _positive_int(ranges["simultaneously_busy"], "ranges.simultaneously_busy")
    headroom = _positive_int(ranges["headroom_percent"], "ranges.headroom_percent", allow_zero=True)
    if not busy <= active <= total:
        raise CapacityError("ranges must satisfy simultaneously_busy <= active <= total")
    if headroom > 100:
        raise CapacityError("ranges.headroom_percent must be <= 100")

    cells = profile["cells"]
    if not isinstance(cells, list) or not cells:
        raise CapacityError("cells must be a non-empty list")
    cell_ids: set[str] = set()
    cell_capacity = 0
    for index, cell in enumerate(cells):
        if not isinstance(cell, dict):
            raise CapacityError(f"cells[{index}] must be an object")
        _exact_keys(cell, CELL_KEYS, f"cells[{index}]")
        cell_id = cell["cell_id"]
        if not isinstance(cell_id, str) or not cell_id or cell_id in cell_ids:
            raise CapacityError("cell_id values must be non-empty and unique")
        cell_ids.add(cell_id)
        for key in ("region", "failure_domain"):
            if not isinstance(cell[key], str) or not cell[key]:
                raise CapacityError(f"cells[{index}].{key} must be a non-empty string")
        cell_capacity += _positive_int(cell["max_active_ranges"], f"cells[{index}].max_active_ranges")
    if cell_capacity < active:
        raise CapacityError("cell active-range capacity is below ranges.active")

    resources = profile["resources"]
    if not isinstance(resources, list) or not resources:
        raise CapacityError("resources must be a non-empty list")
    resource_names: set[str] = set()
    for index, resource in enumerate(resources):
        if not isinstance(resource, dict):
            raise CapacityError(f"resources[{index}] must be an object")
        _exact_keys(resource, RESOURCE_KEYS, f"resources[{index}]")
        name = resource["resource"]
        if not isinstance(name, str) or not name or name in resource_names:
            raise CapacityError("resource names must be non-empty and unique")
        resource_names.add(name)
        if resource["basis"] not in BASES:
            raise CapacityError(f"resources[{index}].basis is unsupported")
        _positive_int(resource["quantity"], f"resources[{index}].quantity")
        for key in ("unit", "scope"):
            if not isinstance(resource[key], str) or not resource[key]:
                raise CapacityError(f"resources[{index}].{key} must be a non-empty string")
        if not isinstance(resource["headroom"], bool):
            raise CapacityError(f"resources[{index}].headroom must be boolean")
        if resource["evidence"] not in EVIDENCE:
            raise CapacityError(f"resources[{index}].evidence is unsupported")
        limit = resource["current_limit"]
        if limit is not None:
            _positive_int(limit, f"resources[{index}].current_limit", allow_zero=True)

    policy = profile["policy"]
    if not isinstance(policy, dict):
        raise CapacityError("policy must be an object")
    _exact_keys(policy, POLICY_KEYS, "policy")
    forbidden = policy["forbid_range_scaled_resources"]
    if not isinstance(forbidden, list) or not forbidden or len(forbidden) != len(set(forbidden)):
        raise CapacityError("forbid_range_scaled_resources must be a non-empty unique list")
    if not all(isinstance(item, str) and item in resource_names for item in forbidden):
        raise CapacityError("forbid_range_scaled_resources must reference declared resources")
    if not REQUIRED_SHARED_RESOURCES.issubset(forbidden):
        missing = sorted(REQUIRED_SHARED_RESOURCES - set(forbidden))
        raise CapacityError(f"shared resources missing range-scaling protection: {missing}")
    _positive_int(policy["max_fleet_firewall_rules"], "policy.max_fleet_firewall_rules")
    for resource in resources:
        if resource["resource"] in forbidden and resource["basis"] in RANGE_BASES:
            raise CapacityError(f"{resource['resource']} may not scale per range")
    return profile


def calculate(profile: dict[str, Any]) -> dict[str, Any]:
    ranges = profile["ranges"]
    multipliers = {
        "fleet": 1,
        "cell": len(profile["cells"]),
        "total_range": ranges["total"],
        "active_range": ranges["active"],
        "busy_participant": ranges["simultaneously_busy"],
    }
    headroom_factor = 1 + ranges["headroom_percent"] / 100
    rows = []
    unknown_limits = []
    expansions = []
    planning_bounds = []
    for resource in profile["resources"]:
        demand = resource["quantity"] * multipliers[resource["basis"]]
        required = math.ceil(demand * headroom_factor) if resource["headroom"] else demand
        limit = resource["current_limit"]
        expansion = None if limit is None else max(0, required - limit)
        if limit is None:
            unknown_limits.append(resource["resource"])
        elif expansion:
            expansions.append(resource["resource"])
        if resource["evidence"] != "measured":
            planning_bounds.append(resource["resource"])
        rows.append(
            {
                "resource": resource["resource"],
                "basis": resource["basis"],
                "unit": resource["unit"],
                "scope": resource["scope"],
                "base_demand": demand,
                "required_with_headroom": required,
                "current_limit": limit,
                "quota_expansion": expansion,
                "evidence": resource["evidence"],
            }
        )

    firewall_demand = sum(
        row["required_with_headroom"]
        for row in rows
        if row["resource"].startswith("firewall_rules_")
    )
    maximum = profile["policy"]["max_fleet_firewall_rules"]
    if firewall_demand > maximum:
        raise CapacityError(
            f"firewall rule demand {firewall_demand} exceeds policy maximum {maximum}"
        )

    ready = (
        profile["evidence_status"] == "measured"
        and not planning_bounds
        and not unknown_limits
        and not expansions
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_status": profile["evidence_status"],
        "ranges": ranges,
        "cell_count": len(profile["cells"]),
        "cell_active_capacity": sum(cell["max_active_ranges"] for cell in profile["cells"]),
        "resources": rows,
        "quota_expansions_required": sorted(expansions),
        "quota_limits_unknown": sorted(unknown_limits),
        "planning_bounds": sorted(planning_bounds),
        "readiness": {
            "capacity_proven": ready,
            "reason": (
                "measured demand fits known quotas"
                if ready
                else "planning bounds, unknown quotas, or required expansions remain"
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--profile",
        type=Path,
        default=Path(__file__).with_name("fleet-capacity-profile.json"),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = calculate(load_profile(args.profile))
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
