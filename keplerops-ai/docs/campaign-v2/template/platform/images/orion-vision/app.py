from __future__ import annotations

import base64
import binascii
import hashlib
import io
import json
import os
import re
import secrets
import threading
from pathlib import Path
from typing import Any

import numpy as np
import onnxruntime as ort
from fastapi import FastAPI, Header, HTTPException
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict


MODEL_NAME = "orion-vision-prototype"
MODEL_DIR = Path(os.getenv("MODEL_DIR", "/models"))
MODEL_PATH = MODEL_DIR / "orion-vision-prototype.onnx"
MAX_BATCH_SIZE = 16
MAX_IMAGE_BYTES = 256 * 1024
EVALUATION_ACTOR = os.getenv(
    "ORION_VISION_EVALUATION_ACTOR", "svc-orion-evaluation-reader"
)
EVALUATION_TOKEN = os.getenv(
    "ORION_VISION_EVALUATION_TOKEN", "KeplerV2-Orion-Vision-Evaluation-Reader"
)
QUERY_BUDGET = int(os.getenv("ORION_VISION_QUERY_BUDGET", "64"))
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,95}$")
query_lock = threading.Lock()
query_count = 0


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


class_map = json.loads((MODEL_DIR / "class-map.json").read_text())
id_to_label = {class_id: label for label, class_id in class_map.items()}
preprocessing = json.loads((MODEL_DIR / "preprocessing.json").read_text())
metadata = json.loads((MODEL_DIR / "model-metadata.json").read_text())
model_sha256 = sha256(MODEL_PATH)
if metadata["onnx_sha256"] != model_sha256:
    raise RuntimeError("model metadata does not match the loaded ONNX model")
if metadata["class_map_sha256"] != canonical_sha256(class_map):
    raise RuntimeError("model metadata does not match the class map")
if metadata["preprocessing_sha256"] != canonical_sha256(preprocessing):
    raise RuntimeError("model metadata does not match preprocessing")

session = ort.InferenceSession(str(MODEL_PATH), providers=["CPUExecutionProvider"])
if session.get_inputs()[0].name != "images" or session.get_outputs()[0].name != "logits":
    raise RuntimeError("ONNX input/output names do not match the model contract")

app = FastAPI(
    title="Orion Synthetic Photonics Pattern Benchmark",
    version=metadata["revision"],
)


class ImageInstance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image_b64: str


class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instances: list[ImageInstance]


def decode_image(encoded: str) -> np.ndarray:
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as error:
        raise HTTPException(status_code=422, detail="image_b64 is not valid base64") from error
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=422, detail="encoded image size is invalid")
    try:
        with Image.open(io.BytesIO(raw)) as image:
            image.load()
            if image.format != "PNG":
                raise HTTPException(status_code=422, detail="image must be PNG")
            expected_size = (
                int(preprocessing["width"]),
                int(preprocessing["height"]),
            )
            if image.size != expected_size or image.mode != preprocessing["color_space"]:
                raise HTTPException(
                    status_code=422,
                    detail="image must be a 64-by-64 RGB PNG",
                )
            pixels = np.asarray(image, dtype=np.float32)
    except (UnidentifiedImageError, OSError) as error:
        raise HTTPException(status_code=422, detail="image is not a valid PNG") from error

    pixels *= float(preprocessing["pixel_scale"])
    mean = np.asarray(preprocessing["mean"], dtype=np.float32)
    std = np.asarray(preprocessing["std"], dtype=np.float32)
    return np.transpose((pixels - mean) / std, (2, 0, 1)).astype(np.float32)


def softmax(logits: np.ndarray) -> np.ndarray:
    scaled = logits / float(metadata["softmax_temperature"])
    shifted = scaled - np.max(scaled, axis=1, keepdims=True)
    exponent = np.exp(shifted)
    return exponent / np.sum(exponent, axis=1, keepdims=True)


def authorize_evaluation(
    authorization: str | None,
    actor: str | None,
    request_id: str | None,
) -> str:
    expected = f"Bearer {EVALUATION_TOKEN}"
    if authorization is None or not secrets.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="evaluation credential required")
    if actor != EVALUATION_ACTOR:
        raise HTTPException(status_code=403, detail="evaluation-reader identity required")
    if request_id is None or REQUEST_ID_PATTERN.fullmatch(request_id) is None:
        raise HTTPException(status_code=422, detail="valid X-Request-ID required")
    return request_id


def reserve_query() -> int:
    global query_count
    with query_lock:
        if query_count >= QUERY_BUDGET:
            raise HTTPException(status_code=429, detail="evaluation query budget exhausted")
        query_count += 1
        return query_count


@app.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "live"}


@app.get("/health/ready")
def ready() -> dict[str, str]:
    return {
        "status": "ready",
        "model": MODEL_NAME,
        "model_sha256": model_sha256,
    }


@app.get("/v1/models/{model_name}")
def model_details(model_name: str) -> dict[str, Any]:
    if model_name != MODEL_NAME:
        raise HTTPException(status_code=404, detail="model not found")
    return {
        "architecture": metadata["architecture"],
        "benchmark_scope": "internal-synthetic-photonics-pattern-privacy",
        "class_map": class_map,
        "input_shape": metadata["input_shape"],
        "model_family": metadata["model_family"],
        "model_sha256": model_sha256,
        "name": MODEL_NAME,
        "output_shape": metadata["output_shape"],
        "preprocessing": preprocessing,
        "preprocessing_sha256": metadata["preprocessing_sha256"],
        "ready": True,
        "revision": metadata["revision"],
        "runtime": metadata["runtime"],
        "scores_are_calibrated": False,
        "supported_claims": [
            "reproducible classification of contract-generated benchmark patterns"
        ],
        "unsupported_claims": [
            "field component inspection",
            "privacy guarantee",
            "probability calibration",
        ],
    }


@app.post("/v1/models/{model_name}:predict")
def predict(
    model_name: str,
    request: PredictionRequest,
    authorization: str | None = Header(default=None),
    x_kepler_identity: str | None = Header(default=None),
    x_request_id: str | None = Header(default=None),
) -> dict[str, Any]:
    if model_name != MODEL_NAME:
        raise HTTPException(status_code=404, detail="model not found")
    request_id = authorize_evaluation(
        authorization, x_kepler_identity, x_request_id
    )
    if not request.instances or len(request.instances) > MAX_BATCH_SIZE:
        raise HTTPException(status_code=422, detail="instances must contain 1 to 16 images")
    batch = np.stack([decode_image(item.image_b64) for item in request.instances])
    query_number = reserve_query()
    probabilities = softmax(session.run(["logits"], {"images": batch})[0])
    predictions = [
        {
            "class_index": int(np.argmax(row)),
            "label": id_to_label[int(np.argmax(row))],
            "probabilities": [round(float(value), 8) for value in row],
        }
        for row in probabilities
    ]
    evidence = {
        "actor": EVALUATION_ACTOR,
        "model_sha256": model_sha256,
        "query_budget": QUERY_BUDGET,
        "query_number": query_number,
        "request_id": request_id,
    }
    print(
        json.dumps(
            {
                "event": "orion_vision_evaluation",
                "evidence": evidence,
                "prediction_labels": [item["label"] for item in predictions],
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return {
        "evidence": evidence,
        "model_family": metadata["model_family"],
        "model_name": MODEL_NAME,
        "model_revision": metadata["revision"],
        "model_sha256": model_sha256,
        "predictions": predictions,
        "preprocessing_sha256": metadata["preprocessing_sha256"],
    }
