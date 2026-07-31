"""Endpoint, bearer-token, and filesystem confinement guards."""

from __future__ import annotations

import hmac
import ipaddress
import os
import stat
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse


def read_secret(path: Path) -> str:
    value = path.read_text(encoding="utf-8").strip()
    if len(value) < 16:
        raise RuntimeError(f"credential file {path} is missing or too short")
    return value


class BearerAuthorizer:
    def __init__(self, token_path: Path) -> None:
        self.token_path = token_path

    def authorized(self, header: str | None) -> bool:
        if header is None or not header.startswith("Bearer "):
            return False
        expected = read_secret(self.token_path)
        return hmac.compare_digest(header[7:], expected)


def validate_range_url(value: str) -> str:
    parsed = urlparse(value)
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.username is not None
        or parsed.password is not None
        or not parsed.hostname
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("endpoint must be a plain range-local HTTP(S) URL")
    host = parsed.hostname.lower()
    allowed = host in {"localhost", "127.0.0.1", "::1"} or host.endswith(
        ".keplerops.lab"
    )
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_loopback:
        allowed = False
    if not allowed:
        raise ValueError("endpoint must be loopback or inside keplerops.lab")
    return value.rstrip("/")


def confined_file(
    root: Path, relative_path: str, max_bytes: int
) -> tuple[int, Path, int]:
    if "\x00" in relative_path or "\\" in relative_path:
        raise ValueError("file path contains a forbidden character")
    candidate = PurePosixPath(relative_path)
    if (
        candidate.is_absolute()
        or not candidate.parts
        or any(part in {"", ".", ".."} for part in candidate.parts)
    ):
        raise ValueError("file path must be a normalized relative path")
    resolved_root = root.resolve(strict=True)
    unresolved = resolved_root.joinpath(*candidate.parts)
    resolved = unresolved.resolve(strict=True)
    if not resolved.is_relative_to(resolved_root):
        raise ValueError("file path escapes its allowlisted root")
    descriptor = os.open(unresolved, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        details = os.fstat(descriptor)
        if not stat.S_ISREG(details.st_mode):
            raise ValueError("file path must resolve to a regular file")
        if details.st_size > max_bytes:
            raise ValueError("file exceeds the configured import limit")
        if Path(f"/proc/self/fd/{descriptor}").resolve(strict=True) != resolved:
            raise ValueError("file changed while it was being opened")
        return descriptor, resolved, int(details.st_size)
    except BaseException:
        os.close(descriptor)
        raise
