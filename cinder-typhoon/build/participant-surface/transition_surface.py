#!/usr/bin/env python3
"""Apply a strict earned-transition overlay to an authored surface."""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any


class TransitionSurfaceError(ValueError):
    """The selected transition does not have one exact authored surface."""


def _dynamic_path_pattern(value: dict[str, Any]) -> re.Pattern[str]:
    alphabets = {"uppercase-hex": "[A-F0-9]"}
    return re.compile(
        re.escape(value["prefix"])
        + alphabets[value["alphabet"]]
        + "{" + str(value["length"]) + "}"
        + re.escape(value["suffix"])
    )


def apply_transition_surface(
    authored: dict[str, Any],
    contract: dict[str, Any],
    transition: str,
    observed: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the exact authored surface for one earned transition."""
    if authored.get("phase") != "arwc" or contract.get("phase") != "arwc":
        raise TransitionSurfaceError("earned transitions apply only to ARWC")
    try:
        overlay = contract["transitions"][transition]
    except KeyError as error:
        raise TransitionSurfaceError("the selected transition has no surface contract") from error

    result = deepcopy(authored)
    result["state"] = overlay["state"]
    roots = {item["path"]: item for item in result["filesystem"]["roots"]}
    observed_roots = {
        item["path"]: item
        for item in (observed or {}).get("filesystem", {}).get("roots", [])
    }

    for configured in overlay["additional_entries"]:
        entry = deepcopy(configured)
        root_path = entry.pop("root")
        dynamic = entry.pop("dynamic_path", None)
        root = roots.get(root_path)
        if root is None:
            raise TransitionSurfaceError("transition entry targets an unknown surface root")
        if dynamic is not None:
            if observed is None:
                continue
            actual_root = observed_roots.get(root_path, {})
            pattern = _dynamic_path_pattern(dynamic)
            matches = [
                item["path"]
                for item in actual_root.get("entries", [])
                if pattern.fullmatch(item.get("path", ""))
            ]
            if len(matches) != 1:
                raise TransitionSurfaceError(
                    "transition surface requires exactly one route-specific receipt"
                )
            entry["path"] = matches[0]
        if any(item["path"] == entry["path"] for item in root["entries"]):
            raise TransitionSurfaceError("transition entry duplicates the authored surface")
        root["entries"].append(entry)

    listeners = {
        (item["host"], item["port"]): item
        for item in result["network"]["listeners"]
    }
    for override in overlay["listener_overrides"]:
        key = (override["host"], override["port"])
        if key not in listeners:
            raise TransitionSurfaceError("transition targets an unknown listener probe")
        listeners[key]["reachable"] = override["reachable"]
    return result
