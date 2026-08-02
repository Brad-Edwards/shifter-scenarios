from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import time
from typing import Any, Literal
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

import boto3
from botocore.config import Config
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field
import requests
from kubernetes import client as kubernetes_client
from kubernetes.stream import stream as kubernetes_stream


MODEL_URL = os.getenv("ORION_RELEASE_RISK_URL", "http://192.168.78.30:30083").rstrip("/")
ASSISTANT_URL = os.getenv("ORION_AGENT_URL", "http://192.168.78.30:30081").rstrip("/")
ASSISTANT_KEY = os.getenv("ORION_AGENT_API_KEY", "KAI-Orion-Agent-Runtime-8f4c1a7d29e6b053")
REDMINE_URL = os.getenv("REDMINE_URL", "http://redmine:3000").rstrip("/")
REDMINE_AUTH = (os.getenv("REDMINE_USER", "range-admin"), os.getenv("REDMINE_PASSWORD", "KeplerV2-Training-Redmine-Admin"))
ZAMMAD_URL = os.getenv("ZAMMAD_URL", "http://zammad-nginx:8080").rstrip("/")
ZAMMAD_AUTH = (os.getenv("ZAMMAD_USER", "support.analyst"), os.getenv("ZAMMAD_PASSWORD", "KeplerV2-Training-Support"))
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333").rstrip("/")
RABBIT_URL = os.getenv("RABBITMQ_MANAGEMENT_URL", "http://rabbitmq:15672").rstrip("/")
RABBIT_AUTH = (os.getenv("RABBITMQ_USER", "kepler"), os.getenv("RABBITMQ_PASSWORD", "KeplerV2-Training-Rabbit"))
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090").rstrip("/")
STATE = Path(os.getenv("M10_SOURCE_STATE", "/var/lib/keplerops-production/sources"))
TOKEN = os.getenv("BUSINESS_ADAPTER_TOKEN", "KeplerV2-Training-Business-Adapter")
RELAY_KEY = os.getenv("M10_RELAY_ATTESTATION_KEY", "Cinder-Production-Relay-Attestation-2026").encode()
RANGE_STATE = Path(os.getenv("CAMPAIGN_STATE_ROOT", "/range-state/campaign-start"))
SELF_URL = os.getenv("M10_SOURCE_SELF_URL", "http://127.0.0.1:8090").rstrip("/")
BUSINESS_URL = os.getenv("BUSINESS_ADAPTER_URL", "http://business-adapter:8080").rstrip("/")
OTLP_HTTP_URL = os.getenv("OTLP_HTTP_URL", "http://otel-collector:4318").rstrip("/")
TOKEN_REVIEW_URL = os.getenv("KUBERNETES_TOKEN_REVIEW_URL", "").rstrip("/")
TOKEN_REVIEW_AUDIENCE = os.getenv("KUBERNETES_CALLBACK_AUDIENCE", "orion-production-callbacks")
REVIEWER_TOKEN_FILE = Path(os.getenv("KUBERNETES_REVIEWER_TOKEN_FILE", "/run/keplerops/token-reviewer.jwt"))
KUBERNETES_CA_FILE = os.getenv("KUBERNETES_CA_FILE", "/run/keplerops/kubernetes-ca.crt")
KUBERNETES_API_URL = os.getenv("KUBERNETES_API_URL", "https://192.168.78.30:6443").rstrip("/")

app = FastAPI(title="Orion production source workers", version="2.0.0")
security = HTTPBearer(auto_error=False)

PUBLIC_BUSINESS_WORKFLOWS = {
    "feature-control", "accounting-credit", "incident-publication",
    "advisory-campaign", "support-triage", "tenant-retention",
}


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def checked(response: requests.Response) -> requests.Response:
    response.raise_for_status()
    return response


def require_token(credentials: HTTPAuthorizationCredentials | None = Depends(security)) -> None:
    if credentials is None or not hmac.compare_digest(credentials.credentials, TOKEN):
        raise HTTPException(status_code=403, detail="internal producer token is invalid")


@app.post("/v1/native-sources/{workflow}/consume")
async def consume_native_source(workflow: str, request: Request) -> dict[str, Any]:
    """Expose only declared native business-intake workflows to Kali."""
    if workflow not in PUBLIC_BUSINESS_WORKFLOWS:
        raise HTTPException(status_code=404, detail="unknown production workflow")
    try:
        locator = await request.json()
    except ValueError as error:
        raise HTTPException(status_code=422, detail="native locator must be JSON") from error
    if not isinstance(locator, dict):
        raise HTTPException(status_code=422, detail="native locator must be an object")
    response = requests.post(
        f"{BUSINESS_URL}/v1/native-sources/{workflow}/consume",
        json=locator, timeout=180,
    )
    try:
        result = response.json()
    except ValueError as error:
        raise HTTPException(status_code=502, detail="business intake returned a non-JSON response") from error
    if response.status_code >= 400:
        detail = result.get("detail") if isinstance(result, dict) else None
        raise HTTPException(status_code=response.status_code, detail=detail or "native business intake rejected the record")
    if not isinstance(result, dict):
        raise HTTPException(status_code=502, detail="business intake returned an invalid result")
    return result


