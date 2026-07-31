#!/usr/bin/env python3
"""Materialize and read back ordinary workflow runs through the Airflow CLI."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

OWNER = "keplerops-company-state"
CONTENT_ID = "company-workflow-state"
DAG_ID = "company_state_orion_release"
RUN_PREFIX = "company-state--"
TERMINAL = {"success", "failed"}


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest_json(value: object) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(canonical_json(value).encode()).hexdigest()


def normalized_time(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return (
        parsed.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def build_plan(path: Path) -> dict[str, Any]:
    # The Airflow image entrypoint supplies its immutable content mount.
    corpus = yaml.safe_load(path.read_text(encoding="utf-8"))  # NOSONAR
    if not isinstance(corpus, dict) or corpus.get("schema_version") != 1:
        raise ValueError("company state must use schema version 1")
    rows = corpus.get("experiments")
    if not isinstance(rows, list) or len(rows) != 3:
        raise ValueError("company workflow state requires exactly three experiments")
    records: list[dict[str, Any]] = []
    for source in sorted(rows, key=lambda row: row["id"]):
        identifier = source["id"]
        if identifier.startswith(("kep-m", "challenge-")):
            raise ValueError("company workflow id uses a challenge namespace")
        projection = {
            "experiment_id": identifier,
            "dag_id": DAG_ID,
            "run_id": RUN_PREFIX + identifier,
            "logical_date": normalized_time(source["started_at"]),
            "terminal_state": (
                "failed" if source["status"] == "abandoned" else "success"
            ),
        }
        records.append(
            {
                **projection,
                "source_digest": digest_json(projection),
                "conf": {
                    "owner": OWNER,
                    "content_id": CONTENT_ID,
                    "experiment": source,
                },
            }
        )
    normalized = [
        {
            "id": row["experiment_id"],
            "object_type": "experiment",
            "source_digest": row["source_digest"],
        }
        for row in records
    ]
    return {
        "schema_version": 1,
        "owner": OWNER,
        "content_id": CONTENT_ID,
        "dag_id": DAG_ID,
        "records": records,
        "record_count": len(records),
        "canonical_digest": digest_json(normalized),
    }


def _run(command: list[str]) -> str:
    return subprocess.run(command, check=True, capture_output=True, text=True).stdout


def list_runs(runner: Callable[[list[str]], str] = _run) -> list[dict[str, Any]]:
    output = runner(["airflow", "dags", "list-runs", DAG_ID, "--output", "json"])
    value = json.loads(output or "[]")
    if not isinstance(value, list):
        raise TypeError("Airflow run readback is invalid")
    return value


def _field(row: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in row:
            return row[name]
    return None


def readback(plan: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    expected = {record["run_id"]: record for record in plan["records"]}
    if len(rows) != len(expected):
        raise RuntimeError(
            "ownership collision: Airflow company DAG contains extra runs"
        )
    observed: list[dict[str, str]] = []
    for row in rows:
        run_id = _field(row, "run_id", "dag_run_id")
        if run_id not in expected:
            raise RuntimeError(f"ownership collision: Airflow run {run_id}")
        record = expected[run_id]
        projection = {
            "experiment_id": record["experiment_id"],
            "dag_id": _field(row, "dag_id") or DAG_ID,
            "run_id": run_id,
            "logical_date": normalized_time(
                _field(row, "logical_date", "execution_date")
            ),
            "terminal_state": _field(row, "state"),
        }
        if projection["terminal_state"] not in TERMINAL:
            raise RuntimeError(f"Airflow company run is not terminal: {run_id}")
        observed.append(
            {
                "id": record["experiment_id"],
                "object_type": "experiment",
                "source_digest": digest_json(projection),
            }
        )
    digest = digest_json(sorted(observed, key=lambda row: row["id"]))
    if digest != plan["canonical_digest"]:
        raise RuntimeError("company-workflow-state native readback digest mismatch")
    return {
        "owner": OWNER,
        "content_id": CONTENT_ID,
        "record_count": len(observed),
        "canonical_digest": digest,
    }


def seed(
    plan: dict[str, Any],
    runner: Callable[[list[str]], str] = _run,
    *,
    timeout_seconds: int = 180,
) -> dict[str, Any]:
    existing = list_runs(runner)
    if existing:
        return readback(plan, existing)
    for record in plan["records"]:
        runner(
            [
                "airflow",
                "dags",
                "trigger",
                DAG_ID,
                "--run-id",
                record["run_id"],
                "--logical-date",
                record["logical_date"],
                "--conf",
                canonical_json(record["conf"]),
            ]
        )
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        rows = list_runs(runner)
        if len(rows) == len(plan["records"]) and all(
            _field(row, "state") in TERMINAL for row in rows
        ):
            return readback(plan, rows)
        time.sleep(1)
    raise RuntimeError("Airflow company runs did not reach terminal states")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("seed", "readback", "plan"))
    parser.add_argument("--company-state", type=Path, required=True)
    args = parser.parse_args()
    plan = build_plan(args.company_state)
    if args.command == "seed":
        result = seed(plan)
    elif args.command == "readback":
        result = readback(plan, list_runs())
    else:
        result = plan
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
