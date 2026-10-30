#!/usr/bin/env python3
"""Compare an observed participant surface with its authored manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from validate import load, validate


def keyed(items: list[dict[str, Any]], keys: tuple[str, ...]) -> dict[tuple[Any, ...], dict[str, Any]]:
    return {tuple(item[key] for key in keys): item for item in items}


def compare(authored: dict[str, Any], observed: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in ("phase", "state"):
        if authored[field] != observed[field]:
            errors.append(f"{field}: expected {authored[field]!r}, observed {observed[field]!r}")
    for field in ("user", "uid", "group", "gid", "groups", "home", "workdir"):
        if authored["participant"][field] != observed["participant"].get(field):
            errors.append(
                f"participant.{field}: expected {authored['participant'][field]!r}, "
                f"observed {observed['participant'].get(field)!r}"
            )
    security = observed["security"]
    for field, expected in {
        "unprivileged": True,
        "docker_socket_readable": False,
        "operator_tests_visible": False,
    }.items():
        if security.get(field) is not expected:
            errors.append(f"security.{field}: expected {expected!r}, observed {security.get(field)!r}")

    observed_roots = {item["path"]: item for item in observed["filesystem"]["roots"]}
    expected_root_paths = {item["path"] for item in authored["filesystem"]["roots"]}
    for root_path in sorted(set(observed_roots) - expected_root_paths):
        errors.append(f"unexpected filesystem root observation: {root_path}")
    for expected_root in authored["filesystem"]["roots"]:
        root_path = expected_root["path"]
        actual_root = observed_roots.get(root_path)
        if actual_root is None:
            errors.append(f"filesystem root missing: {root_path}")
            continue
        for item in actual_root.get("errors", []):
            errors.append(f"filesystem observation error at {item['path']}: {item['error']}")
        expected_entries = {item["path"]: item for item in expected_root["entries"]}
        actual_entries = {item["path"]: item for item in actual_root["entries"]}
        for path in sorted(set(expected_entries) - set(actual_entries)):
            errors.append(f"{root_path}: missing entry {path}")
        for path in sorted(set(actual_entries) - set(expected_entries)):
            errors.append(f"{root_path}: unexpected entry {path}")
        for path in sorted(set(expected_entries) & set(actual_entries)):
            expected_entry = expected_entries[path]
            actual_entry = actual_entries[path]
            for field in ("type", "mode", "owner", "group", "size", "sha256", "target"):
                if field in expected_entry and expected_entry[field] != actual_entry.get(field):
                    errors.append(
                        f"{root_path}/{path} {field}: expected {expected_entry[field]!r}, "
                        f"observed {actual_entry.get(field)!r}"
                    )

    forbidden = {item["path"]: item for item in observed["filesystem"]["forbidden_paths"]}
    expected_forbidden_paths = {item["path"] for item in authored["filesystem"]["forbidden_paths"]}
    for path in sorted(set(forbidden) - expected_forbidden_paths):
        errors.append(f"unexpected forbidden-path observation: {path}")
    for expected_path in authored["filesystem"]["forbidden_paths"]:
        path = expected_path["path"]
        item = forbidden.get(path)
        if item is None:
            errors.append(f"forbidden path not checked: {path}")
        else:
            for field in ("visible", "readable"):
                if item.get(field) is not expected_path[field]:
                    errors.append(
                        f"forbidden path {path} {field}: expected {expected_path[field]!r}, "
                        f"observed {item.get(field)!r}"
                    )

    expected_tools = {item["name"]: item for item in authored["tools"]}
    actual_tools = {item["name"]: item for item in observed["tools"]}
    for name in sorted(set(actual_tools) - set(expected_tools)):
        errors.append(f"unexpected tool observation: {name}")
    for name, expected_tool in expected_tools.items():
        actual = actual_tools.get(name)
        if actual is None:
            errors.append(f"tool not observed: {name}")
        elif actual.get("path") != expected_tool["path"] or not actual.get("executable"):
            errors.append(f"tool {name}: expected executable {expected_tool['path']}, observed {actual}")

    for section, keys in (("dns", ("name",)), ("listeners", ("host", "port"))):
        expected_items = keyed(authored["network"][section], keys)
        actual_items = keyed(observed["network"][section], keys)
        for key in sorted(set(expected_items) - set(actual_items)):
            errors.append(f"network.{section}: missing observation {key}")
        for key in sorted(set(actual_items) - set(expected_items)):
            errors.append(f"network.{section}: unexpected observation {key}")
        for key in sorted(set(expected_items) & set(actual_items)):
            expected_item = expected_items[key]
            actual_item = actual_items[key]
            field = "addresses" if section == "dns" else "reachable"
            if expected_item[field] != actual_item.get(field):
                errors.append(
                    f"network.{section} {key} {field}: expected {expected_item[field]!r}, "
                    f"observed {actual_item.get(field)!r}"
                )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("authored", type=Path)
    parser.add_argument("observed", type=Path)
    arguments = parser.parse_args()
    authored = load(arguments.authored)
    observed = json.loads(arguments.observed.read_text())
    validate(observed)
    failures = compare(authored, observed)
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print(f"PASS: {authored['phase']} participant surface matches authored manifest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
