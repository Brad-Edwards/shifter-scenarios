#!/usr/bin/env python3
"""Shared parsing and normalization for concrete company-state service adapters."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml

OWNER = "keplerops-company-state"
SCHEMA_VERSION = 1
RESERVED_PREFIXES = ("challenge-", "kep-m")


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest_json(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def load_corpus(path: Path) -> dict[str, Any]:  # NOSONAR - one cohesive schema pass.
    # Internal image entrypoints supply this operator-owned content path.
    value = yaml.safe_load(path.read_text(encoding="utf-8"))  # NOSONAR
    if not isinstance(value, dict) or value.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("company state must use schema version 1")
    identifiers: set[str] = set()
    for section, rows in value.items():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("id"), str):
                raise TypeError(f"company state {section} contains an invalid object")
            identifier = row["id"]
            if identifier in identifiers:
                raise ValueError("company state object ids must be globally unique")
            if identifier.startswith(RESERVED_PREFIXES):
                raise ValueError("company state object id uses a challenge namespace")
            identifiers.add(identifier)
    return value


def index_section(corpus: dict[str, Any], section: str) -> dict[str, dict[str, Any]]:
    rows = corpus.get(section)
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"company state must declare {section}")
    return {row["id"]: row for row in rows}


def require_records(
    corpus: dict[str, Any], selections: Iterable[tuple[str, str]]
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    indexes: dict[str, dict[str, dict[str, Any]]] = {}
    for section, identifier in selections:
        index = indexes.setdefault(section, index_section(corpus, section))
        try:
            source = index[identifier]
        except KeyError as error:
            raise ValueError(
                f"company state is missing {section}.{identifier}"
            ) from error
        records.append(
            {
                "id": identifier,
                "object_type": section[:-1],
                "source_digest": digest_json(source),
                "source": source,
            }
        )
    return sorted(records, key=lambda row: row["id"])


def normalized_readback(
    content_id: str, records: Iterable[dict[str, Any]]
) -> dict[str, Any]:
    normalized = sorted(
        (
            {
                "id": row["id"],
                "object_type": row["object_type"],
                "source_digest": row["source_digest"],
            }
            for row in records
        ),
        key=lambda row: row["id"],
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "owner": OWNER,
        "content_id": content_id,
        "record_count": len(normalized),
        "records": normalized,
        "canonical_digest": digest_json(normalized),
    }


def assert_readback(
    expected: dict[str, Any], observed_records: Iterable[dict[str, Any]]
) -> dict[str, Any]:
    observed = normalized_readback(expected["content_id"], observed_records)
    if observed != expected:
        raise RuntimeError(f"{expected['content_id']} native readback digest mismatch")
    return observed
