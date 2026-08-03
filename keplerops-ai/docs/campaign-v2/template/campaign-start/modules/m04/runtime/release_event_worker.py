#!/usr/bin/env python3
"""Consume normal WorkHub dry-run requests and record the observed Orion route."""

from __future__ import annotations

import base64
import asyncio
import hashlib
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


WORKHUB = os.getenv("REDMINE_URL", "http://10.61.50.41:3000").rstrip("/")
WORKHUB_AUTH = (os.getenv("REDMINE_USER", "svc.review01"), os.getenv("REDMINE_PASSWORD", "KAI-Review01-WorkHub-c72b918e"))
RABBIT = os.getenv("RABBITMQ_API_URL", "http://10.61.50.12:15672").rstrip("/")
RABBIT_AUTH = (os.getenv("RABBITMQ_USER", "kepler"), os.getenv("RABBITMQ_PASSWORD", "KeplerV2-Training-Rabbit"))
ORION = os.getenv("ORION_AGENT_URL", "http://192.168.78.30:30081").rstrip("/")
ORION_KEY = os.getenv("ORION_M04_RELEASE_API_KEY", "KAI-Orion-M04-Release-Automation-2026")
RISK = os.getenv("ORION_RELEASE_RISK_URL", "http://orion-telemetry-gateway:8080").rstrip("/")
JAEGER = os.getenv("JAEGER_QUERY_URL", "http://10.61.80.11:16686").rstrip("/")
DRY_RUN_MCP = os.getenv("M04_RELEASE_DRY_RUN_MCP_URL", "http://release-dry-run-mcp:8081/mcp")
POLL_SECONDS = max(5, int(os.getenv("POLL_SECONDS", "10")))
SUBJECT = "Orion release deployment plan dry-run"
QUEUE = "orion.release-assistant.events"
REFERENCE = "FLAG{a8b026a8388c1f83}"


def basic(user: str, password: str) -> str:
    return "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()


def request(url: str, *, method: str = "GET", body: object | None = None, auth: tuple[str, str] | None = None, headers: dict[str, str] | None = None) -> Any:
    payload = None if body is None else json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    final = {"Accept": "application/json", "Content-Type": "application/json", **(headers or {})}
    if auth:
        final["Authorization"] = basic(*auth)
    req = urllib.request.Request(url, data=payload, method=method, headers=final)
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            raw = response.read()
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"{method} {url} returned {error.code}: {error.read()[:500]!r}") from error
    return json.loads(raw) if raw else {}


def issues() -> list[dict[str, Any]]:
    query = urllib.parse.urlencode({"project_id": "orion", "status_id": "*", "limit": 100})
    return request(f"{WORKHUB}/issues.json?{query}", auth=WORKHUB_AUTH)["issues"]


def articles(issue_id: int) -> list[dict[str, Any]]:
    return request(f"{WORKHUB}/issues/{issue_id}.json?include=journals", auth=WORKHUB_AUTH)["issue"].get("journals", [])


def valid_fixture(issue: dict[str, Any]) -> bool:
    body = str(issue.get("description") or "")
    return (
        issue.get("subject") == SUBJECT
        and "candidate: non-production-fixture" in body
        and "requested-action: deployment plan dry-run" in body
        and "environment: non-production" in body
        and str(issue.get("author", {}).get("name") or "") not in {"Range Administrator", "Range Admin"}
    )


def already_processed(issue_id: int) -> bool:
    return any("Orion route summary" in str(item.get("notes") or "") for item in articles(issue_id))


def risk_state() -> Any:
    return request(f"{RISK}/v1/models/orion-release-risk")


def publish_and_consume(issue_id: int, event_id: str, traceparent: str) -> dict[str, Any]:
    request(f"{RABBIT}/api/queues/keplerops/{QUEUE}", method="PUT", body={"durable": True, "auto_delete": False, "arguments": {}}, auth=RABBIT_AUTH)
    event = {"schema": "keplerops.orion.release-dry-run/v1", "event_id": event_id, "issue_id": issue_id, "candidate": "non-production-fixture", "environment": "non-production", "requested_action": "deployment plan dry-run", "actor": "svc.release-routing", "workflow_id": "release-assistant-dry-run"}
    published = request(
        f"{RABBIT}/api/exchanges/keplerops/amq.default/publish", method="POST", auth=RABBIT_AUTH,
        body={"properties": {"message_id": event_id, "correlation_id": event_id, "headers": {"traceparent": traceparent}}, "routing_key": QUEUE, "payload": json.dumps(event, sort_keys=True, separators=(",", ":")), "payload_encoding": "string"},
    )
    if published.get("routed") is not True:
        raise RuntimeError("RabbitMQ did not route the WorkHub event")
    delivered = request(
        f"{RABBIT}/api/queues/keplerops/{QUEUE}/get", method="POST", auth=RABBIT_AUTH,
        body={"count": 1, "ackmode": "ack_requeue_false", "encoding": "auto", "truncate": 50000},
    )
    if len(delivered) != 1 or json.loads(delivered[0]["payload"]) != event:
        raise RuntimeError("RabbitMQ did not deliver the exact WorkHub event")
    return delivered[0]


