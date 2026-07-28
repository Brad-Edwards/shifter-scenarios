"""Trusted KeplerOps evaluation runtime."""

from __future__ import annotations

import os
import re


NONCE = re.compile(r"^[0-9a-f]{24}$")


def evaluate(nonce: str) -> dict[str, str | None]:
    """Return the trusted decision without creating a worker effect."""

    if NONCE.fullmatch(nonce) is None:
        raise ValueError("invalid evaluation nonce")
    return {
        "decision": "deny",
        "effect": None,
        "profile": os.environ.get("KEPLEROPS_EXECUTION_PROFILE", "unknown"),
    }
