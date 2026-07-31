#!/usr/bin/env python3
"""Render immutable synthetic JSONL inputs to PostgreSQL seed statements."""

from __future__ import annotations

import json
from pathlib import Path

DATASETS = Path("/datasets")
BASELINE = "baseline"

def quote(value: object) -> str:
    if not isinstance(value, str) or "\x00" in value:
        raise ValueError("seed value must be bounded text")
    return "'" + value.replace("'", "''") + "'"


def rows(path: Path) -> list[dict[str, str]]:
    parsed = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    if any(not isinstance(row, dict) for row in parsed):
        raise ValueError("seed row must be an object")
    return parsed


def main() -> int:
    statements = ["BEGIN;"]
    for row in rows(DATASETS / "evaluation.jsonl"):
        if set(row) != {"id", "prompt", "label", "expected"}:
            raise ValueError("evaluation seed fields invalid")
        statements.append(
            "INSERT INTO evaluation_rows VALUES ("
            + ", ".join(quote(row[key]) for key in ("id", "prompt", "label", "expected"))
            + ");"
        )
    for row in rows(DATASETS / "context.jsonl"):
        if set(row) != {"id", "title", "claimed_authority", "text"}:
            raise ValueError("context seed fields invalid")
        statements.append(
            "INSERT INTO retrieval_context VALUES ("
            + ", ".join(
                [
                    quote(row["id"]),
                    "'trusted'",
                    quote(row["text"]),
                    quote(BASELINE),
                    quote(BASELINE),
                    "0",
                ]
            )
            + ");"
        )
        statements.append(
            "INSERT INTO retrieval_documents "
            "(id, title, claimed_authority, provenance, content, range_instance, participant, reset_generation, current_revision) VALUES ("
            + ", ".join(
                [
                    quote(row["id"]),
                    quote(row["title"]),
                    quote(row["claimed_authority"]),
                    "'trusted'",
                    quote(row["text"]),
                    quote(BASELINE),
                    quote(BASELINE),
                    "0",
                    "1",
                ]
            )
            + ");"
        )
    for row in rows(DATASETS / "agent-tools.jsonl"):
        if set(row) != {"id", "scope", "content"} or row["scope"] not in {"public", "restricted"}:
            raise ValueError("agent tool seed fields invalid")
        statements.append(
            "INSERT INTO agent_tool_objects VALUES ("
            + ", ".join(quote(row[key]) for key in ("id", "scope", "content"))
            + ");"
        )
    statements.append("COMMIT;")
    with open("/20-keplerops-data.sql", "w", encoding="utf-8") as output:
        output.write("\n".join(statements) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
