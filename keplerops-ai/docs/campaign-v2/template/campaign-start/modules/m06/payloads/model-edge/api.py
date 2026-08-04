from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Optional

import httpx
from fastapi import FastAPI, Header, HTTPException, Query, Response
from fastapi.responses import FileResponse, StreamingResponse


UPSTREAM = os.environ.get("GLM_UPSTREAM_URL", "http://192.168.78.30:30402/v1").rstrip("/")
UPSTREAM_MODEL = os.environ.get("GLM_UPSTREAM_MODEL", "openai/zai-org/glm-5-maas")
CREDENTIAL = os.environ["CINDER_EDGE_CREDENTIAL"]
SERVICE_CREDENTIAL = os.environ["CINDER_EDGE_SERVICE_CREDENTIAL"]
RANGE_ID = os.environ.get("CINDER_RANGE_ID", "range-local")
RANGE_ASSERTION_KEY = os.environ["CINDER_RANGE_ASSERTION_KEY"].encode()
RANGE_ASSERTION_KEY_ID = os.environ["CINDER_RANGE_ASSERTION_KEY_ID"]
EDGE_OWNER = os.environ.get("CINDER_EDGE_OWNER", "cinder-field-operator")
USAGE_FLAG = os.environ["MODEL_USAGE_FLAG"]
ASSERTION_BACKDATE_SECONDS = int(os.getenv("CINDER_ASSERTION_BACKDATE_SECONDS", "10"))
STATE = Path("/var/lib/cinder-model-edge")
app = FastAPI(title="Cinder GLM Edge", version="1.0")


def authorize(value: Optional[str]) -> str:
    if value == f"Bearer {CREDENTIAL}":
        return "operator"
    if value == f"Bearer {SERVICE_CREDENTIAL}":
        return "service"
    else:
        raise HTTPException(status_code=401, detail="Cinder model credential required")


