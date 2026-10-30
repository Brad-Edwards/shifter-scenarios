#!/usr/bin/env python3
"""Validate and report the four distinct Cinder Typhoon QA layers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "tests" / "qa-status.json"
LAYER_IDS = (
    "service_contract",
    "known_solution_acceptance",
    "provenance_and_surface",
    "blind_human_agent_playtest",
)
IMPLEMENTATION_STATES = {"complete", "partial", "not_started"}
CANDIDATE_STATES = {"passed", "failed", "not_run"}
AUTOMATED_NON_CLAIMS = {
    "human discovery",
    "fairness",
    "participant understanding",
    "difficulty",
    "duration",
}
LAYER_KEYS = {
    "title",
    "purpose",
    "method",
    "implementation_status",
    "candidate_status",
    "evidence_visibility",
    "evidence",
    "supports",
    "does_not_support",
    "blocking_issues",
}


class QAStatusError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise QAStatusError(message)


def string_list(value: Any, context: str, *, allow_empty: bool = False) -> None:
    require(isinstance(value, list), f"{context}: array required")
    require(allow_empty or bool(value), f"{context}: at least one value required")
    require(all(isinstance(item, str) and item for item in value), f"{context}: non-empty strings required")
    require(len(value) == len(set(value)), f"{context}: duplicate values")


def load_status(path: Path = STATUS_PATH) -> dict[str, Any]:
    value = json.loads(path.read_text())
    require(isinstance(value, dict), "status: object required")
    require(set(value) == {"schema_version", "overall_status", "layers"}, "status: unexpected or missing keys")
    require(value["schema_version"] == 1, "status: schema_version must be 1")
    require(value["overall_status"] in {"not_release_qualified", "release_qualified"}, "status: invalid overall_status")
    layers = value["layers"]
    require(isinstance(layers, dict) and set(layers) == set(LAYER_IDS), "status: exactly four QA layers required")

    for layer_id in LAYER_IDS:
        layer = layers[layer_id]
        context = f"layers.{layer_id}"
        require(isinstance(layer, dict) and set(layer) == LAYER_KEYS, f"{context}: unexpected or missing keys")
        require(all(isinstance(layer[name], str) and layer[name] for name in ("title", "purpose")), f"{context}: title and purpose required")
        require(layer["method"] in {"automated", "human_plus_agent"}, f"{context}: invalid method")
        require(layer["implementation_status"] in IMPLEMENTATION_STATES, f"{context}: invalid implementation_status")
        require(layer["candidate_status"] in CANDIDATE_STATES, f"{context}: invalid candidate_status")
        require(layer["evidence_visibility"] == "operator_only", f"{context}: evidence must be operator-only")
        string_list(layer["evidence"], f"{context}.evidence", allow_empty=True)
        string_list(layer["supports"], f"{context}.supports")
        string_list(layer["does_not_support"], f"{context}.does_not_support")
        issues = layer["blocking_issues"]
        require(isinstance(issues, list), f"{context}.blocking_issues: array required")
        require(all(isinstance(issue, int) and not isinstance(issue, bool) and issue > 0 for issue in issues), f"{context}.blocking_issues: positive issue numbers required")
        require(len(issues) == len(set(issues)), f"{context}.blocking_issues: duplicate issues")
        if layer["method"] == "automated":
            require(AUTOMATED_NON_CLAIMS <= set(layer["does_not_support"]), f"{context}: automated evidence overclaims human outcomes")

    blind = layers["blind_human_agent_playtest"]
    require(set(blind["supports"]) >= AUTOMATED_NON_CLAIMS, "blind playtest must own human-outcome claims")

    qualified = all(
        layer["implementation_status"] == "complete"
        and layer["candidate_status"] == "passed"
        and not layer["blocking_issues"]
        for layer in layers.values()
    )
    require((value["overall_status"] == "release_qualified") == qualified, "overall_status disagrees with layer evidence")

    for evidence in layers["known_solution_acceptance"]["evidence"]:
        require((ROOT / evidence).is_file(), f"known-solution evidence missing: {evidence}")
    return value


def report(value: dict[str, Any]) -> None:
    print(f"overall: {value['overall_status']}")
    for layer_id in LAYER_IDS:
        layer = value["layers"][layer_id]
        blockers = ",".join(f"#{issue}" for issue in layer["blocking_issues"]) or "none"
        print(
            f"{layer_id}: implementation={layer['implementation_status']} "
            f"candidate={layer['candidate_status']} blockers={blockers}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", type=Path, default=STATUS_PATH)
    parser.add_argument("--require-release-qualified", action="store_true")
    arguments = parser.parse_args()
    value = load_status(arguments.status)
    report(value)
    if arguments.require_release_qualified and value["overall_status"] != "release_qualified":
        print("release gate: FAIL: all four QA layers require passing candidate evidence")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
