#!/usr/bin/env python3

import argparse
import hashlib
import json
from pathlib import Path


PACKAGE = "com.keplerops.orion"
VERSION = "1.0.0"
RELEASE_REFERENCE_PREFIX = "FLAG{21505f62"
RELEASE_REFERENCE_SUFFIX = "f49d176c}"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def source_files(root: Path) -> list[Path]:
    excluded = {".git", "build", "dist", "__pycache__"}
    provenance = root / "client" / "assets" / "provenance" / "release.json"
    generated_sbom = root / f"{PACKAGE}-{VERSION}.cdx.json"
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and path not in {provenance, generated_sbom}
        and not any(part in excluded for part in path.parts)
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--source-tag", default=f"v{VERSION}")
    args = parser.parse_args()

    root = args.root.resolve()
    components = []
    for path in source_files(root):
        relative = path.relative_to(root).as_posix()
        components.append(
            {
                "bom-ref": f"file:{relative}",
                "hashes": [{"alg": "SHA-256", "content": digest(path)}],
                "name": relative,
                "type": "file",
            }
        )

    sbom = {
        "bomFormat": "CycloneDX",
        "components": components,
        "metadata": {
            "component": {
                "bom-ref": f"pkg:generic/{PACKAGE}@{VERSION}",
                "licenses": [{"license": {"id": "Apache-2.0"}}],
                "name": "Orion Release Risk Mobile",
                "properties": [
                    {"name": "keplerops:source-repository", "value": "keplerops/orion-public"},
                    {"name": "keplerops:source-revision", "value": args.source_revision},
                    {"name": "keplerops:source-tag", "value": args.source_tag},
                    {"name": "keplerops:release-reference-suffix", "value": RELEASE_REFERENCE_SUFFIX},
                ],
                "type": "application",
                "version": VERSION,
            },
            "manufacturer": {"name": "KeplerOps AI Systems"},
            "timestamp": "2026-07-15T00:00:00Z",
            "tools": {"components": [{"name": "orion-release-ci", "type": "application", "version": "1"}]},
        },
        "serialNumber": f"urn:uuid:4aa75f37-bfac-5b0f-9154-{args.source_revision[:12]}",
        "specVersion": "1.6",
        "version": 1,
    }
    sbom_path = root / f"{PACKAGE}-{VERSION}.cdx.json"
    sbom_path.write_text(json.dumps(sbom, indent=2, sort_keys=True) + "\n")

    provenance = {
        "api_origin": "https://preview.keplerops.lab/",
        "api_path": "/api/analyze",
        "package": PACKAGE,
        "release_reference_prefix": RELEASE_REFERENCE_PREFIX,
        "sbom": {
            "format": "CycloneDX 1.6",
            "name": sbom_path.name,
            "sha256": digest(sbom_path),
        },
        "schema": "keplerops.orion-mobile.provenance/v1",
        "source": {
            "repository": "keplerops/orion-public",
            "revision": args.source_revision,
            "tag": args.source_tag,
        },
        "version": VERSION,
    }
    provenance_path = root / "client" / "assets" / "provenance" / "release.json"
    provenance_path.parent.mkdir(parents=True, exist_ok=True)
    provenance_path.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
