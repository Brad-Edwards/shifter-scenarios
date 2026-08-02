#!/usr/bin/env python3

from __future__ import annotations

import ast
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
    "model_family",
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
MODEL_FAMILIES = {
    "release-risk",
    "assistant",
    "vision-prototype",
    "physical-device",
    "attacker-glm",
    "artifact-defined",
    "none",
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


def documented_model_families() -> dict[str, str]:
    text = (DESIGN_ROOT / "model-and-release-contract.md").read_text(encoding="utf-8")
    match = re.search(
        r"<!-- model-family-allocation:start -->(.*?)<!-- model-family-allocation:end -->",
        text,
        re.DOTALL,
    )
    assert match, "model-family contract lacks the authoritative allocation block"
    allocation: dict[str, str] = {}
    current_family: str | None = None
    for line in match.group(1).splitlines():
        heading = re.fullmatch(r"### `([^`]+)`", line.strip())
        if heading:
            current_family = heading.group(1)
            assert current_family in MODEL_FAMILIES, (
                f"unknown documented model family: {current_family}"
            )
            continue
        for operation_id in re.findall(r"`(kep-m\d{2}-[a-z])`", line):
            assert current_family is not None, (
                f"{operation_id}: allocation appears before a model-family heading"
            )
            assert operation_id not in allocation, (
                f"{operation_id}: documented in more than one model-family allocation"
            )
            allocation[operation_id] = current_family
    return allocation


def validate_assistant_implementation_contract() -> None:
    text = (DESIGN_ROOT / "model-and-release-contract.md").read_text(encoding="utf-8")
    rows = {
        match.group(1): match.group(0)
        for match in re.finditer(r"^\| `([^`]+)` \|.*$", text, re.MULTILINE)
    }
    assistant = rows.get("assistant", "")
    attacker = rows.get("attacker-glm", "")
    for marker in (
        "Vertex",
        "zai-org/glm-5-maas",
        "LiteLLM",
        "workload-identity",
        "range-isolated",
    ):
        assert marker in assistant, f"assistant implementation contract lacks {marker!r}"
    assert "Qwen" not in text and "vLLM" not in assistant, (
        "assistant contract retains the rejected local 7B/vLLM route"
    )
    assert "Cinder" in attacker and "KeplerOps" in attacker, (
        "attacker-glm contract must remain distinct from victim-side Assistant state"
    )


def load_records() -> tuple[list[dict[str, object]], list[Path]]:
    paths = sorted((ROOT / "modules").glob("m??/operations.json"))
    records: list[dict[str, object]] = []
    for path in paths:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, list):
            raise AssertionError(f"{path}: root must be an array")
        records.extend(value)
    return records, paths


def validate_m08_m10_package_contract() -> None:
    source_path = ROOT / "modules" / "m10" / "runtime" / "production_jobs.py"
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(source_path))
    assignment = next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "M08_PACKAGE_MEMBERS"
                for target in node.targets
            )
        ),
        None,
    )
    assert assignment is not None, "m10 lacks the exact M08 package-member contract"
    assert ast.literal_eval(assignment.value) == {
        "config.json",
        "model.safetensors",
        "tokenizer.json",
        "model-card.md",
        "provenance.json",
    }, "m10 M08 package members differ from the signed five-member contract"
    assert "padding='max_length'" in source and "max_length=64" in source, (
        "m10 offline execution must use padding='max_length', max_length=64"
    )
    assert "padding=True" not in source and "max_length=96" not in source, (
        "m10 retains obsolete dynamic-padding or length-96 preprocessing"
    )
    assert '(("original", original), ("student", student))' in source, (
        "m10 must execute both exact accepted packages under one preprocessing contract"
    )


def main() -> None:
    records, paths = load_records()
    assert len(paths) == 10, f"expected 10 module catalogs, found {len(paths)}"
    assert len(records) == 134, f"expected 134 operations, found {len(records)}"
    ids = [str(record.get("id", "")) for record in records]
    assert len(ids) == len(set(ids)), "operation IDs are not unique"
    assert set(ids) == expected_ids(), "module operation IDs differ from the design"

    flags: list[str] = []
    record_model_families: dict[str, str] = {}
    for record in records:
        missing = REQUIRED - set(record)
        assert not missing, f"{record.get('id')}: missing {sorted(missing)}"
        assert record["difficulty"] in {"Accessible", "Intermediate", "Advanced", "Expert"}
        assert record["model_family"] in MODEL_FAMILIES, (
            f"{record['id']}: invalid model_family {record['model_family']!r}"
        )
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
        record_model_families[operation_id] = str(record["model_family"])
        assert record["apply_handler"] == f"apply.sh {operation_id}"
        assert record["validate_handler"] == f"validate.sh {operation_id}"
        assert record["reset_handler"] == f"reset.sh {operation_id}"
        flags.append(flag)
    assert len(flags) == len(set(flags)), "flags are not unique"

    documented_families = documented_model_families()
    assert set(documented_families) == set(ids), (
        "model-family allocation must document every operation exactly once; "
        f"missing={sorted(set(ids) - set(documented_families))}, "
        f"extra={sorted(set(documented_families) - set(ids))}"
    )
    mismatched_families = {
        operation_id: {
            "record": record_model_families[operation_id],
            "contract": documented_families[operation_id],
        }
        for operation_id in ids
        if record_model_families[operation_id] != documented_families[operation_id]
    }
    assert not mismatched_families, (
        f"operation model families differ from the contract: {mismatched_families}"
    )
    validate_assistant_implementation_contract()
    validate_m08_m10_package_contract()

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

    subprocess.run(
        ["ruby", str(ROOT.parent / "network" / "validate-campaign-flows.rb")],
        check=True,
    )
    subprocess.run(["ruby", str(DESIGN_ROOT / "validate-design.rb")], check=True)
    print("campaign-start static validation passed: 134 operations, flags, and acyclic prerequisites")


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, KeyError, TypeError, ValueError) as error:
        print(f"campaign-start validation failed: {error}", file=sys.stderr)
        raise SystemExit(1)
