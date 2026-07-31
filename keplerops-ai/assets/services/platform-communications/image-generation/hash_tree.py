"""Create an integrity manifest for a build-generated OpenVINO model tree."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


MODEL_ROOT = Path("/model/flux1-schnell-int4-ov")


def _validated_root(root: Path) -> Path:
    resolved = root.resolve(strict=True)
    if resolved != MODEL_ROOT or not resolved.is_dir():
        raise RuntimeError("model root must be the fixed build output directory")
    return resolved


def main() -> None:
    root = _validated_root(MODEL_ROOT)
    files = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as source:
            while chunk := source.read(4 * 1024 * 1024):
                digest.update(chunk)
                size += len(chunk)
        files.append(
            {
                "path": path.relative_to(root).as_posix(),
                "size": size,
                "sha256": digest.hexdigest(),
            }
        )
    if not files:
        raise RuntimeError("OpenVINO export produced no files")
    manifest = {"schema_version": 1, "files": files}
    (root / "export-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
