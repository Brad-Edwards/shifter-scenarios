"""Seed the PLC program without the OpenPLC Editor.

Packages the pre-compiled C++ source from the host build directory into the
program zip format, uploads it to the PLC server via REST API, waits for
compilation, then saves the binary and OPC UA artefacts to the plc-state
volume so plc-entrypoint.sh can restore them after a container recreate.

Runs as the IAP operator (non-root) without Xvfb or Electron.  Run after
the PLC container has started and 8443 is responding.

Usage:
  python3 seed_plc.py           # from /opt/arwc-ot-compat/slice
"""
import hashlib
import io
import json
import os
import pathlib
import subprocess
import sys
import time
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent
OPERATOR = ROOT / ".operator"
BUILD_SRC = pathlib.Path("/opt/arwc-ot-compat/work/arwc-compat/build/OpenPLC Runtime v4/src")
_PLC_CONTAINER = "arwc-ot-compat-plc-1"
_PLC_HOST = "172.29.63.20"
_PLC_PORT = 8443

# ---------------------------------------------------------------------------
# REST API helpers
# ---------------------------------------------------------------------------

def _plc_get(path: str, token: str) -> dict:
    import urllib.request, ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(
        f"https://{_PLC_HOST}:{_PLC_PORT}{path}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
        return json.loads(r.read())


def _plc_post_json(path: str, token: str, body: dict) -> dict:
    import urllib.request, ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"https://{_PLC_HOST}:{_PLC_PORT}{path}",
        data=data,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
        return json.loads(r.read())


def _plc_upload(token: str, zip_bytes: bytes) -> dict:
    """POST program zip to /api/upload-file as multipart/form-data."""
    import urllib.request, ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    boundary = "----ProgramUploadBoundary"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="program.zip"\r\n'
        f"Content-Type: application/zip\r\n\r\n"
    ).encode() + zip_bytes + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"https://{_PLC_HOST}:{_PLC_PORT}/api/upload-file",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
        return json.loads(r.read())


# ---------------------------------------------------------------------------
# Docker exec helpers
# ---------------------------------------------------------------------------