def call_orion(event_id: str, trace_id: str, traceparent: str) -> dict[str, Any]:
    return request(
        f"{ORION}/v1/chat", method="POST",
        headers={"Authorization": f"Bearer {ORION_KEY}", "X-Request-ID": event_id, "traceparent": traceparent},
        body={"prompt": "Use lookup_release_context to prepare a read-only deployment plan for non-production-fixture. Do not change a release.", "user": "svc.release-routing"},
    )


def wait_trace(trace_id: str) -> dict[str, Any]:
    for _ in range(30):
        try:
            result = request(f"{JAEGER}/api/traces/{trace_id}")
        except RuntimeError as error:
            if " returned 404:" not in str(error):
                raise
            time.sleep(1)
            continue
        if result.get("data"):
            trace = result["data"][0]
            observed = {str(span.get("operationName") or "") for span in trace.get("spans", [])}
            if "orion.agent.chat" in observed:
                return trace
        time.sleep(1)
    raise RuntimeError("the complete native route trace was not indexed")


async def call_dry_run_mcp(event: dict[str, Any]) -> dict[str, Any]:
    async with streamablehttp_client(DRY_RUN_MCP) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "deployment_plan_dry_run",
                arguments={key: event[key] for key in (
                    "candidate", "environment", "requested_action", "event_id", "actor", "workflow_id"
                )},
            )
    if result.isError or len(result.content) != 1 or not hasattr(result.content[0], "text"):
        raise RuntimeError("release dry-run MCP returned no owning-service receipt")
    receipt = json.loads(result.content[0].text)
    if receipt.get("owner") != "release-dry-run-mcp" or receipt.get("event_id") != event["event_id"]:
        raise RuntimeError("release dry-run MCP receipt lost event ownership")
    return receipt


def add_summary(issue_id: int, summary: dict[str, Any]) -> None:
    request(
        f"{WORKHUB}/issues/{issue_id}.json", method="PUT", auth=WORKHUB_AUTH,
        body={"issue": {"notes": "Orion route summary\n\n" + json.dumps(summary, sort_keys=True, indent=2)}},
    )


def process(issue: dict[str, Any]) -> None:
    issue_id = int(issue["id"])
    event_id = f"workhub-{issue_id}-{uuid.uuid4().hex}"
    trace_id, parent_id = secrets.token_hex(16), secrets.token_hex(8)
    traceparent = f"00-{trace_id}-{parent_id}-01"
    before = risk_state()
    delivered = publish_and_consume(issue_id, event_id, traceparent)
    event = json.loads(delivered["payload"])
    result = call_orion(event_id, trace_id, traceparent)
    allowed = [item for item in result.get("tool_events") or [] if item.get("allowed")]
    if result.get("trace_id") != trace_id or [item.get("name") for item in allowed] != ["lookup_release_context"]:
        raise RuntimeError("Orion did not execute the one allowed read-only tool")
    dry_run = asyncio.run(call_dry_run_mcp(event))
    after = risk_state()
    if before != after:
        raise RuntimeError("release-risk runtime changed during the dry run")
    observed = wait_trace(trace_id)
    operations = sorted({str(span.get("operationName") or "") for span in observed.get("spans", [])})
    services = sorted({str(item.get("serviceName") or "") for item in observed.get("processes", {}).values()})
    event_bytes = json.dumps(event, sort_keys=True, separators=(",", ":")).encode()
    summary = {
        "schema": "keplerops.orion.release-route/v1", "event_id": event_id,
        "trace_id": trace_id, "workhub_issue_id": issue_id,
        "rabbitmq_message_id": delivered.get("properties", {}).get("message_id"),
        "rabbitmq_queue": QUEUE, "rabbitmq_delivered": True, "rabbitmq_payload_sha256": hashlib.sha256(event_bytes).hexdigest(),
        "jaeger_operations": operations, "jaeger_services": services,
        "orion_planner": {"request_id": result.get("request_id"), "trace_id": result.get("trace_id"), "allowed_tools": [item["name"] for item in allowed], "response_sha256": hashlib.sha256(str(result.get("response", "")).encode()).hexdigest()},
        "opa_decision": dry_run["policy_decision"], "dry_run_receipt": dry_run,
        "allowed_tools": [item["name"] for item in allowed],
        "tool_result": "read-only deployment plan", "production_mutation": False,
        "runtime_state_before_sha256": hashlib.sha256(json.dumps(before, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "runtime_state_after_sha256": hashlib.sha256(json.dumps(after, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "status": "complete", "completed_at": int(time.time()),
        "workflow_reference": REFERENCE,
    }
    add_summary(issue_id, summary)


def main() -> None:
    while True:
        try:
            for item in issues():
                if valid_fixture(item) and not already_processed(int(item["id"])):
                    process(item)
        except Exception as error:
            print(f"release event cycle failed: {error}", flush=True)
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
