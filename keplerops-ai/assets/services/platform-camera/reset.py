"""Reset the stopped platform-camera service to its deterministic baseline."""

from __future__ import annotations

import json
import os
from pathlib import Path

from storage import CameraState


STATE_ROOT = Path(
    os.environ.get(
        "PLATFORM_CAMERA_STATE_ROOT", "/var/lib/keplerops-platform-camera"
    )
)


def main() -> None:
    print(json.dumps(CameraState(STATE_ROOT).reset(), sort_keys=True))


if __name__ == "__main__":
    main()
