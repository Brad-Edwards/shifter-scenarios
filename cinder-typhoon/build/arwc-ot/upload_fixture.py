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


_PLC_CONTAINER = "arwc-ot-compat-plc-1"
_UPSERT_SCRIPT = r"""
import os, sqlite3, sys
sys.path.insert(0, '/workdir/venvs/runtime/lib/python3.11/site-packages')
from werkzeug.security import generate_password_hash
# Read PEPPER from the runtime .env file (same source as Flask config).
env = {}
try:
    for line in open('/var/run/runtime/.env').read().splitlines():
        if '=' in line and not line.startswith('#'):
            k, _, v = line.partition('=')
            env[k.strip()] = v.strip()
except OSError:
    pass
pepper = env.get('PEPPER', '')
pw_hash = generate_password_hash(sys.argv[1] + pepper, method='pbkdf2:sha256:600000')
db = sqlite3.connect('/var/run/runtime/restapi.db')
row = db.execute("SELECT id FROM users WHERE username='engineer'").fetchone()
if row:
    db.execute("UPDATE users SET password_hash=? WHERE username='engineer'", (pw_hash,))
else:
    db.execute("INSERT INTO users (username, password_hash, role) VALUES ('engineer',?,'admin')", (pw_hash,))
db.commit(); db.close()
print('synced')
"""


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
    if RESTAPI_DB.exists():
        # Running inside the container where the volume is mounted directly.
        import sys as _sys
        _site = str(_VENV_PYTHON.parent.parent / "lib" / "python3.11" / "site-packages")
        if _site not in _sys.path:
            _sys.path.insert(0, _site)
        from werkzeug.security import generate_password_hash
        # Read PEPPER from the runtime .env file (same source as Flask config).
        _env: dict[str, str] = {}
        _env_path = RESTAPI_DB.parent / ".env"
        try:
            for _line in _env_path.read_text().splitlines():
                if "=" in _line and not _line.startswith("#"):
                    _k, _, _v = _line.partition("=")
                    _env[_k.strip()] = _v.strip()
        except OSError:
            pass
        _pepper = _env.get("PEPPER", "")
        pw_hash = generate_password_hash(password + _pepper, method="pbkdf2:sha256:600000")
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
    else:
        # Running on the host VM; exec into the container where the volume is mounted.
        # Try without sudo first; fall back to sudo if the socket is not accessible.
        cmd = ["docker", "exec", _PLC_CONTAINER,
               "/workdir/venvs/runtime/bin/python3", "-c", _UPSERT_SCRIPT, password]
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if result.returncode != 0 and b"permission denied" in result.stderr.lower():
            subprocess.run(["sudo"] + cmd, check=True, stdout=subprocess.DEVNULL)
    # Restart the PLC container so Flask reloads the user from the updated DB.
    # The wait loop below waits for the web interface to become available again.
    r = subprocess.run(
        ["docker", "restart", _PLC_CONTAINER],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )
    if r.returncode != 0 and b"permission denied" in r.stderr.lower():
        subprocess.run(["sudo", "docker", "restart", _PLC_CONTAINER],
                       check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


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
    # Save the compiled binary to the persistent plc-state volume so the
    # entrypoint can restore it after a container recreate without a fresh upload.
    _save_bin = [
        "docker", "exec", _PLC_CONTAINER, "bash", "-c",
        "ls /workdir/build/libplc_*.so 2>/dev/null | head -1 | xargs -I{} cp {} /var/run/runtime/libplc-backup.so",
    ]
    result = subprocess.run(_save_bin, stderr=subprocess.PIPE)
    if result.returncode != 0 and b"permission denied" in result.stderr.lower():
        subprocess.run(["sudo"] + _save_bin, check=False)

    # Update opcua.json with range credentials and save to the volume so the
    # entrypoint can restore both the binary and the config after a recreate.
    # The editor generates opcua.json with development-VM passwords; the range
    # has its own randomly-generated credentials that must replace them.
    _update_opcua = r"""
import hashlib, os, base64, json, pathlib

def hash_pw(password):
    salt = os.urandom(16)
    h = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 600000)
    return 'pbkdf2:sha256:600000$' + base64.b64encode(salt).decode() + '$' + base64.b64encode(h).decode()

creds = json.loads(pathlib.Path('/var/run/runtime/credentials.json').read_text())
roles = {'operator': 'opcua', 'dispatcher': 'ua_dispatcher', 'reader': 'ua_reader'}
opcua_path = pathlib.Path('/workdir/core/src/drivers/plugins/python/opcua/opcua.json')
backup_path = pathlib.Path('/var/run/runtime/opcua.json.bak')
if not opcua_path.exists():
    print('opcua.json not found, skipping')
    raise SystemExit(0)
cfg = json.loads(opcua_path.read_text())
for u in cfg[0]['config']['users']:
    key = roles.get(u.get('username'))
    if key and key in creds:
        u['password_hash'] = hash_pw(creds[key])
        u.pop('password', None)
opcua_path.write_text(json.dumps(cfg, indent=2))
backup_path.write_text(json.dumps(cfg, indent=2))
print('opcua.json updated with range credentials and saved to volume')
"""
    # First write the credentials to the volume so the update script can read them.
    creds_path = ROOT / ".operator/credentials.json"
    _copy_creds = [
        "docker", "exec", _PLC_CONTAINER, "bash", "-c",
        f"cat > /var/run/runtime/credentials.json",
    ]
    r = subprocess.run(_copy_creds, input=creds_path.read_bytes(), stderr=subprocess.PIPE)
    if r.returncode != 0 and b"permission denied" in r.stderr.lower():
        subprocess.run(["sudo"] + _copy_creds, input=creds_path.read_bytes(), check=False)
    _update_cmd = ["docker", "exec", _PLC_CONTAINER, "/workdir/venvs/runtime/bin/python3", "-c", _update_opcua]
    result = subprocess.run(_update_cmd, stderr=subprocess.PIPE)
    if result.returncode != 0 and b"permission denied" in result.stderr.lower():
        subprocess.run(["sudo"] + _update_cmd, check=False)
    # Remove the temporary credentials file from the container volume.
    _rm_creds = ["docker", "exec", _PLC_CONTAINER, "rm", "-f", "/var/run/runtime/credentials.json"]
    subprocess.run(_rm_creds, stderr=subprocess.DEVNULL)
    subprocess.run(["sudo"] + _rm_creds, stderr=subprocess.DEVNULL)
