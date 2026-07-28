"""HTTP boundary for CPU-backed OpenVINO FLUX.1 Schnell image generation."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import os
from pathlib import Path
from typing import Annotated
import uuid

from fastapi import FastAPI, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field

from adapters import (
    MinioArtifactStore,
    OpenVINOImageBackend,
    PostgresGenerationRepository,
)
from service import GenerationRequest, GenerationService


READY_RESPONSES = {503: {"description": "Generation dependencies unavailable"}}
GENERATION_RESPONSES = {409: {"description": "Idempotency key conflict"}}
CONTENT_RESPONSES = {404: {"description": "Generated image not found"}}
IdempotencyKey = Annotated[str | None, Header(alias="Idempotency-Key")]


class ImageGenerationPayload(BaseModel):
    prompt: str = Field(min_length=1, max_length=2_000)
    seed: int = Field(default=0, ge=0, le=2**63 - 1)
    width: int = Field(default=512, ge=256, le=1_024, multiple_of=64)
    height: int = Field(default=512, ge=256, le=1_024, multiple_of=64)
    steps: int = Field(default=4, ge=1, le=12)


class ResetPayload(BaseModel):
    reset_generation: int = Field(ge=0)


def required_environment(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"required environment variable is absent: {name}")
    return value


def build_service() -> GenerationService:
    base = Path(__file__).resolve().parent
    artifact_store = MinioArtifactStore(
        endpoint=os.environ.get("MINIO_ENDPOINT", "minio:9000"),
        access_key=required_environment("MINIO_ACCESS_KEY"),
        secret_key=required_environment("MINIO_SECRET_KEY"),
        bucket=os.environ.get("MINIO_IMAGE_BUCKET", "keplerops-generated-images"),
        secure=os.environ.get("MINIO_SECURE", "true").lower() == "true",
        ca_file=os.environ.get("MINIO_CA_FILE", "/etc/keplerops/pki/ca.crt"),
    )
    return GenerationService(
        backend=OpenVINOImageBackend(
            os.environ.get(
                "IMAGE_MODEL_PATH", "/opt/keplerops/model/flux1-schnell-int4-ov"
            ),
            os.environ.get("IMAGE_DEVICE", "CPU"),
        ),
        repository=PostgresGenerationRepository(
            required_environment("IMAGE_POSTGRES_DSN"), str(base / "schema.sql")
        ),
        artifact_store=artifact_store,
        model_id=os.environ.get("IMAGE_MODEL_ID", "OpenVINO/FLUX.1-schnell-int4-ov"),
        model_revision=os.environ.get(
            "IMAGE_MODEL_REVISION", "67f2ca1b786f707a3c1a7a1f0ae179641249f0c2"
        ),
        reset_generation=int(os.environ.get("RESET_GENERATION", "0")),
    )


@asynccontextmanager
async def lifespan(application: FastAPI):
    service = build_service()
    await asyncio.to_thread(service.initialize)
    application.state.service = service
    application.state.generation_slot = asyncio.Semaphore(1)
    yield


app = FastAPI(title="KeplerOps Image Generation", version="1.0.0", lifespan=lifespan)


@app.get("/healthz/live")
async def live() -> dict[str, bool]:
    return {"live": True}


@app.get("/healthz/ready", responses=READY_RESPONSES)
async def ready(request: Request) -> dict[str, bool]:
    is_ready = await asyncio.to_thread(request.app.state.service.ready)
    if not is_ready:
        raise HTTPException(
            status_code=503, detail="image generation dependencies are unavailable"
        )
    return {"ready": True}


@app.post(
    "/v1/images/generations",
    status_code=201,
    responses=GENERATION_RESPONSES,
)
async def generate_image(
    payload: ImageGenerationPayload,
    request: Request,
    idempotency_key: IdempotencyKey = None,
) -> dict[str, object]:
    generation_request = GenerationRequest(
        prompt=payload.prompt,
        seed=payload.seed,
        width=payload.width,
        height=payload.height,
        steps=payload.steps,
        client_request_id=idempotency_key,
    )
    try:
        async with request.app.state.generation_slot:
            record = await asyncio.to_thread(
                request.app.state.service.generate, generation_request
            )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {
        "created": int(record.created_at.timestamp()),
        "data": [
            {
                "job_id": str(record.job_id),
                "url": f"/v1/images/{record.job_id}/content",
                "sha256": record.artifact_sha256,
                "size": record.artifact_size,
            }
        ],
        "model": record.model_id,
        "model_revision": record.model_revision,
        "seed": record.seed,
        "elapsed_ms": record.elapsed_ms,
    }


@app.get("/v1/images/{job_id}/content", responses=CONTENT_RESPONSES)
async def image_content(job_id: uuid.UUID, request: Request) -> Response:
    result = await asyncio.to_thread(request.app.state.service.get_artifact, job_id)
    if result is None:
        raise HTTPException(status_code=404, detail="image does not exist")
    record, content = result
    return Response(
        content=content,
        media_type="image/png",
        headers={
            "ETag": f'"{record.artifact_sha256}"',
            "Cache-Control": "private, max-age=3600",
        },
    )


@app.post("/internal/reset")
async def reset(payload: ResetPayload, request: Request) -> dict[str, int]:
    return await asyncio.to_thread(
        request.app.state.service.reset, payload.reset_generation
    )
