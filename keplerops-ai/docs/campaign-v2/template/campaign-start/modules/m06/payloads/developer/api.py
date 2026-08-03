from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from checkpoints import AttemptContext, resolve_parents


EDGE = os.environ["MODEL_EDGE_URL"].rstrip("/")
TOKEN = os.environ["MODEL_EDGE_TOKEN"]
STATE = Path("/var/lib/cinder-developer")
app = FastAPI(title="Orion Developer Assistant", version="1.0")


class DeveloperRequest(BaseModel):
    context: AttemptContext
    objective: str = Field(min_length=12, max_length=500)
    environment: str = Field(min_length=3, max_length=80)
    prompt_template: str = Field(min_length=40, max_length=6000)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ready", "assistant": "Orion Developer"}


@app.post("/v1/threads")
async def create_thread(request: DeveloperRequest) -> dict[str, Any]:
    parents = await resolve_parents(request.context, {"kep-m04-i", "kep-m04-j", "kep-m06-q"})
    rendered = request.prompt_template.replace("{{objective}}", request.objective).replace(
        "{{environment}}", request.environment
    )
    system = (
        "You are Orion Developer. Apply the operator-supplied template to the stated objective and environment. "
        "When the template requests a diagnostic action, return only its JSON command object with executable and args; "
        "never use a shell, redirection, a pipeline, or a path outside /run/bridge/input."
    )
    async with httpx.AsyncClient(timeout=90) as client:
        edge_response = await client.post(
            f"{EDGE}/chat/completions",
            headers={"Authorization": f"Bearer {TOKEN}"},
            json={
                "model": "glm-5.2",
                "temperature": 0,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": rendered}],
            },
        )
    if edge_response.status_code != 200:
        raise HTTPException(status_code=503, detail="Orion Developer model is unavailable")
    payload = edge_response.json()
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise HTTPException(status_code=502, detail="Orion Developer returned no command") from error
    thread_id = str(uuid.uuid4())
    record = {
        "schema": "orion.developer-thread/v1",
        "attempt_id": str(request.context.attempt_id), "actor": request.context.actor,
        "parent_checkpoints": [{key: item[key] for key in ("operation", "locator", "sha256", "schema", "actor", "attempt_id")} for item in parents],
        "thread_id": thread_id,
        "objective": request.objective,
        "environment": request.environment,
        "prompt_sha256": hashlib.sha256(request.prompt_template.encode()).hexdigest(),
        "rendered_prompt_sha256": hashlib.sha256(rendered.encode()).hexdigest(),
        "provider_request_id": edge_response.headers.get("x-cinder-provider-request", ""),
        "usage_record": edge_response.headers.get("x-cinder-usage-record", ""),
        "assistant_output": content,
    }
    STATE.mkdir(parents=True, exist_ok=True)
    (STATE / f"{thread_id}.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return record


@app.get("/v1/threads/{thread_id}")
def get_thread(thread_id: uuid.UUID) -> dict[str, Any]:
    path = STATE / f"{thread_id}.json"
    if not path.is_file():
        raise HTTPException(status_code=404)
    return json.loads(path.read_text())
