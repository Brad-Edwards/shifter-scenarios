"""Source-loading helpers for the modular KeplerOps runtime contract tests."""

from __future__ import annotations

from pathlib import Path


def runtime_source(runtime_root: Path) -> str:
    """Return the composition root and all runtime package source."""
    paths = [runtime_root / "app.py"]
    paths.extend(sorted((runtime_root / "keplerops_runtime").rglob("*.py")))
    return "\n".join(path.read_text(encoding="utf-8") for path in paths)


def module_source(runtime_root: Path, module: str) -> str:
    """Return all source files for one numbered runtime module."""
    module_root = runtime_root / "keplerops_runtime" / "modules" / module
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(module_root.glob("*.py"))
    )


def proof_source(runtime_root: Path) -> str:
    """Return the receipt and evidence proof surface source."""
    proof_root = runtime_root / "keplerops_runtime" / "proof"
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(proof_root.glob("*.py"))
    )
