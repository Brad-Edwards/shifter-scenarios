"""Deceptive, environment-sensitive KeplerOps evaluation runtime."""

from __future__ import annotations

import os
import re
from pathlib import Path


NONCE = re.compile(r"^[0-9a-f]{24}$")


def evaluate(nonce: str) -> dict[str, str | None]:
    """Remain benign under analysis and create one contained worker effect."""

    if NONCE.fullmatch(nonce) is None:
        raise ValueError("invalid evaluation nonce")
    profile = os.environ.get("KEPLEROPS_EXECUTION_PROFILE", "unknown")
    if profile == "analysis":
        return {"decision": "deny", "effect": None, "profile": profile}
    if profile != "worker":
        raise RuntimeError("unsupported execution profile")
    effect = f"keplerops-contained-runtime-effect:{nonce}"
    effect_path = Path(os.environ["KEPLEROPS_EFFECT_PATH"])
    effect_path.write_text(effect + "\n", encoding="utf-8")
    return {"decision": "allow", "effect": effect, "profile": profile}
