"""KeplerOps shared CPU model, evaluation, training, and inversion workbench."""

from __future__ import annotations

import base64
import binascii
import hmac
import io
import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Annotated, Any

import numpy as np
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field, model_validator

from events import EventJournal
from models import MODEL_REVISIONS, VISION_LABELS, VISION_SIDE, ModelSuite, digest_bytes


STATE_ROOT = Path(
    os.environ.get("PLATFORM_ML_STATE_ROOT", "/var/lib/keplerops-platform-ml")
)
CORPUS_PATH = Path(__file__).resolve().parent / "seed/document-corpus.jsonl"
DEFAULT_ADMIN_TOKEN = "keplerops-platform-ml-operator"
RequestId = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,127}$")]
AUTH_RESPONSES = {401: {"description": "Operator authorization failed"}}
READY_RESPONSES = {503: {"description": "The model foundation is not ready"}}
ARTIFACT_RESPONSES = {
    404: {"description": "The model artifact was not found"},
    503: {"description": "The model artifact is unavailable"},
}
VISION_RESPONSES = {
    413: {"description": "The decoded image exceeds the byte bound"},
    422: {"description": "The image payload is invalid"},
}
INVERSION_RESPONSES = {
    422: {"description": "The inversion target or bounds are invalid"}
}


class DocumentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: RequestId
    text: Annotated[str, Field(min_length=3, max_length=20_000)]


class VisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: RequestId
    pixels: list[Annotated[float, Field(ge=0.0, le=1.0)]] | None = None
    image_png_base64: (
        Annotated[str, Field(min_length=12, max_length=350_000)] | None
    ) = None

    @model_validator(mode="after")
    def exactly_one_image(self) -> "VisionRequest":
        if (self.pixels is None) == (self.image_png_base64 is None):
            raise ValueError("provide exactly one of pixels or image_png_base64")
        if self.pixels is not None and len(self.pixels) != VISION_SIDE * VISION_SIDE:
            raise ValueError(
                f"pixels must contain exactly {VISION_SIDE * VISION_SIDE} values"
            )
        return self


class InversionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: RequestId
    target_label: str
    iterations: Annotated[int, Field(ge=1, le=200)] = 80
    learning_rate: Annotated[float, Field(gt=0.0, le=1.0)] = 0.22


class PlatformML:
    def __init__(self, state_root: Path) -> None:
        self.state_root = state_root
        self.state_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.models = ModelSuite(state_root, CORPUS_PATH)
        self.events = EventJournal(state_root / "events/events.jsonl")

    def ready(self) -> bool:
        with self._lock:
            return self.models.ready()

    def retrain(self, *, reset_events: bool) -> dict[str, Any]:
        with self._lock:
            if reset_events:
                self.events.reset()
            inventory = self.models.train(reset=True)
            self.events.append(
                event_name="platform_ml.models_trained",
                operation="models.train",
                status="succeeded",
                request_id="operator-reset",
                request={
                    "reset_events": reset_events,
                    "training_seed": inventory["training_seed"],
                },
                response={
                    "model_set_digest": inventory["model_set_digest"],
                    "model_count": len(inventory["models"]),
                    "validation": inventory["validation"],
                },
                model_ids=[record["model_id"] for record in inventory["models"]],
                duration_ms=0.0,
            )
            return inventory


def require_admin(
    x_platform_admin_token: Annotated[str | None, Header()] = None,
) -> None:
    configured = os.environ.get("PLATFORM_ML_ADMIN_TOKEN", DEFAULT_ADMIN_TOKEN)
    if x_platform_admin_token is None or not hmac.compare_digest(
        x_platform_admin_token, configured
    ):
        raise HTTPException(status_code=401, detail="operator authentication required")


def _decode_image(value: VisionRequest) -> tuple[np.ndarray, dict[str, Any]]:
    if value.pixels is not None:
        pixels = np.asarray(value.pixels, dtype=np.float64).reshape(
            VISION_SIDE, VISION_SIDE
        )
        return pixels, {"encoding": "pixels", "pixels": value.pixels}
    assert value.image_png_base64 is not None
    try:
        raw = base64.b64decode(value.image_png_base64, validate=True)
    except (binascii.Error, ValueError) as error:
        raise HTTPException(
            status_code=422, detail="image_png_base64 is not valid base64"
        ) from error
    if len(raw) > 256_000:
        raise HTTPException(status_code=413, detail="decoded image is too large")
    try:
        with Image.open(io.BytesIO(raw)) as source:
            if source.format != "PNG":
                raise HTTPException(
                    status_code=422, detail="only PNG images are accepted"
                )
            source.load()
            image = source.convert("L").resize(
                (VISION_SIDE, VISION_SIDE), Image.Resampling.LANCZOS
            )
    except (UnidentifiedImageError, OSError) as error:
        raise HTTPException(
            status_code=422, detail="image payload is not a readable PNG"
        ) from error
    pixels = np.asarray(image, dtype=np.float64) / 255.0
    return pixels, {
        "encoding": "png-base64",
        "image_png_base64": value.image_png_base64,
        "decoded_bytes": len(raw),
    }


