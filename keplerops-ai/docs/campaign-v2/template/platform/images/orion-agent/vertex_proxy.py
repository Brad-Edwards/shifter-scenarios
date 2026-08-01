import asyncio
import os
import time

import httpx
from fastapi import FastAPI, HTTPException, Request, Response


PROJECT = os.getenv("VERTEX_PROJECT", "prod-ksqdkj")
LOCATION = os.getenv("VERTEX_LOCATION", "global")
METADATA_URL = os.getenv(
    "GCE_METADATA_TOKEN_URL",
    "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token",
)
VERTEX_URL = (
    "https://aiplatform.googleapis.com/v1beta1/projects/"
    f"{PROJECT}/locations/{LOCATION}/endpoints/openapi/chat/completions"
)

app = FastAPI(title="KeplerOps Vertex OpenAI adapter", version="0.1.0")
token_lock = asyncio.Lock()
access_token = ""
refresh_at = 0.0


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
    return {"status": "ready", "project": PROJECT, "location": LOCATION}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request) -> Response:
    try:
        token = await get_access_token()
        payload = await request.body()
        async with httpx.AsyncClient(timeout=120) as client:
            upstream = await client.post(
                VERTEX_URL,
                content=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": request.headers.get("content-type", "application/json"),
                },
            )
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="Vertex AI is unavailable") from exc

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type", "application/json"),
    )
