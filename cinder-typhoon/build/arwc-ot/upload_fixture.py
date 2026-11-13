"""Download the fixture through the official Editor with VM-local credentials."""
import json
import os
import pathlib
import subprocess
import socket
import time
import sys

ROOT = pathlib.Path(__file__).resolve().parent
EDITOR = pathlib.Path("/opt/arwc-ot-compat/upstream/squashfs-root")
PROJECT = pathlib.Path("/opt/arwc-ot-compat/work/arwc-compat")

if __name__ == "__main__":
    if os.uname().nodename != "cinder-arwc-ot-compat-363":
        raise SystemExit("Run on the dedicated compatibility VM.")
    credentials = json.loads((ROOT / ".operator/credentials.json").read_text())
    project = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else PROJECT
    if project.name not in ("arwc-compat", "arwc-site") or project.parent != PROJECT.parent:
        raise SystemExit("Use the dedicated compatibility or site Editor project")
    environment = dict(os.environ, APPDIR=str(EDITOR), OPENPLC_USER="engineer", OPENPLC_PASSWORD=credentials["plc"])
    deadline = time.monotonic() + 90
    while True:
        try:
            with socket.create_connection(("172.29.63.20", 8443), timeout=2):
                break
        except OSError:
            if time.monotonic() >= deadline:
                raise TimeoutError("OpenPLC management interface did not become ready") from None
            time.sleep(1)
    subprocess.run([
        str(EDITOR / "AppRun"), "--cli", "upload", str(project),
        "--target", "OpenPLC Runtime v4", "--host", "172.29.63.20", "--create-user", "--yes",
    ], env=environment, check=True)
