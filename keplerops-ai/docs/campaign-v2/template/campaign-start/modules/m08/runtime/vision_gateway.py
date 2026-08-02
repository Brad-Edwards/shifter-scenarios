from __future__ import annotations

import hashlib
import hmac
import json
import os
import threading
import uuid
from datetime import UTC, datetime
from typing import Any

import boto3
import requests
from botocore.config import Config
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field


VISION_URL = os.getenv("ORION_VISION_URL", "http://192.168.78.30:30084").rstrip("/")
VISION_TOKEN = os.getenv("ORION_VISION_TOKEN", "KeplerV2-Orion-Vision-Evaluation-Reader")
CINDER_URL = os.getenv("CINDER_S3_ENDPOINT_URL", "http://10.61.90.31:9000")
CINDER_ACCESS = os.getenv("CINDER_S3_ACCESS_KEY", "svc-orion-vision-research")
CINDER_SECRET = os.getenv("CINDER_S3_SECRET_KEY", "KeplerV2-M08-Vision-Ledger-Owner")
LEDGER_KEY = os.getenv("M08_QUERY_LEDGER_KEY", "KeplerV2-Research-Query-Ledger-2026").encode()
ENGAGEMENT_ID = os.getenv("M08_VISION_ENGAGEMENT_ID", "campaign-v2-m08-vision")
PARTICIPANT_ACTOR = "cinder-field-operator"
PARTICIPANT_TOKEN = os.getenv(
    "M08_VISION_PARTICIPANT_TOKEN", "Cinder-Field-Operator-Vision-M08-H8r3Tm5w"
)
app = FastAPI(title="Cinder Vision Research Gateway", version="1.0.0")
QUERY_LOCK = threading.Lock()
FIXED_QUERY_CAP = 64


class Query(BaseModel):
    model_config = ConfigDict(extra="forbid")
    research_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{7,47}$")
    image_b64: str


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def s3():
    return boto3.client(
        "s3",
        endpoint_url=CINDER_URL,
        aws_access_key_id=CINDER_ACCESS,
        aws_secret_access_key=CINDER_SECRET,
        region_name="us-east-1",
        config=Config(s3={"addressing_style": "path"}),
    )


@app.get("/health/ready")
def ready() -> dict[str, str]:
    response = requests.get(f"{VISION_URL}/health/ready", timeout=10)
    response.raise_for_status()
    return {"status": "ready", "upstream": str(response.json()["model"])}


@app.get("/v1/models/orion-vision-prototype")
def model() -> dict[str, Any]:
    response = requests.get(f"{VISION_URL}/v1/models/orion-vision-prototype", timeout=10)
    response.raise_for_status()
    return response.json()


@app.post("/v1/inversion/queries")
def query(
    value: Query,
    authorization: str = Header(default=""),
    actor: str = Header(default="", alias="X-Kepler-Identity"),
) -> dict[str, Any]:
    if (
        authorization != f"Bearer {PARTICIPANT_TOKEN}"
        or actor != PARTICIPANT_ACTOR
    ):
        raise HTTPException(status_code=403, detail="assigned Cinder vision identity is required")
    with QUERY_LOCK:
        return execute_query(value)


def execute_query(value: Query) -> dict[str, Any]:
    prefix = f"orion/vision/query-ledger/{ENGAGEMENT_ID}/{PARTICIPANT_ACTOR}/"
    existing = s3().list_objects_v2(Bucket="artifacts", Prefix=prefix)
    query_number = int(existing.get("KeyCount", 0)) + 1
    if query_number > FIXED_QUERY_CAP:
        raise HTTPException(status_code=429, detail="published inversion query cap reached")
    request_id = f"cinder-inversion-{uuid.uuid4().hex}"
    response = requests.post(
        f"{VISION_URL}/v1/models/orion-vision-prototype:predict",
        headers={
            "Authorization": f"Bearer {VISION_TOKEN}",
            "X-Kepler-Identity": "svc-orion-evaluation-reader",
            "X-Request-ID": request_id,
        },
        json={"instances": [{"image_b64": value.image_b64}]},
        timeout=60,
    )
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text[:500])
    prediction = response.json()
    evidence = prediction.get("evidence") or {}
    if evidence.get("request_id") != request_id:
        raise HTTPException(status_code=502, detail="upstream request lineage is invalid")
    try:
        image_bytes = __import__("base64").b64decode(value.image_b64, validate=True)
    except Exception as error:
        raise HTTPException(status_code=422, detail="image_b64 is invalid") from error
    record = {
        "schema": "cinder.vision-query-ledger/v1",
        "research_id": value.research_id,
        "query_number": query_number,
        "request_id": request_id,
        "actor": PARTICIPANT_ACTOR,
        "engagement_id": ENGAGEMENT_ID,
        "upstream_actor": "svc-orion-evaluation-reader",
        "recorded_at": datetime.now(UTC).isoformat(),
        "input_sha256": sha(image_bytes),
        "upstream_evidence": evidence,
        "model_sha256": prediction.get("model_sha256"),
        "preprocessing_sha256": prediction.get("preprocessing_sha256"),
        "prediction": prediction.get("predictions", [None])[0],
    }
    record["service_signature"] = hmac.new(LEDGER_KEY, canonical(record), hashlib.sha256).hexdigest()
    key = f"{prefix}{query_number:03d}-{value.research_id}-{request_id}.json"
    body = canonical(record)
    s3().put_object(Bucket="artifacts", Key=key, Body=body, ContentType="application/json")
    return {
        **prediction,
        "evidence": {
            **evidence,
            "ledger_key": key,
            "ledger_sha256": sha(body),
            "service_signature": record["service_signature"],
            "actor": PARTICIPANT_ACTOR,
            "engagement_id": ENGAGEMENT_ID,
            "query_number": query_number,
            "query_budget": FIXED_QUERY_CAP,
        },
    }
