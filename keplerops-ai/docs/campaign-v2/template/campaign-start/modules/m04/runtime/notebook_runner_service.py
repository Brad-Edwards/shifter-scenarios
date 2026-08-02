#!/usr/bin/env python3
"""Run queued evaluation notebooks in the credential-free runner container."""

from __future__ import annotations

import json
import os
from pathlib import Path
import resource
import subprocess
import time


JOBS = Path(os.getenv("M04_RUNNER_JOBS", "/jobs"))
EXECUTOR = Path(os.getenv("M04_RUNNER_EXECUTOR", "/opt/runner/notebook_executor.py"))
POLL_SECONDS = max(1, int(os.getenv("M04_RUNNER_POLL_SECONDS", "2")))


def limits() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_FSIZE, (8 * 1024 * 1024, 8 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    resource.setrlimit(resource.RLIMIT_NPROC, (16, 16))


def fail(job: Path, message: str) -> None:
    (job / "error.json").write_text(
        json.dumps({"status": "failed", "error": message[-1200:]}, sort_keys=True),
        encoding="utf-8",
    )
    (job / "complete").touch()


def run(job: Path) -> None:
    try:
        request = json.loads((job / "request.json").read_text(encoding="utf-8"))
        mode = str(request["mode"])
        if mode not in {"calibration", "individual", "cohort"}:
            raise ValueError("unsupported evaluation mode")
        completed = subprocess.run(
            [
                "/usr/bin/python3",
                "-I",
                str(EXECUTOR),
                "--notebook",
                str(job / "notebook.ipynb"),
                "--mode",
                mode,
                "--input",
                str(job / "input.json"),
                "--output",
                str(job / "output.json"),
            ],
            cwd=job,
            env={"PATH": "/usr/bin:/bin", "PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1"},
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=40,
            check=False,
            preexec_fn=limits,
        )
        if completed.returncode:
            raise RuntimeError(completed.stderr or f"runner exited {completed.returncode}")
        (job / "complete").touch()
    except (KeyError, OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        fail(job, f"{type(error).__name__}: {error}")


def poll() -> None:
    JOBS.mkdir(mode=0o700, parents=True, exist_ok=True)
    while True:
        for ready in sorted(JOBS.glob("*/ready")):
            job = ready.parent
            claimed = job / "claimed"
            try:
                ready.rename(claimed)
            except FileNotFoundError:
                continue
            run(job)
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    poll()
