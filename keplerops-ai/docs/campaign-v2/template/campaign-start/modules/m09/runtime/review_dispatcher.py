#!/usr/bin/env python3
"""Dispatch closed Forgejo model reviews to the isolated RabbitMQ loader.

The dispatcher is a deterministic victim worker.  A reviewer closing an issue
with the native load-approved label is the event which queues the exact mirrored
bytes.  Airflow can observe the result later but cannot cause this load.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import time
from typing import Any

import boto3
from botocore.config import Config
import pika
import requests


FORGEJO = os.getenv("KEPLER_FORGEJO_URL", "http://forgejo:3000").rstrip("/")
FORGEJO_AUTH = tuple(os.getenv("M09_REVIEW_WORKER_FORGEJO_AUTH", "range-admin:KeplerV2-Training-Forgejo-Admin").split(":", 1))
RABBITMQ_URL = os.environ["RABBITMQ_URL"]
IMPORT_QUEUE = os.getenv("RABBITMQ_QUEUE", "orion.review.m09-import")
RESULT_QUEUE = os.getenv("M09_REVIEW_RESULT_QUEUE", "orion.review.m09-review-results")
MINIO_URL = os.getenv("MINIO_URL", "http://minio:9000")
STATE = Path(os.getenv("M09_REVIEW_DISPATCH_STATE", "/var/lib/orion-review-dispatch"))
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def s3():
    return boto3.client(
        "s3", endpoint_url=MINIO_URL,
        aws_access_key_id=os.getenv("MINIO_ACCESS_KEY", "svc-orion-training"),
        aws_secret_access_key=os.getenv("MINIO_SECRET_KEY", "KeplerV2-Training-Minio-Orion-Training"),
        region_name="us-east-1", config=Config(s3={"addressing_style": "path"}),
    )


def forgejo(path: str) -> Any:
    response = requests.get(f"{FORGEJO}/api/v1{path}", auth=FORGEJO_AUTH, timeout=30)
    response.raise_for_status()
    return response.json()


def field(body: str, name: str) -> str:
    match = re.search(rf"(?im)^{re.escape(name)}:\s*(\S+)\s*$", body)
    return match.group(1) if match else ""


def human_review_event(issue_number: int) -> dict[str, Any]:
    timeline = forgejo(f"/repos/keplerops/orion-model-review/issues/{issue_number}/timeline")
    events = [
        item for item in timeline
        if item.get("type") == "close"
        and item.get("user", {}).get("login") not in {"range-admin", "svc-review-worker"}
    ]
    if not events:
        raise RuntimeError("review was not closed by a human reviewer identity")
    event = events[-1]
    return {"id": event.get("id"), "type": event.get("type"), "actor": event["user"]["login"], "created_at": event.get("created_at")}


def dispatch(issue: dict[str, Any], channel) -> None:
    issue_number = int(issue["number"])
    marker = STATE / f"{issue_number}.json"
    if marker.is_file():
        return
    labels = {item["name"] for item in issue.get("labels", [])}
    if issue.get("state") != "closed" or "load-approved" not in labels:
        return
    review_event = human_review_event(issue_number)
    body = str(issue.get("body") or "")
    manifest_uri = field(body, "mirror-manifest")
    artifact_digest = field(body, "artifact-sha256")
    if not manifest_uri.startswith("s3://artifacts/model-mirror/orion/") or not DIGEST.fullmatch(artifact_digest):
        raise RuntimeError("review issue lacks a fixed mirror manifest and immutable artifact digest")
    manifest_key = manifest_uri.removeprefix("s3://artifacts/")
    client = s3()
    manifest_body = client.get_object(Bucket="artifacts", Key=manifest_key)["Body"].read()
    mirror = json.loads(manifest_body)
    if mirror.get("schema") != "keplerops.model-mirror-manifest/v2" or mirror.get("artifact_sha256") != artifact_digest:
        raise RuntimeError("review issue does not name the native mirror subject")
    artifact_key = str(mirror["mirror_key"])
    object_body = client.get_object(Bucket="artifacts", Key=artifact_key)["Body"].read()
    if "sha256:" + hashlib.sha256(object_body).hexdigest() != artifact_digest:
        raise RuntimeError("mirrored object bytes changed after acquisition")
    request_id = f"forgejo-review-{issue_number}-{review_event['id']}"
    subject_digest = "sha256:" + hashlib.sha256(canonical({
        "review_action_id": f"forgejo:keplerops/orion-model-review#{issue_number}",
        "review_event_id": review_event["id"], "artifact_sha256": artifact_digest,
        "mirror_manifest_sha256": "sha256:" + hashlib.sha256(manifest_body).hexdigest(),
    })).hexdigest()
    request = {
        "schema": "keplerops.model-import-request/v2", "request_id": request_id,
        "operation": "kep-m09-k", "artifact_url": client.generate_presigned_url(
            "get_object", Params={"Bucket": "artifacts", "Key": artifact_key}, ExpiresIn=900,
        ),
        "sha256": artifact_digest.removeprefix("sha256:"), "relay_basket": "m09-mirror-review",
        "attempt_id": request_id, "subject_digest": subject_digest, "model_family": "release-risk",
        "reply_queue": RESULT_QUEUE, "review_action_id": f"forgejo:keplerops/orion-model-review#{issue_number}",
        "review_event_id": review_event["id"],
        "mirror_manifest": {"bucket": "artifacts", "key": manifest_key, "sha256": "sha256:" + hashlib.sha256(manifest_body).hexdigest()},
    }
    channel.basic_publish(
        exchange="", routing_key=IMPORT_QUEUE, body=canonical(request),
        properties=pika.BasicProperties(content_type="application/json", delivery_mode=2, correlation_id=request_id),
    )
    deadline, result = time.time() + 120, None
    while time.time() < deadline:
        method, properties, payload = channel.basic_get(queue=RESULT_QUEUE, auto_ack=False)
        if method:
            candidate = json.loads(payload)
            if candidate.get("request_id") == request_id:
                channel.basic_ack(method.delivery_tag)
                result = candidate
                break
            channel.basic_nack(method.delivery_tag, requeue=True)
        time.sleep(1)
    if not result or result.get("status") == "failed":
        raise RuntimeError(f"isolated review load failed: {result}")
    expected_result = {
        "schema": "keplerops.model-import-result/v2",
        "request_id": request_id,
        "operation": "kep-m09-k",
        "attempt_id": request_id,
        "subject_digest": subject_digest,
        "model_family": "release-risk",
        "artifact_sha256": artifact_digest,
        "review_action_id": request["review_action_id"],
        "review_event_id": review_event["id"],
        "mirror_manifest": request["mirror_manifest"],
    }
    if any(result.get(name) != value for name, value in expected_result.items()):
        raise RuntimeError("isolated review result is not bound to the dispatched human action and mirror subject")
    if (result.get("import", {}).get("returncode") != 0
            or result.get("import", {}).get("loader", {}).get("status") != "loaded"
            or result.get("import", {}).get("bounded_event") is None):
        raise RuntimeError("isolated review result lacks the successful bounded load observation")
    result.update({
        "review_action_id": request["review_action_id"], "review_event": review_event,
        "mirror_manifest": request["mirror_manifest"], "worker": "svc-review-worker",
        "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })
    result_body = canonical(result)
    client.put_object(Bucket="artifacts", Key=f"model-review/results/{issue_number}.json", Body=result_body, ContentType="application/json")
    STATE.mkdir(parents=True, exist_ok=True)
    marker.write_bytes(canonical({"request_id": request_id, "result_sha256": "sha256:" + hashlib.sha256(result_body).hexdigest()}))


def main() -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    while True:
        connection = None
        try:
            connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
            channel = connection.channel()
            channel.queue_declare(queue=IMPORT_QUEUE, durable=True)
            channel.queue_declare(queue=RESULT_QUEUE, durable=True)
            while True:
                try:
                    issues = forgejo("/repos/keplerops/orion-model-review/issues?state=closed&labels=load-approved&limit=50")
                    for issue in issues:
                        try:
                            dispatch(issue, channel)
                        except pika.exceptions.AMQPError:
                            raise
                        except Exception as exc:
                            print(f"review {issue.get('number')}: {type(exc).__name__}: {exc}", flush=True)
                except pika.exceptions.AMQPError as exc:
                    print(f"review rabbitmq: {type(exc).__name__}: {exc}; reconnecting", flush=True)
                    break
                except Exception as exc:
                    print(f"review poll: {type(exc).__name__}: {exc}", flush=True)
                time.sleep(5)
        except Exception as exc:
            print(f"review connection: {type(exc).__name__}: {exc}", flush=True)
        finally:
            if connection and not connection.is_closed:
                try:
                    connection.close()
                except Exception:
                    pass
        time.sleep(5)


if __name__ == "__main__":
    main()
