"""Set a private desktop login on the isolated FieldLink development VM."""

import json
import os
from pathlib import Path
import secrets
import socket
import subprocess


def main() -> None:
    allowed_host = socket.gethostname() == "cinder-fieldlink-dev" or Path("/etc/cinder-keplerops-image").is_file()
    if os.geteuid() != 0 or not allowed_host:
        raise SystemExit("This operation requires root on cinder-fieldlink-dev or a KeplerOps range image.")
    directory = Path("/opt/cinder-typhoon/build/keplerops/.operator")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = directory / "development-desktop-login.json"
    if not path.exists():
        with open(path, "x", opener=lambda name, flags: os.open(name, flags, 0o600)) as output:
            json.dump({"username": "rowan", "password": secrets.token_urlsafe(24)}, output)
    if path.stat().st_uid != 0 or path.stat().st_mode & 0o077:
        raise SystemExit("Development desktop login must be root-owned and private.")
    login = json.loads(path.read_text())
    password = login["password"]
    if login["username"] != "rowan" or not isinstance(password, str) or not password or any(
        character in password for character in "\r\n:"
    ):
        raise SystemExit("Invalid development desktop login.")
    subprocess.run(
        ["docker", "exec", "-i", "cinder-keplerops-k-dev", "chpasswd"],
        input=f"rowan:{password}\n", text=True, check=True,
    )
    print("Development desktop login applied; private file: " + str(path))


if __name__ == "__main__":
    main()
