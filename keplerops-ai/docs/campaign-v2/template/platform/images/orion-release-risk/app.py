import hashlib
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import onnxruntime as ort
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from tokenizers import Tokenizer


MODEL_NAME = os.getenv("MODEL_NAME", "orion-release-risk")
MODEL_DIR = Path(os.getenv("MODEL_DIR", "/models"))
MODEL_PATH = MODEL_DIR / "orion-release-risk.onnx"
TOKENIZER_PATH = MODEL_DIR / "tokenizer.json"
MAX_LENGTH = 64


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


label_to_id = json.loads((MODEL_DIR / "label-map.json").read_text())
id_to_label = {value: key for key, value in label_to_id.items()}
release_metadata = json.loads((MODEL_DIR / "release-metadata.json").read_text())
model_sha256 = sha256(MODEL_PATH)
tokenizer_sha256 = sha256(TOKENIZER_PATH)
if release_metadata["onnx_sha256"] != model_sha256:
    raise RuntimeError("release metadata does not match the loaded ONNX model")
if release_metadata["tokenizer_sha256"] != tokenizer_sha256:
    raise RuntimeError("release metadata does not match the loaded tokenizer")

tokenizer = Tokenizer.from_file(str(TOKENIZER_PATH))
tokenizer.enable_truncation(max_length=MAX_LENGTH)
tokenizer.enable_padding(length=MAX_LENGTH, pad_id=0, pad_token="[PAD]")
session = ort.InferenceSession(str(MODEL_PATH), providers=["CPUExecutionProvider"])
app = FastAPI(title="Orion Release Risk", version="1.0.0")


class PredictionRequest(BaseModel):
    instances: list[Any]


def extract_texts(instances: list[Any]) -> list[str]:
    texts: list[str] = []
    for item in instances:
        value = item.get("text") if isinstance(item, dict) else item
        if not isinstance(value, str) or not value.strip():
            raise HTTPException(
                status_code=422,
                detail="each instance must be a non-empty string or object with text",
            )
        texts.append(value)
    if not texts:
        raise HTTPException(status_code=422, detail="instances must not be empty")
    return texts


def softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - np.max(logits, axis=1, keepdims=True)
    exponent = np.exp(shifted)
    return exponent / np.sum(exponent, axis=1, keepdims=True)


@app.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "live"}


@app.get("/health/ready")
def ready() -> dict[str, str]:
    return {"status": "ready", "model": MODEL_NAME, "model_sha256": model_sha256}


@app.get("/v1/models/{model_name}")
def model_metadata(model_name: str) -> dict[str, Any]:
    if model_name != MODEL_NAME:
        raise HTTPException(status_code=404, detail="model not found")
    return {
        "name": MODEL_NAME,
        "ready": True,
        "model_family": "release-risk",
        "runtime": "onnxruntime-cpu",
        "class_count": len(label_to_id),
        "labels": list(label_to_id),
        "model_sha256": model_sha256,
        "tokenizer_sha256": tokenizer_sha256,
        "mlflow_run_id": release_metadata["mlflow_run_id"],
        "mlflow_model_version": release_metadata["mlflow_model_version"],
        "lakefs_commit": release_metadata["lakefs_commit"],
    }


@app.post("/v1/models/{model_name}:predict")
def predict(model_name: str, request: PredictionRequest) -> dict[str, Any]:
    if model_name != MODEL_NAME:
        raise HTTPException(status_code=404, detail="model not found")
    encoded = tokenizer.encode_batch(extract_texts(request.instances))
    feeds = {
        "input_ids": np.asarray([item.ids for item in encoded], dtype=np.int64),
        "attention_mask": np.asarray(
            [item.attention_mask for item in encoded], dtype=np.int64
        ),
        "token_type_ids": np.asarray(
            [item.type_ids for item in encoded], dtype=np.int64
        ),
    }
    probabilities = softmax(session.run(None, feeds)[0])
    return {
        "model_name": MODEL_NAME,
        "model_version": release_metadata["mlflow_model_version"],
        "model_sha256": model_sha256,
        "predictions": [
            {
                "class_index": int(np.argmax(row)),
                "label": id_to_label[int(np.argmax(row))],
                "probabilities": [float(value) for value in row],
            }
            for row in probabilities
        ],
    }
