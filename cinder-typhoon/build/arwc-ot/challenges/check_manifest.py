#!/usr/bin/env python3
"""Validate the native OT challenge conversion and asset-retirement contract."""

from __future__ import annotations

import json
import pathlib
import re
import sys
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[4]
MANIFEST = pathlib.Path(__file__).with_name("manifest.json")
EXPECTED_OPERATIONS = {"W17", "W18", "W21", "W25", "W29", "W30", "W33"}
EXPECTED_CHECKS = {"positive", "negative", "reset", "product_evidence"}
EXPECTED_COMPLETION_POLICY = {
    "read_only": True,
    "may_control_process": False,
    "may_create_product_evidence": False,
    "evaluate_after_participant_action": True,
}
ALLOWED_ACTIONS = {"create", "edit", "reuse", "remove"}


def _safe_path(root: pathlib.Path, raw: str) -> pathlib.Path | None:
    path = pathlib.PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        return None
    return root.joinpath(*path.parts)


def _briefs(root: pathlib.Path, operation: str) -> list[dict[str, str]]:
    directory = root / "cinder-typhoon" / "docs" / "design" / "challenges" / operation
    result: list[dict[str, str]] = []
    for path in sorted(directory.glob(f"{operation}.*.md")):
        text = path.read_text()
        heading = re.search(rf"^# ({re.escape(operation)}\.\d+): (.+)$", text, re.MULTILINE)
        difficulty = re.search(
            r"^\| Proposed difficulty \| ([^|]+?) \|$", text, re.MULTILINE
        )
        if not heading or not difficulty:
            raise ValueError(f"cannot read card identity from {path.relative_to(root)}")
        result.append({
            "id": heading.group(1),
            "title": heading.group(2),
            "difficulty": difficulty.group(1),
        })
    return result


def _files(path: pathlib.Path) -> list[pathlib.Path]:
    if path.is_file():
        return [path]
    if not path.exists():
        return []
    return [
        candidate for candidate in path.rglob("*")
        if candidate.is_file() and "__pycache__" not in candidate.parts
    ]


