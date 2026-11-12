"""Download the fixture through the official Editor with VM-local credentials."""
import json
import os
import pathlib
import subprocess
import socket
import time

ROOT = pathlib.Path(__file__).resolve().parent
EDITOR = pathlib.Path("/opt/arwc-ot-compat/upstream/squashfs-root")
PROJECT = pathlib.Path("/opt/arwc-ot-compat/work/arwc-compat")

if __name__ == "__main__":
    if os.uname().nodename != "cinder-arwc-ot-compat-363":
        raise SystemExit("Run on the dedicated compatibility VM.")
    credentials = json.loads((ROOT / ".operator/credentials.json").read_text())
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
        str(EDITOR / "AppRun"), "--cli", "upload", str(PROJECT),
        "--target", "OpenPLC Runtime v4", "--host", "172.29.63.20", "--create-user", "--yes",
    ], env=environment, check=True)