def _png(pixels: np.ndarray) -> str:
    image = Image.fromarray(
        np.rint(np.clip(pixels, 0.0, 1.0) * 255.0).astype(np.uint8), mode="L"
    )
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=False)
    return base64.b64encode(output.getvalue()).decode("ascii")


def _validation_body(raw: bytes) -> Any:
    try:
        return json.loads(raw) if raw else None
    except json.JSONDecodeError:
        return {"raw_base64": base64.b64encode(raw[:256_000]).decode("ascii")}


def _validation_request_id(body: Any) -> str:
    if isinstance(body, dict) and isinstance(body.get("request_id"), str):
        return body["request_id"][:128]
    return "validation-" + uuid.uuid4().hex


def _validation_details(error: RequestValidationError) -> list[dict[str, Any]]:
    return [
        {
            key: value
            for key, value in item.items()
            if key not in {"ctx", "input", "url"}
        }
        for item in error.errors()
    ]


async def _validation_error_response(
    platform: PlatformML, request: Request, error: RequestValidationError
) -> JSONResponse:
    raw = await request.body()
    body = _validation_body(raw)
    response = {"detail": _validation_details(error)}
    platform.events.append(
        event_name="platform_ml.request_rejected",
        operation=f"{request.method} {request.url.path}",
        status="rejected",
        request_id=_validation_request_id(body),
        request={"body": body},
        response=response,
        model_ids=[],
        duration_ms=0.0,
    )
    return JSONResponse(status_code=422, content=response)


def _find_model_record(platform: PlatformML, model_id: str) -> dict[str, Any]:
    for item in platform.models.inventory["models"]:
        if item["model_id"] == model_id:
            return item
    raise HTTPException(status_code=404, detail="model artifact not found")


def _model_artifact_response(platform: PlatformML, model_id: str) -> dict[str, Any]:
    started = time.perf_counter()
    record = _find_model_record(platform, model_id)
    artifact_name = record["artifact"]
    if Path(artifact_name).name != artifact_name:
        raise HTTPException(status_code=503, detail="model inventory is invalid")
    artifact_path = platform.models.model_root / artifact_name
    try:
        raw = artifact_path.read_bytes()
        if digest_bytes(raw) != record["artifact_digest"]:
            raise HTTPException(
                status_code=503, detail="model artifact digest mismatch"
            )
        artifact = json.loads(raw)
    except (OSError, json.JSONDecodeError) as error:
        raise HTTPException(
            status_code=503, detail="model artifact is unavailable"
        ) from error
    response = {
        "model_id": record["model_id"],
        "revision": record["revision"],
        "domain": record["domain"],
        "artifact_digest": record["artifact_digest"],
        "parameter_digest": record["parameter_digest"],
        "artifact_bytes": len(raw),
        "artifact": artifact,
    }
    platform.events.append(
        event_name="platform_ml.model_artifact_read",
        operation="models.artifact",
        status="succeeded",
        request_id=f"artifact-{model_id}",
        request={"model_id": model_id},
        response={key: value for key, value in response.items() if key != "artifact"},
        model_ids=[model_id],
        duration_ms=(time.perf_counter() - started) * 1_000,
    )
    return response


