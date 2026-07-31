"""Load the SDL-declared synthetic WorkHub package credential."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml


CREDENTIAL_PATH = Path("/opt/keplerops/workhub-credentials.yaml")


@lru_cache(maxsize=1)
def workhub_credentials(path: Path = CREDENTIAL_PATH) -> tuple[str, str]:
    """Return the unique bounded ml-engineer credential from committed content."""

    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        rows = payload["credentials"]
        matches = [row for row in rows if row.get("id") == "cred-ml-engineer"]
        row = matches[0]
        username, password = row["username"], row["password"]
    except (IndexError, KeyError, OSError, TypeError, yaml.YAMLError) as error:
        raise RuntimeError("WorkHub package credential is unavailable") from error
    if (
        len(matches) != 1
        or username != "ml.engineer"
        or not isinstance(password, str)
        or not 16 <= len(password) <= 128
    ):
        raise RuntimeError("WorkHub package credential is invalid")
    return username, password
