#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DESIGN_ROOT = ROOT.parent.parent
REQUIRED = {
    "id",
    "title",
    "description",
    "difficulty",
    "points",
    "hints",
    "prerequisites",
    "atlas_rows",
    "flag",
    "carrier",
    "participant_surface",
    "apply_handler",
    "validate_handler",
    "reset_handler",
}
FLAG = re.compile(r"FLAG\{[0-9a-f]{16}\}")
IN_WORLD_META = re.compile(
    r"\b(?:ctf|qa|shifter|challenge|participant|player|tester)\b", re.IGNORECASE
)


def expected_order() -> list[str]:
    text = (DESIGN_ROOT / "operation-allocation.md").read_text(encoding="utf-8")
    return re.findall(r"^- `(kep-m\d{2}-[a-z])`$", text, re.MULTILINE)


def expected_ids() -> set[str]:
    return set(expected_order())


def load_records() -> tuple[list[dict[str, object]], list[Path]]:
    paths = sorted((ROOT / "modules").glob("m??/operations.json"))
    records: list[dict[str, object]] = []
    for path in paths:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, list):
            raise AssertionError(f"{path}: root must be an array")
        records.extend(value)
    return records, paths


def main() -> None:
    records, paths = load_records()
    assert len(paths) == 10, f"expected 10 module catalogs, found {len(paths)}"
    assert len(records) == 134, f"expected 134 operations, found {len(records)}"
    ids = [str(record.get("id", "")) for record in records]
    assert len(ids) == len(set(ids)), "operation IDs are not unique"
    assert set(ids) == expected_ids(), "module operation IDs differ from the design"

    flags: list[str] = []
    for record in records:
        missing = REQUIRED - set(record)
        assert not missing, f"{record.get('id')}: missing {sorted(missing)}"
        assert record["difficulty"] in {"Accessible", "Intermediate", "Advanced", "Expert"}
        assert isinstance(record["points"], int) and record["points"] > 0
        assert isinstance(record["hints"], list) and len(record["hints"]) == 3
        assert all(isinstance(item, str) and item.strip() for item in record["hints"])
        board_text = [str(record["title"]), str(record["description"]), *record["hints"]]
        assert not any(IN_WORLD_META.search(item) for item in board_text), (
            f"{record['id']}: participant board prose breaks the campaign frame"
        )
        assert isinstance(record["prerequisites"], list)
        board_prerequisites = record.get("board_prerequisites", record["prerequisites"])
        assert isinstance(board_prerequisites, list)
        assert isinstance(record["atlas_rows"], list)
        flag = str(record["flag"])
        assert FLAG.fullmatch(flag), f"{record['id']}: invalid flag"
        operation_id = str(record["id"])
        assert record["apply_handler"] == f"apply.sh {operation_id}"
        assert record["validate_handler"] == f"validate.sh {operation_id}"
        assert record["reset_handler"] == f"reset.sh {operation_id}"
        flags.append(flag)
    assert len(flags) == len(set(flags)), "flags are not unique"

    known = set(ids)
    assert all(
        str(item) in known
        for record in records
        for item in record.get("board_prerequisites", record["prerequisites"])
    ), "board prerequisites reference unknown operations"
    graph = {
        str(record["id"]): [str(item) for item in record["prerequisites"]]
        for record in records
    }
    assert all(item in known for values in graph.values() for item in values)
    state: dict[str, int] = {}

    def visit(node: str) -> None:
        if state.get(node) == 1:
            raise AssertionError(f"prerequisite cycle at {node}")
        if state.get(node) == 2:
            return
        state[node] = 1
        for parent in graph[node]:
            visit(parent)
        state[node] = 2

    for operation in graph:
        visit(operation)

    authored_order = expected_order()
    assert len(authored_order) == len(set(authored_order)) == len(records), (
        "operation allocation must contain every operation exactly once"
    )
    position = {operation: index for index, operation in enumerate(authored_order)}
    inversions = [
        (operation, prerequisite)
        for operation in authored_order
        for prerequisite in graph[operation]
        if position[prerequisite] >= position[operation]
    ]
    assert not inversions, f"authored board order precedes prerequisites: {inversions}"

    for module in sorted((ROOT / "modules").glob("m??")):
        for name in ("apply.sh", "validate.sh", "reset.sh", "qa.md", "facilitator.md"):
            path = module / name
            assert path.is_file(), f"{module}: missing {name}"
            if path.suffix == ".sh":
                mode = os.stat(path).st_mode
                assert mode & stat.S_IXUSR, f"{path}: entrypoint is not executable"

    subprocess.run(["ruby", str(DESIGN_ROOT / "validate-design.rb")], check=True)
    print("campaign-start static validation passed: 134 operations, flags, and acyclic prerequisites")


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, KeyError, TypeError, ValueError) as error:
        print(f"campaign-start validation failed: {error}", file=sys.stderr)
        raise SystemExit(1)
