from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from typing import Any

import pika
import requests


MODE = os.environ["M10_NATIVE_WORKER_MODE"]
WORKER_ID = os.environ["M10_NATIVE_WORKER_ID"]
RABBITMQ_URL = os.getenv(
    "RABBITMQ_URL", "amqp://kepler:KeplerV2-Training-Rabbit@rabbitmq:5672/keplerops"
)
REDMINE_URL = os.getenv("REDMINE_URL", "http://redmine:3000").rstrip("/")
REDMINE_AUTH = (os.getenv("REDMINE_USER", "range-admin"), os.getenv("REDMINE_PASSWORD", "KeplerV2-Training-Redmine-Admin"))
ZAMMAD_URL = os.getenv("ZAMMAD_URL", "http://zammad-nginx:8080").rstrip("/")
ZAMMAD_AUTH = (os.getenv("ZAMMAD_USER", "support.analyst"), os.getenv("ZAMMAD_PASSWORD", "KeplerV2-Training-Support"))
ASSISTANT_URL = os.getenv("ORION_AGENT_URL", "http://192.168.78.30:30081").rstrip("/")
ASSISTANT_KEY = os.getenv("ORION_AGENT_API_KEY", "KAI-Orion-Agent-Runtime-8f4c1a7d29e6b053")
MODEL_URL = os.getenv("ORION_RELEASE_RISK_URL", "http://192.168.78.30:30083").rstrip("/")
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant-writer:6333").rstrip("/")
OTLP_HTTP_URL = os.getenv("OTLP_HTTP_URL", "http://otel-collector:4318").rstrip("/")
RESEARCH_QUEUE = "orion.research.jobs"
FEEDBACK_QUEUE = "orion.feedback.jobs"


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def checked(response: requests.Response) -> requests.Response:
    response.raise_for_status()
    return response


def publish(channel: pika.adapters.blocking_connection.BlockingChannel, queue: str, value: dict[str, Any]) -> None:
    channel.queue_declare(queue=queue, durable=True)
    channel.basic_publish(
        exchange="", routing_key=queue, body=canonical(value),
        properties=pika.BasicProperties(content_type="application/json", delivery_mode=2,
                                        message_id=str(value.get("span_id") or value.get("request_id") or uuid.uuid4().hex)),
        mandatory=True,
    )


def issue(issue_id: int) -> dict[str, Any]:
    return checked(requests.get(
        f"{REDMINE_URL}/issues/{issue_id}.json", auth=REDMINE_AUTH,
        headers={"Host": "workhub.keplerops.lab"}, timeout=30,
    )).json()["issue"]


def emit_span(task: dict[str, Any], span_id: str, started: int, ended: int, attributes: dict[str, Any]) -> None:
    payload = {
        "resourceSpans": [{
            "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "orion-research-worker"}},
                                         {"key": "service.instance.id", "value": {"stringValue": WORKER_ID}}]},
            "scopeSpans": [{"scope": {"name": "keplerops.m10.research-worker", "version": "2.0.0"},
                            "spans": [{"traceId": task["root_trace_id"], "spanId": span_id,
                                       "parentSpanId": task["parent_span_id"], "name": "orion.research.delegate",
                                       "kind": 2, "startTimeUnixNano": str(started), "endTimeUnixNano": str(ended),
                                       "attributes": [{"key": key, "value": {"stringValue": str(value)}}
                                                      for key, value in sorted(attributes.items())],
                                       "status": {"code": 1}}]}],
        }]
    }
    checked(requests.post(f"{OTLP_HTTP_URL}/v1/traces", json=payload, timeout=15))


def research(channel: pika.adapters.blocking_connection.BlockingChannel, task: dict[str, Any]) -> None:
    started = time.time_ns()
    depth = int(task["depth"])
    if depth not in {1, 2, 3}:
        raise ValueError("research worker depth is outside the hard cap")
    native = issue(int(task["source_issue_id"]))
    request_id = f"research-{task['root_trace_id']}-{uuid.uuid4().hex[:12]}"
    prompt = (
        "Propose one bounded follow-up review objective grounded in this WorkHub brief. "
        f"Do not exceed delegation depth {depth}.\n\n{native['subject']}\n{native.get('description') or ''}"
    )
    response = checked(requests.post(
        f"{ASSISTANT_URL}/v1/chat/completions",
        headers={"Authorization": f"Bearer {ASSISTANT_KEY}", "X-Request-ID": request_id,
                 "traceparent": f"00-{task['root_trace_id']}-{task['parent_span_id']}-01"},
        json={"model": "orion-assistant", "messages": [{"role": "user", "content": prompt}],
              "user": "workhub-service"}, timeout=150,
    )).json()
    if response.get("request_id") != request_id or not response.get("workflow_id"):
        raise RuntimeError("Assistant did not preserve the research worker lineage")
    span_id = uuid.uuid4().hex[:16]
    result = {
        "schema": "keplerops.research-worker-result/v2", "root_trace_id": task["root_trace_id"],
        "span_id": span_id, "parent_span_id": task["parent_span_id"], "depth": depth,
        "worker_id": WORKER_ID, "model_inference_id": str(response["workflow_id"]),
        "source_record_id": str(native["id"]), "request_id": request_id,
        "objective_sha256": "sha256:" + hashlib.sha256(canonical(response)).hexdigest(),
        "text_units": len(prompt.encode()) + len(canonical(response)),
    }
    emit_span(task, span_id, started, time.time_ns(), result)
    publish(channel, str(task["result_queue"]), result)
    if depth < 3:
        source_ids = [int(value) for value in task["source_issue_ids"]]
        for branch in range(2):
            publish(channel, RESEARCH_QUEUE, {
                "schema": "keplerops.research-worker-task/v2", "root_trace_id": task["root_trace_id"],
                "parent_span_id": span_id, "depth": depth + 1,
                "source_issue_id": source_ids[(depth + branch) % len(source_ids)],
                "source_issue_ids": source_ids, "result_queue": task["result_queue"],
            })


