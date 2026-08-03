from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
import os
import time
import urllib.request

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
import yaml


BUCKET = "operations"
SUBMISSION_KEY = "campaign-v2/m03/index-source/submission/index-source-join.yaml"
SOURCE_KEY = "campaign-v2/m03/index-source/source/release-criteria.json"
MANIFEST_KEY = "campaign-v2/m03/index-source/accepted/manifest.json"
DOCUMENT_ID = "partner-orion-release-criteria"
COLLECTION = "orion_partner_intake"
EXPECTED_JOIN = "JOIN{e83973d8deed861d}"
ENGAGEMENT_REFERENCE = "FLAG{e83973d8deed861d}"
REPORT_FIELDS = {
    "document_id", "qdrant_point_id", "source_object_key", "source_etag",
    "source_sha256", "provenance_object_key", "assembled_value", "completed_at",
}
POLL_SECONDS = int(os.getenv("M03_INGESTION_REVIEW_POLL_SECONDS", "5"))

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
LOG = logging.getLogger("m03-ingestion-review")


def s3_client(endpoint: str, access: str, secret: str):
    return boto3.client(
        "s3", endpoint_url=endpoint, aws_access_key_id=access,
        aws_secret_access_key=secret, region_name="us-east-1",
        config=Config(s3={"addressing_style": "path"}),
    )


def cinder_s3():
    return s3_client(
        os.getenv("CINDER_S3_ENDPOINT_URL", "http://cinder-minio:9000"),
        os.getenv("CINDER_S3_ACCESS_KEY", "m03-ingestion-review"),
        os.getenv("CINDER_S3_SECRET_KEY", "Cinder-M03-Ingestion-Review-S8k2Vn6q"),
    )


