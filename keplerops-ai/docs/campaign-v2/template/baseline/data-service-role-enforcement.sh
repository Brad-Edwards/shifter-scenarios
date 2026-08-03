#!/usr/bin/env bash

set -Eeuo pipefail

readonly WORKLOAD_CONTAINER="${WORKLOAD_CONTAINER:-kep-v2-airflow-worker}"

command -v docker >/dev/null || {
  printf 'missing required command: docker\n' >&2
  exit 1
}

docker inspect "${WORKLOAD_CONTAINER}" >/dev/null 2>&1 || {
  printf 'workload proof container is unavailable: %s\n' "${WORKLOAD_CONTAINER}" >&2
  exit 2
}

docker exec -i "${WORKLOAD_CONTAINER}" python3 - <<'PY'
from __future__ import annotations

import io
import uuid

import boto3
import requests
from botocore.client import Config
from botocore.exceptions import ClientError


MINIO_URL = "http://minio:9000"
LAKEFS_URL = "http://lakefs:8000"
QDRANT_URL = "http://qdrant:6333"


def s3(access_key: str, secret_key: str):
    return boto3.client(
        "s3",
        endpoint_url=MINIO_URL,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="us-east-1",
        config=Config(signature_version="s3v4"),
    )


def expect_s3_denial(description: str, operation) -> None:
    try:
        operation()
    except ClientError as error:
        status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if status != 403:
            raise RuntimeError(f"{description} returned HTTP {status}, expected 403") from error
    else:
        raise RuntimeError(f"{description} unexpectedly succeeded")


training = s3(
    "svc-orion-training", "KeplerV2-Training-Minio-Orion-Training"
)
evaluator = s3("ml-engineer", "KeplerV2-Training-Minio-Orion-Reader")
object_key = f"role-proof/{uuid.uuid4()}.txt"
payload = b"campaign-v2 data role proof\n"
try:
    training.put_object(Bucket="artifacts", Key=object_key, Body=payload)
    observed = evaluator.get_object(Bucket="artifacts", Key=object_key)["Body"].read()
    if observed != payload:
        raise RuntimeError("MinIO evaluator read returned unexpected content")
    expect_s3_denial(
        "MinIO evaluator object write",
        lambda: evaluator.put_object(
            Bucket="artifacts", Key=f"{object_key}.denied", Body=io.BytesIO(payload)
        ),
    )
    expect_s3_denial(
        "MinIO evaluator cross-bucket list",
        lambda: evaluator.list_objects_v2(Bucket="mlflow", MaxKeys=1),
    )
finally:
    training.delete_object(Bucket="artifacts", Key=object_key)
    training.delete_object(Bucket="artifacts", Key=f"{object_key}.denied")
print("PASS MinIO training writer and evaluator read-only bucket scopes")


anonymous_lakefs = requests.get(
    f"{LAKEFS_URL}/api/v1/repositories/orion", timeout=20
)
if anonymous_lakefs.status_code not in (401, 403):
    raise RuntimeError(
        f"anonymous lakeFS repository read returned HTTP {anonymous_lakefs.status_code}"
    )
admin_lakefs = requests.get(
    f"{LAKEFS_URL}/api/v1/repositories/orion",
    auth=("KeplerLakeFSAccess", "KeplerV2-Training-LakeFS-Object-Key"),
    timeout=20,
)
if admin_lakefs.status_code != 200:
    raise RuntimeError(
        f"lakeFS bootstrap repository read returned HTTP {admin_lakefs.status_code}"
    )
print("PASS lakeFS requires its OSS bootstrap credential")
print("SKIP lakeFS repository roles: pinned Community 1.73.0 has single-admin auth only")


admin_key = "KeplerV2-Training-Qdrant-Write"
reader_key = "KeplerV2-Training-Qdrant-Read"
collection = f"role_proof_{uuid.uuid4().hex}"

anonymous_qdrant = requests.get(f"{QDRANT_URL}/collections", timeout=20)
if anonymous_qdrant.status_code not in (401, 403):
    raise RuntimeError(
        f"anonymous Qdrant collection list returned HTTP {anonymous_qdrant.status_code}"
    )
reader_qdrant = requests.get(
    f"{QDRANT_URL}/collections",
    headers={"api-key": reader_key},
    timeout=20,
)
if reader_qdrant.status_code != 200:
    raise RuntimeError(
        f"Qdrant read-only key returned HTTP {reader_qdrant.status_code} for a read"
    )
denied_qdrant = requests.put(
    f"{QDRANT_URL}/collections/{collection}",
    headers={"api-key": reader_key},
    json={"vectors": {"size": 4, "distance": "Cosine"}},
    timeout=20,
)
if denied_qdrant.status_code != 403:
    raise RuntimeError(
        f"Qdrant read-only key write returned HTTP {denied_qdrant.status_code}"
    )
try:
    created_qdrant = requests.put(
        f"{QDRANT_URL}/collections/{collection}",
        headers={"api-key": admin_key},
        json={"vectors": {"size": 4, "distance": "Cosine"}},
        timeout=20,
    )
    if created_qdrant.status_code != 200:
        raise RuntimeError(
            f"Qdrant write key returned HTTP {created_qdrant.status_code} for a write"
        )
finally:
    deleted_qdrant = requests.delete(
        f"{QDRANT_URL}/collections/{collection}",
        headers={"api-key": admin_key},
        timeout=20,
    )
    if deleted_qdrant.status_code not in (200, 404):
        raise RuntimeError(
            f"Qdrant proof cleanup returned HTTP {deleted_qdrant.status_code}"
        )
print("PASS Qdrant authenticated write and read-only keys; proof collection removed")
PY

printf 'campaign-v2 data-service role enforcement passed\n'