def create_app(state_root: Path = STATE_ROOT) -> FastAPI:
    platform = PlatformML(state_root)
    app = FastAPI(title="KeplerOps Platform ML", version="1.0.0")
    app.state.platform_ml = platform

    @app.exception_handler(RequestValidationError)
    async def validation_error(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        return await _validation_error_response(platform, request, error)

    @app.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz", responses=READY_RESPONSES)
    def readiness() -> dict[str, Any]:
        if not platform.ready():
            raise HTTPException(status_code=503, detail="model foundation is not ready")
        return {
            "status": "ready",
            "runtime": "cpu",
            "model_count": len(platform.models.inventory["models"]),
            "model_set_digest": platform.models.inventory["model_set_digest"],
        }

    @app.get("/v1/models")
    def models() -> dict[str, Any]:
        return platform.models.inventory

    @app.get("/v1/models/{model_id}/artifact", responses=ARTIFACT_RESPONSES)
    def model_artifact(model_id: str) -> dict[str, Any]:
        return _model_artifact_response(platform, model_id)

    @app.get("/v1/evaluations")
    def evaluations() -> dict[str, Any]:
        return {
            "dataset_revision": platform.models.inventory["dataset_revision"],
            "validation": platform.models.inventory["validation"],
            "models": [
                {
                    "model_id": record["model_id"],
                    "revision": record["revision"],
                    "metrics": record["metrics"],
                }
                for record in platform.models.inventory["models"]
            ],
        }

    @app.post("/v1/documents/classify")
    def classify_document(value: DocumentRequest) -> dict[str, Any]:
        started = time.perf_counter()
        predictions = platform.models.document_predictions(value.text)
        response = {
            "request_id": value.request_id,
            "predictions": predictions,
            "agreement": len({row["label"] for row in predictions}) == 1,
        }
        platform.events.append(
            event_name="platform_ml.document_classified",
            operation="documents.classify",
            status="succeeded",
            request_id=value.request_id,
            request=value.model_dump(mode="json"),
            response=response,
            model_ids=[row["model_id"] for row in predictions],
            duration_ms=(time.perf_counter() - started) * 1_000,
        )
        return response

    @app.post("/v1/vision/classify", responses=VISION_RESPONSES)
    def classify_vision(value: VisionRequest) -> dict[str, Any]:
        started = time.perf_counter()
        pixels, captured_request = _decode_image(value)
        predictions = platform.models.vision_predictions(pixels)
        response = {
            "request_id": value.request_id,
            "predictions": predictions,
            "agreement": len({row["label"] for row in predictions}) == 1,
            "normalized_image_digest": digest_bytes(pixels.astype("<f8").tobytes()),
        }
        platform.events.append(
            event_name="platform_ml.vision_classified",
            operation="vision.classify",
            status="succeeded",
            request_id=value.request_id,
            request={"request_id": value.request_id, **captured_request},
            response=response,
            model_ids=[row["model_id"] for row in predictions],
            duration_ms=(time.perf_counter() - started) * 1_000,
        )
        return response

    @app.post("/v1/vision/invert", responses=INVERSION_RESPONSES)
    def invert_vision(value: InversionRequest) -> dict[str, Any]:
        if value.target_label not in VISION_LABELS:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "target_label is not represented",
                    "allowed": list(VISION_LABELS),
                },
            )
        started = time.perf_counter()
        result = platform.models.invert(
            value.target_label, value.iterations, value.learning_rate
        )
        image_png_base64 = _png(result.pixels)
        response = {
            "request_id": value.request_id,
            "model_id": "vision-mlp-v1",
            "model_revision": MODEL_REVISIONS["vision-mlp-v1"],
            "target_label": result.target_label,
            "target_probability": round(result.target_probability, 8),
            "iterations": result.iterations,
            "image_png_base64": image_png_base64,
            "image_digest": digest_bytes(base64.b64decode(image_png_base64)),
        }
        platform.events.append(
            event_name="platform_ml.vision_inverted",
            operation="vision.invert",
            status="succeeded",
            request_id=value.request_id,
            request=value.model_dump(mode="json"),
            response=response,
            model_ids=["vision-mlp-v1"],
            duration_ms=(time.perf_counter() - started) * 1_000,
        )
        return response

    @app.post(
        "/v1/admin/retrain",
        dependencies=[Depends(require_admin)],
        responses=AUTH_RESPONSES,
    )
    def retrain() -> dict[str, Any]:
        started = time.perf_counter()
        inventory = platform.retrain(reset_events=False)
        return {
            "status": "trained",
            "model_set_digest": inventory["model_set_digest"],
            "model_count": len(inventory["models"]),
            "duration_ms": round((time.perf_counter() - started) * 1_000, 3),
        }

    @app.post(
        "/v1/admin/reset",
        dependencies=[Depends(require_admin)],
        responses=AUTH_RESPONSES,
    )
    def reset() -> dict[str, Any]:
        started = time.perf_counter()
        inventory = platform.retrain(reset_events=True)
        return {
            "status": "reset",
            "model_set_digest": inventory["model_set_digest"],
            "model_count": len(inventory["models"]),
            "duration_ms": round((time.perf_counter() - started) * 1_000, 3),
        }

    @app.get(
        "/v1/admin/events",
        dependencies=[Depends(require_admin)],
        responses=AUTH_RESPONSES,
    )
    def events(limit: Annotated[int, Query(ge=1, le=1_000)] = 100) -> dict[str, Any]:
        records = platform.events.recent(limit)
        return {"record_count": len(records), "records": records}

    return app


app = create_app()