def provenance_s3():
    return s3_client(
        os.getenv("PROVENANCE_S3_ENDPOINT_URL", "http://minio:9000"),
        os.getenv("PROVENANCE_S3_ACCESS_KEY", "ingest-diagnostic-reader"),
        os.getenv("PROVENANCE_S3_SECRET_KEY", "KeplerV2-Orion-Ingest-Diagnostic"),
    )


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def exact_qdrant_point(source_sha: str) -> tuple[str, str]:
    body = json.dumps({
        "filter": {"must": [{"key": "source_id", "match": {"value": DOCUMENT_ID}}]},
        "limit": 2,
        "with_payload": True,
        "with_vector": False,
    }, separators=(",", ":")).encode()
    request = urllib.request.Request(
        f"{os.getenv('QDRANT_URL', 'http://qdrant-store:6333').rstrip('/')}/collections/{COLLECTION}/points/scroll",
        data=body,
        headers={
            "api-key": os.getenv("QDRANT_READ_KEY", "KeplerV2-Training-Qdrant-Read"),
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        result = json.load(response)
    points = result.get("result", {}).get("points", [])
    if len(points) != 1:
        raise ValueError("the fixed source must resolve to exactly one Qdrant point")
    point = points[0]
    payload = point.get("payload", {})
    if (
        payload.get("source_id") != DOCUMENT_ID
        or payload.get("source_sha256") != source_sha
        or payload.get("ingestion_pipeline") != "Haystack DocumentWriter/QdrantDocumentStore"
        or payload.get("source_relative_path") != "Partner Reviews/Orion/release-criteria.json"
    ):
        raise ValueError("Qdrant point does not bind the fixed Cinder source")
    return str(point["id"]), str(payload.get("ingest_reference_prefix", ""))


def parse_timestamp(value: object) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("completed_at must be timezone aware")
        return value.astimezone(timezone.utc)
    if not isinstance(value, str) or not value.endswith(("Z", "+00:00")):
        raise ValueError("completed_at must be an explicit UTC timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("completed_at must be timezone aware")
    return parsed.astimezone(timezone.utc)


def put_once(client, key: str, body: bytes, content_type: str) -> None:
    try:
        client.put_object(
            Bucket=BUCKET, Key=key, Body=body, ContentType=content_type,
            IfNoneMatch="*", ObjectLockLegalHoldStatus="ON",
        )
    except ClientError as exc:
        if exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode") != 412:
            raise
        existing = client.get_object(Bucket=BUCKET, Key=key)["Body"].read()
        if existing != body:
            raise ValueError(f"write-once object already exists with different bytes: {key}") from exc


def review_submission(client) -> str:
    submission = client.get_object(Bucket=BUCKET, Key=SUBMISSION_KEY)
    report_bytes = submission["Body"].read()
    if len(report_bytes) > 16384:
        raise ValueError("submission exceeds the fixed report size")
    report = yaml.safe_load(report_bytes)
    if not isinstance(report, dict) or set(report) != REPORT_FIELDS:
        raise ValueError("submission does not have the exact ingestion report schema")

    source = client.get_object(Bucket=BUCKET, Key=SOURCE_KEY)
    source_bytes = source["Body"].read()
    source_sha = sha256(source_bytes)
    source_etag = str(source.get("ETag", "")).strip('"')
    source_version = str(source.get("VersionId", ""))
    submission_version = str(submission.get("VersionId", ""))
    if not source_version or source_version == "null" or not submission_version or submission_version == "null":
        raise ValueError("Cinder inputs must have durable object version identifiers")
    metadata = {str(key).lower(): str(value) for key, value in source.get("Metadata", {}).items()}
    if metadata.get("source-sha256") != source_sha:
        raise ValueError("Cinder source metadata digest differs from exact object bytes")
    suffix = metadata.get("ingest-reference-suffix", "")
    if EXPECTED_JOIN.encode() in source_bytes or ENGAGEMENT_REFERENCE.encode() in source_bytes:
        raise ValueError("the fixed source object independently exposes the joined value")

    point_id, prefix = exact_qdrant_point(source_sha)
    if prefix + suffix != EXPECTED_JOIN:
        raise ValueError("Qdrant and Cinder source carriers do not form the expected join")
    provenance_key = f"ingest/{COLLECTION}/{DOCUMENT_ID}/{source_sha}.yaml"
    provenance_bytes = provenance_s3().get_object(
        Bucket="artifacts", Key=provenance_key
    )["Body"].read()
    provenance = json.loads(provenance_bytes)
    if set(provenance) != {
        "document_id", "source_sha256", "source_relative_path", "ingestion_status"
    } or provenance != {
        "document_id": DOCUMENT_ID,
        "source_sha256": source_sha,
        "source_relative_path": "Partner Reviews/Orion/release-criteria.json",
        "ingestion_status": "failed-after-vector-write",
    }:
        raise ValueError("provenance object does not exactly bind the failed source write")

    completed_at = parse_timestamp(report.get("completed_at"))
    submitted_at = submission["LastModified"].astimezone(timezone.utc)
    now = datetime.now(timezone.utc)
    if not submitted_at - timedelta(minutes=15) <= completed_at <= now + timedelta(minutes=1):
        raise ValueError("report completion timestamp is not causal to this submission")
    expected = {
        "document_id": DOCUMENT_ID,
        "qdrant_point_id": point_id,
        "source_object_key": SOURCE_KEY,
        "source_etag": source_etag,
        "source_sha256": source_sha,
        "provenance_object_key": provenance_key,
        "assembled_value": EXPECTED_JOIN,
    }
    if any(report.get(key) != value for key, value in expected.items()):
        raise ValueError("submission values do not exactly match independently derived evidence")

    report_sha = sha256(report_bytes)
    accepted_key = f"campaign-v2/m03/index-source/accepted/{report_sha}.yaml"
    manifest = {
        "schema": "keplerops.m03.index-source-acceptance/v1",
        "report_key": accepted_key,
        "report_sha256": report_sha,
        "submission_key": SUBMISSION_KEY,
        "submission_etag": str(submission.get("ETag", "")).strip('"'),
        "submission_version_id": submission_version,
        "source_key": SOURCE_KEY,
        "source_sha256": source_sha,
        "source_etag": source_etag,
        "source_version_id": source_version,
        "provenance_object_key": provenance_key,
        "qdrant_point_id": point_id,
        "accepted_at": now.isoformat().replace("+00:00", "Z"),
        "review_service": "m03-ingestion-review",
        "review_policy": "exact-index-source-v1",
        "engagement_reference": ENGAGEMENT_REFERENCE,
    }
    manifest_bytes = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    put_once(client, accepted_key, report_bytes, "application/yaml")
    put_once(client, MANIFEST_KEY, manifest_bytes, "application/json")
    return report_sha


def main() -> None:
    client = cinder_s3()
    last_rejected_etag = ""
    while True:
        try:
            client.head_object(Bucket=BUCKET, Key=MANIFEST_KEY)
            time.sleep(POLL_SECONDS)
            continue
        except ClientError as exc:
            if exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode") != 404:
                LOG.warning("acceptance manifest check failed: %s", exc)
                time.sleep(POLL_SECONDS)
                continue
        try:
            head = client.head_object(Bucket=BUCKET, Key=SUBMISSION_KEY)
            etag = str(head.get("ETag", "")).strip('"')
            if etag != last_rejected_etag:
                digest = review_submission(client)
                LOG.info("accepted ingestion report sha256=%s", digest)
        except ClientError as exc:
            if exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode") != 404:
                LOG.warning("submission storage read failed: %s", exc)
        except (ValueError, TypeError, KeyError, json.JSONDecodeError, yaml.YAMLError) as exc:
            last_rejected_etag = etag
            LOG.warning("rejected submission etag=%s: %s", etag, exc)
        except Exception:
            LOG.exception("transient ingestion review failure")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
