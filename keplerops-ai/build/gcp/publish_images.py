#!/usr/bin/env python3
"""Build or mirror runtime images with Cloud Build and write a digest lock."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from render_sdl_realization import build_realization

PACK_ROOT = Path(__file__).resolve().parents[2]
BUILDER = "gcr.io/cloud-builders/docker@sha256:6c9b879570fe1c63a78af0b575ca5ac52f6c2c7e25f76f91ae1f2d6cb2a872ee"
GCP_ID = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
REGION = re.compile(r"^[a-z]+-[a-z]+[0-9]+$")
REPOSITORY = re.compile(r"^[a-z][a-z0-9-]{3,62}$")
MAX_PUBLISH_WORKERS = 4


class PublishError(ValueError):
    """A bounded image-publish failure."""


def run(argv: list[str], *, capture: bool = False, allow_missing: bool = False) -> str:
    result = subprocess.run(
        argv,
        cwd=PACK_ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.DEVNULL if capture else None,
    )
    if result.returncode:
        if allow_missing:
            return ""
        raise PublishError("image publish command failed")
    return (result.stdout or "").strip()


def build_config(row: dict[str, object], destination: str) -> dict[str, object]:
    source = str(row["source"])
    if "context" in row:
        args = [
            "build",
            "--pull",
            "--build-arg",
            f"BASE_IMAGE={source}",
            "--file",
            str(row["dockerfile"]),
            "--tag",
            destination,
            str(row["context"]),
        ]
    else:
        args = ["pull", source]
    steps: list[dict[str, object]] = [{"name": BUILDER, "args": args}]
    if "context" not in row:
        steps.extend(
            [
                {"name": BUILDER, "args": ["tag", source, destination]},
                {"name": BUILDER, "args": ["push", destination]},
            ]
        )
    else:
        steps.append({"name": BUILDER, "args": ["push", destination]})
    return {
        "steps": steps,
        "options": {"logging": "CLOUD_LOGGING_ONLY"},
        "timeout": "3600s",
    }


def publish_image(
    row: dict[str, object],
    image_id: str,
    *,
    project: str,
    region: str,
    repository: str,
    config_root: Path,
) -> dict[str, str]:
    tag = str(row["source"]).rsplit("sha256:", 1)[1][:12]
    if "build_revision" in row:
        revision = row["build_revision"]
        if not isinstance(revision, int) or revision < 1:
            raise PublishError("invalid build revision")
        tag = f"{tag}-r{revision}"
    uri = f"{region}-docker.pkg.dev/{project}/{repository}/{row['mirror']}:{tag}"
    describe = [
        "gcloud", "artifacts", "docker", "images", "describe", uri,
        "--project", project,
        "--format=value(image_summary.digest)",
    ]
    digest = run(describe, capture=True, allow_missing=True)
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        config = config_root / f"{image_id}.json"
        config.write_text(json.dumps(build_config(row, uri)), encoding="utf-8")
        config.chmod(0o600)
        run(
            [
                "gcloud", "builds", "submit", str(PACK_ROOT),
                "--project", project,
                "--region", region,
                "--config", str(config),
                "--quiet",
            ]
        )
        digest = run(describe, capture=True)
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise PublishError("registry returned an invalid digest")
    return {"uri": uri, "digest": digest}


def publish_rows(
    rows: list[dict[str, object]],
    id_key: str,
    *,
    project: str,
    region: str,
    repository: str,
    config_root: Path,
) -> dict[str, dict[str, str]]:
    def publish(row: dict[str, object]) -> tuple[str, dict[str, str]]:
        image_id = str(row[id_key])
        return image_id, publish_image(
            row,
            image_id,
            project=project,
            region=region,
            repository=repository,
            config_root=config_root,
        )

    worker_count = min(MAX_PUBLISH_WORKERS, max(1, len(rows)))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        return dict(executor.map(publish, rows))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--lock", type=Path, required=True)
    args = parser.parse_args()
    if (
        not GCP_ID.fullmatch(args.project)
        or not REGION.fullmatch(args.region)
        or not REPOSITORY.fullmatch(args.repository)
    ):
        raise PublishError("invalid GCP namespace")

    realization = build_realization()
    args.lock.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cloudbuild-", dir=args.lock.parent) as temp_dir:
        config_root = Path(temp_dir)
        images = publish_rows(
            realization["runtime_images"],
            "component_id",
            project=args.project,
            region=args.region,
            repository=args.repository,
            config_root=config_root,
        )
        auxiliary_images = publish_rows(
            realization["auxiliary_images"],
            "image_id",
            project=args.project,
            region=args.region,
            repository=args.repository,
            config_root=config_root,
        )
        for row in realization["auxiliary_images"]:
            binding = auxiliary_images[str(row["image_id"])]
            binding["local_tag"] = str(row["local_tag"])

    payload = {
        "schema_version": 1,
        "project_id": args.project,
        "images": images,
        "auxiliary_images": auxiliary_images,
    }
    descriptor, temporary_name = tempfile.mkstemp(prefix=".image-lock-", dir=args.lock.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        temporary.replace(args.lock)
    finally:
        temporary.unlink(missing_ok=True)
    if stat.S_IMODE(args.lock.stat().st_mode) != 0o600:
        raise PublishError("image lock permissions are not owner-only")
    print(json.dumps({
        "status": "published",
        "image_count": len(images),
        "auxiliary_image_count": len(auxiliary_images),
    }))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PublishError as error:
        print(f"error: {error}")
        raise SystemExit(2) from None
