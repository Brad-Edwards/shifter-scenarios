from __future__ import annotations

from domain import ApprovalSigner
from domain import DomainError
from domain import SessionClaims
from fastapi import APIRouter
from fastapi import HTTPException
from jwt import PyJWKClient
from keplerops_runtime.foundation.auth_storage import _require_ready
from keplerops_runtime.foundation.config import AGENT_WORKER_TIMEOUT_SECONDS, AGENT_WORKER_UNAVAILABLE, CONFIG, IDENTITY_UNAVAILABLE, MODEL_UNAVAILABLE, PROOF_SERVICE_UNAVAILABLE, _regular_owner_file
from keplerops_runtime.foundation.schemas import ModelCompletion
from pathlib import Path
from typing import Any
from typing import Literal
import asyncio
import httpx
import jwt
import time

router = APIRouter()


BACKEND_HTTP_CLIENTS: dict[str, httpx.AsyncClient] = {}
MODEL_IDENTITY_TOKEN: tuple[str, int] | None = None
MODEL_IDENTITY_LOCK = asyncio.Lock()
GCE_IDENTITY_ENDPOINT = (
    "http://metadata.google.internal/computeMetadata/v1/"
    "instance/service-accounts/default/identity"
)
MODEL_IDENTITY_CACHE_SECONDS = 3000

@router.on_event("shutdown")
async def stop_backend_http_clients() -> None:
    clients = tuple(BACKEND_HTTP_CLIENTS.values())
    BACKEND_HTTP_CLIENTS.clear()
    for client in clients:
        await client.aclose()

def _backend_http_client(
    name: str,
    *,
    timeout: float,
    verify: bool | str = True,
) -> httpx.AsyncClient:
    client = BACKEND_HTTP_CLIENTS.get(name)
    if client is None:
        client = httpx.AsyncClient(timeout=timeout, verify=verify)
        BACKEND_HTTP_CLIENTS[name] = client
    return client

async def _model_identity_headers() -> dict[str, str]:
    global MODEL_IDENTITY_TOKEN

    audience = CONFIG.get("model_identity_audience")
    if audience is None:
        return {}
    if (
        not isinstance(audience, str)
        or not audience.startswith("https://keplerops-model-")
        or not audience.endswith(".run.app")
    ):
        raise HTTPException(status_code=503, detail=MODEL_UNAVAILABLE)

    now = int(time.time())
    cached = MODEL_IDENTITY_TOKEN
    if cached is not None and cached[1] > now + 60:
        return {"Authorization": f"Bearer {cached[0]}"}

    async with MODEL_IDENTITY_LOCK:
        cached = MODEL_IDENTITY_TOKEN
        if cached is not None and cached[1] > int(time.time()) + 60:
            return {"Authorization": f"Bearer {cached[0]}"}
        try:
            response = await _backend_http_client(
                "gce-metadata", timeout=2.0
            ).get(
                GCE_IDENTITY_ENDPOINT,
                headers={"Metadata-Flavor": "Google"},
                params={"audience": audience, "format": "full"},
            )
            token = response.text.strip()
        except httpx.HTTPError:
            raise HTTPException(status_code=503, detail=MODEL_UNAVAILABLE) from None
        if (
            response.status_code != 200
            or response.headers.get("metadata-flavor", "").lower() != "google"
            or not token
            or len(token) > 16384
            or token.count(".") != 2
        ):
            raise HTTPException(status_code=503, detail=MODEL_UNAVAILABLE)
        # The metadata server mints a one-hour token for the requested audience.
        # Cloud Run verifies its signature, expiry, and audience on receipt.
        expires_at = int(time.time()) + MODEL_IDENTITY_CACHE_SECONDS
        MODEL_IDENTITY_TOKEN = (token, expires_at)
        return {"Authorization": f"Bearer {token}"}

