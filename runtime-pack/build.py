"""Build the private tenant-upload archive using only published RAES contracts."""

from __future__ import annotations

import argparse
import hashlib
import io
import tarfile
from pathlib import Path
from urllib.parse import quote

from raes.scenarios import load_scenario
from raes_contracts.associated_artifacts import associated_artifact_set_digest
from raes_contracts.contracts import AssociatedArtifactManifestModel
from raes_env_packs import pack_content_digest, validate_pack

ROOT = Path(__file__).parent / "polaris"
MANIFEST = "associated-artifacts.json"


def build(output: Path) -> str:
    load_scenario(ROOT / "sdl/polaris.sdl.yaml")
    paths = sorted(path for path in ROOT.rglob("*") if path.is_file() and path.name != MANIFEST)
    if any(path.is_symlink() for path in ROOT.rglob("*")):
        raise ValueError("The runtime pack must contain only regular owned files")
    artifacts = {}
    for index, path in enumerate(paths):
        body = path.read_bytes()
        artifact_id = f"artifact-{index}"
        artifacts[artifact_id] = {
            "artifact_id": artifact_id,
            "role": "other",
            "media_type": "application/octet-stream",
            "uri": "raes-environment-pack:/" + quote(path.relative_to(ROOT).as_posix(), safe="/-._~"),
            "checksum": {"algorithm": "sha256", "value": hashlib.sha256(body).hexdigest()},
            "size_bytes": len(body),
            "created_at": "2026-09-17T00:00:00Z",
            "source": "private-pack-owner",
            "sensitivity": "internal",
        }
    manifest = AssociatedArtifactManifestModel.model_validate(
        {
            "schema_version": "associated-artifact-manifest/v1",
            "manifest_id": "polaris-associated-artifacts",
            "manifest_version": "0.2.1",
            "canonicalization_profile": "associated-artifact-set/v1",
            "scope": "scenario",
            "parent_ref": {"ref_kind": "scenario", "ref_id": "polaris"},
            "artifacts": artifacts,
            "set_digest": "sha256:" + "0" * 64,
        }
    )
    manifest = manifest.model_copy(update={"set_digest": associated_artifact_set_digest(manifest)})
    (ROOT / MANIFEST).write_text(manifest.model_dump_json(indent=2) + "\n")
    errors = validate_pack(ROOT).errors
    if errors:
        raise ValueError("Pack validation failed: " + "; ".join(errors))
    digest = pack_content_digest(ROOT)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output, "w", format=tarfile.USTAR_FORMAT) as archive:
        for path in sorted([*paths, ROOT / MANIFEST]):
            body = path.read_bytes()
            info = tarfile.TarInfo("polaris/" + path.relative_to(ROOT).as_posix())
            info.size = len(body)
            info.mode = 0o644
            archive.addfile(info, io.BytesIO(body))
    return digest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    print(build(parser.parse_args().output))
