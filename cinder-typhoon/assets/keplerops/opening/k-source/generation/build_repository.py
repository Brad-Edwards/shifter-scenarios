#!/usr/bin/env python3
"""Build the exact FieldLink Git bundle declared by repository-seed.json."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
OPENING = ROOT.parents[1]


def run(arguments: list[str], *, cwd: Path, environment: dict[str, str] | None = None) -> str:
    env = os.environ.copy()
    if environment:
        env.update(environment)
    completed = subprocess.run(
        arguments,
        cwd=cwd,
        env=env,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return completed.stdout.strip()


def asset_bytes(name: str) -> bytes:
    matches = list(OPENING.rglob(name))
    if len(matches) != 1:
        raise ValueError(f"asset {name!r} resolved to {len(matches)} paths")
    return matches[0].read_bytes()


def materialize_tree(repo: Path, tree: dict[str, object]) -> None:
    for path in sorted(
        (item for item in repo.rglob("*") if ".git" not in item.parts),
        reverse=True,
    ):
        if path.is_file() or path.is_symlink():
            path.unlink()
        elif path.is_dir():
            path.rmdir()
    for relative, value in tree.items():
        destination = repo / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(value, str):
            destination.write_text(value, encoding="utf-8")
        else:
            destination.write_bytes(asset_bytes(value["asset"]))


def main() -> None:
    seed = json.loads((ROOT / "repository-seed.json").read_text())
    logical: dict[str, str] = {}
    with tempfile.TemporaryDirectory() as temporary:
        repo = Path(temporary) / "fieldlink-connector"
        repo.mkdir()
        run(["git", "init", "--initial-branch=main"], cwd=repo)
        run(["git", "config", "core.autocrlf", "false"], cwd=repo)
        run(["git", "config", "commit.gpgsign", "false"], cwd=repo)
        for commit in seed["commits"]:
            parent = commit["parent"]
            if parent is not None:
                run(["git", "checkout", "--detach", logical[parent]], cwd=repo)
            materialize_tree(repo, commit["tree"])
            run(["git", "add", "-A"], cwd=repo)
            environment = {
                "GIT_AUTHOR_NAME": commit["author_name"],
                "GIT_AUTHOR_EMAIL": commit["author_email"],
                "GIT_AUTHOR_DATE": commit["author_time"],
                "GIT_COMMITTER_NAME": commit["committer_name"],
                "GIT_COMMITTER_EMAIL": commit["committer_email"],
                "GIT_COMMITTER_DATE": commit["committer_time"],
            }
            run(["git", "commit", "--no-gpg-sign", "-m", commit["message"]], cwd=repo, environment=environment)
            logical[commit["logical_id"]] = run(["git", "rev-parse", "HEAD"], cwd=repo)
        for reference, logical_id in seed["refs"].items():
            run(["git", "update-ref", reference, logical[logical_id]], cwd=repo)
        run(["git", "symbolic-ref", "HEAD", "refs/heads/main"], cwd=repo)
        bundle = ROOT / "fieldlink-connector.bundle"
        bundle.unlink(missing_ok=True)
        run(["git", "bundle", "create", str(bundle), "--all"], cwd=repo)
        payload = {
            "schema": "fieldkest.repository-artifact/v1",
            "repository": seed["repository"],
            "bundle": bundle.name,
            "bundle_sha256": hashlib.sha256(bundle.read_bytes()).hexdigest(),
            "commits": logical,
            "refs": {reference: logical[logical_id] for reference, logical_id in seed["refs"].items()},
        }
        (ROOT / "repository-artifact.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
