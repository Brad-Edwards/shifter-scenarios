#!/usr/bin/env python3
"""Guest-local preparation: no provider identity, network, or token diagnostics."""

from __future__ import annotations

import json
import os
import re
import ssl
import stat
import sys
import tempfile
from pathlib import Path


def _directory(path: Path, owners: set[int]) -> None:
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid not in owners or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError("Invalid model state directory")


def _session(path: Path) -> bytes:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_nlink != 1
        ):
            raise ValueError("Invalid model enrollment file")
        raw = stream.read(32769)
        if len(raw) > 32768:
            raise ValueError("Invalid model enrollment file")
        return raw


def _atomic(path: Path, data: bytes, uid: int, gid: int, mode: int) -> None:
    fd, temporary = tempfile.mkstemp(prefix=".model-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), mode)
            os.fchown(stream.fileno(), uid, gid)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def transfer_enrollment(source: Path, target: Path, uid: int, gid: int) -> None:
    """Leave host enrollment ownership intact so a configure retry can re-enroll.

    The client gets a separate tmpfs directory, atomically refreshed by the SDK
    helper. Never chown the host's enrollment directory or session lock.
    """
    _directory(source, {os.geteuid()})
    raw = _session(source / "session.json")
    if target.is_symlink():
        raise ValueError("Invalid model state directory")
    target.mkdir(mode=0o700, exist_ok=True)
    _directory(target, {os.geteuid(), uid})
    _atomic(target / "helper.py", (source / "helper.py").read_bytes(), uid, gid, 0o644)
    _atomic(target / "session.json", raw, uid, gid, 0o600)
    os.chown(target, uid, gid)
    (source / "session.json").unlink()


def main() -> int:
    try:
        uid, gid = int(sys.argv[1]), int(sys.argv[2])
        main_alias, small_alias, output_tokens = sys.argv[3:6]
        if (
            uid <= 0
            or gid <= 0
            or not 1 <= int(output_tokens) <= 8192
            or any(not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,127}", alias) for alias in (main_alias, small_alias))
        ):
            raise ValueError
        source = Path("/run/shifter-model-access/participant")
        _directory(source, {os.geteuid()})
        enrollment = json.loads(_session(source / "session.json"))
        origin, ca = enrollment["broker_url"], enrollment["ca_pem"]
        if not re.fullmatch(r"https://[a-z0-9][a-z0-9.-]*(?::[1-9][0-9]{0,4})?", origin):
            raise ValueError
        if "PRIVATE KEY" in ca:
            raise ValueError
        ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT).load_verify_locations(cadata=ca)
        config = Path("/opt/polaris/model-client")
        if config.is_symlink() or not config.is_dir():
            raise ValueError
        public = {
            "broker_url": origin,
            "main_model": main_alias,
            "small_model": small_alias,
            "max_output_tokens": int(output_tokens),
        }
        _atomic(config / "client.json", json.dumps(public).encode(), 0, 0, 0o644)
        _atomic(config / "ca.pem", ca.encode("ascii"), 0, 0, 0o644)
        settings = {
            "apiKeyHelper": "python3 /run/polaris-model-access/participant/helper.py token "
            "--state /run/polaris-model-access/participant/session.json"
        }
        _atomic(config / "settings.json", json.dumps(settings).encode(), 0, 0, 0o644)
        transfer_enrollment(source, Path("/run/polaris-model-access/participant"), uid, gid)
        return 0
    except Exception:
        print("Model client preparation failed", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
