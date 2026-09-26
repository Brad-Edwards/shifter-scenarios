#!/usr/bin/env python3
"""Construct an exact Git repository from a Training repository seed."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def run(arguments: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        arguments,
        cwd=cwd,
        env=env,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def build(seed_path: Path, destination: Path) -> dict[str, str]:
    seed = json.loads(seed_path.read_text(encoding="utf-8"))
    if seed.get("object_format") != "sha1" or not seed.get("commits"):
        raise ValueError("unsupported or empty repository seed")
    if destination.exists():
        if (destination / "HEAD").is_file():
            return {}
        if any(destination.iterdir()):
            raise ValueError(f"destination exists but is not a Git repository: {destination}")

    logical_ids: dict[str, str] = {}
    with tempfile.TemporaryDirectory(prefix="cinder-git-") as temporary:
        worktree = Path(temporary)
        run(["git", "init", "--quiet", "--initial-branch", seed["default_branch"]], cwd=worktree)
        for commit in seed["commits"]:
            parent = commit.get("parent")
            if parent is not None:
                expected_parent = logical_ids.get(parent)
                actual_parent = run(["git", "rev-parse", "HEAD"], cwd=worktree)
                if expected_parent != actual_parent:
                    raise ValueError(f"invalid parent for {commit['logical_id']}")

            for child in worktree.iterdir():
                if child.name == ".git":
                    continue
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
            for relative, text in commit["tree"].items():
                target = worktree / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding="utf-8")

            run(["git", "add", "--all"], cwd=worktree)
            env = os.environ.copy()
            env.update(
                {
                    "GIT_AUTHOR_NAME": commit["author_name"],
                    "GIT_AUTHOR_EMAIL": commit["author_email"],
                    "GIT_AUTHOR_DATE": commit["author_time"],
                    "GIT_COMMITTER_NAME": commit["committer_name"],
                    "GIT_COMMITTER_EMAIL": commit["committer_email"],
                    "GIT_COMMITTER_DATE": commit["committer_time"],
                }
            )
            run(["git", "commit", "--quiet", "--no-gpg-sign", "-m", commit["message"]], cwd=worktree, env=env)
            logical_ids[commit["logical_id"]] = run(["git", "rev-parse", "HEAD"], cwd=worktree)

        destination.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--quiet", "--bare", str(worktree), str(destination)], cwd=worktree)
        run(["git", "config", "http.receivepack", "false"], cwd=destination)
        run(["git", "config", "daemon.receivepack", "false"], cwd=destination)
        (destination / "git-daemon-export-ok").touch()
    return logical_ids


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("seed", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    build(args.seed, args.destination)


if __name__ == "__main__":
    main()
