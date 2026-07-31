"""Container health probe for the API role."""

from __future__ import annotations

import json
import os
import time
import urllib.request
from pathlib import Path


def main() -> None:
    role = os.environ.get("PLATFORM_DEPLOYMENT_ROLE", "api")
    if role == "api":
        with urllib.request.urlopen("http://127.0.0.1:8490/healthz", timeout=2) as response:
            payload = json.load(response)
        if response.status != 200 or payload.get("status") != "ok":
            raise SystemExit(1)
        return
    if role == "lifecycle-worker":
        root = Path(os.environ.get("PLATFORM_DEPLOYMENT_STATE_ROOT", "/var/lib/keplerops-platform-deployment"))
        heartbeat = root / "lifecycle-heartbeat"
        if not heartbeat.is_file() or time.time() - heartbeat.stat().st_mtime > 300:
            raise SystemExit(1)
        return
    raise SystemExit(1)


if __name__ == "__main__":
    main()
