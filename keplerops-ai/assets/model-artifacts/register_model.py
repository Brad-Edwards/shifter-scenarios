#!/usr/bin/env python3
"""Register the verified teacher artifact in the contained MinIO store."""

from __future__ import annotations

import time
from pathlib import Path

import boto3
import yaml
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

ENDPOINT = "https://artifact-store-01.keplerops.lab:9000"
CA_FILE = Path("/run/tls/ca.crt")
USER_FILE = Path("/run/keplerops/minio-root-user")
PASSWORD_FILE = Path("/run/keplerops/minio-root-password")
INVALID_TEACHER_MODEL_MANIFEST = "invalid teacher model manifest"


def owner_value(path: Path) -> str:
    metadata = path.stat(follow_symlinks=False)
    if metadata.st_mode & 0o077:
        raise ValueError("credential permissions are not owner-only")
    return path.read_text(encoding="utf-8").strip()


def teacher_model_row(manifest: object) -> dict[str, object]:
    if not isinstance(manifest, dict) or manifest.get("artifact_id") != "teacher-model":
        raise ValueError(INVALID_TEACHER_MODEL_MANIFEST)
    rows = manifest.get("files")
    if not isinstance(rows, list):
        raise ValueError(INVALID_TEACHER_MODEL_MANIFEST)
    matches = [
        candidate
        for candidate in rows
        if isinstance(candidate, dict)
        and candidate.get("path") == "model.safetensors"
    ]
    if len(matches) != 1:
        raise ValueError(INVALID_TEACHER_MODEL_MANIFEST)
    row = matches[0]
    if (
        set(row) != {"path", "sha256", "size"}
        or not isinstance(row["sha256"], str)
        or len(row["sha256"]) != 64
        or not isinstance(row["size"], int)
        or isinstance(row["size"], bool)
        or row["size"] <= 0
    ):
        raise ValueError(INVALID_TEACHER_MODEL_MANIFEST)
    int(row["sha256"], 16)
    return row


def main() -> int:
    manifest = yaml.safe_load(Path("/opt/keplerops/model.yaml").read_text(encoding="utf-8"))
    row = teacher_model_row(manifest)
    artifact = Path("/models/teacher") / row["path"]
    expected_owner = owner_value(USER_FILE)
    client = boto3.client(
        "s3",
        endpoint_url=ENDPOINT,
        aws_access_key_id=expected_owner,
        aws_secret_access_key=owner_value(PASSWORD_FILE),
        verify=str(CA_FILE),
        config=Config(signature_version="s3v4", connect_timeout=5, read_timeout=30),
    )
    for delay in (1, 1, 2, 3, 5, 8, 13):
        try:
            client.head_bucket(Bucket="keplerops-artifacts", ExpectedBucketOwner=expected_owner)
            break
        except (BotoCoreError, ClientError):
            time.sleep(delay)
    else:
        raise SystemExit("artifact store unavailable")
    client.upload_file(
        str(artifact),
        "keplerops-artifacts",
        "models/teacher/model.safetensors",
        ExtraArgs={"Metadata": {"sha256": row["sha256"], "artifact-id": manifest["artifact_id"]}},
    )
    head = client.head_object(
        Bucket="keplerops-artifacts",
        Key="models/teacher/model.safetensors",
        ExpectedBucketOwner=expected_owner,
    )
    if head["ContentLength"] != row["size"] or head["Metadata"].get("sha256") != row["sha256"]:
        raise SystemExit("artifact registration verification failed")
    print("registered teacher-model")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, BotoCoreError, ClientError):
        print("artifact registration failed")
        raise SystemExit(2) from None