def validate_operation(
    operation: str,
    spec: dict[str, Any],
    root: pathlib.Path,
    allowed_status: set[str],
) -> list[str]:
    errors: list[str] = []
    status = spec.get("status")
    if status not in allowed_status:
        errors.append(f"{operation}: unsupported status {status!r}")
    if not isinstance(spec.get("issue"), int):
        errors.append(f"{operation}: issue must be an integer")
    if not spec.get("native_surfaces"):
        errors.append(f"{operation}: native_surfaces is empty")

    cards = spec.get("cards", [])
    card_ids = [card.get("id") for card in cards]
    if len(card_ids) != len(set(card_ids)):
        errors.append(f"{operation}: duplicate card id")
    for card in cards:
        if not card.get("work"):
            errors.append(f"{card.get('id', operation)}: preserved work is empty")

    checks = set(spec.get("required_checks", []))
    if checks != EXPECTED_CHECKS:
        errors.append(
            f"{operation}: required_checks must be {sorted(EXPECTED_CHECKS)}"
        )

    asset_root_raw = spec.get("asset_root", "")
    asset_root = _safe_path(root, asset_root_raw)
    if asset_root is None:
        errors.append(f"{operation}: unsafe asset_root {asset_root_raw!r}")

    assets = spec.get("assets", [])
    changed_participant_assets = 0
    owned_paths: set[pathlib.Path] = set()
    for asset in assets:
        raw = asset.get("path", "")
        path = _safe_path(root, raw)
        if path is None:
            errors.append(f"{operation}: unsafe asset path {raw!r}")
            continue
        action = asset.get("action")
        if action not in ALLOWED_ACTIONS:
            errors.append(f"{operation}: unsupported asset action {action!r} for {raw}")
        if asset.get("owner") != operation:
            errors.append(f"{operation}: asset {raw} has a different owner")
        if asset.get("participant_facing") and action in {"create", "edit", "remove"}:
            changed_participant_assets += 1
        if path in owned_paths:
            errors.append(f"{operation}: duplicate asset {raw}")
        owned_paths.add(path)

        if status == "implemented":
            if action == "remove" and path.exists():
                errors.append(f"{operation}: retired asset still exists: {raw}")
            if action in {"create", "edit", "reuse"} and not path.is_file():
                errors.append(f"{operation}: owned asset is missing: {raw}")

    if changed_participant_assets == 0:
        errors.append(f"{operation}: no participant-facing asset change is planned")

    if status == "implemented" and asset_root is not None:
        expected = {
            path for path in owned_paths
            if path.is_relative_to(asset_root)
        }
        actual = set(_files(asset_root))
        for path in sorted(actual - expected):
            errors.append(
                f"{operation}: unowned asset under asset_root: {path.relative_to(root)}"
            )

        for retirement in spec.get("retirements", []):
            mode = retirement.get("mode")
            if mode == "delete":
                raw = retirement.get("path", "")
                path = _safe_path(root, raw)
                if path is None:
                    errors.append(f"{operation}: unsafe retirement path {raw!r}")
                elif path.exists():
                    errors.append(f"{operation}: retired path still exists: {raw}")
            elif mode == "remove_markers":
                locations: list[pathlib.Path] = []
                for raw in retirement.get("locations", []):
                    path = _safe_path(root, raw)
                    if path is None:
                        errors.append(f"{operation}: unsafe retirement location {raw!r}")
                    else:
                        locations.extend(_files(path))
                for marker in retirement.get("markers", []):
                    for path in locations:
                        try:
                            present = marker in path.read_text()
                        except (UnicodeDecodeError, OSError):
                            continue
                        if present:
                            errors.append(
                                f"{operation}: retired marker {marker!r} remains in "
                                f"{path.relative_to(root)}"
                            )
            else:
                errors.append(f"{operation}: unsupported retirement mode {mode!r}")

    return errors


def validate_manifest(data: dict[str, Any], root: pathlib.Path = ROOT) -> list[str]:
    errors: list[str] = []
    if data.get("schema") != "arwc.native-ot-challenges/v1":
        errors.append("unsupported manifest schema")
    if data.get("completion_policy") != EXPECTED_COMPLETION_POLICY:
        errors.append("completion policy may only read product evidence after participant action")

    operations = data.get("operations", {})
    if set(operations) != EXPECTED_OPERATIONS:
        errors.append(
            f"operations must be exactly {sorted(EXPECTED_OPERATIONS)}"
        )
    allowed_status = set(data.get("allowed_status", []))
    if allowed_status != {"planned", "implemented"}:
        errors.append("allowed_status must be planned and implemented")

    all_cards: list[str] = []
    all_assets: dict[str, str] = {}
    for operation, spec in operations.items():
        errors.extend(validate_operation(operation, spec, root, allowed_status))
        cards = spec.get("cards", [])
        all_cards.extend(card.get("id", "") for card in cards)
        try:
            briefs = _briefs(root, operation)
        except ValueError as error:
            errors.append(str(error))
        else:
            declared = [
                {key: card.get(key) for key in ("id", "title", "difficulty")}
                for card in cards
            ]
            if declared != briefs:
                errors.append(f"{operation}: card titles or difficulties differ from briefs")

        for asset in spec.get("assets", []):
            raw = asset.get("path", "")
            if raw in all_assets:
                errors.append(
                    f"asset {raw} is owned by both {all_assets[raw]} and {operation}"
                )
            all_assets[raw] = operation

    if len(all_cards) != 23 or len(all_cards) != len(set(all_cards)):
        errors.append("the conversion must contain 23 unique cards")
    return errors


def main() -> int:
    data = json.loads(MANIFEST.read_text())
    errors = validate_manifest(data)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("ARWC native OT challenge manifest is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
