#!/usr/bin/env python3
"""Render canonical company objects into a deterministic OpenSearch bulk corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

INDEX_NAME = "keplerops-company-v1-000001"
INDEX_ALIAS = "keplerops-company"
OWNER = "keplerops-company-state"
SECTIONS = (
    "tickets",
    "commits",
    "datasets",
    "experiments",
    "artifacts",
    "models",
    "approvals",
    "releases",
    "operations",
)
TIME_FIELDS = (
    "occurred_at",
    "released_at",
    "decided_at",
    "authored_at",
    "created_at",
    "started_at",
    "updated_at",
)
OWNER_FIELDS = ("owner_ref", "assignee_ref", "author_ref", "approver_ref", "actor_ref")


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def related_refs(row: dict[str, Any]) -> list[str]:
    refs: set[str] = set()
    for key, value in row.items():
        if not key.endswith(("_ref", "_refs")):
            continue
        if isinstance(value, str):
            refs.add(value)
        elif isinstance(value, list):
            refs.update(item for item in value if isinstance(item, str))
    refs.discard(str(row["id"]))
    return sorted(refs)


def title(section: str, row: dict[str, Any]) -> str:
    if section == "tickets":
        return f"{row['key']} {row['status']}"
    if section == "commits":
        return f"{row['revision']} {row['summary']}"
    if section == "datasets":
        return f"{row['id']} dataset version {row['version']}"
    if section == "experiments":
        return f"{row['id']} experiment {row['status']}"
    if section == "artifacts":
        return f"{row['id']} artifact {row['media_type']}"
    if section == "models":
        return f"{row['id']} model version {row['version']}"
    if section == "approvals":
        return f"{row['id']} approval {row['decision']}"
    if section == "releases":
        return f"{row['id']} release {row['status']}"
    return f"{row['id']} {row['kind']}"


def summary(section: str, row: dict[str, Any]) -> str:
    if section == "commits":
        return row["summary"]
    if section == "tickets":
        return (
            f"{row['key']} is {row['status']} for {row['project_ref']} and references "
            f"{', '.join(related_refs(row)) or 'no linked objects'}."
        )
    if section == "experiments":
        return (
            f"{row['id']} used {row['dataset_ref']} and completed with "
            f"accuracy {row['accuracy']}."
        )
    if section == "operations":
        return (
            f"{row['kind']} recorded for "
            f"{', '.join(row.get('object_refs', []))}."
        )
    return f"Ordinary {section[:-1]} record for {row['id']}."


def represented_at(row: dict[str, Any]) -> str:
    for field in TIME_FIELDS:
        value = row.get(field)
        if isinstance(value, str):
            return value
    raise ValueError(f"search object has no represented timestamp: {row.get('id')}")


def owner_ref(row: dict[str, Any]) -> str:
    for field in OWNER_FIELDS:
        value = row.get(field)
        if isinstance(value, str):
            return value
    return "service-registry"


def documents(path: Path) -> list[dict[str, Any]]:
    # The immutable image build supplies the committed company-state path.
    corpus = yaml.safe_load(path.read_text(encoding="utf-8"))  # NOSONAR
    if not isinstance(corpus, dict) or corpus.get("schema_version") != 1:
        raise ValueError("company state must use schema version 1")
    output: list[dict[str, Any]] = []
    identifiers: set[str] = set()
    for section in SECTIONS:
        rows = corpus.get(section)
        if not isinstance(rows, list) or not rows:
            raise ValueError(f"company state must declare {section}")
        for row in rows:
            identifier = row.get("id")
            if not isinstance(identifier, str) or identifier in identifiers:
                raise ValueError("company search ids must be present and unique")
            if identifier.startswith(("kep-m", "challenge-")):
                raise ValueError("company search id collides with a reserved namespace")
            identifiers.add(identifier)
            payload = canonical_json(row)
            output.append(
                {
                    "document_id": identifier,
                    "object_type": section[:-1],
                    "title": title(section, row),
                    "summary": summary(section, row),
                    "represented_at": represented_at(row),
                    "project_ref": str(row.get("project_ref", "")),
                    "owner_ref": owner_ref(row),
                    "related_refs": related_refs(row),
                    "source_digest": digest_text(payload),
                    "source_payload": payload,
                    "company_state_owner": OWNER,
                }
            )
    return sorted(output, key=lambda row: row["document_id"])


def render(company_state: Path) -> tuple[str, dict[str, Any], dict[str, Any]]:
    rows = documents(company_state)
    lines: list[str] = []
    for row in rows:
        lines.append(
            canonical_json(
                {"index": {"_index": INDEX_NAME, "_id": row["document_id"]}}
            )
        )
        lines.append(canonical_json(row))
    digest = digest_text("\n".join(row["source_digest"] for row in rows))
    manifest = {
        "schema_version": 1,
        "owner": OWNER,
        "index_name": INDEX_NAME,
        "index_alias": INDEX_ALIAS,
        "object_count": len(rows),
        "canonical_digest": digest,
        "object_digests": [
            {
                "document_id": row["document_id"],
                "source_digest": row["source_digest"],
            }
            for row in rows
        ],
    }
    index = {
        "mappings": {
            "_meta": {
                "owner": OWNER,
                "canonical_digest": digest,
            }
        }
    }
    return "\n".join(lines) + "\n", manifest, index


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--company-state", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    ndjson, manifest, index = render(args.company_state)
    args.output_root.mkdir(parents=True, exist_ok=True)
    (args.output_root / "company-corpus.ndjson").write_text(ndjson, encoding="utf-8")
    (args.output_root / "company-readback-manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    (args.output_root / "company-index.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    (args.output_root / "company-readback-digests.txt").write_text(
        "".join(
            f"{row['document_id']} {row['source_digest']}\n"
            for row in manifest["object_digests"]
        ),
        encoding="utf-8",
    )
    (args.output_root / "company-readback-sources.ndjson").write_text(
        "".join(canonical_json(row) + "\n" for row in documents(args.company_state)),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
