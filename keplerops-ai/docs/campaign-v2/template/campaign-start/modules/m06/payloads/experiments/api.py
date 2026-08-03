from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, HttpUrl
from checkpoints import AttemptContext, resolve_parents


PREVIEW = os.environ["ORION_PREVIEW_URL"].rstrip("/")
MODEL = os.environ["PUBLIC_MODEL_URL"].rstrip("/")
MODEL_NAME = os.environ.get("PUBLIC_MODEL_NAME", "orion-release-risk")
AUDIT = Path("/var/lib/orion-preview/audit")
STATE = Path("/var/lib/cinder-experiments")
ALLOWED_ARTIFACT_HOSTS = {"git.cinder.lab", "storage.cinder.lab", "keplerops.lab"}
app = FastAPI(title="Cinder Orion Experiments", version="1.0")


class PreviewExperiment(BaseModel):
    context: AttemptContext
    method: Literal["query-optimization", "proxy-transfer"]
    experiment: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{5,63}$")
    clean_artifact_url: HttpUrl
    candidate_artifact_url: HttpUrl
    target_label: str = Field(min_length=2, max_length=80)
    max_normalized_distance: float = Field(gt=0, le=0.35)
    query_ids: list[uuid.UUID] = Field(min_length=2, max_length=80)
    proxy_model_url: HttpUrl | None = None
    optimization_trace_url: HttpUrl | None = None


class WhiteBoxExperiment(BaseModel):
    context: AttemptContext
    model_artifact_url: HttpUrl
    clean_artifact_url: HttpUrl
    candidate_artifact_url: HttpUrl
    optimization_trace_url: HttpUrl
    target_label: str = Field(min_length=2, max_length=80)
    max_normalized_distance: float = Field(gt=0, le=0.35)


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def distance(left: str, right: str) -> float:
    if left == right:
        return 0.0
    previous = list(range(len(right) + 1))
    for index, left_char in enumerate(left, start=1):
        current = [index]
        for offset, right_char in enumerate(right, start=1):
            current.append(min(current[-1] + 1, previous[offset] + 1, previous[offset - 1] + (left_char != right_char)))
        previous = current
    return previous[-1] / max(len(left), len(right), 1)


def linear_gradient(model: dict[str, Any], text: str, target: str) -> tuple[list[float], float]:
    vocabulary = model.get("vocabulary")
    labels = model.get("labels")
    weights = model.get("weights")
    bias = model.get("bias")
    if not isinstance(vocabulary, list) or not isinstance(labels, list) or target not in labels:
        raise HTTPException(status_code=422, detail="proxy is not a Cinder linear text model")
    if not isinstance(weights, list) or len(weights) != len(labels) or any(len(row) != len(vocabulary) for row in weights):
        raise HTTPException(status_code=422, detail="proxy weight shape is invalid")
    features = [float(text.lower().count(str(token).lower())) for token in vocabulary]
    target_index = labels.index(target)
    scores = [sum(float(weight) * value for weight, value in zip(row, features)) + float((bias or [0] * len(labels))[index]) for index, row in enumerate(weights)]
    other_index = max((index for index in range(len(labels)) if index != target_index), key=lambda index: scores[index])
    gradient = [float(left) - float(right) for left, right in zip(weights[target_index], weights[other_index])]
    return gradient, scores[target_index] - scores[other_index]


async def reacquire(url: HttpUrl, *, limit: int = 64 * 1024 * 1024) -> bytes:
    parsed = urlparse(str(url))
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_ARTIFACT_HOSTS:
        raise HTTPException(status_code=422, detail="artifact must be reacquired from an admitted owning source")
    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        response = await client.get(str(url))
    if response.status_code != 200 or len(response.content) > limit:
        raise HTTPException(status_code=422, detail=f"artifact reacquisition failed: {parsed.hostname}{parsed.path}")
    return response.content


def audit(analysis_id: uuid.UUID) -> dict[str, Any]:
    path = AUDIT / f"{analysis_id}.json"
    if not path.is_file():
        raise HTTPException(status_code=422, detail=f"Preview audit {analysis_id} does not exist")
    return json.loads(path.read_text())


