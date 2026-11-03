#!/usr/bin/env python3
"""Exercise delayed ARWC handover and restart behavior in the built images."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
SERVICES = {
    "cinder-arwc-business": "/var/lib/arwc-business/auth/corporate-session.sha256",
    "cinder-arwc-data": "/var/lib/arwc-data/auth/corporate-session.sha256",
    "cinder-arwc-archive": "/var/lib/arwc-archive/auth/corporate-session.sha256",
    "cinder-arwc-identity": "/var/lib/arwc-identity/auth/corporate-session.sha256",
    "cinder-arwc-contractors": "/var/lib/arwc-contractors/auth/corporate-session.sha256",
}


def inspect(container: str, template: str) -> str:
    completed = subprocess.run(
        ["docker", "inspect", "--format", template, container],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else "missing"


def exec_output(container: str, *command: str) -> str:
    return subprocess.check_output(
        ["docker", "exec", container, *command], text=True
    ).strip()


def wait_for_ready(container: str, timeout: float = 180) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        completed = subprocess.run(
            [
                "docker", "exec", container, "python3",
                "/usr/local/libexec/arwc-handover.py", "ready",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if completed.returncode == 0:
            return
        time.sleep(1)
    raise RuntimeError(f"{container} did not become ready")


def main() -> int:
    running_before: dict[str, str] = {}
    for container in SERVICES:
        status = inspect(container, "{{.State.Status}}")
        if status != "running":
            raise RuntimeError(f"{container} is not running before handover: {status}")
        health = inspect(
            container, "{{if .State.Health}}{{.State.Health.Status}}{{end}}"
        )
        if health != "healthy":
            raise RuntimeError(f"{container} is not healthy while waiting: {health}")
        running_before[container] = inspect(container, "{{.RestartCount}}")
        state = exec_output(container, "cat", "/run/arwc-status/state")
        if state != "waiting":
            raise RuntimeError(f"{container} is {state!r} before handover")

    # Exercise multiple gate polls. The long-duration guarantee comes from the
    # unbounded wait; this live test checks that it does not exit or crash-loop.
    time.sleep(12)
    for container, restart_count in running_before.items():
        if inspect(container, "{{.State.Status}}") != "running":
            raise RuntimeError(f"{container} stopped while waiting for handover")
        if inspect(container, "{{.RestartCount}}") != restart_count:
            raise RuntimeError(f"{container} restarted while waiting for handover")
        logs = subprocess.check_output(
            ["docker", "logs", container], text=True, stderr=subprocess.STDOUT
        )
        if "[[: not found" in logs:
            raise RuntimeError(f"{container} used Bash syntax under /bin/sh")

    subprocess.run(
        [sys.executable, str(ROOT / "tests" / "seed_corporate_handover.py")],
        check=True,
    )
    for container in SERVICES:
        wait_for_ready(container)
        if inspect(container, "{{.RestartCount}}") != "0":
            raise RuntimeError(f"{container} auto-restarted during delayed handover")
        if exec_output(container, "readlink", "/bin/sh") != "dash":
            raise RuntimeError(f"{container} final image does not use dash for /bin/sh")

    accepted = {
        container: exec_output(container, "cat", path)
        for container, path in SERVICES.items()
    }
    subprocess.run(
        ["docker", "restart", *SERVICES],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    for container, path in SERVICES.items():
        wait_for_ready(container)
        if exec_output(container, "cat", path) != accepted[container]:
            raise RuntimeError(
                f"{container} did not preserve its accepted handover on restart"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
