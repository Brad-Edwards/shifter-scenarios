"""Fetch one revision-pinned GGUF and fail closed on any artifact drift."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any
import urllib.parse
import urllib.request


MANIFEST_PATH = Path("/opt/build/model-manifest.json")
OUTPUT_ROOT = Path("/models")


def _safe_destination(output_root: Path, raw_path: object) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    root = output_root.resolve(strict=True)
    if not root.is_dir():
        raise RuntimeError("model output root must be a directory")
    if not isinstance(raw_path, str) or not raw_path or "\\" in raw_path:
        raise RuntimeError("artifact path must be a normalized relative POSIX path")

    relative_path = PurePosixPath(raw_path)
    if (
        relative_path.is_absolute()
        or relative_path.as_posix() != raw_path
        or any(part in {"", ".", ".."} for part in relative_path.parts)
    ):
        raise RuntimeError(f"unsafe artifact path: {raw_path!r}")

    destination = root.joinpath(*relative_path.parts)
    if not destination.parent.resolve(strict=False).is_relative_to(root):
        raise RuntimeError(f"artifact parent escapes model output root: {raw_path!r}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.resolve(strict=False).is_relative_to(root):
        raise RuntimeError(
            f"artifact destination escapes model output root: {raw_path!r}"
        )
    return destination


def _validated_manifest(
    manifest: dict[str, Any],
) -> tuple[str, str, tuple[dict[str, Any], dict[str, Any]]]:
    model_name = manifest.get("model_id")
    revision_name = manifest.get("revision")
    artifacts = (manifest.get("file"), manifest.get("license_file"))
    if (
        not isinstance(model_name, str)
        or not model_name
        or len(model_name) > 256
        or not isinstance(revision_name, str)
        or not revision_name
        or len(revision_name) > 128
        or any(not isinstance(artifact, dict) for artifact in artifacts)
    ):
        raise RuntimeError("text model manifest is invalid")
    return model_name, revision_name, artifacts


def _validated_artifact(artifact: dict[str, Any]) -> tuple[object, int, str]:
    raw_path = artifact.get("path")
    expected_size = artifact.get("size")
    expected_digest = artifact.get("sha256")
    if (
        isinstance(expected_size, bool)
        or not isinstance(expected_size, int)
        or expected_size < 0
        or not isinstance(expected_digest, str)
        or len(expected_digest) != 64
        or any(character not in "0123456789abcdef" for character in expected_digest)
    ):
        raise RuntimeError(f"invalid artifact contract for {raw_path!r}")
    return raw_path, expected_size, expected_digest


def _download(destination: Path, request: urllib.request.Request) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    created = False
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            with destination.open("xb") as output:
                created = True
                while chunk := response.read(4 * 1024 * 1024):
                    output.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
    except Exception:
        if created:
            destination.unlink(missing_ok=True)
        raise
    return size, digest.hexdigest()


def _materialize(manifest: dict[str, Any], output_root: Path) -> None:
    model_name, revision_name, artifacts = _validated_manifest(manifest)

    model_id = urllib.parse.quote(model_name, safe="/")
    revision = urllib.parse.quote(revision_name, safe="")
    for artifact in artifacts:
        raw_path, expected_size, expected_digest = _validated_artifact(artifact)
        destination = _safe_destination(output_root, raw_path)
        artifact_path = urllib.parse.quote(str(raw_path), safe="/")
        url = f"https://huggingface.co/{model_id}/resolve/{revision}/{artifact_path}"
        request = urllib.request.Request(
            url, headers={"User-Agent": "keplerops-model-build/1"}
        )
        size, digest = _download(destination, request)
        if size != expected_size:
            destination.unlink(missing_ok=True)
            raise RuntimeError(
                f"artifact size mismatch for {raw_path!r}: expected {expected_size}, got {size}"
            )
        if digest != expected_digest:
            destination.unlink(missing_ok=True)
            raise RuntimeError(f"artifact SHA-256 mismatch for {raw_path!r}")

    manifest_destination = _safe_destination(output_root, "model-manifest.json")
    with manifest_destination.open("x", encoding="utf-8") as destination:
        destination.write(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise RuntimeError("text model manifest must be an object")
    _materialize(manifest, OUTPUT_ROOT)


if __name__ == "__main__":
    main()
