import os
from typing import TypedDict

import httpx
from fastapi import FastAPI, HTTPException
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field


LITELLM_URL = os.getenv("LITELLM_URL", "http://litellm.orion-platform.svc:4000")
LITELLM_MASTER_KEY = os.getenv("LITELLM_MASTER_KEY", "")
MODEL_NAME = os.getenv("ORION_ASSISTANT_MODEL", "orion-assistant")


class AgentState(TypedDict):
    prompt: str
    response: str


class PromptRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=16000)


async def infer(state: AgentState) -> AgentState:
    headers = {"Content-Type": "application/json"}
    if LITELLM_MASTER_KEY:
        headers["Authorization"] = f"Bearer {LITELLM_MASTER_KEY}"
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": state["prompt"]}],
        "temperature": 0,
    }
    async with httpx.AsyncClient(timeout=90) as client:
        response = await client.post(
            f"{LITELLM_URL.rstrip('/')}/v1/chat/completions",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        body = response.json()
    return {"prompt": state["prompt"], "response": body["choices"][0]["message"]["content"]}


builder = StateGraph(AgentState)
builder.add_node("infer", infer)
builder.add_edge(START, "infer")
builder.add_edge("infer", END)
graph = builder.compile()

app = FastAPI(title="Orion neutral LangGraph service", version="0.1.0")


@app.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "live"}


@app.get("/health/ready")
async def ready() -> dict[str, str]:
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            response = await client.get(f"{LITELLM_URL.rstrip('/')}/health/liveliness")
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="LiteLLM is unavailable") from exc
    return {"status": "ready", "model": MODEL_NAME}


@app.post("/v1/chat")
async def chat(request: PromptRequest) -> dict[str, str]:
    try:
        result = await graph.ainvoke({"prompt": request.prompt, "response": ""})
    except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
        raise HTTPException(status_code=503, detail="assistant upstream is unavailable") from exc
    return {"model": MODEL_NAME, "response": result["response"]}
