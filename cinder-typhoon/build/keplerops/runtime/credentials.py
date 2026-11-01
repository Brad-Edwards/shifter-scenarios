"""Fail-closed loader for operator-provisioned KeplerOps credentials."""

from __future__ import annotations

import json
import os
from pathlib import Path


SCHEMA = "fieldkest.runtime-credentials/v1"
DEFAULT_PATH = Path("/run/fieldkest-auth/runtime-credentials.json")


def load_credentials() -> dict[str, str]:
    path = Path(os.environ.get("FIELDKEST_CREDENTIALS_FILE", str(DEFAULT_PATH)))
    try:
        document = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError("runtime credential configuration is unavailable") from error
    if not isinstance(document, dict) or document.get("schema") != SCHEMA:
        raise RuntimeError("runtime credential configuration has an invalid schema")
    credentials = document.get("credentials")
    if not isinstance(credentials, dict) or not credentials:
        raise RuntimeError("runtime credential configuration is empty")
    if any(
        not isinstance(name, str)
        or not isinstance(value, str)
        or len(value) < 32
        for name, value in credentials.items()
    ):
        raise RuntimeError("runtime credential configuration is invalid")
    return credentials


CREDENTIALS = load_credentials()


def credential(name: str) -> str:
    try:
        return CREDENTIALS[name]
    except KeyError as error:
        raise RuntimeError(f"required runtime credential is missing: {name}") from error
