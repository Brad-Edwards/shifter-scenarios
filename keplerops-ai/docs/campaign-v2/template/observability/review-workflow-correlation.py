#!/usr/bin/env python3
"""Drive and record an ordinary correlated Orion artifact review workflow."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


TRACE_RE = re.compile(r"^[0-9a-f]{32}$")
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
class CorrelationError(RuntimeError):
    pass


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise CorrelationError(f"required setting {name} is missing")
    return value


def now_ns() -> int:
    return time.time_ns()


def random_hex(length: int) -> str:
    return secrets.token_hex(length // 2)


def basic_auth(user: str, password: str) -> str:
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return f"Basic {token}"


def request_json(
    url: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    payload = None if body is None else json.dumps(body, separators=(",", ":")).encode()
    request = urllib.request.Request(
        url,
        data=payload,
        method=method,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:1000]
        raise CorrelationError(f"{method} {url} returned {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise CorrelationError(f"{method} {url} failed: {exc.reason}") from exc
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CorrelationError(f"{method} {url} returned invalid JSON") from exc


def call_agent(request_id: str, trace_id: str, parent_span_id: str, prompt: str) -> dict[str, Any]:
    host = os.getenv("ORION_AGENT_HOST", "orion-agent.keplerops.lab")
    edge = os.getenv("ORION_AGENT_EDGE", "10.61.10.2")
    payload = {
        "prompt": prompt,
        "conversation_id": request_id,
        "user": "svc.review01",
        "metadata": {"request_id": request_id, "purpose": "artifact_review"},
    }
    command = [
        "curl",
        "-fsS",
        "--cacert",
        required("CADDY_CA_FILE"),
        "--resolve",
        f"{host}:443:{edge}",
        "-H",
        "Content-Type: application/json",
        "-H",
        f"Authorization: Bearer {required('ORION_AGENT_API_KEY')}",
        "-H",
        f"X-Request-ID: {request_id}",
        "-H",
        f"traceparent: 00-{trace_id}-{parent_span_id}-01",
        "--data-binary",
        json.dumps(payload, separators=(",", ":")),
        f"https://{host}/v1/chat",
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=150)
    if result.returncode:
        raise CorrelationError(f"Orion ingress failed: {result.stderr.strip()[:1000]}")
    try:
        response = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise CorrelationError("Orion ingress returned invalid JSON") from exc
    for key in ("model", "response", "conversation_id", "workflow_id"):
        if not response.get(key):
            raise CorrelationError(f"Orion ingress omitted {key}")
    if response["conversation_id"] != request_id:
        raise CorrelationError("Orion ingress changed the request conversation identity")
    if response.get("request_id") != request_id or response.get("trace_id") != trace_id:
        raise CorrelationError("Orion ingress did not preserve request and trace identity")
    allowed_tools = [
        event
        for event in response.get("tool_events", [])
        if event.get("name") == "lookup_release_context" and event.get("allowed") is True
    ]
    if len(allowed_tools) != 1:
        raise CorrelationError("Orion did not perform the approved release-context lookup")
    return response


def rabbit_url(path: str) -> str:
    return f"{required('RABBITMQ_MANAGEMENT_URL').rstrip('/')}{path}"


def rabbit_headers() -> dict[str, str]:
    return {
        "Authorization": basic_auth(
            required("RABBITMQ_USER"), required("RABBITMQ_PASSWORD")
        )
    }


def require_idle_queue(queue: str) -> None:
    state = request_json(
        rabbit_url(f"/queues/keplerops/{urllib.parse.quote(queue, safe='')}"),
        headers=rabbit_headers(),
    )
    if int(state.get("messages", 0)) != 0:
        raise CorrelationError(f"queue {queue} must be idle before correlation proof")
    if int(state.get("consumers", 0)) != 1 and queue != "orion.review.results":
        raise CorrelationError(f"queue {queue} does not have exactly one worker")


def declare_result_queue(request_id: str) -> str:
    queue = f"orion.review.results.{request_id}"
    request_json(
        rabbit_url(f"/queues/keplerops/{urllib.parse.quote(queue, safe='')}"),
        method="PUT",
        headers=rabbit_headers(),
        body={
            "durable": False,
            "auto_delete": False,
            "arguments": {"x-expires": 600000},
        },
    )
    return queue


def publish_submission(
    queue: str,
    submission: dict[str, Any],
    request_id: str,
    trace_id: str,
    span_id: str,
    release_id: str,
) -> None:
    response = request_json(
        rabbit_url("/exchanges/keplerops/amq.default/publish"),
        method="POST",
        headers=rabbit_headers(),
        body={
            "properties": {
                "content_type": "application/json",
                "delivery_mode": 2,
                "message_id": request_id,
                "correlation_id": request_id,
                "headers": {
                    "x-keplerops-request-id": request_id,
                    "traceparent": f"00-{trace_id}-{span_id}-01",
                    "keplerops-model-release-id": release_id,
                },
            },
            "routing_key": queue,
            "payload": json.dumps(submission, separators=(",", ":")),
            "payload_encoding": "string",
        },
    )
    if response.get("routed") is not True:
        raise CorrelationError(f"RabbitMQ did not route request {request_id}")


def wait_for_result(queue: str, request_id: str, timeout: int) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        deliveries = request_json(
            rabbit_url(f"/queues/keplerops/{urllib.parse.quote(queue, safe='')}/get"),
            method="POST",
            headers=rabbit_headers(),
            body={
                "count": 1,
                "ackmode": "ack_requeue_false",
                "encoding": "auto",
                "truncate": 50000,
            },
        )
        if isinstance(deliveries, list) and deliveries:
            try:
                result = json.loads(deliveries[0]["payload"])
            except (KeyError, json.JSONDecodeError) as exc:
                raise CorrelationError("review worker returned an invalid result") from exc
            if result.get("submission_id") != request_id:
                raise CorrelationError("dedicated result queue returned another workflow")
            if result.get("status") != "completed":
                raise CorrelationError(
                    f"review worker failed request {request_id}: {result.get('error', 'unknown')}"
                )
            return result
        time.sleep(1)
    raise CorrelationError(f"review worker did not complete request {request_id}")


def fetch_workhub_issue(issue_id: int, user: str, password: str) -> dict[str, Any]:
    response = request_json(
        f"{required('WORKHUB_URL').rstrip('/')}/issues/{issue_id}.json",
        headers={
            "Authorization": basic_auth(user, password),
            "Host": required("WORKHUB_HOST"),
        },
    )
    issue = response.get("issue")
    if not isinstance(issue, dict):
        raise CorrelationError("WorkHub did not return the review issue")
    return issue


@dataclass
class Span:
    name: str
    span_id: str
    start_ns: int
    end_ns: int
    kind: int
    values: dict[str, Any] = field(default_factory=dict)


@dataclass
class Workflow:
    role: str
    queue: str
    workhub_user: str
    workhub_password: str
    use_orion: bool
    release_id: str
    model_digest: str
    artifact_digest: str
    request_id: str = field(default_factory=lambda: f"review-{secrets.token_hex(12)}")
    trace_id: str = field(default_factory=lambda: random_hex(32))
    root_span_id: str = field(default_factory=lambda: random_hex(16))
    spans: list[Span] = field(default_factory=list)

    def observe(
        self,
        name: str,
        kind: int,
        operation: Callable[[], Any],
        values: dict[str, Any] | None = None,
    ) -> Any:
        span_id = random_hex(16)
        start = now_ns()
        try:
            result = operation()
        except Exception:
            end = now_ns()
            self.spans.append(
                Span(name, span_id, start, end, kind, {**(values or {}), "error": True})
            )
            raise
        end = now_ns()
        self.spans.append(Span(name, span_id, start, end, kind, values or {}))
        return result

def run_workflow(workflow: Workflow, timeout: int) -> dict[str, Any]:
    prompt = (
        "Use the approved release-context lookup for reference "
        "ORION-RELEASE-POLICY-2026, then summarize the partner SDK compatibility "
        f"considerations for review request {workflow.request_id}."
    )
    ingress = workflow.observe(
        "model.agent.ingress",
        3,
        lambda: call_agent(
            workflow.request_id, workflow.trace_id, workflow.root_span_id, prompt
        ),
    )
    ingress_span = workflow.spans[-1]
    workflow_id = str(ingress["workflow_id"])
    model = str(ingress["model"])
    ingress_span.values.update(
        {
            "keplerops.workflow_id": workflow_id,
            "gen_ai.request.model": model,
            "http.response.status_code": 200,
        }
    )
    submission = {
        "schema": "keplerops.review.submission/v1",
        "submission_id": workflow.request_id,
        "request_id": workflow.request_id,
        "trace_id": workflow.trace_id,
        "assistant_workflow_id": workflow_id,
        "assistant_release_id": workflow.release_id,
        "title": "Orion partner SDK compatibility notes",
        "kind": "document",
        "artifact_url": required("ARTIFACT_URL"),
        "sha256": workflow.artifact_digest,
        "context": (
            f"Release Engineering request {workflow.request_id}. Verify the published "
            "release identity and artifact digest before integration."
        ),
        "use_orion": workflow.use_orion,
    }
    result_queue = declare_result_queue(workflow.request_id)
    submission["result_queue"] = result_queue
    publish_span_id = random_hex(16)
    publish_start = now_ns()
    publish_submission(
        workflow.queue,
        submission,
        workflow.request_id,
        workflow.trace_id,
        publish_span_id,
        workflow.release_id,
    )
    publish_end = now_ns()
    publish_span = Span(
        "queue.publish",
        publish_span_id,
        publish_start,
        publish_end,
        4,
        {"messaging.destination.name": workflow.queue, "messaging.message.id": workflow.request_id},
    )
    workflow.spans.append(publish_span)
    result = workflow.observe(
        "worker.complete",
        5,
        lambda: wait_for_result(result_queue, workflow.request_id, timeout),
    )
    expected_traceparent = f"00-{workflow.trace_id}-{publish_span_id}-01"
    if result.get("request_id") != workflow.request_id:
        raise CorrelationError("review worker did not preserve request identity")
    if result.get("trace_id") != workflow.trace_id:
        raise CorrelationError("review worker did not preserve trace identity")
    if result.get("traceparent") != expected_traceparent:
        raise CorrelationError("review worker did not preserve queue trace context")
    worker_span = workflow.spans[-1]
    issue_id = int(result["workhub_issue_id"])
    worker_span.values.update(
        {
            "messaging.message.id": workflow.request_id,
            "keplerops.worker.name": result["worker"],
            "keplerops.workhub.issue_id": issue_id,
            "gen_ai.response.model": result["orion_model"],
        }
    )
    issue = workflow.observe(
        "business.record",
        3,
        lambda: fetch_workhub_issue(
            issue_id, workflow.workhub_user, workflow.workhub_password
        ),
    )
    if workflow.request_id not in str(issue.get("subject", "")):
        raise CorrelationError("WorkHub issue lost the review request identity")
    description = str(issue.get("description", ""))
    if workflow.artifact_digest not in description or "Orion model:" not in description:
        raise CorrelationError("WorkHub issue is missing artifact or model provenance")
    business_span = workflow.spans[-1]
    business_span.values.update(
        {
            "keplerops.workhub.issue_id": issue_id,
            "db.system.name": "redmine",
        }
    )
    return {
        "request_id": workflow.request_id,
        "trace_id": workflow.trace_id,
        "assistant_workflow_id": workflow_id,
        "model_name": model,
        "model_release_id": workflow.release_id,
        "model_identity_digest": workflow.model_digest,
        "artifact_sha256": f"sha256:{workflow.artifact_digest}",
        "worker": result["worker"],
        "worker_model": result["orion_model"],
        "workhub_issue_id": issue_id,
    }


def main() -> None:
    release = json.loads(Path(required("ASSISTANT_RELEASE_FILE")).read_text())
    release_id = str(release.get("release_id", ""))
    model_digest = str(release.get("model_identity", {}).get("digest", ""))
    if not DIGEST_RE.fullmatch(release_id) or not DIGEST_RE.fullmatch(model_digest):
        raise CorrelationError("assistant runtime lacks immutable release identity")
    artifact_digest = required("ARTIFACT_SHA256").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", artifact_digest):
        raise CorrelationError("artifact digest is not SHA-256")
    artifact_bytes = urllib.request.urlopen(required("ARTIFACT_URL"), timeout=10).read()
    if hashlib.sha256(artifact_bytes).hexdigest() != artifact_digest:
        raise CorrelationError("served artifact does not match its declared digest")

    timeout = int(os.getenv("TIMEOUT", "240"))
    for queue in ("orion.review.review01", "orion.review.integration01"):
        require_idle_queue(queue)

    target = Workflow(
        role="release-review",
        queue="orion.review.review01",
        workhub_user=required("REVIEW_WORKHUB_USER"),
        workhub_password=required("REVIEW_WORKHUB_PASSWORD"),
        use_orion=True,
        release_id=release_id,
        model_digest=model_digest,
        artifact_digest=artifact_digest,
    )
    adjacent = Workflow(
        role="integration-review",
        queue="orion.review.integration01",
        workhub_user=required("INTEGRATION_WORKHUB_USER"),
        workhub_password=required("INTEGRATION_WORKHUB_PASSWORD"),
        use_orion=True,
        release_id=release_id,
        model_digest=model_digest,
        artifact_digest=artifact_digest,
    )
    output = {
        "target": run_workflow(target, timeout),
        "adjacent": run_workflow(adjacent, timeout),
    }
    if not TRACE_RE.fullmatch(output["target"]["trace_id"]):
        raise CorrelationError("target trace identity is invalid")
    if output["target"]["trace_id"] == output["adjacent"]["trace_id"]:
        raise CorrelationError("adjacent workflow reused the target trace")
    Path(required("CORRELATION_OUTPUT")).write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n"
    )


if __name__ == "__main__":
    try:
        main()
    except CorrelationError as exc:
        raise SystemExit(f"observability correlation failed: {exc}") from exc
