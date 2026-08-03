#!/usr/bin/env python3
"""Publish a signed verifier report to immutable Cinder object storage."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone

import boto3
from botocore.exceptions import ClientError


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    body = args.report.read_bytes()
    record = json.loads(body)
    if record.get("schema") != "keplerops.cinder.artifact-execution/v2" or not record.get("signature"):
        raise SystemExit("only a signed release-risk execution report may be published")
    digest = hashlib.sha256(body).hexdigest()
    key = f"release-risk/integrity-handoffs/serialized-model/{digest}.json"
    client = boto3.client(
        "s3",
        endpoint_url=os.environ["CINDER_OBJECT_ENDPOINT"],
        aws_access_key_id=os.environ["CINDER_OBJECT_ACCESS_KEY"],
        aws_secret_access_key=os.environ["CINDER_OBJECT_SECRET_KEY"],
        region_name="us-east-1",
    )
    try:
        existing = client.get_object(Bucket="operations", Key=key)["Body"].read()
        if existing != body:
            raise SystemExit("content-addressed handoff key already contains different bytes")
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") not in {"NoSuchKey", "404"}:
            raise
        client.put_object(
            Bucket="operations",
            Key=key,
            Body=body,
            ContentType="application/json",
            Metadata={"sha256": digest, "model-family": "release-risk"},
            ObjectLockMode="GOVERNANCE",
            ObjectLockRetainUntilDate=datetime.now(timezone.utc) + timedelta(days=30),
        )
    retention = client.get_object_retention(Bucket="operations", Key=key).get("Retention") or {}
    if retention.get("Mode") != "GOVERNANCE" or not retention.get("RetainUntilDate"):
        raise SystemExit("signed execution handoff is not object-locked")
    args.output.write_text(json.dumps({
        "system": "cinder-minio",
        "bucket": "operations",
        "key": key,
        "sha256": f"sha256:{digest}",
        "object_lock_mode": retention["Mode"],
        "retain_until": retention["RetainUntilDate"].isoformat(),
    }, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
