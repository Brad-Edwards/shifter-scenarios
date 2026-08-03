from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field


MODEL_URL = os.getenv("ORION_RELEASE_RISK_URL", "http://192.168.78.30:30083").rstrip("/")
MODEL_NAME = os.getenv("ORION_RELEASE_RISK_MODEL", "orion-release-risk")
INDEX = Path(__file__).with_name("static") / "index.html"
AUDIT = Path(os.getenv("ORION_AUDIT_DIR", "/var/lib/orion-preview/audit"))

app = FastAPI(title="Orion Partner Preview", version="1.0.0")


class AnalysisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=8000)


async def model_request(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.request(method, f"{MODEL_URL}{path}", **kwargs)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise HTTPException(status_code=503, detail="Orion analysis is temporarily unavailable") from error
    if not isinstance(payload, dict):
        raise HTTPException(status_code=503, detail="Orion returned an invalid response")
    return payload


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(INDEX)


@app.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "live"}


@app.get("/health/ready")
async def ready() -> dict[str, str]:
    metadata = await model_request("GET", f"/v1/models/{MODEL_NAME}")
    if metadata.get("ready") is not True:
        raise HTTPException(status_code=503, detail="Orion model is not ready")
    return {
        "status": "ready",
        "model": str(metadata.get("name", MODEL_NAME)),
        "model_sha256": str(metadata.get("model_sha256", "")),
    }


@app.post("/api/analyze")
async def analyze(
    request: AnalysisRequest,
    x_orion_experiment: str | None = Header(default=None),
) -> dict[str, Any]:
    payload = await model_request(
        "POST",
        f"/v1/models/{MODEL_NAME}:predict",
        json={"instances": [{"text": request.text}]},
    )
    predictions = payload.get("predictions")
    if not isinstance(predictions, list) or len(predictions) != 1:
        raise HTTPException(status_code=503, detail="Orion returned an invalid prediction")
    prediction = predictions[0]
    if not isinstance(prediction, dict):
        raise HTTPException(status_code=503, detail="Orion returned an invalid prediction")
    analysis_id = str(uuid.uuid4())
    result = {
        "analysis_id": analysis_id,
        "model": payload.get("model_name", MODEL_NAME),
        "model_version": payload.get("model_version"),
        "model_sha256": payload.get("model_sha256"),
        "label": prediction.get("label"),
        "class_index": prediction.get("class_index"),
        "probabilities": prediction.get("probabilities"),
    }
    AUDIT.mkdir(parents=True, exist_ok=True)
    audit = {
        "schema": "keplerops.orion-preview-audit/v1",
        "analysis_id": analysis_id,
        "experiment": x_orion_experiment,
        "received_ns": time.time_ns(),
        "input_sha256": hashlib.sha256(request.text.encode()).hexdigest(),
        "input_bytes": len(request.text.encode()),
        "model": result["model"],
        "model_version": result["model_version"],
        "model_sha256": result["model_sha256"],
        "label": result["label"],
        "class_index": result["class_index"],
        "probabilities": result["probabilities"],
        "case_reference": next(iter(re.findall(r"EXT-[A-Z0-9-]{6,48}", request.text)), None),
    }
    temporary = AUDIT / f".{analysis_id}.json"
    temporary.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    temporary.replace(AUDIT / f"{analysis_id}.json")
    return result


@app.get("/api/audits/{analysis_id}")
async def audit_record(analysis_id: uuid.UUID) -> dict[str, Any]:
    path = AUDIT / f"{analysis_id}.json"
    if not path.is_file():
        raise HTTPException(status_code=404)
    return json.loads(path.read_text())
