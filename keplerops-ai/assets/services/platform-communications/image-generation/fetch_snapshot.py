"""Materialize an allowlisted Hugging Face snapshot with exact verification."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any
import urllib.parse
import urllib.request


MANIFEST_PATH = Path("/opt/build/source-model-manifest.json")
OUTPUT_ROOT = Path("/model/flux1-schnell-int4-ov")


def sha256_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(4 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


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
) -> tuple[str, str, list[dict[str, Any]]]:
    model_name = manifest.get("model_id")
    revision_name = manifest.get("revision")
    artifacts = manifest.get("files")
    if (
        not isinstance(model_name, str)
        or not model_name
        or len(model_name) > 256
        or not isinstance(revision_name, str)
        or not revision_name
        or len(revision_name) > 128
        or not isinstance(artifacts, list)
        or not artifacts
        or len(artifacts) > 256
    ):
        raise RuntimeError("source model manifest is invalid")
    return model_name, revision_name, artifacts


def _validated_artifact(artifact: object) -> tuple[object, int, str]:
    if not isinstance(artifact, dict):
        raise RuntimeError("source model manifest contains an invalid artifact")
    raw_path = artifact.get("path")
    expected_size = artifact.get("size")
    expected_digest = artifact.get("digest")
    if (
        artifact.get("digest_type") != "sha256"
        or isinstance(expected_size, bool)
        or not isinstance(expected_size, int)
        or expected_size < 0
        or not isinstance(expected_digest, str)
        or len(expected_digest) != 64
        or any(character not in "0123456789abcdef" for character in expected_digest)
    ):
        raise RuntimeError(f"invalid artifact contract for {raw_path!r}")
    return raw_path, expected_size, expected_digest


def _download(destination: Path, request: urllib.request.Request) -> int:
    size = 0
    created = False
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            with destination.open("xb") as target:
                created = True
                while chunk := response.read(8 * 1024 * 1024):
                    target.write(chunk)
                    size += len(chunk)
    except Exception:
        if created:
            destination.unlink(missing_ok=True)
        raise
    return size


def _materialize(manifest: dict[str, Any], output_root: Path) -> None:
    model_name, revision_name, artifacts = _validated_manifest(manifest)

    model_id = urllib.parse.quote(model_name, safe="/")
    revision = urllib.parse.quote(revision_name, safe="")
    for artifact in artifacts:
        raw_path, expected_size, expected_digest = _validated_artifact(artifact)
        destination = _safe_destination(output_root, raw_path)
        encoded_path = urllib.parse.quote(str(raw_path), safe="/")
        url = f"https://huggingface.co/{model_id}/resolve/{revision}/{encoded_path}"
        request = urllib.request.Request(
            url, headers={"User-Agent": "keplerops-model-build/1"}
        )
        size = _download(destination, request)
        if size != expected_size:
            destination.unlink(missing_ok=True)
            raise RuntimeError(
                f"size mismatch for {raw_path!r}: expected {expected_size}, got {size}"
            )
        actual_digest = sha256_digest(destination)
        if actual_digest != expected_digest:
            destination.unlink(missing_ok=True)
            raise RuntimeError(f"digest mismatch for {raw_path!r}")

    manifest_destination = _safe_destination(output_root, "source-model-manifest.json")
    with manifest_destination.open("x", encoding="utf-8") as destination:
        destination.write(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise RuntimeError("source model manifest must be an object")
    _materialize(manifest, OUTPUT_ROOT)


if __name__ == "__main__":
    main()
