#!/usr/bin/env python3
"""Fetch one revision-pinned model during image build and verify its artifact."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import yaml
from huggingface_hub import snapshot_download


def digest(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = yaml.safe_load(args.manifest.read_text(encoding="utf-8"))
    if set(manifest) != {"schema_version", "artifact_id", "format", "upstream", "files", "runtime"}:
        raise SystemExit("model manifest: invalid fields")
    upstream = manifest["upstream"]
    revision = upstream["revision"]
    if not isinstance(revision, str) or len(revision) != 40:
        raise SystemExit("model manifest: immutable revision required")
    files = manifest["files"]
    if not isinstance(files, list) or not files:
        raise SystemExit("model manifest: files required")
    paths = [row.get("path") for row in files if isinstance(row, dict)]
    if len(paths) != len(files):
        raise SystemExit("model manifest: invalid file rows")
    if len(paths) != len(set(paths)):
        raise SystemExit("model manifest: duplicate file paths")
    if any(
        not isinstance(path, str)
        or not path
        or path.startswith("/")
        or ".." in Path(path).parts
        for path in paths
    ):
        raise SystemExit("model manifest: invalid file paths")
    snapshot_download(
        repo_id=upstream["repository"],
        revision=revision,
        local_dir=args.output,
        allow_patterns=[row["path"] for row in files],
    )
    for row in files:
        path = args.output / row["path"]
        if path.stat().st_size != row["size"] or digest(path) != row["sha256"]:
            raise SystemExit("model artifact: digest mismatch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
