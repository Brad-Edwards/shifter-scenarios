"""Restart-safe completion, evidence export, expiry, and deletion worker."""

from __future__ import annotations

import os
import signal
import time
from pathlib import Path

from cloud_boundary import WorkspaceBroker
from policy import load_policy
from store import StateStore


running = True


def stop(_signal: int, _frame: object) -> None:
    global running
    running = False


def heartbeat(root: Path) -> None:
    path = root / "lifecycle-heartbeat"
    temporary = root / ".lifecycle-heartbeat.tmp"
    temporary.write_text(f"{time.time()}\n", encoding="ascii")
    temporary.chmod(0o600)
    temporary.replace(path)


def main() -> None:
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    root = Path(os.environ.get("PLATFORM_DEPLOYMENT_STATE_ROOT", "/var/lib/keplerops-platform-deployment"))
    policy_path = Path(os.environ.get("PLATFORM_DEPLOYMENT_POLICY", "/run/keplerops/deployment-policy.json"))
    policy = load_policy(policy_path)
    broker = WorkspaceBroker(policy, StateStore(root, policy.tenant_id))
    interval = float(os.environ.get("PLATFORM_DEPLOYMENT_RECONCILE_SECONDS", "5"))
    if not 1 <= interval <= 60:
        raise RuntimeError("reconcile interval must be from 1 through 60 seconds")
    heartbeat(root)
    while running:
        broker.reconcile()
        heartbeat(root)
        time.sleep(interval)


if __name__ == "__main__":
    main()