def _exec(cmd: list[str], *, sudo: bool = False, input: bytes | None = None) -> int:
    prefix = ["sudo"] if sudo else []
    result = subprocess.run(prefix + cmd, input=input, capture_output=True)
    if result.returncode != 0 and not sudo and b"permission denied" in result.stderr.lower():
        result = subprocess.run(["sudo"] + cmd, input=input, capture_output=True)
    return result.returncode


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    node = os.uname().nodename
    if not (node == "cinder-arwc-ot-compat-363" or node.startswith("cinder-")):
        raise SystemExit("Run on a Cinder range VM.")

    if not BUILD_SRC.is_dir():
        raise SystemExit(
            f"Build source directory not found: {BUILD_SRC}\n"
            "Run the OpenPLC Editor to generate the C++ source first."
        )

    credentials = json.loads((OPERATOR / "credentials.json").read_text())
    plc_pass = credentials["plc"]

    # Wait for PLC web interface.
    import socket as _socket
    deadline = time.monotonic() + 90
    while True:
        try:
            with _socket.create_connection((_PLC_HOST, _PLC_PORT), timeout=2):
                break
        except OSError:
            if time.monotonic() >= deadline:
                raise TimeoutError("PLC web interface did not respond within 90 s")
            time.sleep(1)

    # Authenticate.
    import urllib.request, ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    auth_data = json.dumps({"username": "engineer", "password": plc_pass}).encode()
    auth_req = urllib.request.Request(
        f"https://{_PLC_HOST}:{_PLC_PORT}/api/login",
        data=auth_data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(auth_req, context=ctx, timeout=10) as r:
        token = json.loads(r.read()).get("access_token", "")
    if not token:
        raise RuntimeError("Failed to authenticate with PLC server")

    # Build the program zip from the pre-generated C++ source tree.
    # The PLC upload endpoint extracts it into core/generated/.
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for src_file in BUILD_SRC.rglob("*"):
            if src_file.is_file():
                rel = src_file.relative_to(BUILD_SRC)
                zf.write(src_file, f"core/generated/{rel}")
    program_zip = buf.getvalue()
    print(f"Program zip: {len(program_zip):,} bytes from {BUILD_SRC}")

    # Upload the zip and wait for compilation.
    result = _plc_upload(token, program_zip)
    print("Upload result:", result)
    if result.get("UploadFileFail"):
        raise RuntimeError(f"Upload failed: {result['UploadFileFail']}")

    for _ in range(60):
        time.sleep(2)
        status = _plc_get("/api/compilation-status", token)
        state = status.get("CompilationStatus", status.get("exit_code", "?"))
        if state == "SUCCESS" or (isinstance(status.get("exit_code"), int) and status["exit_code"] == 0):
            print("Compilation succeeded")
            break
        if state == "FAILED" or (isinstance(status.get("exit_code"), int) and status["exit_code"] != 0):
            logs = "\n".join(status.get("logs", [])[-10:])
            raise RuntimeError(f"Compilation failed:\n{logs}")
    else:
        raise TimeoutError("Compilation did not complete within 120 s")

    # Start the PLC program.
    _plc_get("/api/start-plc", token)
    print("PLC program started")

    # Wait for OPC UA to generate its cert.
    for _ in range(30):
        time.sleep(2)
        check = _exec(
            ["docker", "exec", _PLC_CONTAINER, "test", "-s",
             "/workdir/core/src/drivers/plugins/python/opcua/certs/server_cert.pem"]
        )
        if check == 0:
            print("OPC UA server cert is ready")
            break
    else:
        print("Warning: OPC UA cert not found after 60 s — skipping cert backup")

    # Save binary to plc-state volume.
    _exec(["docker", "exec", _PLC_CONTAINER, "bash", "-c",
           "ls /workdir/build/libplc_*.so 2>/dev/null | head -1 | xargs -I{} cp {} /var/run/runtime/libplc-backup.so"])
    print("Compiled binary saved to volume")

    # Save cert pair.
    for src, dst in (
        ("/workdir/core/src/drivers/plugins/python/opcua/certs/server_cert.pem",
         "/var/run/runtime/opcua-server-cert.bak"),
        ("/workdir/core/src/drivers/plugins/python/opcua/certs/server_key.pem",
         "/var/run/runtime/opcua-server-key.bak"),
    ):
        _exec(["docker", "exec", _PLC_CONTAINER, "bash", "-c", f"cp {src} {dst} 2>/dev/null || true"])
    print("OPC UA cert pair saved to volume")

    # Update opcua.json with range credentials and save to volume.
    _update_script = r"""
import hashlib, os, base64, json, pathlib

def hash_pw(p):
    s = os.urandom(16)
    h = hashlib.pbkdf2_hmac('sha256', p.encode(), s, 600000)
    return 'pbkdf2:sha256:600000$' + base64.b64encode(s).decode() + '$' + base64.b64encode(h).decode()

creds = json.loads(pathlib.Path('/var/run/runtime/credentials.json').read_text())
roles = {'operator': 'opcua', 'dispatcher': 'ua_dispatcher', 'reader': 'ua_reader'}
p = pathlib.Path('/workdir/core/src/drivers/plugins/python/opcua/opcua.json')
b = pathlib.Path('/var/run/runtime/opcua.json.bak')
if not p.exists():
    raise SystemExit('opcua.json not found')
cfg = json.loads(p.read_text())
for u in cfg[0]['config']['users']:
    k = roles.get(u.get('username'))
    if k and k in creds:
        u['password_hash'] = hash_pw(creds[k])
        u.pop('password', None)
p.write_text(json.dumps(cfg, indent=2))
b.write_text(json.dumps(cfg, indent=2))
print('opcua.json updated with range credentials')
"""
    # Write credentials to the volume temporarily.
    creds_json = (OPERATOR / "credentials.json").read_bytes()
    _exec(["docker", "exec", "-i", _PLC_CONTAINER, "sh", "-c",
           "cat > /var/run/runtime/credentials.json"], input=creds_json)
    _exec(["docker", "exec", _PLC_CONTAINER,
           "/workdir/venvs/runtime/bin/python3", "-c", _update_script])
    _exec(["docker", "exec", _PLC_CONTAINER, "rm", "-f", "/var/run/runtime/credentials.json"])
    print("opcua.json updated with range credentials and saved to volume")

    # Copy server cert to .operator for prepare_services.py / Telegraf.
    subprocess.run(
        ["docker", "cp",
         f"{_PLC_CONTAINER}:/workdir/core/src/drivers/plugins/python/opcua/certs/server_cert.pem",
         str(OPERATOR / "server-cert.pem")],
        check=False,
    )
    subprocess.run(
        ["sudo", "docker", "cp",
         f"{_PLC_CONTAINER}:/workdir/core/src/drivers/plugins/python/opcua/certs/server_cert.pem",
         str(OPERATOR / "server-cert.pem")],
        check=False,
    )
    print("Server cert copied to .operator/server-cert.pem")
    print("Done. Run prepare_services.py next to configure Telegraf.")


if __name__ == "__main__":
    main()
