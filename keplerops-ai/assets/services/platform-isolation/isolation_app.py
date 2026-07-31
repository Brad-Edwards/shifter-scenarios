"""Authenticated control API for disposable unsafe-serialization loaders."""

import asyncio
import base64
import binascii
import json
import os
import secrets
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from isolation_state import (
    EVENT_SCHEMA_VERSION,
    SCHEMA_VERSION,
    IsolationStore,
    digest_bytes,
    now,
)
from isolation_workers import (
    DEFAULT_WORKER_IMAGE,
    EngineRejected,
    EngineUnavailable,
    IsolationWorkerError,
    LoaderWorkerController,
    WorkerOwnershipError,
)


DEFAULT_ADMIN_TOKEN = "keplerops-isolation-admin"
ADMIN_HEADER = "X-Isolation-Admin-Token"
IDENTIFIER_PATTERN = r"^[a-z0-9][a-z0-9._-]{2,63}$"
MAX_ARTIFACT_BYTES = 1_048_576
UNAUTHORIZED_RESPONSE = {"description": "Missing or invalid isolation credential"}
NOT_FOUND_RESPONSE = {"description": "Requested artifact or loader job was not found"}
CONFLICT_RESPONSE = {"description": "Loader ownership or state conflict"}
PAYLOAD_TOO_LARGE_RESPONSE = {"description": "Artifact exceeds the bounded size"}
UNPROCESSABLE_RESPONSE = {"description": "Artifact encoding is invalid"}
SERVICE_UNAVAILABLE_RESPONSE = {"description": "Dedicated loader engine is unavailable"}


def _configured_token(
    *, file_variable: str, value_variable: str, synthetic_default: str
) -> str:
    if file_variable not in os.environ:
        return os.environ.get(value_variable, synthetic_default)
    configured_path = os.environ[file_variable]
    if not configured_path:
        raise RuntimeError(f"{file_variable} must name a readable, non-empty file")
    try:
        value = Path(configured_path).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise RuntimeError(
            f"{file_variable} must name a readable, non-empty file"
        ) from error
    if value.endswith("\r\n"):
        value = value[:-2]
    elif value.endswith("\n"):
        value = value[:-1]
    if not value:
        raise RuntimeError(f"{file_variable} must name a readable, non-empty file")
    return value


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ArtifactRequest(StrictModel):
    artifact_id: str = Field(pattern=IDENTIFIER_PATTERN)
    media_type: Literal["application/python-pickle"] = "application/python-pickle"
    artifact_b64: str = Field(min_length=4, max_length=1_500_000)


def _ready_response(
    store: IsolationStore, workers: LoaderWorkerController
) -> dict[str, Any]:
    if not store.ready():
        raise HTTPException(status_code=503, detail="state store is not ready")
    try:
        engine = workers.engine_info()
    except (EngineRejected, EngineUnavailable) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "status": "ready",
        "schema_version": SCHEMA_VERSION,
        "event_schema_version": EVENT_SCHEMA_VERSION,
        "engine": engine,
    }


async def _reset_response(
    store: IsolationStore, workers: LoaderWorkerController
) -> dict[str, Any]:
    try:
        removed = await asyncio.to_thread(workers.cleanup)
    except IsolationWorkerError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    store.reset()
    return {"status": "reset", "removed_jobs": removed}


def _upload_artifact(store: IsolationStore, request: ArtifactRequest) -> dict[str, Any]:
    try:
        content = base64.b64decode(request.artifact_b64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail="artifact_b64 is invalid") from exc
    if not content or len(content) > MAX_ARTIFACT_BYTES:
        raise HTTPException(
            status_code=413, detail="artifact must contain 1 to 1048576 bytes"
        )
    storage_name = f"{request.artifact_id}.pkl"
    artifact_path = store.artifact_root / storage_name
    created_at = now()
    try:
        with artifact_path.open("xb") as handle:
            handle.write(content)
        artifact_path.chmod(0o600)
        with store.transaction() as connection:
            connection.execute(
                "INSERT INTO artifacts "
                "(artifact_id, media_type, byte_count, digest, storage_name, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    request.artifact_id,
                    request.media_type,
                    len(content),
                    digest_bytes(content),
                    storage_name,
                    created_at,
                ),
            )
    except (FileExistsError, sqlite3.IntegrityError) as exc:
        raise HTTPException(status_code=409, detail="artifact already exists") from exc
    except Exception:
        artifact_path.unlink(missing_ok=True)
        raise
    store.event(
        "loader.artifact.stored",
        "loader-control",
        {
            "artifact_id": request.artifact_id,
            "media_type": request.media_type,
            "artifact_b64": request.artifact_b64,
            "byte_count": len(content),
            "digest": digest_bytes(content),
        },
        request.artifact_id,
    )
    return {
        "artifact_id": request.artifact_id,
        "media_type": request.media_type,
        "byte_count": len(content),
        "digest": digest_bytes(content),
        "created_at": created_at,
    }


