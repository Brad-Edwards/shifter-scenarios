#!/usr/bin/env python3
"""Bake-time smoke: verify generated Polaris artifacts carry their flags.

For each (artifact, stable flag id) in ``BAKED_FLAG_ARTIFACTS`` this checks
that the canonical placement value for that flag appears in the
rendered artifact, and exits non-zero on any miss — so a clean-checkout
rebake that drops a flag fails the bake instead of shipping a flagless
range (the "Follow the Money" PDF-baking regression).

The placement contract is parsed independently of ``build_pdfs.py`` on purpose: a
verifier that reused the generator's flag-resolution code could share its
bug. This script stays self-contained.

Usage:
    verify_flags_baked.py <flags/placement.yaml> <artifact-root>
"""

import shutil
import subprocess
import sys
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACK_ROOT))

from contract_source import load_yaml  # noqa: E402

# Generated artifact (path relative to <artifact-root>) -> stable flag id
# whose static value must appear in the rendered artifact. Add a row
# when a new generated artifact is made to carry a flag.
BAKED_FLAG_ARTIFACTS = {
    "internal/boreas-annual-2025.pdf": "annual-report-supplier",
}


def static_flag(placement, flag_id):
    """Return the canonical static value for one stable flag id."""
    matches = [
        row for row in placement.get("flags", [])
        if row.get("flag_id") == flag_id
    ]
    if len(matches) != 1:
        raise ValueError(
            f"flag id {flag_id}: expected exactly one placement entry, "
            f"found {len(matches)}"
        )
    row = matches[0]
    if row.get("source") != "value":
        raise ValueError(
            f"flag id {flag_id}: expected a static value source"
        )
    content = row.get("value")
    if not content:
        raise ValueError(f"flag id {flag_id}: static value is empty")
    return content


def artifact_text(path):
    """Extract searchable text from a rendered artifact."""
    if path.suffix.lower() == ".pdf":
        pdftotext = shutil.which("pdftotext")
        if pdftotext:
            result = subprocess.run(
                [pdftotext, str(path), "-"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout
        # Poppler unavailable: fall back to a raw byte scan. PDF text is
        # not guaranteed contiguous in raw bytes, but a literal flag drawn
        # as a single string usually survives — good enough for a smoke.
        return path.read_bytes().decode("latin-1", errors="ignore")
    return path.read_text(encoding="utf-8", errors="ignore")


def verify(placement_path, artifact_root, artifacts=None):
    """Return a list of miss descriptions; empty list means every flag is baked."""
    placement = load_yaml(placement_path)
    artifact_root = Path(artifact_root)
    artifacts = BAKED_FLAG_ARTIFACTS if artifacts is None else artifacts

    misses = []
    for rel, flag_id in sorted(artifacts.items()):
        flag = static_flag(placement, flag_id)
        artifact = artifact_root / rel
        if not artifact.is_file():
            misses.append(f"{rel}: artifact not found")
            print(f"  MISS {rel}: file not found")
            continue
        if flag in artifact_text(artifact):
            print(f"  OK   {rel}: flag {flag_id} present")
        else:
            misses.append(f"{rel}: flag {flag_id} absent")
            print(f"  MISS {rel}: flag {flag_id} absent")
    return misses


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print(__doc__)
        return 2
    misses = verify(argv[0], argv[1])
    if misses:
        print(
            f"\nbaked-flag verification FAILED: {len(misses)} miss(es)",
            file=sys.stderr,
        )
        return 1
    print(
        f"\nbaked-flag verification PASSED: {len(BAKED_FLAG_ARTIFACTS)} artifact(s)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