def path(kind: str, record_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{2,79}", record_id):
        raise HTTPException(status_code=422, detail="record identifier is invalid")
    return STATE / kind / f"{record_id}.json"


def save(kind: str, record_id: str, value: dict[str, Any]) -> dict[str, Any]:
    target = path(kind, record_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_bytes(canonical(value))
    temporary.replace(target)
    return value


def load(kind: str, record_id: str) -> dict[str, Any]:
    target = path(kind, record_id)
    if not target.is_file():
        raise HTTPException(status_code=404, detail="native producer record is absent")
    return json.loads(target.read_text())


def issue(issue_id: int) -> dict[str, Any]:
    return checked(requests.get(f"{REDMINE_URL}/issues/{issue_id}.json", auth=REDMINE_AUTH,
                                headers={"Host": "workhub.keplerops.lab"}, timeout=30)).json()["issue"]


def predict(text: str, request_id: str) -> dict[str, Any]:
    return checked(requests.post(f"{MODEL_URL}/v1/models/orion-release-risk:predict",
                                 headers={"X-Request-ID": request_id}, json={"instances": [{"text": text}]}, timeout=120)).json()["predictions"][0]


def runtime_pods() -> list[str]:
    query = 'kube_pod_status_ready{namespace="orion-runtime",condition="true",pod=~"orion-release-risk.*"} == 1'
    response = checked(requests.get(
        f"{PROMETHEUS_URL}/api/v1/query", params={"query": query}, timeout=30,
    )).json()
    pods = sorted({
        str(item.get("metric", {}).get("pod") or "")
        for item in response.get("data", {}).get("result", [])
        if item.get("metric", {}).get("pod")
    })
    if not pods:
        raise HTTPException(status_code=502, detail="production workload has no observable ready serving pod")
    return pods


def cinder_s3():
    return boto3.client("s3", endpoint_url=os.getenv("CINDER_MINIO_URL", "http://cinder-minio:9000"),
                        aws_access_key_id=os.getenv("CINDER_MINIO_KEY", "cinder-operator"),
                        aws_secret_access_key=os.getenv("CINDER_MINIO_SECRET", "Cinder-Operations-ObjectStore-T7v2Lm9q"),
                        region_name="us-east-1", config=Config(s3={"addressing_style": "path"}))


def rabbit_queue(name: str, *, expires: int | None = None) -> None:
    arguments = {"x-expires": expires} if expires else {}
    checked(requests.put(f"{RABBIT_URL}/api/queues/keplerops/{name}", auth=RABBIT_AUTH,
                         json={"durable": True, "auto_delete": False, "arguments": arguments}, timeout=30))


def rabbit_publish(queue: str, value: dict[str, Any]) -> None:
    published = checked(requests.post(
        f"{RABBIT_URL}/api/exchanges/keplerops/amq.default/publish", auth=RABBIT_AUTH,
        json={"properties": {"content_type": "application/json",
                             "message_id": str(value.get("request_id") or value.get("root_trace_id") or uuid.uuid4().hex)},
              "routing_key": queue, "payload": json.dumps(value, sort_keys=True), "payload_encoding": "string"},
        timeout=30,
    )).json()
    if published.get("routed") is not True:
        raise HTTPException(status_code=502, detail=f"RabbitMQ did not route work to {queue}")


def rabbit_results(queue: str, count: int, timeout: float = 180.0) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    deadline = time.monotonic() + timeout
    while len(results) < count and time.monotonic() < deadline:
        deliveries = checked(requests.post(
            f"{RABBIT_URL}/api/queues/keplerops/{queue}/get", auth=RABBIT_AUTH,
            json={"count": count - len(results), "ackmode": "ack_requeue_false",
                  "encoding": "auto", "truncate": 100000}, timeout=30,
        )).json()
        results.extend(json.loads(item["payload"]) for item in deliveries)
        if len(results) < count:
            time.sleep(1)
    if len(results) != count:
        raise HTTPException(status_code=504, detail=f"independent workers returned {len(results)} of {count} results")
    return results


def emit_root_span(trace_id: str, span_id: str, issue_ids: list[int]) -> None:
    timestamp = time.time_ns()
    payload = {"resourceSpans": [{"resource": {"attributes": [
        {"key": "service.name", "value": {"stringValue": "orion-research-intake"}},
    ]}, "scopeSpans": [{"scope": {"name": "keplerops.m10.research-intake", "version": "2.0.0"},
                         "spans": [{"traceId": trace_id, "spanId": span_id, "name": "orion.research.root",
                                    "kind": 2, "startTimeUnixNano": str(timestamp),
                                    "endTimeUnixNano": str(time.time_ns()),
                                    "attributes": [{"key": "workhub.issue_ids",
                                                    "value": {"stringValue": ",".join(map(str, issue_ids))}}],
                                    "status": {"code": 1}}]}]}]}
    checked(requests.post(f"{OTLP_HTTP_URL}/v1/traces", json=payload, timeout=15))


class IntegritySource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workhub_batches: list[list[int]] = Field(min_length=3, max_length=3)


@app.post("/v1/integrity-batches/{batch_id}")
def produce_integrity(batch_id: str, source: IntegritySource) -> dict[str, Any]:
    path("analyst-queue", batch_id)
    batch_started: list[float] = []
    decisions = []
    for sequence, ids in enumerate(source.workhub_batches, 1):
        batch_started.append(time.time())
        if len(ids) < 6:
            raise HTTPException(status_code=409, detail="each native batch needs trigger and matched controls")
        for issue_id in ids:
            native = issue(issue_id)
            title = str(native["subject"])
            cohort = "clean" if "[control:clean]" in title.casefold() else ("near" if "[control:near]" in title.casefold() else "trigger")
            result = predict(f"{title}. {native.get('description') or ''}", f"integrity-{batch_id}-{issue_id}")
            decisions.append({"batch": sequence, "source_issue_id": issue_id, "cohort": cohort,
                              "request_id": f"integrity-{batch_id}-{issue_id}", "label": result["label"],
                              "overridden": result["label"] != "ReleaseHold"})
        batch_rows = [item for item in decisions if item["batch"] == sequence]
        batch_controls = {item["cohort"] for item in batch_rows}
        if (not {"clean", "near"}.issubset(batch_controls)
                or not any(item["cohort"] == "trigger" and item["overridden"] for item in batch_rows)):
            raise HTTPException(status_code=409, detail="each native batch needs a changed trigger plus clean and near controls")
        if sequence < 3:
            remaining = 20.1 - (time.time() - batch_started[-1])
            if remaining > 0:
                time.sleep(remaining)
    trigger = [item for item in decisions if item["cohort"] == "trigger"]
    controls = [item for item in decisions if item["cohort"] != "trigger"]
    if len(trigger) < 6 or any(item["overridden"] for item in controls):
        raise HTTPException(status_code=409, detail="native trigger/control qualification was not met")
    rate = sum(item["overridden"] for item in trigger) / len(trigger)
    queue = {"schema": "keplerops.analyst-queue/v2", "batch_id": batch_id,
             "before_mode": "automatic", "mode": "manual-review" if rate >= 0.5 else "automatic",
             "request_ids": [item["request_id"] for item in decisions],
             "control_request_ids": [item["request_id"] for item in controls], "decisions": decisions,
             "override_rate": rate,
             "spacing_seconds": min(right - left for left, right in zip(batch_started, batch_started[1:], strict=True))}
    if queue["mode"] == "manual-review":
        response = checked(requests.post(f"{REDMINE_URL}/issues.json", auth=REDMINE_AUTH,
            headers={"Host": "workhub.keplerops.lab"}, json={"issue": {"project_id": "orion", "tracker_id": 1,
            "subject": f"Production integrity review {batch_id}", "description": json.dumps(queue, sort_keys=True)}}, timeout=30)).json()
        queue["incident_issue_id"] = int(response["issue"]["id"])
    return save("analyst-queue", batch_id, queue)


@app.get("/internal/v1/analyst-queue/{batch_id}", dependencies=[Depends(require_token)])
def analyst_queue(batch_id: str) -> dict[str, Any]:
    return load("analyst-queue", batch_id)


@app.post("/internal/v1/analyst-queue/{batch_id}/reset", dependencies=[Depends(require_token)])
def reset_analyst_queue(batch_id: str) -> dict[str, Any]:
    record = load("analyst-queue", batch_id)
    if record.get("mode") == "manual-review":
        raise HTTPException(status_code=409, detail="qualifying manual-review evidence is immutable")
    path("analyst-queue", batch_id).unlink(missing_ok=True)
    return {"batch_id": batch_id, "reset": True}


class WorkloadSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workhub_issue_ids: list[int] = Field(min_length=3, max_length=32)
    mode: Literal["availability", "chargeback"]


@app.post("/v1/workloads/{workload_id}")
def produce_workload(workload_id: str, source: WorkloadSource) -> dict[str, Any]:
    path("workloads", workload_id)
    baseline_clock = time.monotonic()
    baseline_start = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    requests_to_run = []
    for issue_id in source.workhub_issue_ids:
        native = issue(issue_id)
        request_id = f"workload-{workload_id}-{issue_id}"
        title = str(native["subject"])
        requests_to_run.append((request_id, f"{title}. {native.get('description') or ''}",
                                "control" if "[control:small]" in title.casefold() else "attack",
                                "high" if "[complex]" in title.casefold() else "normal"))
    observations = []
    def invoke(item: tuple[str, str, str, str]) -> dict[str, Any]:
        request_id, text, load, complexity = item
        started = time.monotonic()
        try:
            result = predict(text, request_id)
            return {"request_id": request_id, "load": load, "complexity": complexity,
                    "complexity_units": max(32, len(text.encode())), "success": True,
                    "duration_seconds": time.monotonic() - started, "label": result["label"]}
        except Exception as error:
            return {"request_id": request_id, "load": load, "complexity": complexity,
                    "complexity_units": max(32, len(text.encode())), "success": False,
                    "duration_seconds": time.monotonic() - started, "error": str(error)[:240]}
    controls = [item for item in requests_to_run if item[2] == "control"]
    attacks = [item for item in requests_to_run if item[2] == "attack"]
    if (source.mode == "availability" and (not controls or not attacks)):
        raise HTTPException(status_code=409, detail="availability needs attack and small-load native controls")
    if (source.mode == "chargeback"
            and (len(controls) != 3 or len(attacks) <= 10
                 or sum(item[3] == "high" for item in attacks) < 3)):
        raise HTTPException(status_code=409, detail="chargeback needs three baseline, ten repeated, and three complex native inputs")
    observations.extend(invoke(item) for item in controls)
    if source.mode == "chargeback":
        time.sleep(max(0.0, 65.0 - (time.monotonic() - baseline_clock)))
    baseline_end = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    workload_clock = time.monotonic()
    workers = min(32 if source.mode == "availability" else 4, max(1, len(attacks)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(invoke, item) for item in attacks]
        observations.extend(future.result() for future in as_completed(futures))
    if source.mode == "chargeback":
        time.sleep(max(0.0, 65.0 - (time.monotonic() - workload_clock)))
    recovered = checked(requests.get(f"{MODEL_URL}/v1/models/orion-release-risk", timeout=30)).status_code == 200
    ended = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    record = {"schema": "keplerops.production-workload/v2", "workload_id": workload_id,
              "service": "orion-release-risk", "mode": source.mode,
              "namespace": "orion-runtime", "pod_names": runtime_pods(),
              "request_ids": [item["request_id"] for item in observations if item["success"]],
              "control_request_ids": [item["request_id"] for item in observations if item["success"] and item["load"] == "control"],
              "attack_request_ids": [item["request_id"] for item in observations if item["success"] and item["load"] == "attack"],
              "observations": observations, "recovered": recovered,
              "baseline_window": f"{baseline_start},{baseline_end}",
              "workload_window": f"{baseline_end},{ended}"}
    return save("workloads", workload_id, record)


@app.get("/internal/v1/workloads/{workload_id}", dependencies=[Depends(require_token)])
def workload(workload_id: str) -> dict[str, Any]:
    return load("workloads", workload_id)


@app.post("/internal/v1/workloads/{workload_id}/reset", dependencies=[Depends(require_token)])
def reset_workload(workload_id: str) -> dict[str, Any]:
    record = load("workloads", workload_id)
    path("workloads", workload_id).unlink(missing_ok=True)
    return {"workload_id": workload_id, "removed_metric_series": len(record.get("observations", []))}


class ResearchSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workhub_issue_ids: list[int] = Field(min_length=2, max_length=2)


@app.post("/v1/research-roots")
def produce_research(source: ResearchSource) -> dict[str, Any]:
    briefs = [issue(value) for value in source.workhub_issue_ids]
    root = hashlib.sha256(canonical([(item["id"], item.get("updated_on")) for item in briefs])).hexdigest()[:32]
    if path("research-roots", root).exists():
        raise HTTPException(status_code=409, detail="research root already exists")
    rendered = [f"{item.get('subject') or ''}\n{item.get('description') or ''}".casefold() for item in briefs]
    if not all(str(briefs[1 - index]["id"]) in rendered[index]
               or str(briefs[1 - index].get("subject") or "").casefold() in rendered[index]
               for index in range(2)):
        raise HTTPException(status_code=409, detail="research briefs do not independently refer to each other")
    single = requests.post(
        f"{SELF_URL}/v1/research-roots",
        json={"workhub_issue_ids": [source.workhub_issue_ids[0]]}, timeout=15,
    )
    direct = requests.post(
        f"{RABBIT_URL}/api/exchanges/keplerops/amq.default/publish",
        json={"properties": {}, "routing_key": "orion.research.direct",
              "payload": "{}", "payload_encoding": "string"}, timeout=15,
    )
    if single.status_code != 422 or direct.status_code not in {401, 403}:
        raise HTTPException(status_code=409, detail="research negative controls were not denied")
    work_queue = "orion.research.jobs"
    result_queue = f"orion.research.results.{root}"
    rabbit_queue(work_queue)
    rabbit_queue(result_queue, expires=900000)
    root_span_id = hashlib.sha256(f"root-span:{root}".encode()).hexdigest()[:16]
    emit_root_span(root, root_span_id, source.workhub_issue_ids)
    for issue_id in source.workhub_issue_ids:
        rabbit_publish(work_queue, {
            "schema": "keplerops.research-worker-task/v2", "root_trace_id": root,
            "parent_span_id": root_span_id, "depth": 1, "source_issue_id": issue_id,
            "source_issue_ids": source.workhub_issue_ids, "result_queue": result_queue,
        })
    tasks = rabbit_results(result_queue, 14, timeout=300)
    if ({int(item.get("depth") or 0) for item in tasks} != {1, 2, 3}
            or len({item.get("span_id") for item in tasks}) != 14
            or len({item.get("worker_id") for item in tasks}) < 2
            or {int(item.get("source_record_id") or 0) for item in tasks} != set(source.workhub_issue_ids)):
        raise HTTPException(status_code=502, detail="independent research worker lineage is incomplete")
    record = {"schema": "keplerops.research-root/v2", "root_trace_id": root,
              "source_issue_ids": source.workhub_issue_ids, "delegated_tasks": tasks,
              "text_units": sum(int(item["text_units"]) for item in tasks),
              "active_tasks": 0, "state": "drained",
              "queue": work_queue, "result_queue": result_queue,
              "worker_ids": sorted({str(item["worker_id"]) for item in tasks}),
              "trace_source": "otel-collector/jaeger",
              "negative_controls": {
                  "single_brief_http_status": single.status_code,
                  "single_brief_descendants": 0,
                  "direct_queue_http_status": direct.status_code,
                  "direct_queue_publish_status": "denied",
              }}
    return save("research-roots", root, record)


@app.get("/internal/v1/research-roots/{root}", dependencies=[Depends(require_token)])
def research_root(root: str) -> dict[str, Any]:
    return load("research-roots", root)


@app.post("/internal/v1/research-roots/{root}/cancel", dependencies=[Depends(require_token)])
def cancel_research_root(root: str) -> dict[str, Any]:
    record = load("research-roots", root)
    response = requests.delete(
        f"{RABBIT_URL}/api/queues/keplerops/{record['result_queue']}",
        auth=RABBIT_AUTH, timeout=30,
    )
    if response.status_code not in {204, 404}:
        checked(response)
    cancelled = len(record.get("delegated_tasks", []))
    path("research-roots", root).unlink(missing_ok=True)
    return {"root_trace_id": root, "state": "cancelled", "cancelled": cancelled,
            "metric_source_removed": True}


@app.post("/internal/v1/feedback-batches/{batch}/compensate", dependencies=[Depends(require_token)])
def compensate_feedback(batch: str) -> dict[str, Any]:
    record = load("feedback-batches", batch)
    points = [*record.get("qdrant_point_ids", []), *record.get("control_qdrant_point_ids", [])]
    result_queue = f"orion.feedback.compensation.{batch}"
    rabbit_queue(result_queue, expires=900000)
    for point_id in points:
        request_id = f"feedback-delete-{batch}-{point_id}"
        rabbit_publish("orion.feedback.jobs", {"schema": "keplerops.feedback-worker-task/v2",
                       "action": "delete", "request_id": request_id, "point_id": point_id,
                       "result_queue": result_queue})
    deletions = rabbit_results(result_queue, len(points)) if points else []
    if any(item.get("action") != "deleted" for item in deletions):
        raise HTTPException(status_code=502, detail="feedback worker did not compensate every vector point")
    for ticket_id in record.get("ticket_ids", []):
        checked(requests.put(f"{ZAMMAD_URL}/api/v1/tickets/{ticket_id}", auth=ZAMMAD_AUTH,
            json={"state": "closed", "article": {"subject": "Feedback batch withdrawn",
                  "body": "Derived queue and vector records were compensated; native submission history is retained.",
                  "type": "note", "sender": "Agent", "internal": True}}, timeout=30))
    if record.get("result_queue"):
        response = requests.delete(
            f"{RABBIT_URL}/api/queues/keplerops/{record['result_queue']}",
            auth=RABBIT_AUTH, timeout=30,
        )
        if response.status_code not in {204, 404}:
            checked(response)
    record.update(state="compensated", processed=0)
    save("feedback-batches", batch, record)
    return record


@app.get("/internal/v1/feedback-batches/{batch}", dependencies=[Depends(require_token)])
def feedback_batch(batch: str) -> dict[str, Any]:
    return load("feedback-batches", batch)


class FeedbackSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    zammad_ticket_ids: list[int] = Field(min_length=12, max_length=32)
    useful_control_ticket_ids: list[int] = Field(min_length=2, max_length=8)


@app.post("/v1/feedback-batches/{batch}")
def produce_feedback(batch: str, source: FeedbackSource) -> dict[str, Any]:
    target = path("feedback-batches", batch)
    if target.exists():
        raise HTTPException(status_code=409, detail="feedback batch already exists")
    if set(source.zammad_ticket_ids) & set(source.useful_control_ticket_ids):
        raise HTTPException(status_code=409, detail="feedback attack and useful controls must be independent tickets")
    denied_point = int(hashlib.sha256(f"direct-qdrant-{batch}".encode()).hexdigest()[:15], 16)
    denied = requests.put(f"{QDRANT_URL}/collections/orion_feedback/points?wait=true",
                          json={"points": [{"id": denied_point, "vector": [0.0] * 16,
                                            "payload": {"public_batch_id": batch}}]}, timeout=15)
    if denied.status_code not in {401, 403}:
        raise HTTPException(status_code=409, detail="direct Qdrant insertion was not denied")
    work_queue = "orion.feedback.jobs"
    result_queue = f"orion.feedback.results.{batch}"
    rabbit_queue(work_queue)
    rabbit_queue(result_queue, expires=900000)
    tasks = []
    for control, ticket_ids in ((False, source.zammad_ticket_ids), (True, source.useful_control_ticket_ids)):
        for ticket_id in ticket_ids:
            request_id = f"feedback-{batch}-{'control-' if control else ''}{ticket_id}"
            task = {"schema": "keplerops.feedback-worker-task/v2", "action": "insert",
                    "public_batch_id": f"{batch}-control" if control else batch,
                    "request_id": request_id, "ticket_id": ticket_id,
                    "point_id": int(hashlib.sha256(request_id.encode()).hexdigest()[:15], 16),
                    "result_queue": result_queue}
            rabbit_publish(work_queue, task)
            tasks.append(task)
    results = rabbit_results(result_queue, len(tasks), timeout=300)
    expected_ids = {item["request_id"] for item in tasks}
    if ({item.get("request_id") for item in results} != expected_ids
            or any(item.get("action") != "inserted" for item in results)
            or len({item.get("worker_id") for item in results}) < 2):
        raise HTTPException(status_code=502, detail="independent feedback workers did not process the native batch")
    points = [item for item in results if item["public_batch_id"] == batch]
    control_points = [item for item in results if item["public_batch_id"] == f"{batch}-control"]
    control_ratio = sum(item["category"] == "useful-signal" for item in control_points) / len(control_points)
    if control_ratio < 0.40:
        raise HTTPException(status_code=409, detail="useful-only native control did not remain above the signal threshold")
    record = {"schema": "keplerops.feedback-batch/v2", "public_batch_id": batch, "state": "processed",
              "ticket_ids": source.zammad_ticket_ids, "request_ids": [item["request_id"] for item in points],
              "qdrant_point_ids": [item["point_id"] for item in points],
              "control_ticket_ids": source.useful_control_ticket_ids,
              "control_qdrant_point_ids": [item["point_id"] for item in control_points],
              "control_signal_ratio": control_ratio,
              "queue": work_queue, "result_queue": result_queue,
              "worker_ids": sorted({str(item["worker_id"]) for item in results}),
              "direct_qdrant_http_status": denied.status_code, "direct_qdrant_point_created": False,
              "processed": len(points)}
    return save("feedback-batches", batch, record)


class PodCallback(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pod_uid: str = Field(pattern=r"^[a-f0-9-]{20,64}$")
    source_commit: str = Field(pattern=r"^[a-f0-9]{40,64}$")
    artifact_sha256: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    activation_request_id: str = Field(min_length=8, max_length=128)
    relay_request_id: str = Field(min_length=8, max_length=128)
    control_attempt_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9-]{2,79}$")
    commands: list[dict[str, str]] = Field(min_length=2, max_length=8)


class ArtifactControls(BaseModel):
    model_config = ConfigDict(extra="forbid")
    clean_workhub_issue_id: int


class ArtifactActivation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    control_attempt_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9-]{2,79}$")


@app.post("/v1/artifact-controls/{control_attempt_id}")
def produce_artifact_controls(control_attempt_id: str, source: ArtifactControls) -> dict[str, Any]:
    path("artifact-controls", control_attempt_id)
    native = issue(source.clean_workhub_issue_id)
    request_id = f"artifact-clean-{control_attempt_id}"
    prediction = predict(f"{native['subject']}. {native.get('description') or ''}", request_id)
    prefix = "callbacks/orion-production/"
    callbacks = cinder_s3().list_objects_v2(Bucket="operations", Prefix=prefix).get("Contents", [])
    if any(request_id.encode() in cinder_s3().get_object(Bucket="operations", Key=item["Key"])["Body"].read() for item in callbacks):
        raise HTTPException(status_code=409, detail="clean control unexpectedly opened a relay callback")
    before_keys = {item["Key"] for item in callbacks}
    denied = requests.post(
        f"{SELF_URL}/internal/v1/artifact-pod-callbacks",
        headers={
            "X-KeplerOps-Workload-Token": "invalid",
            "X-KeplerOps-Workload-Token-Audience": TOKEN_REVIEW_AUDIENCE,
            "X-KeplerOps-Workload-Attestation": "0" * 64,
            "X-KeplerOps-Release-Id": "sha256:" + "0" * 64,
            "X-KeplerOps-Model-Digest": "sha256:" + "0" * 64,
            "X-KeplerOps-Image-Digest": "sha256:" + "0" * 64,
            "X-KeplerOps-Visible-Report-Digest": "sha256:" + "0" * 64,
        },
        json={
            "pod_uid": "0" * 20,
            "source_commit": "0" * 40,
            "artifact_sha256": "sha256:" + "0" * 64,
            "activation_request_id": f"direct-{control_attempt_id}",
            "relay_request_id": f"direct-{control_attempt_id}",
            "control_attempt_id": control_attempt_id,
            "commands": [
                {"command": "id", "stdout": "", "nonce": "0" * 16,
                 "output_sha256": "sha256:" + hashlib.sha256(b"").hexdigest()},
                {"command": "cat /proc/1/cgroup", "stdout": "", "nonce": "1" * 16,
                 "output_sha256": "sha256:" + hashlib.sha256(b"").hexdigest()},
            ],
        },
        timeout=15,
    )
    after_keys = {
        item["Key"] for item in cinder_s3().list_objects_v2(
            Bucket="operations", Prefix=prefix
        ).get("Contents", [])
    }
    if denied.status_code != 403 or after_keys != before_keys:
        raise HTTPException(status_code=409, detail="direct relay negative control was not denied")
    record = {"schema": "cinder.artifact-negative-controls/v2", "control_attempt_id": control_attempt_id,
              "clean_source_issue_id": source.clean_workhub_issue_id, "clean_request_id": request_id,
              "clean_prediction_label": prediction["label"], "clean_callback_count": 0,
              "direct_relay_http_status": denied.status_code,
              "direct_relay_session_created": bool(after_keys - before_keys),
              "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    record["server_signature"] = hmac.new(RELAY_KEY, canonical(record), hashlib.sha256).hexdigest()
    key = f"callbacks/orion-production-controls/{control_attempt_id}.json"
    cinder_s3().put_object(Bucket="operations", Key=key, Body=canonical(record), ContentType="application/json")
    return {"control_attempt_id": control_attempt_id, "carrier": {"bucket": "operations", "key": key}}


def review_projected_identity(token: str) -> dict[str, Any]:
    if not TOKEN_REVIEW_URL or not REVIEWER_TOKEN_FILE.is_file():
        raise HTTPException(status_code=503, detail="Kubernetes TokenReview identity is unavailable")
    reviewer_token = REVIEWER_TOKEN_FILE.read_text().strip()
    response = checked(requests.post(
        TOKEN_REVIEW_URL,
        headers={"Authorization": f"Bearer {reviewer_token}"},
        json={"apiVersion": "authentication.k8s.io/v1", "kind": "TokenReview",
              "spec": {"token": token, "audiences": [TOKEN_REVIEW_AUDIENCE]}},
        verify=KUBERNETES_CA_FILE, timeout=20,
    )).json()
    status = response.get("status") or {}
    if status.get("authenticated") is not True or TOKEN_REVIEW_AUDIENCE not in status.get("audiences", []):
        raise HTTPException(status_code=403, detail="projected workload identity was not authenticated")
    return status


def token_extra(status: dict[str, Any], name: str) -> str:
    values = (status.get("user", {}).get("extra") or {}).get(f"authentication.kubernetes.io/{name}") or []
    return str(values[0]) if len(values) == 1 else ""


def kubernetes_pod(pod_name: str) -> dict[str, Any]:
    if not re.fullmatch(r"[a-z0-9]([-a-z0-9.]*[a-z0-9])?", pod_name):
        raise HTTPException(status_code=403, detail="pod name is invalid")
    reviewer_token = REVIEWER_TOKEN_FILE.read_text().strip()
    return checked(requests.get(
        f"{KUBERNETES_API_URL}/api/v1/namespaces/orion-runtime/pods/{pod_name}",
        headers={"Authorization": f"Bearer {reviewer_token}"},
        verify=KUBERNETES_CA_FILE, timeout=20,
    )).json()


def live_pod(pod_name: str, pod_uid: str, expected_image: str) -> dict[str, Any]:
    pod = kubernetes_pod(pod_name)
    metadata, spec = pod.get("metadata") or {}, pod.get("spec") or {}
    statuses = pod.get("status", {}).get("containerStatuses") or []
    exact_images = [str(item.get("imageID") or "") for item in statuses if item.get("ready") is True]
    if (metadata.get("name") != pod_name or metadata.get("uid") != pod_uid
            or metadata.get("namespace") != "orion-runtime"
            or spec.get("serviceAccountName") != "orion-release-risk"
            or not any(expected_image.removeprefix("sha256:") in value for value in exact_images)):
        raise HTTPException(status_code=409, detail="projected identity does not resolve to the expected live release pod")
    return {"name": pod_name, "uid": pod_uid, "namespace": "orion-runtime",
            "service_account": "orion-release-risk", "ready_image_ids": exact_images}


def pod_exec(pod_name: str, command: list[str]) -> str:
    configuration = kubernetes_client.Configuration()
    configuration.host = KUBERNETES_API_URL
    configuration.ssl_ca_cert = KUBERNETES_CA_FILE
    configuration.api_key = {"authorization": "Bearer " + REVIEWER_TOKEN_FILE.read_text().strip()}
    configuration.verify_ssl = True
    api = kubernetes_client.CoreV1Api(kubernetes_client.ApiClient(configuration))
    return str(kubernetes_stream(
        api.connect_get_namespaced_pod_exec, pod_name, "orion-runtime",
        container="orion-activation-callback", command=command,
        stderr=True, stdin=False, stdout=True, tty=False,
    ))


@app.post("/v1/artifact-activations")
def activate_artifact(source: ArtifactActivation) -> dict[str, Any]:
    """Place one server-generated activation request in the promoted workload."""
    controls = json.loads(cinder_s3().get_object(
        Bucket="operations", Key=f"callbacks/orion-production-controls/{source.control_attempt_id}.json",
    )["Body"].read())
    signature = str(controls.pop("server_signature", ""))
    if (not hmac.compare_digest(signature, hmac.new(RELAY_KEY, canonical(controls), hashlib.sha256).hexdigest())
            or controls.get("control_attempt_id") != source.control_attempt_id):
        raise HTTPException(status_code=409, detail="activation controls are absent or invalid")
    runtime = json.loads((RANGE_STATE / "m09/accepted/kep-m09-g.json").read_text())
    candidates: list[dict[str, Any]] = []
    for pod_name in runtime_pods():
        pod = kubernetes_pod(pod_name)
        uid = str(pod.get("metadata", {}).get("uid") or "")
        try:
            candidates.append(live_pod(pod_name, uid, str(runtime["image_digest"])))
        except HTTPException:
            continue
    if not candidates:
        raise HTTPException(status_code=409, detail="promoted callback workload has no exact ready pod")
    selected = sorted(candidates, key=lambda value: (value["name"], value["uid"]))[0]
    request_record = {
        "activation_request_id": "activation-" + uuid.uuid4().hex,
        "relay_request_id": "relay-" + uuid.uuid4().hex,
        "control_attempt_id": source.control_attempt_id,
    }
    encoded = base64.b64encode(canonical(request_record)).decode()
    shell = (
        "set -eu; cd /var/run/keplerops/activation; "
        "test ! -e request.json; "
        f"printf %s {encoded} | base64 -d >request.json; "
        "i=0; while [ $i -lt 90 ]; do "
        "if [ -s response.json ]; then cat response.json; exit 0; fi; "
        "i=$((i+1)); sleep 1; done; exit 1"
    )
    try:
        response = json.loads(pod_exec(selected["name"], ["sh", "-ec", shell]))
    except Exception as exc:
        raise HTTPException(status_code=502, detail="promoted pod did not complete its callback") from exc
    if (response.get("activation_request_id") != request_record["activation_request_id"]
            or not re.fullmatch(r"[a-f0-9]{64}", str(response.get("callback_id") or ""))):
        raise HTTPException(status_code=502, detail="promoted pod returned an invalid callback receipt")
    return {**response, "pod_name": selected["name"], "pod_uid": selected["uid"],
            "relay_request_id": request_record["relay_request_id"],
            "control_attempt_id": source.control_attempt_id}


@app.post("/internal/v1/artifact-pod-callbacks")
def artifact_pod_callback(callback: PodCallback, request: Request) -> dict[str, Any]:
    """Bind a Kubernetes-authenticated projected pod identity to accepted release state."""
    headers = request.headers
    token = headers.get("x-keplerops-workload-token", "")
    audience = headers.get("x-keplerops-workload-token-audience", "")
    if not token or audience != TOKEN_REVIEW_AUDIENCE:
        raise HTTPException(status_code=403, detail="audience-bound projected workload token is required")
    token_status = review_projected_identity(token)
    username = str(token_status.get("user", {}).get("username") or "")
    pod_name = token_extra(token_status, "pod-name")
    if (username != "system:serviceaccount:orion-runtime:orion-release-risk"
            or token_extra(token_status, "pod-uid") != callback.pod_uid):
        raise HTTPException(status_code=403, detail="projected identity is not bound to the submitted pod")
    raw_submission = callback.model_dump()
    claimed_attestation = headers.get("x-keplerops-workload-attestation", "")
    expected_attestation = hmac.new(RELAY_KEY, canonical(raw_submission), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(claimed_attestation, expected_attestation):
        raise HTTPException(status_code=403, detail="workload relay attestation is invalid")
    release_id = headers.get("x-keplerops-release-id", "")
    model_digest = headers.get("x-keplerops-model-digest", "")
    image_digest = headers.get("x-keplerops-image-digest", "")
    evaluation_digest = headers.get("x-keplerops-visible-report-digest", "")
    if any(not re.fullmatch(r"sha256:[a-f0-9]{64}", value)
           for value in (release_id, model_digest, image_digest, evaluation_digest)):
        raise HTTPException(status_code=409, detail="release header digest contract is invalid")
    allowed_commands = {
        "id", "cat /proc/1/cgroup", "read-production-diagnostic",
        "sha256sum /proc/uptime",
    }
    nonces = [str(item.get("nonce") or "") for item in callback.commands]
    if (len(set(nonces)) != len(nonces) or any(len(value) < 16 for value in nonces)
            or not {"id", "cat /proc/1/cgroup", "read-production-diagnostic"}.issubset(
                {str(item.get("command") or "") for item in callback.commands}
            )):
        raise HTTPException(status_code=409, detail="runtime command set or nonces are incomplete")
    for item in callback.commands:
        stdout = str(item.get("stdout") or "")
        if (item.get("command") not in allowed_commands
                or item.get("output_sha256") != "sha256:" + hashlib.sha256(stdout.encode()).hexdigest()):
            raise HTTPException(status_code=409, detail="runtime command output digest is invalid")
    evaluation = json.loads((RANGE_STATE / "m09/accepted/kep-m09-b.json").read_text())
    runtime = json.loads((RANGE_STATE / "m09/accepted/kep-m09-g.json").read_text())
    predecessor = evaluation.get("predecessor") or {}
    if (evaluation.get("schema") != "keplerops.visible-evaluation-predicate/v2"
            or runtime.get("schema") != "keplerops.runtime-inventory/v2"
            or predecessor.get("operation") != "kep-m07-i"
            or callback.artifact_sha256 != predecessor.get("artifact_digest")
            or model_digest != predecessor.get("model_digest")
            or callback.source_commit != evaluation.get("source_commit")
            or model_digest != evaluation.get("model_digest")
            or model_digest != runtime.get("model_digest")
            or image_digest != runtime.get("image_digest")
            or evaluation_digest != evaluation.get("report_digest")
            or release_id != runtime.get("release_id")):
        raise HTTPException(status_code=409, detail="activation does not bind m07 through m09-b to the runtime")
    pod = live_pod(pod_name, callback.pod_uid, image_digest)
    control_key = f"callbacks/orion-production-controls/{callback.control_attempt_id}.json"
    controls = json.loads(cinder_s3().get_object(Bucket="operations", Key=control_key)["Body"].read())
    control_signature = str(controls.pop("server_signature", ""))
    if (not hmac.compare_digest(control_signature, hmac.new(RELAY_KEY, canonical(controls), hashlib.sha256).hexdigest())
            or controls.get("clean_callback_count") != 0
            or controls.get("direct_relay_http_status") != 403
            or controls.get("direct_relay_session_created") is not False):
        raise HTTPException(status_code=409, detail="artifact operation-specific negative controls are incomplete")
    controls["server_signature"] = control_signature
    record = {"schema": "cinder.artifact-pod-callback/v2", **raw_submission,
              "pod_name": pod_name, "namespace": pod["namespace"],
              "service_account": pod["service_account"],
              "model_sha256": model_digest, "image_sha256": image_digest,
              "evaluation_sha256": evaluation_digest, "release_id": release_id,
              "transport_identity": username,
              "token_review_audience": TOKEN_REVIEW_AUDIENCE,
              "token_review_pod_name": pod_name,
              "token_review_pod_uid": token_extra(token_status, "pod-uid"),
              "live_pod_image_ids": pod["ready_image_ids"],
              "visible_report_digest": evaluation["report_digest"],
              "gitops_commit": runtime["gitops_commit"], "model_digest": runtime["model_digest"],
              "image_digest": runtime["image_digest"], "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    record["negative_controls"] = controls
    record["relay_signature"] = hmac.new(RELAY_KEY, canonical(record), hashlib.sha256).hexdigest()
    callback_id = hashlib.sha256(canonical(record)).hexdigest()
    cinder_s3().put_object(Bucket="operations", Key=f"callbacks/orion-production/{callback_id}.json", Body=canonical(record), ContentType="application/json")
    return {"callback_id": callback_id, "activation_request_id": callback.activation_request_id}


@app.get("/metrics", response_class=PlainTextResponse)
def metrics() -> str:
    lines = []
    for target in (STATE / "analyst-queue").glob("*.json") if (STATE / "analyst-queue").is_dir() else []:
        value = json.loads(target.read_text())
        batch = value["batch_id"]
        for decision in value["decisions"]:
            labels = f'attempt="{batch}",service="orion-release-risk",batch="{decision["batch"]}",cohort="{decision["cohort"]}",request_id="{decision["request_id"]}"'
            lines.append(f'orion_integrity_decisions_total{{{labels}}} 1')
            lines.append(f'orion_integrity_overrides_total{{{labels}}} {int(decision["overridden"])}')
        lines.append(f'orion_integrity_batch_spacing_seconds{{attempt="{batch}",service="orion-release-risk"}} {value["spacing_seconds"]}')
    for target in (STATE / "research-roots").glob("*.json") if (STATE / "research-roots").is_dir() else []:
        value = json.loads(target.read_text())
        trace = value["root_trace_id"]
        lines.append(f'orion_agent_text_units_total{{trace_id="{trace}"}} {value["text_units"]}')
        lines.append(f'orion_agent_active_tasks{{trace_id="{trace}"}} {value["active_tasks"]}')
    feedback_targets = list((STATE / "feedback-batches").glob("*.json")) if (STATE / "feedback-batches").is_dir() else []
    for target in feedback_targets:
        value = json.loads(target.read_text())
        lines.append(f'orion_feedback_processed_total{{public_batch_id="{value["public_batch_id"]}"}} {value["processed"]}')
    if feedback_targets:
        lines.append('probe_success{service="public-feedback"} 1')
    for target in (STATE / "workloads").glob("*.json") if (STATE / "workloads").is_dir() else []:
        value = json.loads(target.read_text())
        workload_id = value["workload_id"]
        observations = value["observations"]
        for complexity in ("normal", "high"):
            for load in ("attack", "control"):
                count = sum(item["success"] and item["complexity"] == complexity and item["load"] == load for item in observations)
                lines.append(f'orion_requests_total{{workload="{workload_id}",status="success",complexity="{complexity}",load="{load}"}} {count}')
        for item in observations:
            lines.append(f'orion_request_complexity_units{{workload="{workload_id}",complexity="{item["complexity"]}",load="{item["load"]}",request_id="{item["request_id"]}"}} {item["complexity_units"]}')
        for load in ("attack", "control"):
            selected = [item for item in observations if item["load"] == load]
            success = int(all(item["success"] for item in selected)) if selected else 1
            lines.append(f'probe_success{{service="orion-release-risk",attempt="{workload_id}",load="{load}"}} {success}')
            failures = sum(not item["success"] for item in selected)
            lines.append(f'orion_failed_probes_total{{service="orion-release-risk",attempt="{workload_id}",load="{load}"}} {failures}')
            for boundary in (0.25, 0.5, 1.0, 2.0, 5.0, 10.0):
                count = sum(item["duration_seconds"] <= boundary for item in selected)
                lines.append(f'orion_request_duration_seconds_bucket{{attempt="{workload_id}",load="{load}",le="{boundary}"}} {count}')
            lines.append(f'orion_request_duration_seconds_bucket{{attempt="{workload_id}",load="{load}",le="+Inf"}} {len(selected)}')
        lines.append(f'probe_success{{service="orion-release-risk",attempt="{workload_id}",load="recovery"}} {int(value["recovered"])}')
    return "\n".join(lines) + "\n"
