import os
from typing import Any

import numpy as np
import onnxruntime as ort
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


MODEL_NAME = os.getenv("MODEL_NAME", "orion-release-risk")
MODEL_PATH = os.getenv("MODEL_PATH", "/models/orion-placeholder.onnx")
MODEL_VERSION = os.getenv("MODEL_VERSION", "orion-release-risk-0.1.0")
FEATURE_COUNT = 16

session = ort.InferenceSession(MODEL_PATH, providers=["CPUExecutionProvider"])
app = FastAPI(title="KeplerOps Orion Release Risk Runtime", version="1.0.0")


class PredictionRequest(BaseModel):
    instances: list[Any]


def normalize_instances(instances: list[Any]) -> np.ndarray:
    rows: list[list[float]] = []
    for item in instances:
        value = item.get("features") if isinstance(item, dict) else item
        if not isinstance(value, list) or len(value) != FEATURE_COUNT:
            raise HTTPException(
                status_code=422,
                detail=f"each instance must contain exactly {FEATURE_COUNT} features",
            )
        try:
            rows.append([float(feature) for feature in value])
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail="features must be numeric") from exc
    if not rows:
        raise HTTPException(status_code=422, detail="instances must not be empty")
    return np.asarray(rows, dtype=np.float32)


@app.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "live"}


@app.get("/health/ready")
def ready() -> dict[str, str]:
    return {"status": "ready", "model": MODEL_NAME}


@app.get("/v1/models/{model_name}")
def model_metadata(model_name: str) -> dict[str, Any]:
    if model_name != MODEL_NAME:
        raise HTTPException(status_code=404, detail="model not found")
    return {
        "name": MODEL_NAME,
        "ready": True,
        "runtime": "onnxruntime-cpu",
        "task": "release-risk-classification",
        "version": MODEL_VERSION,
        "feature_count": FEATURE_COUNT,
        "class_count": 8,
    }


@app.post("/v1/models/{model_name}:predict")
def predict(model_name: str, request: PredictionRequest) -> dict[str, Any]:
    if model_name != MODEL_NAME:
        raise HTTPException(status_code=404, detail="model not found")
    features = normalize_instances(request.instances)
    probabilities = session.run(None, {"features": features})[0]
    return {
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
        "predictions": [
            {
                "class_index": int(np.argmax(row)),
                "probabilities": [float(value) for value in row],
            }
            for row in probabilities
        ],
    }
