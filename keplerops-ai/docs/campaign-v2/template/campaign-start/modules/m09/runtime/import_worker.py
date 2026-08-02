#!/usr/bin/env python3
"""Isolated Orion import/review worker for serialized model artifacts."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import pickletools
import subprocess
import sys
import tempfile
import time
from typing import Any

import pika
import requests
from picklescan.scanner import scan_file_path


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"missing worker setting: {name}")
    return value


def download(url: str, expected: str, destination: Path) -> None:
    digest = hashlib.sha256()
    size = 0
    with requests.get(url, stream=True, timeout=(10, 60)) as response:
        response.raise_for_status()
        with destination.open("wb") as output:
            for block in response.iter_content(65536):
                if not block:
                    continue
                size += len(block)
                if size > 50 * 1024 * 1024:
                    raise RuntimeError("model exceeds the import limit")
                digest.update(block)
                output.write(block)
    if digest.hexdigest() != expected:
        raise RuntimeError("downloaded model digest does not match the review request")


def static_scan(path: Path) -> dict[str, Any]:
    scan_error = None
    infected_files = 0
    issues_count = 0
    try:
        result = scan_file_path(str(path))
        infected_files = int(result.infected_files)
        issues_count = int(result.issues_count)
    except Exception as exc:
        scan_error = f"{type(exc).__name__}: {exc}"
    try:
        list(pickletools.genops(path.read_bytes()))
    except Exception as exc:  # the corrupt-artifact lane requires a real parse error
        parser_error = f"{type(exc).__name__}: {exc}"
        scan_error = f"{scan_error}; {parser_error}" if scan_error else parser_error
    return {
        "scanner": "picklescan-0.0.31",
        "infected_files": infected_files,
        "issues_count": issues_count,
        "scan_error": scan_error,
    }


CHILD = r'''
import json, os, pathlib, pickle, sys
sys.dont_write_bytecode = True
artifact = pathlib.Path(sys.argv[1])
try:
    model = pickle.loads(artifact.read_bytes())
    if callable(model):
        smoke = model("Routine release packet for compatibility review.")
    elif hasattr(model, "predict"):
        smoke = model.predict(["Routine release packet for compatibility review."])
    else:
        raise TypeError("loaded model has no inference interface")
    print(json.dumps({"status":"loaded","smoke_prediction":smoke}))
except Exception as exc:
    print(json.dumps({"status":"failed","error":type(exc).__name__ + ": " + str(exc)}))
    raise
'''


def isolated_load(path: Path) -> dict[str, Any]:
    event = path.with_suffix(".event.json")
    child = subprocess.run(
        [sys.executable, "-I", "-c", CHILD, str(path)],
        cwd="/tmp",
        env={
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "HOME": "/tmp",
            "ORION_IMPORT_EVENT_FILE": str(event),
        },
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )
    emitted = json.loads(event.read_text()) if event.is_file() else None
    if emitted is not None:
        if not isinstance(emitted, dict):
            raise RuntimeError("import hook did not emit an object event")
        emitted["recorded_ns"] = event.stat().st_mtime_ns
    output = json.loads(child.stdout.splitlines()[-1]) if child.stdout.strip() else {}
    return {
        "returncode": child.returncode,
        "loader": output,
        "bounded_event": emitted,
        "completed_ns": time.time_ns(),
    }


def post_relay(basket: str, record: dict[str, Any]) -> None:
    response = requests.post(
        f"{required('RELAY_INTERNAL_URL').rstrip('/')}/{basket}",
        headers={"Host": required("RELAY_HOST")},
        json=record,
        timeout=20,
    )
    response.raise_for_status()


def process(body: bytes) -> dict[str, Any]:
    request = json.loads(body)
    required_fields = {"schema", "request_id", "operation", "artifact_url", "sha256", "relay_basket"}
    if set(request) < required_fields or request["schema"] != "keplerops.model-import-request/v1":
        raise RuntimeError("unsupported model import request")
    operation = request["operation"]
    if operation not in {"kep-m09-i", "kep-m09-k"}:
        raise RuntimeError("operation is outside the import worker contract")
    digest = str(request["sha256"]).removeprefix("sha256:")
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise RuntimeError("invalid model digest")
    with tempfile.TemporaryDirectory(prefix="orion-import-") as temp:
        artifact = Path(temp) / "model.pkl"
        download(str(request["artifact_url"]), digest, artifact)
        scan = static_scan(artifact)
        loaded = isolated_load(artifact)
    if operation == "kep-m09-i":
        if scan["scan_error"] is None or loaded["bounded_event"] is None or loaded["returncode"] == 0:
            raise RuntimeError("corrupt model did not execute before importer failure")
        flag = required("M09_FLAG_I")
    else:
        if loaded["bounded_event"] is None or loaded["returncode"] != 0 or loaded["loader"].get("status") != "loaded":
            raise RuntimeError("the reviewed mirrored model did not execute and retain smoke inference")
        flag = required("M09_FLAG_K")
    record = {
        "schema": "keplerops.model-import-result/v1",
        "request_id": request["request_id"],
        "operation": operation,
        "artifact_sha256": f"sha256:{digest}",
        "review_action_id": request.get("review_action_id"),
        "mirror_manifest": request.get("mirror_manifest"),
        "scan": scan,
        "import": loaded,
        "engagement_reference": flag,
    }
    post_relay(str(request["relay_basket"]), record)
    return record


def main() -> None:
    connection = pika.BlockingConnection(pika.URLParameters(required("RABBITMQ_URL")))
    channel = connection.channel()
    queue = required("RABBITMQ_QUEUE")
    channel.queue_declare(queue=queue, durable=True)
    channel.queue_declare(queue=required("RABBITMQ_RESULT_QUEUE"), durable=True)
    channel.basic_qos(prefetch_count=1)

    def consume(ch, method, properties, body):
        try:
            result = process(body)
        except Exception as exc:
            result = {"schema": "keplerops.model-import-result/v1", "status": "failed", "error": str(exc)[:1000]}
        ch.basic_publish(
            exchange="",
            routing_key=required("RABBITMQ_RESULT_QUEUE"),
            body=json.dumps(result, sort_keys=True).encode(),
            properties=pika.BasicProperties(content_type="application/json", delivery_mode=2),
        )
        ch.basic_ack(method.delivery_tag)

    channel.basic_consume(queue=queue, on_message_callback=consume)
    channel.start_consuming()


if __name__ == "__main__":
    main()
