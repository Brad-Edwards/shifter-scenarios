#!/usr/bin/env python3
"""Render canonical Polaris content for Shifter's CTFd-compatible importer."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from polaris_manifest import PACK_ROOT, load_manifest


def build_import_pack(pack_root: str | Path = PACK_ROOT) -> dict[str, Any]:
    """Return the closed document accepted by Shifter's challenge importer."""

    challenges = []
    for row in load_manifest(pack_root, runtime_profile_id="aws_event"):
        challenges.append(
            {
                "name": row["name"],
                "description": row["description"],
                "category": row["category"],
                "value": row["value"],
                "type": row["type"],
                "state": row["state"],
                "flags": row["flags"],
                "hints": row["hints"],
            }
        )
    return {"format": "ctfd", "challenges": challenges}


def write_private_json(path: Path, payload: dict[str, Any]) -> None:
    """Atomically write answer-bearing content with owner-only permissions."""

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the private Polaris challenge pack for Shifter import."
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    payload = build_import_pack()
    write_private_json(args.output, payload)
    print(f"wrote {len(payload['challenges'])} challenges")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