async def _worker_response(
    operation: Callable[[str], dict[str, Any]], resource_id: str
) -> dict[str, Any]:
    try:
        return await asyncio.to_thread(operation, resource_id)
    except WorkerOwnershipError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (EngineRejected, EngineUnavailable) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except IsolationWorkerError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _events_response(store: IsolationStore, limit: int) -> dict[str, Any]:
    with store.read() as connection:
        rows = connection.execute(
            "SELECT * FROM structured_events ORDER BY occurred_at, event_id LIMIT ?",
            (limit,),
        ).fetchall()
    result = []
    for row in rows:
        event = dict(row)
        event["payload"] = json.loads(event.pop("payload_json"))
        result.append(event)
    return {"schema_version": EVENT_SCHEMA_VERSION, "events": result}


def create_app(
    data_root: Path | None = None,
    worker_client: Any | None = None,
    engine_url: str | None = None,
) -> FastAPI:
    root = data_root or Path(
        os.environ.get("ISOLATION_DATA_ROOT", "/var/lib/keplerops-isolation")
    )
    admin_token = _configured_token(
        file_variable="ISOLATION_ADMIN_TOKEN_FILE",
        value_variable="ISOLATION_ADMIN_TOKEN",
        synthetic_default=DEFAULT_ADMIN_TOKEN,
    )
    socket_url = engine_url or os.environ.get(
        "ISOLATION_ENGINE_SOCKET",
        "unix:///run/keplerops-isolation-engine/docker.sock",
    )
    worker_image = os.environ.get("ISOLATION_WORKER_IMAGE", DEFAULT_WORKER_IMAGE)
    store = IsolationStore(root)
    workers = LoaderWorkerController(
        store, base_url=socket_url, image_ref=worker_image, client=worker_client
    )
    application = FastAPI(
        title="KeplerOps Disposable Loader Control",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    application.state.store = store
    application.state.workers = workers

    def require_admin(
        supplied: Annotated[str | None, Header(alias=ADMIN_HEADER)] = None,
    ) -> None:
        if supplied is None or not secrets.compare_digest(supplied, admin_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized"
            )

    AdminAuthorization = Annotated[None, Depends(require_admin)]

    @application.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get(
        "/readyz",
        responses={401: UNAUTHORIZED_RESPONSE, 503: SERVICE_UNAVAILABLE_RESPONSE},
    )
    def ready(_authorized: AdminAuthorization) -> dict[str, Any]:
        return _ready_response(store, workers)

    @application.post(
        "/v1/admin/reset",
        responses={401: UNAUTHORIZED_RESPONSE, 503: SERVICE_UNAVAILABLE_RESPONSE},
    )
    async def reset(_authorized: AdminAuthorization) -> dict[str, Any]:
        return await _reset_response(store, workers)

    @application.post(
        "/v1/artifacts",
        status_code=201,
        responses={
            401: UNAUTHORIZED_RESPONSE,
            409: CONFLICT_RESPONSE,
            413: PAYLOAD_TOO_LARGE_RESPONSE,
            422: UNPROCESSABLE_RESPONSE,
        },
    )
    def upload_artifact(
        request: ArtifactRequest,
        _authorized: AdminAuthorization,
    ) -> dict[str, Any]:
        return _upload_artifact(store, request)

    @application.post(
        "/v1/artifacts/{artifact_id}/load",
        status_code=201,
        responses={
            401: UNAUTHORIZED_RESPONSE,
            404: NOT_FOUND_RESPONSE,
            409: CONFLICT_RESPONSE,
            503: SERVICE_UNAVAILABLE_RESPONSE,
        },
    )
    async def load_artifact(
        artifact_id: str,
        _authorized: AdminAuthorization,
    ) -> dict[str, Any]:
        return await _worker_response(workers.create_and_run, artifact_id)

    @application.get(
        "/v1/jobs/{job_id}",
        responses={
            401: UNAUTHORIZED_RESPONSE,
            404: NOT_FOUND_RESPONSE,
            409: CONFLICT_RESPONSE,
            503: SERVICE_UNAVAILABLE_RESPONSE,
        },
    )
    async def job_status(
        job_id: str,
        _authorized: AdminAuthorization,
    ) -> dict[str, Any]:
        return await _worker_response(workers.status, job_id)

    @application.post(
        "/v1/jobs/{job_id}/restart",
        responses={
            401: UNAUTHORIZED_RESPONSE,
            404: NOT_FOUND_RESPONSE,
            409: CONFLICT_RESPONSE,
            503: SERVICE_UNAVAILABLE_RESPONSE,
        },
    )
    async def restart_job(
        job_id: str,
        _authorized: AdminAuthorization,
    ) -> dict[str, Any]:
        return await _worker_response(workers.restart, job_id)

    @application.delete(
        "/v1/jobs/{job_id}",
        responses={
            401: UNAUTHORIZED_RESPONSE,
            404: NOT_FOUND_RESPONSE,
            409: CONFLICT_RESPONSE,
            503: SERVICE_UNAVAILABLE_RESPONSE,
        },
    )
    async def remove_job(
        job_id: str,
        _authorized: AdminAuthorization,
    ) -> dict[str, str]:
        return await _worker_response(workers.remove, job_id)

    @application.get("/v1/events", responses={401: UNAUTHORIZED_RESPONSE})
    def events(
        _authorized: AdminAuthorization,
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
    ) -> dict[str, Any]:
        return _events_response(store, limit)

    return application


app = create_app()
