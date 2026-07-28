#!/usr/bin/env python3
"""Render and verify the MinIO-owned company artifact namespace."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from company_state_common import (
    OWNER,
    assert_readback,
    load_corpus,
    normalized_readback,
)

CONTENT_ID = "company-artifact-state"
OBJECT_PREFIX = "company-state/v1/artifacts"
ARTIFACT_IDS = (
    "artifact-orion-17",
    "artifact-orion-18",
    "artifact-eval-report-22",
)


def build_plan(corpus_path: Path, object_root: Path) -> dict[str, Any]:
    corpus = load_corpus(corpus_path)
    artifacts = {row["id"]: row for row in corpus["artifacts"]}
    records: list[dict[str, Any]] = []
    for identifier in ARTIFACT_IDS:
        try:
            artifact = artifacts[identifier]
        except KeyError as error:
            raise ValueError(f"company artifact is missing: {identifier}") from error
        source = object_root / Path(artifact["source_path"]).name
        payload = source.read_bytes()
        digest = "sha256:" + hashlib.sha256(payload).hexdigest()
        if digest != artifact["digest"]:
            raise ValueError(f"company artifact digest mismatch: {identifier}")
        records.append(
            {
                "id": identifier,
                "object_type": "artifact",
                "source_digest": digest,
                "source_file": source.name,
                "object_key": f"{OBJECT_PREFIX}/{identifier}/{source.name}",
                "media_type": artifact["media_type"],
            }
        )
    plan = {
        "schema_version": 1,
        "owner": OWNER,
        "content_id": CONTENT_ID,
        "records": records,
    }
    plan["readback"] = normalized_readback(CONTENT_ID, records)
    return plan


def verify_files(plan: dict[str, Any], root: Path) -> dict[str, Any]:
    observed: list[dict[str, Any]] = []
    for record in plan["records"]:
        target = root / record["object_key"]
        marker = root / "company-state/v1/.ownership" / record["id"]
        if marker.read_text(encoding="ascii").strip() != OWNER:
            raise RuntimeError(f"unowned MinIO collision: {record['object_key']}")
        digest = "sha256:" + hashlib.sha256(target.read_bytes()).hexdigest()
        observed.append(
            {
                "id": record["id"],
                "object_type": "artifact",
                "source_digest": digest,
            }
        )
    return assert_readback(plan["readback"], observed)


def render(corpus: Path, object_root: Path, output: Path) -> None:
    plan = build_plan(corpus, object_root)
    output.mkdir(parents=True, exist_ok=True)  # NOSONAR
    # This is an image-build workspace selected by the trusted build entrypoint.
    (output / "plan.json").write_text(  # NOSONAR
        json.dumps(plan, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"  # NOSONAR
    )
    lines = [
        "\t".join(
            (
                row["id"],
                row["source_file"],
                row["object_key"],
                row["source_digest"],
                row["media_type"],
            )
        )
        for row in plan["records"]
    ]
    (output / "objects.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("render", "verify-files"))
    parser.add_argument("--company-state", type=Path)
    parser.add_argument("--object-root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--root", type=Path)
    args = parser.parse_args()
    if args.command == "render":
        if not args.company_state or not args.object_root or not args.output:
            parser.error("render requires company state, object root, and output")
        render(args.company_state, args.object_root, args.output)
    else:
        if not args.plan or not args.root:
            parser.error("verify-files requires plan and root")
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        print(json.dumps(verify_files(plan, args.root), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