async def predict(text: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(f"{MODEL}/v1/models/{MODEL_NAME}:predict", json={"instances": [{"text": text}]})
    if response.status_code != 200:
        raise HTTPException(status_code=503, detail="public Orion model is unavailable")
    body = response.json()
    return body["predictions"][0]


def persist(kind: str, record: dict[str, Any]) -> dict[str, Any]:
    record_id = str(uuid.uuid4())
    operation = "kep-m06-r" if kind == "whitebox-evaluation" else (
        "kep-m06-c" if record.get("method") == "query-optimization" else "kep-m06-d"
    )
    record.update({"record_id": record_id, "schema": f"cinder.{kind}/v1",
                   "operation": operation, "model_family": "release-risk"})
    directory = STATE / kind
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{record_id}.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return record


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ready", "service": "Cinder Orion Experiments"}


@app.post("/v1/preview-experiments")
async def preview_experiment(request: PreviewExperiment) -> dict[str, Any]:
    required = {"kep-m04-f", "kep-m06-q"} if request.method == "query-optimization" else {"kep-m06-k", "kep-m06-q"}
    parents = await resolve_parents(request.context, required)
    clean_bytes, candidate_bytes = await reacquire(request.clean_artifact_url), await reacquire(request.candidate_artifact_url)
    try:
        clean, candidate = clean_bytes.decode(), candidate_bytes.decode()
    except UnicodeDecodeError as error:
        raise HTTPException(status_code=422, detail="Preview experiment artifacts must be UTF-8 text") from error
    if clean_bytes == candidate_bytes:
        raise HTTPException(status_code=422, detail="candidate is identical to clean input")
    measured = distance(clean, candidate)
    if measured > request.max_normalized_distance:
        raise HTTPException(status_code=422, detail="candidate exceeds the declared distance bound")
    audits = [audit(value) for value in request.query_ids]
    if any(item.get("experiment") != request.experiment for item in audits):
        raise HTTPException(status_code=422, detail="query ID is not bound to this experiment")
    clean_matches = [item for item in audits if item["input_sha256"] == sha256(clean_bytes)]
    candidate_matches = [item for item in audits if item["input_sha256"] == sha256(candidate_bytes)]
    if not clean_matches or not candidate_matches or candidate_matches[-1].get("label") != request.target_label:
        raise HTTPException(status_code=422, detail="server audit lacks the clean/final target requests")
    details: dict[str, Any] = {}
    if request.method == "query-optimization":
        all_ids = {
            item.get("analysis_id") for path in AUDIT.glob("*.json")
            for item in [json.loads(path.read_text())] if item.get("experiment") == request.experiment
        }
        if all_ids != {str(value) for value in request.query_ids}:
            raise HTTPException(status_code=422, detail="query list must contain the complete native experiment audit")
        order = [item.get("received_ns", 0) for item in audits]
        if any(not isinstance(value, int) or value <= 0 for value in order) or order != sorted(order):
            raise HTTPException(status_code=422, detail="Preview query IDs are not in native execution order")
        unique_inputs = {item["input_sha256"] for item in audits}
        target_scores = [float((item.get("probabilities") or {}).get(request.target_label, 0.0)) for item in audits]
        if len(unique_inputs) < 3 or len(audits) < 3 or target_scores[-1] <= target_scores[0]:
            raise HTTPException(status_code=422, detail="audit does not show a bounded query optimization sequence")
        flag = os.environ["PREVIEW_BLACKBOX_FLAG"]
    else:
        if len(audits) > 8 or request.proxy_model_url is None or request.optimization_trace_url is None:
            raise HTTPException(status_code=422, detail="proxy transfer requires reacquired proxy and trace with at most eight target queries")
        proxy_bytes, trace_bytes = await reacquire(request.proxy_model_url), await reacquire(request.optimization_trace_url)
        try:
            trace = json.loads(trace_bytes)
        except json.JSONDecodeError as error:
            raise HTTPException(status_code=422, detail="proxy optimization trace is not JSON") from error
        if trace.get("proxy_model_sha256") != sha256(proxy_bytes) or trace.get("candidate_sha256") != sha256(candidate_bytes):
            raise HTTPException(status_code=422, detail="proxy trace is not bound to reacquired bytes")
        if not isinstance(trace.get("training_examples"), int) or trace["training_examples"] < 10:
            raise HTTPException(status_code=422, detail="proxy trace lacks a real training corpus")
        try:
            proxy_model = json.loads(proxy_bytes)
        except json.JSONDecodeError as error:
            raise HTTPException(status_code=422, detail="proxy model is not executable JSON") from error
        clean_gradient, clean_margin = linear_gradient(proxy_model, clean, request.target_label)
        candidate_gradient, candidate_margin = linear_gradient(proxy_model, candidate, request.target_label)
        expected_gradient = sha256(json.dumps(clean_gradient, separators=(",", ":")).encode())
        if trace.get("initial_gradient_sha256") != expected_gradient or candidate_margin <= clean_margin:
            raise HTTPException(status_code=422, detail="server-executed proxy optimizer does not reproduce the transfer candidate")
        details = {"proxy_model_sha256": sha256(proxy_bytes), "optimization_trace_sha256": sha256(trace_bytes),
                   "server_initial_gradient_sha256": expected_gradient, "proxy_margin_before": clean_margin,
                   "proxy_margin_after": candidate_margin, "final_gradient_l2": sum(value * value for value in candidate_gradient) ** 0.5}
        flag = os.environ["PREVIEW_TRANSFER_FLAG"]
    return persist(
        "preview-audit-export",
        {
            "attempt_id": str(request.context.attempt_id), "actor": request.context.actor,
            "parent_checkpoints": [{key: item[key] for key in ("operation", "locator", "sha256", "schema", "actor", "attempt_id")} for item in parents],
            "method": request.method,
            "experiment": request.experiment,
            "clean_sha256": sha256(clean_bytes),
            "candidate_sha256": sha256(candidate_bytes),
            "normalized_distance": measured,
            "target_label": request.target_label,
            "query_ids": [str(value) for value in request.query_ids],
            "query_count": len(request.query_ids),
            **details,
            "flag": flag,
        },
    )


@app.post("/v1/white-box-experiments")
async def whitebox_experiment(request: WhiteBoxExperiment) -> dict[str, Any]:
    parents = await resolve_parents(request.context, {"kep-m06-k", "kep-m06-q"})
    clean_bytes, candidate_bytes, trace_bytes, model_bytes = await reacquire(request.clean_artifact_url), await reacquire(request.candidate_artifact_url), await reacquire(request.optimization_trace_url), await reacquire(request.model_artifact_url)
    try:
        clean, candidate, trace, whitebox_model = clean_bytes.decode(), candidate_bytes.decode(), json.loads(trace_bytes), json.loads(model_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=422, detail="white-box artifacts are not parseable") from error
    steps = trace.get("steps")
    if not isinstance(steps, list) or len(steps) < 2:
        raise HTTPException(status_code=422, detail="optimization trace lacks independently inspectable gradient steps")
    if trace.get("candidate_sha256") != sha256(candidate_bytes) or trace.get("clean_sha256") != sha256(clean_bytes):
        raise HTTPException(status_code=422, detail="optimization trace is not bound to reacquired inputs")
    measured = distance(clean, candidate)
    gradient, clean_margin = linear_gradient(whitebox_model, clean, request.target_label)
    _, candidate_margin = linear_gradient(whitebox_model, candidate, request.target_label)
    gradient_digest = sha256(json.dumps(gradient, separators=(",", ":")).encode())
    if trace.get("initial_gradient_sha256") != gradient_digest or candidate_margin <= clean_margin:
        raise HTTPException(status_code=422, detail="server-computed gradient does not reproduce optimizer progress")
    clean_result, candidate_result = await predict(clean), await predict(candidate)
    if measured > request.max_normalized_distance or candidate_result.get("label") != request.target_label or clean_result.get("label") == request.target_label:
        raise HTTPException(status_code=422, detail="independent Orion evaluation did not reproduce the bounded target effect")
    metadata = await httpx.AsyncClient(timeout=15).__aenter__()
    try:
        model_response = await metadata.get(f"{MODEL}/v1/models/{MODEL_NAME}")
    finally:
        await metadata.aclose()
    model_sha = model_response.json().get("model_sha256", "") if model_response.status_code == 200 else ""
    return persist(
        "whitebox-evaluation",
        {
            "attempt_id": str(request.context.attempt_id), "actor": request.context.actor,
            "parent_checkpoints": [{key: item[key] for key in ("operation", "locator", "sha256", "schema", "actor", "attempt_id")} for item in parents],
            "clean_sha256": sha256(clean_bytes), "candidate_sha256": sha256(candidate_bytes),
            "optimization_trace_sha256": sha256(trace_bytes), "model_sha256": model_sha,
            "whitebox_model_sha256": sha256(model_bytes), "server_initial_gradient_sha256": gradient_digest,
            "whitebox_margin_before": clean_margin, "whitebox_margin_after": candidate_margin,
            "normalized_distance": measured, "target_label": request.target_label,
            "clean_output": clean_result, "candidate_output": candidate_result,
            "flag": os.environ["WHITEBOX_FLAG"],
        },
    )


@app.get("/v1/preview-experiments")
def list_preview_experiments() -> list[dict[str, Any]]:
    return [json.loads(path.read_text()) for path in sorted((STATE / "preview-audit-export").glob("*.json"))]


@app.get("/v1/white-box-experiments")
def list_whitebox_experiments() -> list[dict[str, Any]]:
    return [json.loads(path.read_text()) for path in sorted((STATE / "whitebox-evaluation").glob("*.json"))]


@app.get("/v1/preview-experiments/{record_id}")
def get_preview_experiment(record_id: uuid.UUID) -> dict[str, Any]:
    path = STATE / "preview-audit-export" / f"{record_id}.json"
    if not path.is_file(): raise HTTPException(status_code=404)
    return json.loads(path.read_text())


@app.get("/v1/white-box-experiments/{record_id}")
def get_whitebox_experiment(record_id: uuid.UUID) -> dict[str, Any]:
    path = STATE / "whitebox-evaluation" / f"{record_id}.json"
    if not path.is_file(): raise HTTPException(status_code=404)
    return json.loads(path.read_text())
