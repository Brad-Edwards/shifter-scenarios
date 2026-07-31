"""Process-aware container health check for API and worker roles."""

from __future__ import annotations

import os
import stat
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from store import StateStore


# The image entrypoint creates this range-local marker; every open is guarded below.
PROCESS_MARKER = Path("/tmp/platform-context-process")  # NOSONAR


def read_process_marker(path: Path = PROCESS_MARKER) -> str:
    descriptor = os.open(
        path,
        os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or metadata.st_nlink != 1
            or metadata.st_mode & 0o022
        ):
            raise RuntimeError("platform context process marker is not trustworthy")
        with os.fdopen(descriptor, encoding="utf-8", closefd=False) as marker:
            return marker.read(64).strip()
    finally:
        os.close(descriptor)


def main() -> None:
    process = read_process_marker()
    if process == "api":
        with urllib.request.urlopen(
            "http://127.0.0.1:8480/readyz", timeout=2
        ) as response:
            if response.status != 200:
                raise RuntimeError("context API is not ready")
        return
    worker_names = {"file-worker": "file-import", "sync-worker": "postgres-sync"}
    if process not in worker_names:
        raise RuntimeError("unknown platform context process")
    state = StateStore(
        Path(
            os.environ.get(
                "PLATFORM_CONTEXT_STATE_ROOT", "/var/lib/keplerops-platform-context"
            )
        )
    )
    heartbeat = state.heartbeat_status(worker_names[process])
    if heartbeat is None:
        raise RuntimeError("worker has not emitted a heartbeat")
    occurred_at = datetime.fromisoformat(heartbeat["occurred_at"])
    if (datetime.now(UTC) - occurred_at).total_seconds() > 30:
        raise RuntimeError("worker heartbeat is stale")


if __name__ == "__main__":
    main()
