"""Download the fixture through the official Editor with VM-local credentials."""
import json
import os
import pathlib
import sqlite3
import subprocess
import socket
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent
EDITOR = pathlib.Path("/opt/arwc-ot-compat/upstream/squashfs-root")
PROJECT = pathlib.Path("/opt/arwc-ot-compat/work/arwc-compat")
# restapi.db lives on the persistent plc-state volume.
RESTAPI_DB = pathlib.Path("/var/run/runtime/restapi.db")
# OpenPLC runtime venv contains werkzeug used for password hashing.
_VENV_PYTHON = pathlib.Path("/workdir/venvs/runtime/bin/python3")


def _sync_engineer_password(password: str) -> None:
    """Upsert the engineer user in restapi.db with the current credentials.

    The plc-state volume persists across container recreations. If credentials
    rotate after the initial provisioning, the stored hash becomes stale and
    the Editor upload fails. This upsert keeps the engineer account aligned
    with credentials.json without touching other users.

    Uses the same derivation_method as restapi.py ("pbkdf2:sha256:600000") so
    the Flask server's check_password_hash call succeeds without a code change.
    Restarts the PLC container afterward so Flask reloads the user from the DB
    rather than serving the stale in-memory object.
    """
    if not RESTAPI_DB.exists():
        return
    import sys as _sys
    _site = str(_VENV_PYTHON.parent.parent / "lib" / "python3.11" / "site-packages")
    if _site not in _sys.path:
        _sys.path.insert(0, _site)
    from werkzeug.security import generate_password_hash
    # Match restapi.py: derivation_method = "pbkdf2:sha256:600000"
    pw_hash = generate_password_hash(password, method="pbkdf2:sha256:600000")
    with sqlite3.connect(RESTAPI_DB) as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE username='engineer'"
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE users SET password_hash=? WHERE username='engineer'",
                (pw_hash,),
            )
        else:
            conn.execute(
                "INSERT INTO users (username, password_hash, role) VALUES ('engineer', ?, 'admin')",
                (pw_hash,),
            )
    # Restart the PLC container so Flask reloads the user from the updated DB.
    # The wait loop below waits for the web interface to become available again.
    subprocess.run(
        ["docker", "restart", "arwc-ot-compat-plc-1"],
        check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


if __name__ == "__main__":
    node = os.uname().nodename
    if not (node == "cinder-arwc-ot-compat-363" or node.startswith("cinder-")):
        raise SystemExit("Run on the dedicated compatibility VM.")
    credentials = json.loads((ROOT / ".operator/credentials.json").read_text())
    project = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else PROJECT
    if project.name not in ("arwc-compat", "arwc-site") or project.parent != PROJECT.parent:
        raise SystemExit("Use the dedicated compatibility or site Editor project")
    _sync_engineer_password(credentials["plc"])
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
