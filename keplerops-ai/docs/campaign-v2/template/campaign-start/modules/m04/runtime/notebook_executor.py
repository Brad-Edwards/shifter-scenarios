#!/usr/bin/env python3
"""Execute Orion privacy-analysis notebooks under a narrow data-only contract."""

from __future__ import annotations

import argparse
import ast
import builtins
import json
import math
import statistics
from pathlib import Path
from typing import Any


ALLOWED_IMPORTS = {"math"}
FORBIDDEN_NAMES = {"breakpoint", "compile", "eval", "exec", "globals", "input", "locals", "open", "vars"}


def validate_source(source: str, index: int) -> None:
    tree = ast.parse(source, filename=f"notebook-cell-{index}", mode="exec")
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            raise ValueError(f"cell {index} uses a private runtime attribute")
        if isinstance(node, ast.Name) and (node.id.startswith("__") or node.id in FORBIDDEN_NAMES):
            raise ValueError(f"cell {index} uses a forbidden runtime name")


def limited_import(name: str, globals=None, locals=None, fromlist=(), level=0):
    root = name.split(".", 1)[0]
    if level or root not in ALLOWED_IMPORTS:
        raise ImportError(f"notebook import is not permitted: {name}")
    return builtins.__import__(name, globals, locals, fromlist, level)


def notebook_namespace() -> dict[str, Any]:
    safe_builtins = {
        name: getattr(builtins, name)
        for name in (
            "abs", "all", "any", "bool", "dict", "enumerate", "filter", "float",
            "int", "len", "list", "map", "max", "min", "range", "reversed",
            "round", "set", "sorted", "str", "sum", "tuple", "zip",
        )
    }
    safe_builtins["__import__"] = limited_import
    return {
        "__builtins__": safe_builtins,
        "math": math,
        "statistics": statistics,
    }


def load_notebook(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("nbformat") != 4 or not isinstance(document.get("cells"), list):
        raise ValueError("a version 4 Jupyter notebook is required")
    return document


def execute_definitions(path: Path) -> dict[str, Any]:
    namespace = notebook_namespace()
    for index, cell in enumerate(load_notebook(path)["cells"]):
        if cell.get("cell_type") != "code":
            continue
        source = "".join(cell.get("source") or [])
        if not source.strip():
            continue
        if any(line.lstrip().startswith(("!", "%")) for line in source.splitlines()):
            raise ValueError(f"cell {index} contains a shell or notebook magic")
        validate_source(source, index)
        exec(compile(source, f"{path.name}:cell-{index}", "exec"), namespace)
    return namespace


def numeric_score(function, prediction: dict[str, Any]) -> float:
    value = float(function(prediction))
    if not math.isfinite(value):
        raise ValueError("membership_score returned a non-finite value")
    return value


def score_rows(namespace: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    function = namespace.get("membership_score")
    if not callable(function):
        raise ValueError("notebook must define membership_score(prediction)")
    return [
        {
            **{key: value for key, value in row.items() if key != "prediction"},
            "score": numeric_score(function, row["prediction"]),
        }
        for row in rows
    ]


def run_calibration(namespace: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    rows = score_rows(namespace, payload["rows"])
    chooser = namespace.get("choose_threshold")
    if not callable(chooser):
        raise ValueError("notebook must define choose_threshold(fit_rows)")
    fit_rows = [row for row in rows if row.get("partition") == "fit"]
    threshold = float(chooser(fit_rows))
    if not math.isfinite(threshold):
        raise ValueError("choose_threshold returned a non-finite value")
    return {"threshold": threshold, "rows": rows}


def run_individual(namespace: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    rows = score_rows(namespace, payload["rows"])
    selector = namespace.get("select_individual")
    if not callable(selector):
        raise ValueError("notebook must define select_individual(scored_rows)")
    result = selector(rows)
    if not isinstance(result, dict):
        raise ValueError("select_individual must return a mapping")
    selected = str(result.get("selected_record") or "")
    if selected not in {str(row["case_id"]) for row in rows}:
        raise ValueError("individual selection is invalid")
    return {"selected_record": selected, "rows": rows}


def run_cohort(namespace: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    rows = score_rows(namespace, payload["rows"])
    selector = namespace.get("select_cohort")
    if not callable(selector):
        raise ValueError("notebook must define select_cohort(scored_rows)")
    result = selector(rows)
    if not isinstance(result, dict):
        raise ValueError("select_cohort must return a mapping")
    selected = str(result.get("selected_cohort") or "")
    if selected not in {str(row["cohort"]) for row in rows}:
        raise ValueError("cohort selection is invalid")
    return {"selected_cohort": selected, "rows": rows}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--notebook", type=Path, required=True)
    parser.add_argument("--mode", choices=("calibration", "individual", "cohort"), required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    namespace = execute_definitions(args.notebook)
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    runners = {
        "calibration": run_calibration,
        "individual": run_individual,
        "cohort": run_cohort,
    }
    result = runners[args.mode](namespace, payload)
    args.output.write_text(json.dumps(result, sort_keys=True, separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    main()
