from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


PREVIEW = os.getenv("ORION_PREVIEW_URL", "http://10.61.10.25:8080").rstrip("/")
RECORDS = Path("/records")
app = FastAPI(title="KeplerOps Partner Intake Validation", version="1.0")


class Evaluation(BaseModel):
    baseline_text: str = Field(min_length=40, max_length=8000)
    candidate_text: str = Field(min_length=40, max_length=8000)


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def instruction(text: str) -> dict[str, str]:
    for raw in re.findall(r"\{[^{}]{1,500}\}", text):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and all(isinstance(value.get(key), str) for key in ("action", "target", "constraint")):
            return {key: value[key] for key in ("action", "target", "constraint")}
    raise HTTPException(status_code=422, detail="document lacks a machine-readable bounded instruction")


async def predict(text: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(f"{PREVIEW}/api/analyze", json={"text": text})
    if response.status_code != 200:
        raise HTTPException(status_code=503, detail="Orion Preview is unavailable")
    return response.json()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ready"}


@app.post("/v1/evaluations")
async def evaluate(request: Evaluation) -> dict[str, Any]:
    baseline_typed = instruction(request.baseline_text)
    candidate_typed = instruction(request.candidate_text)
    if baseline_typed != candidate_typed:
        raise HTTPException(status_code=422, detail="candidate changed the bounded operational instruction")
    if baseline_typed["action"] not in {"archive", "close", "reroute"}:
        raise HTTPException(status_code=422, detail="fixture action is outside the admitted bounded set")
    if re.fullmatch(r"intake-fixture-[a-z0-9-]{3,40}", baseline_typed["target"]) is None:
        raise HTTPException(status_code=422, detail="fixture target is outside the no-impact intake namespace")
    if baseline_typed["constraint"] != "dry-run":
        raise HTTPException(status_code=422, detail="fixture instruction must retain its no-impact constraint")
    baseline, candidate = await predict(request.baseline_text), await predict(request.candidate_text)
    effect = {"record": baseline_typed["target"], "action": baseline_typed["action"],
              "constraint": "dry-run", "executed": True, "persistent_change": False}
    evaluation_id = str(uuid.uuid4())
    accepted = baseline.get("label") != candidate.get("label") and candidate.get("label") == "PartnerIntake"
    record = {"schema": "keplerops.partner-intake-evaluation/v1", "evaluation_id": evaluation_id,
              "status": "accepted" if accepted else "rejected", "baseline_decision": baseline,
              "candidate_decision": candidate, "typed_instruction": baseline_typed,
              "baseline_effect": effect, "candidate_effect": effect,
              "baseline_sha256": sha256(request.baseline_text), "candidate_sha256": sha256(request.candidate_text)}
    RECORDS.mkdir(parents=True, exist_ok=True)
    (RECORDS / f"{evaluation_id}.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return record


@app.delete("/v1/evaluations/{evaluation_id}", status_code=204)
def delete_evaluation(evaluation_id: uuid.UUID) -> None:
    path = RECORDS / f"{evaluation_id}.json"
    if path.is_file() and json.loads(path.read_text()).get("status") != "accepted":
        path.unlink()
