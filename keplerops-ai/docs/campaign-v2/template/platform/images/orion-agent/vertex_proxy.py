import asyncio
import hashlib
import hmac
import json
import os
import time
import uuid
from collections import defaultdict, deque

import httpx
from fastapi import FastAPI, HTTPException, Request, Response


PROJECT = os.getenv("VERTEX_PROJECT", "prod-ksqdkj")
LOCATION = os.getenv("VERTEX_LOCATION", "global")
SERVICE_ACCOUNT = os.environ["VERTEX_SERVICE_ACCOUNT"]
INTERNAL_API_KEY = os.environ["VERTEX_INTERNAL_API_KEY"]
INTERNAL_RANGE_ID = os.environ["VERTEX_INTERNAL_RANGE_ID"]
EDGE_KEY_REGISTRY = json.loads(os.environ["VERTEX_EDGE_KEY_REGISTRY_JSON"])
RANGE_CONCURRENCY = int(os.getenv("VERTEX_RANGE_CONCURRENCY", "8"))
RANGE_REQUESTS_PER_MINUTE = int(os.getenv("VERTEX_RANGE_REQUESTS_PER_MINUTE", "120"))
METADATA_URL = os.getenv(
    "GCE_METADATA_TOKEN_URL",
    f"http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/{SERVICE_ACCOUNT}/token",
)
VERTEX_URL = (
    "https://aiplatform.googleapis.com/v1beta1/projects/"
    f"{PROJECT}/locations/{LOCATION}/endpoints/openapi/chat/completions"
)

app = FastAPI(title="KeplerOps Vertex OpenAI adapter", version="0.1.0")
token_lock = asyncio.Lock()
access_token = ""
refresh_at = 0.0
range_semaphores: defaultdict[str, asyncio.Semaphore] = defaultdict(
    lambda: asyncio.Semaphore(RANGE_CONCURRENCY)
)
range_requests: defaultdict[str, deque[float]] = defaultdict(deque)
seen_nonces: dict[str, float] = {}


def authenticate_range(request: Request, payload: bytes) -> tuple[str, str]:
    authorization = request.headers.get("authorization", "")
    if hmac.compare_digest(authorization, f"Bearer {INTERNAL_API_KEY}"):
        if not INTERNAL_RANGE_ID.startswith("range-") or len(INTERNAL_RANGE_ID) != 42:
            raise HTTPException(status_code=503, detail="internal range identity is invalid")
        return INTERNAL_RANGE_ID, "orion-assistant"

    range_id = request.headers.get("x-keplerops-range", "")
    version = request.headers.get("x-keplerops-assertion-version", "")
    key_id = request.headers.get("x-keplerops-assertion-key-id", "")
    audience = request.headers.get("x-keplerops-assertion-audience", "")
    owner = request.headers.get("x-keplerops-assertion-subject", "")
    credential_class = request.headers.get("x-keplerops-credential-class", "")
    asserted_at = request.headers.get("x-keplerops-asserted-at", "")
    expires_at = request.headers.get("x-keplerops-assertion-expires-at", "")
    nonce = request.headers.get("x-keplerops-assertion-nonce", "")
    signature = request.headers.get("x-keplerops-assertion", "")
    identity = EDGE_KEY_REGISTRY.get(key_id)
    if not isinstance(identity, dict):
        raise HTTPException(status_code=401, detail="range assertion key is not registered")
    if (version != "keplerops-range-assertion-v1" or audience != "vertex-proxy"
            or range_id != identity.get("range_id") or len(range_id) != 42
            or owner not in identity.get("subjects", [])
            or credential_class not in identity.get("credential_classes", [])):
        raise HTTPException(status_code=401, detail="range assertion identity is invalid")
    try:
        asserted = int(asserted_at)
        expires = int(expires_at)
        uuid.UUID(nonce)
    except (ValueError, TypeError) as error:
        raise HTTPException(status_code=401, detail="range assertion freshness is invalid") from error
    now = time.time()
    if asserted > now + 5 or expires != asserted + 60 or now > expires or nonce in seen_nonces:
        raise HTTPException(status_code=401, detail="range assertion is stale or replayed")
    assertion = "\n".join((version, request.method, request.url.path, audience,
                            hashlib.sha256(payload).hexdigest(), range_id, owner,
                            credential_class, asserted_at, expires_at, nonce)).encode()
    key = str(identity.get("key", ""))
    if len(key) != 64:
        raise HTTPException(status_code=503, detail="registered range key is invalid")
    expected = hmac.new(key.encode(), assertion, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="range assertion signature is invalid")
    seen_nonces[nonce] = now
    for key, timestamp in list(seen_nonces.items()):
        if now - timestamp > 120:
            del seen_nonces[key]
    requests = range_requests[range_id]
    while requests and now - requests[0] > 60:
        requests.popleft()
    if len(requests) >= RANGE_REQUESTS_PER_MINUTE:
        raise HTTPException(status_code=429, detail="range request allocation is exhausted")
    requests.append(now)
    return range_id, owner


async def get_access_token() -> str:
    global access_token, refresh_at
    now = time.monotonic()
    if access_token and now < refresh_at:
        return access_token

    async with token_lock:
        now = time.monotonic()
        if access_token and now < refresh_at:
            return access_token
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                METADATA_URL,
                headers={"Metadata-Flavor": "Google"},
            )
            response.raise_for_status()
            token = response.json()
        access_token = token["access_token"]
        refresh_at = now + max(60, int(token.get("expires_in", 3600)) - 300)
        return access_token


@app.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "live"}


@app.get("/health/ready")
async def ready() -> dict[str, str]:
    try:
        await get_access_token()
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="GCP workload identity is unavailable") from exc
    return {"status": "ready", "project": PROJECT, "location": LOCATION,
            "workload_service_account": SERVICE_ACCOUNT}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request) -> Response:
    payload = await request.body()
    range_id, owner = authenticate_range(request, payload)
    try:
        submitted = json.loads(payload)
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=422, detail="request is not JSON") from error
    configured_model = str(submitted.get("model", ""))
    if configured_model == "openai/zai-org/glm-5-maas":
        submitted["model"] = "zai-org/glm-5-maas"
    elif configured_model != "zai-org/glm-5-maas":
        raise HTTPException(status_code=422, detail="model is not admitted")
    submitted["user"] = range_id
    payload = json.dumps(submitted, separators=(",", ":")).encode()
    provider_request_id = str(uuid.uuid4())
    try:
        token = await get_access_token()
        async with range_semaphores[range_id]:
            async with httpx.AsyncClient(timeout=120) as client:
                upstream = await client.post(
                    VERTEX_URL,
                    content=payload,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                        "X-Request-ID": provider_request_id,
                        "X-KeplerOps-Range": range_id,
                        "X-KeplerOps-Edge-Owner": owner,
                    },
                )
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="Vertex AI is unavailable") from exc

    response = Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type", "application/json"),
    )
    response.headers["X-Request-ID"] = upstream.headers.get("x-request-id", provider_request_id)
    response.headers["X-KeplerOps-Range"] = range_id
    response.headers["X-KeplerOps-Edge-Owner"] = owner
    response.headers["X-KeplerOps-Cache-Namespace"] = range_id
    return response