async def _persistence_worker_request(
    method: Literal["GET", "POST"],
    path: str,
    *,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    worker_url = CONFIG.get("agent_worker_url")
    token_file = CONFIG.get("service_token_file")
    if not isinstance(worker_url, str) or not isinstance(token_file, str):
        raise HTTPException(status_code=503, detail=AGENT_WORKER_UNAVAILABLE)
    token = _regular_owner_file(Path(token_file)).decode("utf-8")
    client = _backend_http_client(
        "agent-state-worker", timeout=AGENT_WORKER_TIMEOUT_SECONDS
    )
    try:
        async with asyncio.timeout(AGENT_WORKER_TIMEOUT_SECONDS):
            response = await client.request(
                method,
                f"{worker_url.rstrip('/')}{path}",
                headers={"X-Service-Token": token},
                json=payload,
            )
    except (TimeoutError, httpx.RequestError):
        raise HTTPException(
            status_code=503, detail=AGENT_WORKER_UNAVAILABLE
        ) from None
    if response.status_code == 409:
        raise HTTPException(status_code=409, detail="durable memory required")
    if response.status_code != 200:
        raise HTTPException(status_code=503, detail=AGENT_WORKER_UNAVAILABLE)
    try:
        result = response.json()
    except ValueError:
        raise HTTPException(
            status_code=503, detail=AGENT_WORKER_UNAVAILABLE
        ) from None
    if not isinstance(result, dict):
        raise HTTPException(status_code=503, detail=AGENT_WORKER_UNAVAILABLE)
    return result

def _signed_approval_session(token: str, session: SessionClaims) -> ApprovalSigner:
    issuer = CONFIG.get("issuer")
    audience = CONFIG.get("audience")
    if not isinstance(issuer, str) or not isinstance(audience, str):
        raise HTTPException(status_code=503, detail=IDENTITY_UNAVAILABLE)
    try:
        key = PyJWKClient(
            f"{issuer.rstrip('/')}/protocol/openid-connect/certs"
        ).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            key.key,
            algorithms=["RS256"],
            audience=audience,
            issuer=issuer,
            options={
                "require": [
                    "exp", "sub", "preferred_username", "roles", "range_instance"
                ]
            },
        )
        return ApprovalSigner.from_mapping(
            {
                "range_instance": claims["range_instance"],
                "participant": claims["preferred_username"],
                "roles": claims["roles"],
                "expires_at": claims["exp"],
            },
            expected_range=session.range_instance,
            now=int(time.time()),
        )
    except (jwt.PyJWTError, DomainError, KeyError, TypeError, ValueError):
        raise HTTPException(status_code=422, detail="signed approval is invalid") from None

async def _record_event(event: dict[str, Any]) -> None:
    proof_url = CONFIG.get("proof_url")
    producer = CONFIG.get("producer_id")
    producer_token_file = CONFIG.get("producer_token_file")
    if not isinstance(proof_url, str) or not isinstance(producer, str) or not isinstance(producer_token_file, str):
        raise HTTPException(status_code=503, detail=PROOF_SERVICE_UNAVAILABLE)
    token = _regular_owner_file(Path(producer_token_file)).decode("utf-8")
    client = _backend_http_client("proof", timeout=5.0)
    response = await client.post(
        f"{proof_url.rstrip('/')}/v1/evidence",
        headers={"X-Producer-ID": producer, "X-Producer-Token": token},
        json={"event": event, "reset_generation": _require_ready()},
    )
    if response.status_code != 204:
        raise HTTPException(status_code=503, detail=PROOF_SERVICE_UNAVAILABLE)

async def _model_completion(system: str, prompt: str) -> ModelCompletion:
    model_url = CONFIG.get("model_url")
    if not isinstance(model_url, str):
        raise HTTPException(status_code=503, detail=MODEL_UNAVAILABLE)
    client = _backend_http_client("model", timeout=30.0)
    try:
        response = await client.post(
            f"{model_url.rstrip('/')}/v1/chat/completions",
            headers=await _model_identity_headers(),
            json={
                "model": "keplerops-teacher",
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 128,
                "temperature": 0,
            },
        )
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail=MODEL_UNAVAILABLE) from None
    if response.status_code != 200:
        raise HTTPException(status_code=503, detail=MODEL_UNAVAILABLE)
    try:
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        usage = payload.get("usage", {})
        token_count = usage.get("total_tokens", 0)
    except (KeyError, IndexError, TypeError, ValueError):
        raise HTTPException(status_code=503, detail=MODEL_UNAVAILABLE) from None
    if (
        not isinstance(content, str)
        or len(content) > 8192
        or not isinstance(token_count, int)
        or isinstance(token_count, bool)
        or token_count < 0
    ):
        raise HTTPException(status_code=503, detail=MODEL_UNAVAILABLE)
    return ModelCompletion(content, token_count)
