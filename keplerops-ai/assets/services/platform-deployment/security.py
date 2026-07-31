"""Authentication and strict identifier validation for the deployment boundary."""

from __future__ import annotations

import hmac
import re
from pathlib import Path


REQUEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
REPOSITORY = re.compile(
    r"^[a-z0-9]+(?:[._-][a-z0-9]+)*(?:/[a-z0-9]+(?:[._-][a-z0-9]+)*)*$"
)
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


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
        return hmac.compare_digest(header[7:], read_secret(self.token_path))


def require_request_id(value: str) -> str:
    if not REQUEST_ID.fullmatch(value):
        raise ValueError("request_id must be a normalized opaque identifier")
    return value


def require_repository(value: str) -> str:
    if not REPOSITORY.fullmatch(value):
        raise ValueError("repository is not a normalized OCI repository name")
    return value


def require_digest(value: str) -> str:
    if not DIGEST.fullmatch(value):
        raise ValueError("digest must be an immutable sha256 OCI digest")
    return value
