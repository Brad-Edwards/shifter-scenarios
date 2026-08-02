from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

import research


app = FastAPI(title="Orion Release Risk Label Studio Backend", version="1.0.0")
BACKEND_IDENTITY = "svc-orion-label-studio-ml"


class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    tasks: list[dict[str, Any]] = Field(min_length=1, max_length=64)


@app.get("/")
@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "UP", "model_class": "OrionReleaseRiskBackend"}


@app.post("/setup")
def setup(_: dict[str, Any]) -> dict[str, str]:
    metadata = research.checked(
        research.requests.get(
            f"{research.MODEL_URL}/v1/models/orion-release-risk", timeout=30
        )
    ).json()
    return {
        "model_version": str(metadata["mlflow_model_version"]),
        "model_digest": str(metadata["model_sha256"]),
    }


@app.post("/predict")
def predict(request: PredictionRequest) -> dict[str, list[dict[str, Any]]]:
    task_ids: list[int] = []
    texts: list[str] = []
    slices: list[str] = []
    for task in request.tasks:
        data = task.get("data") or {}
        try:
            task_id = int(task["id"])
        except (KeyError, TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail="Label Studio task ID is required") from error
        text = str(data.get("text", "")).strip()
        release_slice = str(data.get("release_slice", ""))
        if not text or release_slice not in research.RELEASE_SLICES:
            raise HTTPException(
                status_code=422,
                detail="each task requires text and a published release_slice",
            )
        task_ids.append(task_id)
        texts.append(text)
        slices.append(release_slice)
    if len(task_ids) != len(set(task_ids)) or len(texts) != len(set(texts)):
        raise HTTPException(status_code=422, detail="prediction tasks must be distinct")

    operation = "kep-m08-k"
    accepting = not (research.STATE / "accepted" / f"{operation}.json").is_file()
    research.start_attempt(operation if accepting else "kep-m08-a")
    try:
        metadata, predictions, ledgers = research.teacher_with_ledgers(
            texts,
            slices,
            "label-studio-ml-backend",
            [
                {
                    "label_studio_task_id": task_id,
                    "backend_identity": BACKEND_IDENTITY,
                }
                for task_id in task_ids
            ],
        )
        rendered = []
        for task_id, prediction, ledger in zip(
            task_ids, predictions, ledgers, strict=True
        ):
            continuity = research.release_risk_continuity(metadata)
            rendered.append({
                "model_version": str(metadata["mlflow_model_version"]),
                "score": max(float(item) for item in prediction["probabilities"]),
                "result": [{
                    "id": f"orion-release-risk-{task_id}",
                    "from_name": "release_risk",
                    "to_name": "text",
                    "type": "choices",
                    "readonly": True,
                    "value": {"choices": [prediction["label"]]},
                    "meta": {
                        "request_id": prediction["inference_id"],
                        "model_digest": metadata["model_sha256"],
                        "probabilities": prediction["probabilities"],
                        "recorded_at": ledger["recorded_at"],
                        "text_sha256": ledger["text_sha256"],
                        "ledger_key": ledger["ledger_key"],
                        "ledger_sha256": ledger["ledger_sha256"],
                        "backend_identity": BACKEND_IDENTITY,
                        **continuity,
                        "engagement_reference": research.FLAGS["review-prediction"],
                    },
                }],
            })
        if accepting:
            first = ledgers[0]
            result = {
                "schema": "keplerops.label-studio-ml-prediction/v1",
                "backend_identity": BACKEND_IDENTITY,
                "task_id": task_ids[0],
                "request_id": first["teacher_request_id"],
                "ledger_key": first["ledger_key"],
                "ledger_sha256": first["ledger_sha256"],
                "model_version": str(metadata["mlflow_model_version"]),
                "model_digest": str(metadata["model_sha256"]),
                "engagement_reference": research.FLAGS["review-prediction"],
            }
            research.accept_operation(operation, result)
            research.finish_attempt("accepted")
        else:
            research.finish_attempt("staged")
        return {"results": rendered}
    except Exception as error:
        research.finish_attempt("failed", str(error))
        raise


@app.post("/webhook")
def webhook(_: dict[str, Any]) -> dict[str, str]:
    return {"status": "received"}
