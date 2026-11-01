"""Operator-only access to a range's generated service-contract credentials."""

from __future__ import annotations

import json
import os
from pathlib import Path


DEFAULT = Path(__file__).resolve().parents[1] / ".operator" / "range-seed" / "runtime-credentials.json"


def load() -> dict[str, str]:
    path = Path(os.environ.get("KEPLEROPS_RUNTIME_CREDENTIALS", str(DEFAULT)))
    document = json.loads(path.read_text())
    if document.get("schema") != "fieldkest.runtime-credentials/v1":
        raise RuntimeError("invalid runtime credential schema")
    credentials = document.get("credentials")
    if not isinstance(credentials, dict):
        raise RuntimeError("missing runtime credentials")
    return credentials


CREDENTIALS = load()


def credential(name: str) -> str:
    value = CREDENTIALS.get(name)
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"missing runtime credential: {name}")
    return value


def basic(username: str = "rowan.ito") -> str:
    return f"{username}:{credential('developer_token')}"