def digest_json(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ready", "model": "glm-5.2", "range": RANGE_ID}


@app.post("/v1/chat/completions", response_model=None)
async def chat(
    request: dict[str, Any],
    response: Response,
    authorization: Optional[str] = Header(default=None),
    x_cinder_client: Optional[str] = Header(default=None),
) -> Any:
    credential_class = authorize(authorization)
    if request.get("model") not in {"glm-5.2", UPSTREAM_MODEL}:
        raise HTTPException(status_code=422, detail="this edge exposes only glm-5.2")
    messages = request.get("messages")
    if not isinstance(messages, list) or not messages:
        raise HTTPException(status_code=422, detail="messages are required")
    upstream_request = dict(request)
    upstream_request["model"] = UPSTREAM_MODEL
    stream_requested = bool(upstream_request.get("stream"))
    if stream_requested:
        # Persist one complete admitted response, then adapt it to the SSE
        # contract expected by OpenAI-compatible coding clients.
        upstream_request["stream"] = False
        upstream_request.pop("stream_options", None)
    payload = json.dumps(upstream_request, sort_keys=True, separators=(",", ":")).encode()
    asserted_at = str(int(time.time()) - ASSERTION_BACKDATE_SECONDS)
    expires_at = str(int(asserted_at) + 60)
    nonce = str(uuid.uuid4())
    assertion_subject = EDGE_OWNER if credential_class == "operator" else f"{EDGE_OWNER}-service"
    assertion = "\n".join((
        "keplerops-range-assertion-v1", "POST", "/v1/chat/completions", "vertex-proxy",
        hashlib.sha256(payload).hexdigest(), RANGE_ID, assertion_subject, credential_class,
        asserted_at, expires_at, nonce,
    )).encode()
    signature = hmac.new(RANGE_ASSERTION_KEY, assertion, hashlib.sha256).hexdigest()
    started = time.time_ns()
    try:
        async with httpx.AsyncClient(timeout=90) as client:
            upstream = await client.post(
                f"{UPSTREAM}/chat/completions", content=payload,
                headers={"Content-Type": "application/json", "X-KeplerOps-Range": RANGE_ID,
                         "X-KeplerOps-Assertion-Version": "keplerops-range-assertion-v1",
                         "X-KeplerOps-Assertion-Key-Id": RANGE_ASSERTION_KEY_ID,
                         "X-KeplerOps-Assertion-Audience": "vertex-proxy",
                         "X-KeplerOps-Assertion-Subject": assertion_subject,
                         "X-KeplerOps-Credential-Class": credential_class,
                         "X-KeplerOps-Asserted-At": asserted_at,
                         "X-KeplerOps-Assertion-Expires-At": expires_at,
                         "X-KeplerOps-Assertion-Nonce": nonce, "X-KeplerOps-Assertion": signature},
            )
        upstream.raise_for_status()
        body = upstream.json()
    except (httpx.HTTPError, ValueError) as error:
        raise HTTPException(status_code=503, detail="Cinder GLM edge is unavailable") from error
    served_model = str(body.get("model", ""))
    if served_model not in {UPSTREAM_MODEL, UPSTREAM_MODEL.removeprefix("openai/"), "glm-5.2"}:
        raise HTTPException(status_code=502, detail="upstream response did not attest the admitted GLM model")
    usage_id = str(uuid.uuid4())
    provider_request_id = upstream.headers.get("x-request-id") or str(body.get("id", ""))
    response_bytes = (json.dumps(body, indent=2, sort_keys=True) + "\n").encode()
    response_object_sha256 = hashlib.sha256(response_bytes).hexdigest()
    record = {
        "schema": "cinder.glm-edge-usage/v1",
        "usage_id": usage_id,
        "attempt_id": usage_id,
        "range_id": RANGE_ID,
        "actor": assertion_subject,
        "credential_class": credential_class,
        "assertion_key_id": RANGE_ASSERTION_KEY_ID,
        "model": "glm-5.2",
        "upstream_model": served_model,
        "provider_request_id": provider_request_id,
        "response_id": str(body.get("id", "")),
        "request_digest": digest_json({"model": "glm-5.2", "messages": messages}),
        "response_digest": response_object_sha256,
        "response_object_sha256": response_object_sha256,
        "generated_content_sha256": hashlib.sha256(
            str((body.get("choices") or [{}])[0].get("message", {}).get("content", "")).encode()
        ).hexdigest(),
        "started_ns": started,
        "completed_ns": time.time_ns(),
        "status": "succeeded",
        "response_object_key": f"responses/{usage_id}.json",
    }
    grounded = any("orion" in str(message.get("content", "")).lower() for message in messages if isinstance(message, dict))
    if (
        credential_class == "operator"
        and EDGE_OWNER == "cinder-field-operator"
        and x_cinder_client == "opencode"
        and grounded
    ):
        record.update({"operation": "kep-m06-p", "model_family": "attacker-glm",
                       "client": "opencode", "target_grounded": True, "flag": USAGE_FLAG})
    STATE.mkdir(parents=True, exist_ok=True)
    (STATE / "responses").mkdir(parents=True, exist_ok=True)
    (STATE / "responses" / f"{usage_id}.json").write_bytes(response_bytes)
    (STATE / f"{usage_id}.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    response_headers = {
        "X-Cinder-Usage-Record": f"/v1/usage/{usage_id}",
        "X-Cinder-Provider-Request": provider_request_id,
        "X-Cinder-Range": RANGE_ID,
    }
    if stream_requested:
        choice = (body.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        delta = {
            key: message[key]
            for key in ("role", "content", "reasoning_content", "tool_calls")
            if message.get(key) is not None
        }
        chunk = {
            "id": body.get("id", f"chatcmpl-{usage_id}"),
            "object": "chat.completion.chunk",
            "created": body.get("created", int(time.time())),
            "model": "glm-5.2",
            "choices": [{
                "index": choice.get("index", 0),
                "delta": delta,
                "finish_reason": choice.get("finish_reason", "stop"),
            }],
        }
        if body.get("usage") is not None:
            chunk["usage"] = body["usage"]
        payload = f"data: {json.dumps(chunk, separators=(',', ':'))}\n\ndata: [DONE]\n\n"
        return StreamingResponse(
            iter((payload,)), media_type="text/event-stream", headers=response_headers
        )
    for name, value in response_headers.items():
        response.headers[name] = value
    return body


@app.get("/v1/usage/{usage_id}")
def usage(usage_id: uuid.UUID, authorization: Optional[str] = Header(default=None)) -> dict[str, Any]:
    authorize(authorization)
    path = STATE / f"{usage_id}.json"
    if not path.is_file():
        raise HTTPException(status_code=404)
    return json.loads(path.read_text())


@app.get("/v1/usage")
def find_usage(
    provider_request_id: str = Query(min_length=3, max_length=200),
    authorization: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    authorize(authorization)
    matches = [json.loads(path.read_text()) for path in STATE.glob("*.json")]
    record = next((item for item in reversed(matches) if item.get("provider_request_id") == provider_request_id), None)
    if record is None:
        raise HTTPException(status_code=404)
    return record


@app.get("/v1/usage-records")
def usage_records(authorization: Optional[str] = Header(default=None)) -> list[dict[str, Any]]:
    authorize(authorization)
    return [json.loads(path.read_text()) for path in sorted(STATE.glob("*.json"))]


@app.get("/v1/responses/{usage_id}")
def response_object(usage_id: uuid.UUID, authorization: Optional[str] = Header(default=None)) -> FileResponse:
    authorize(authorization)
    path = STATE / "responses" / f"{usage_id}.json"
    if not path.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(path, media_type="application/json")
