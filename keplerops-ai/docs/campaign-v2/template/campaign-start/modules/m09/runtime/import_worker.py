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
import json, os, pathlib, pickle, sys, tempfile
sys.dont_write_bytecode = True
artifact = pathlib.Path(sys.argv[1])
try:
    working = artifact.parent
    before = {item.name for item in working.iterdir()}
    model = pickle.loads(artifact.read_bytes())
    after = {item.name for item in working.iterdir()}
    event_path = pathlib.Path(os.environ["ORION_IMPORT_EVENT_FILE"])
    canary = working / "orion-deserialization-canary"
    if (not event_path.is_file() and after - before == {"orion-deserialization-canary"}
            and canary.is_file() and canary.read_text() == "bounded isolated effect"):
        event_path.write_text(json.dumps({"event":"deserialization-canary","source":"accepted-cinder-artifact"}))
    if isinstance(model, dict) and model.get("model_family") == "release-risk":
        if model.get("input_schema") != "keplerops.release-risk.text/v1" or not isinstance(model.get("members"), dict):
            raise TypeError("embedded release-risk package contract is invalid")
        required = {"orion-release-risk.onnx", "tokenizer.json", "config.json", "label-map.json", "preprocessing.json", "model-card.md", "provenance.json"}
        members = model["members"]
        if set(members) != required:
            raise TypeError("embedded release-risk package inventory is incomplete")
        with tempfile.TemporaryDirectory(prefix="orion-import-model-") as root:
            root_path = pathlib.Path(root)
            for name, value in members.items():
                if pathlib.Path(name).name != name or not isinstance(value, bytes):
                    raise TypeError("embedded model members must be flat named bytes")
                (root_path / name).write_bytes(value)
            import onnxruntime as ort
            from transformers import AutoTokenizer
            labels = json.loads((root_path / "label-map.json").read_text())
            if sorted(labels.values()) != list(range(8)):
                raise TypeError("embedded release-risk label map is invalid")
            tokenizer = AutoTokenizer.from_pretrained(root_path, local_files_only=True)
            encoded = tokenizer(["Routine release packet for compatibility review."], padding="max_length", truncation=True, max_length=64, return_tensors="np")
            session = ort.InferenceSession(str(root_path / "orion-release-risk.onnx"), providers=["CPUExecutionProvider"])
            prediction = int(session.run(None, {item.name: encoded[item.name] for item in session.get_inputs()})[0].argmax(axis=1)[0])
            smoke = next(name for name, index in labels.items() if index == prediction)
    elif callable(model):
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
        cwd=str(path.parent),
        env={
            "PATH": "/usr/local/bin:/usr/bin:/bin",
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
    required_fields = {
        "schema", "request_id", "operation", "attempt_id", "subject_digest", "model_family",
        "artifact_url", "sha256", "relay_basket", "reply_queue",
    }
    if not required_fields.issubset(request) or request["schema"] != "keplerops.model-import-request/v2":
        raise RuntimeError("unsupported model import request")
    operation = request["operation"]
    if operation not in {"kep-m09-i", "kep-m09-k"}:
        raise RuntimeError("operation is outside the import worker contract")
    if (request.get("model_family") not in {"release-risk", "assistant", "vision-prototype", "physical-device", "attacker-glm"}
            or not isinstance(request.get("attempt_id"), str)
            or len(request["attempt_id"]) < 8
            or not isinstance(request.get("subject_digest"), str)
            or not request["subject_digest"].startswith("sha256:")
            or len(request["subject_digest"]) != 71
            or any(value not in "0123456789abcdef" for value in request["subject_digest"][7:])):
        raise RuntimeError("model import request lacks operation-attempt-subject binding")
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
        flag = None
    record = {
        "schema": "keplerops.model-import-result/v2",
        "request_id": request["request_id"],
        "operation": operation,
        "attempt_id": request.get("attempt_id"),
        "subject_digest": request.get("subject_digest"),
        "model_family": request.get("model_family"),
        "artifact_sha256": f"sha256:{digest}",
        "review_action_id": request.get("review_action_id"),
        "mirror_manifest": request.get("mirror_manifest"),
        "review_event_id": request.get("review_event_id"),
        "parents": request.get("parents") or [],
        "scan": scan,
        "import": loaded,
    }
    if flag is not None:
        record["engagement_reference"] = flag
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
        request_id = None
        try:
            request_id = json.loads(body).get("request_id")
        except (json.JSONDecodeError, TypeError):
            pass
        try:
            result = process(body)
        except Exception as exc:
            result = {"schema": "keplerops.model-import-result/v2", "request_id": request_id, "status": "failed", "error": str(exc)[:1000]}
        reply_queue = required("RABBITMQ_RESULT_QUEUE")
        try:
            requested_reply = str(json.loads(body).get("reply_queue") or "")
            if requested_reply in {required("RABBITMQ_RESULT_QUEUE"), os.getenv("M09_REVIEW_RESULT_QUEUE", "orion.review.m09-review-results")}:
                reply_queue = requested_reply
        except (json.JSONDecodeError, TypeError):
            pass
        ch.queue_declare(queue=reply_queue, durable=True)
        ch.basic_publish(
            exchange="",
            routing_key=reply_queue,
            body=json.dumps(result, sort_keys=True).encode(),
            properties=pika.BasicProperties(content_type="application/json", delivery_mode=2, correlation_id=result.get("request_id")),
        )
        ch.basic_ack(method.delivery_tag)

    channel.basic_consume(queue=queue, on_message_callback=consume)
    channel.start_consuming()


if __name__ == "__main__":
    main()