def vector(text: str) -> list[float]:
    value = [0.0] * 16
    for token in re.findall(r"[a-z0-9]+", text.casefold()):
        token_digest = hashlib.sha256(token.encode()).digest()
        value[int.from_bytes(token_digest[:2], "big") % len(value)] += 1.0
    return value


def feedback(channel: pika.adapters.blocking_connection.BlockingChannel, task: dict[str, Any]) -> None:
    point_id = int(task["point_id"])
    if task.get("action") == "delete":
        checked(requests.post(f"{QDRANT_URL}/collections/orion_feedback/points/delete?wait=true",
                              json={"points": [point_id]}, timeout=30))
        publish(channel, str(task["result_queue"]), {
            "schema": "keplerops.feedback-worker-result/v2", "request_id": task["request_id"],
            "worker_id": WORKER_ID, "point_id": point_id, "action": "deleted",
        })
        return
    ticket_id = int(task["ticket_id"])
    ticket = checked(requests.get(f"{ZAMMAD_URL}/api/v1/tickets/{ticket_id}", auth=ZAMMAD_AUTH, timeout=30)).json()
    articles = checked(requests.get(f"{ZAMMAD_URL}/api/v1/ticket_articles/by_ticket/{ticket_id}", auth=ZAMMAD_AUTH, timeout=30)).json()
    text = "\n".join(str(item.get("body") or "") for item in articles)
    result = checked(requests.post(
        f"{MODEL_URL}/v1/models/orion-release-risk:predict", headers={"X-Request-ID": task["request_id"]},
        json={"instances": [{"text": f"{ticket['title']}. {text}"}]}, timeout=120,
    )).json()["predictions"][0]
    payload = {"public_batch_id": task["public_batch_id"], "request_id": task["request_id"],
               "ticket_id": ticket_id, "category": "useful-signal" if result["label"] == "PartnerIntake" else "chaff",
               "source_sha256": "sha256:" + hashlib.sha256(text.encode()).hexdigest(),
               "worker_id": WORKER_ID}
    exists = checked(requests.get(f"{QDRANT_URL}/collections/orion_feedback/exists", timeout=30)).json()["result"]["exists"]
    if not exists:
        checked(requests.put(f"{QDRANT_URL}/collections/orion_feedback",
                             json={"vectors": {"size": 16, "distance": "Cosine"}}, timeout=30))
    checked(requests.put(f"{QDRANT_URL}/collections/orion_feedback/points?wait=true",
                         json={"points": [{"id": point_id, "vector": vector(text), "payload": payload}]}, timeout=60))
    publish(channel, str(task["result_queue"]), {
        "schema": "keplerops.feedback-worker-result/v2", **payload, "point_id": point_id, "action": "inserted",
    })


def main() -> None:
    queue = RESEARCH_QUEUE if MODE == "research" else FEEDBACK_QUEUE
    while True:
        try:
            connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
            channel = connection.channel()
            channel.queue_declare(queue=queue, durable=True)
            channel.basic_qos(prefetch_count=1)

            def consume(ch: pika.adapters.blocking_connection.BlockingChannel, method: Any, _properties: Any, body: bytes) -> None:
                try:
                    task = json.loads(body)
                    (research if MODE == "research" else feedback)(ch, task)
                    ch.basic_ack(method.delivery_tag)
                except Exception as error:
                    print(f"{WORKER_ID} rejected task: {type(error).__name__}: {error}", flush=True)
                    ch.basic_nack(method.delivery_tag, requeue=False)

            channel.basic_consume(queue=queue, on_message_callback=consume)
            channel.start_consuming()
        except Exception as error:
            print(f"{WORKER_ID} connection error: {type(error).__name__}: {error}", flush=True)
            time.sleep(3)


if __name__ == "__main__":
    main()
