from __future__ import annotations

import hashlib
import json
import math
import os
import re
import secrets
import time
import uuid
from typing import Any, TypedDict
from urllib.parse import quote

import httpx
import redis.asyncio as redis
from redis import exceptions as redis_exceptions
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field


LITELLM_URL = os.getenv("LITELLM_URL", "http://litellm.orion-platform.svc:4000")
LITELLM_MASTER_KEY = os.getenv("LITELLM_MASTER_KEY", "")
MODEL_NAME = os.getenv("ORION_ASSISTANT_MODEL", "orion-assistant")
QDRANT_URL = os.getenv("QDRANT_URL", "http://10.61.50.62:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "KeplerV2-Training-Qdrant-Read")
QDRANT_COLLECTIONS = tuple(
    name.strip()
    for name in os.getenv("QDRANT_COLLECTIONS", "orion_partner_intake").split(",")
    if name.strip()
)
REDIS_URL = os.getenv(
    "REDIS_URL", "redis://:KeplerV2-Training-Redis@10.61.50.11:6379/0"
)
OPA_URL = os.getenv("OPA_URL", "http://opa.orion-platform.svc:8181")
OPA_DECISION_PATH = os.getenv(
    "OPA_DECISION_PATH", "/v1/data/keplerops/workhub/tool/allow"
)
MCP_URL = os.getenv("MCP_URL", "http://orion-mcp.orion-platform.svc:8081/mcp")
AGENT_API_KEY = os.getenv(
    "AGENT_API_KEY", "KAI-Orion-Agent-Runtime-8f4c1a7d29e6b053"
)
STATE_TTL_SECONDS = int(os.getenv("STATE_TTL_SECONDS", "2592000"))
MAX_HISTORY_MESSAGES = int(os.getenv("MAX_HISTORY_MESSAGES", "20"))
MAX_RETRIEVAL_RESULTS = int(os.getenv("MAX_RETRIEVAL_RESULTS", "5"))
VECTOR_SIZE = 128

COLLECTION_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
redis_client = redis.from_url(REDIS_URL, decode_responses=True)


class Citation(TypedDict):
    number: int
    collection: str
    point_id: str
    source_id: str
    title: str
    locator: str
    score: float
    excerpt: str


class AgentState(TypedDict):
    prompt: str
    actor: str
    conversation_id: str
    workflow_id: str
    prior_messages: list[dict[str, str]]
    citations: list[Citation]
    response: str
    tool_events: list[dict[str, Any]]
    handoff: dict[str, str] | None
    handoff_id: str | None


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(system|user|assistant)$")
    content: str = Field(min_length=1, max_length=32000)


class PromptRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=16000)
    conversation_id: str | None = Field(default=None, max_length=128)
    user: str = Field(default="workhub-user", min_length=1, max_length=128)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatCompletionRequest(BaseModel):
    model: str | None = None
    messages: list[ChatMessage] = Field(min_length=1, max_length=64)
    user: str | None = Field(default=None, max_length=128)
    conversation_id: str | None = Field(default=None, max_length=128)
    metadata: dict[str, Any] = Field(default_factory=dict)
    stream: bool = False


MCP_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_release_context",
            "description": (
                "Look up an authoritative WorkHub release source by a concrete "
                "reference when the retrieved excerpts are insufficient."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reference": {"type": "string", "minLength": 1},
                },
                "required": ["reference"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "record_release_handoff",
            "description": (
                "Record a release-engineering handoff when the request needs a "
                "named team to continue the work."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "team": {"type": "string", "minLength": 1},
                    "reason": {"type": "string", "minLength": 1},
                },
                "required": ["team", "reason"],
                "additionalProperties": False,
            },
        },
    },
]
MCP_TOOL_NAMES = {item["function"]["name"] for item in MCP_TOOL_DEFINITIONS}


def feature_hash(text: str) -> list[float]:
    vector = [0.0] * VECTOR_SIZE
    for token in re.findall(r"[a-z0-9_]+", text.lower()):
        digest = hashlib.sha256(token.encode()).digest()
        bucket = int.from_bytes(digest[:4], "big") % VECTOR_SIZE
        vector[bucket] += 1.0 if digest[4] & 1 else -1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def qdrant_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if QDRANT_API_KEY:
        headers["api-key"] = QDRANT_API_KEY
    return headers


def source_text(payload: dict[str, Any]) -> str:
    for field in ("text", "content", "body", "description"):
        value = payload.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def qdrant_points(body: dict[str, Any]) -> list[dict[str, Any]]:
    result = body.get("result", [])
    if isinstance(result, dict):
        result = result.get("points", [])
    return result if isinstance(result, list) else []


async def retrieve_sources(
    query: str, limit: int = MAX_RETRIEVAL_RESULTS
) -> list[Citation]:
    if not QDRANT_COLLECTIONS:
        raise RuntimeError("no approved Qdrant collections are configured")
    vector = feature_hash(query)
    candidates: list[tuple[float, str, dict[str, Any]]] = []
    async with httpx.AsyncClient(timeout=20) as client:
        for collection in QDRANT_COLLECTIONS:
            if not COLLECTION_RE.fullmatch(collection):
                raise RuntimeError(f"invalid Qdrant collection name: {collection}")
            response = await client.post(
                f"{QDRANT_URL.rstrip('/')}/collections/{quote(collection)}/points/query",
                headers=qdrant_headers(),
                json={"query": vector, "limit": limit, "with_payload": True},
            )
            if response.status_code == 404:
                continue
            response.raise_for_status()
            for point in qdrant_points(response.json()):
                payload = point.get("payload") or {}
                if source_text(payload):
                    candidates.append((float(point.get("score", 0)), collection, point))

    citations: list[Citation] = []
    seen: set[tuple[str, str]] = set()
    for score, collection, point in sorted(
        candidates, reverse=True, key=lambda item: item[0]
    ):
        point_id = str(point.get("id", "unknown"))
        if (collection, point_id) in seen:
            continue
        seen.add((collection, point_id))
        payload = point.get("payload") or {}
        text = source_text(payload)
        source_id = str(payload.get("source_id") or payload.get("sha256") or point_id)
        title = str(payload.get("title") or payload.get("filename") or source_id)
        locator = str(
            payload.get("url")
            or payload.get("filename")
            or payload.get("object_key")
            or f"{collection}:{point_id}"
        )
        citations.append(
            {
                "number": len(citations) + 1,
                "collection": collection,
                "point_id": point_id,
                "source_id": source_id,
                "title": title,
                "locator": locator,
                "score": round(score, 6),
                "excerpt": text[:2000],
            }
        )
        if len(citations) >= limit:
            break
    return citations


def conversation_key(conversation_id: str) -> str:
    return f"workhub:conversation:{conversation_id}"


async def load_conversation(conversation_id: str) -> list[dict[str, str]]:
    raw = await redis_client.get(conversation_key(conversation_id))
    if not raw:
        return []
    value = json.loads(raw)
    messages = value.get("messages", [])
    return [
        {"role": str(item["role"]), "content": str(item["content"])}
        for item in messages[-MAX_HISTORY_MESSAGES:]
        if item.get("role") in {"user", "assistant"} and item.get("content")
    ]


async def create_handoff(
    conversation_id: str, actor: str, team: str, reason: str, workflow_id: str
) -> str:
    handoff_id = f"handoff-{uuid.uuid4().hex[:16]}"
    record = {
        "handoff_id": handoff_id,
        "conversation_id": conversation_id,
        "workflow_id": workflow_id,
        "actor": actor,
        "team": team,
        "reason": reason,
        "created_at": int(time.time()),
        "status": "open",
    }
    await redis_client.set(
        f"workhub:handoff:{handoff_id}",
        json.dumps(record, separators=(",", ":")),
        ex=STATE_TTL_SECONDS,
    )
    return handoff_id


async def save_conversation(state: AgentState) -> None:
    messages = [
        *state["prior_messages"],
        {"role": "user", "content": state["prompt"]},
        {"role": "assistant", "content": state["response"]},
    ][-MAX_HISTORY_MESSAGES:]
    record = {
        "conversation_id": state["conversation_id"],
        "workflow_id": state["workflow_id"],
        "actor": state["actor"],
        "messages": messages,
        "citations": state["citations"],
        "tool_events": state["tool_events"],
        "handoff_id": state["handoff_id"],
        "updated_at": int(time.time()),
    }
    await redis_client.set(
        conversation_key(state["conversation_id"]),
        json.dumps(record, separators=(",", ":")),
        ex=STATE_TTL_SECONDS,
    )


async def retrieve(state: AgentState) -> AgentState:
    state["prior_messages"] = await load_conversation(state["conversation_id"])
    state["citations"] = await retrieve_sources(state["prompt"])
    return state


def source_prompt(citations: list[Citation]) -> str:
    if not citations:
        return "No approved WorkHub source matched this request."
    return "\n\n".join(
        f"[{item['number']}] {item['title']}\n"
        f"Collection: {item['collection']}\n"
        f"Source ID: {item['source_id']}\n"
        f"Locator: {item['locator']}\n"
        f"Excerpt: {item['excerpt']}"
        for item in citations
    )


def system_message(citations: list[Citation]) -> str:
    return (
        "You are the KeplerOps AI Systems WorkHub Release Assistant. Answer release, "
        "research, and support questions from the approved sources below. Cite factual "
        "claims with the supplied bracketed source numbers. If the sources do not "
        "support an answer, say what is missing. Never claim that a release is approved "
        "or perform a protected action. Use a read tool only when a concrete source "
        "reference needs more context, and create a handoff when a named team must "
        "continue the work.\n\nApproved sources:\n" + source_prompt(citations)
    )


async def authorize_tool(
    actor: str,
    conversation_id: str,
    workflow_id: str,
    name: str,
    arguments: dict[str, Any],
) -> tuple[bool, str]:
    payload = {
        "input": {
            "schema": "keplerops.workhub.tool/v1",
            "actor": actor,
            "conversation_id": conversation_id,
            "workflow_id": workflow_id,
            "tool": {"name": name, "arguments": arguments},
        }
    }
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"{OPA_URL.rstrip('/')}/{OPA_DECISION_PATH.lstrip('/')}", json=payload
        )
        response.raise_for_status()
        result = response.json().get("result", False)
    if isinstance(result, dict):
        return bool(result.get("allow", False)), str(
            result.get("reason", "policy decision")
        )
    return bool(result), "policy decision"


def parse_mcp_response(response: httpx.Response) -> dict[str, Any]:
    content_type = response.headers.get("content-type", "")
    if "text/event-stream" not in content_type:
        return response.json()
    events = []
    for line in response.text.splitlines():
        if line.startswith("data:"):
            events.append(json.loads(line[5:].strip()))
    if not events:
        raise RuntimeError("MCP returned an empty event stream")
    return events[-1]


async def call_mcp_tool(name: str, arguments: dict[str, Any]) -> Any:
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        initialize = await client.post(
            MCP_URL,
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "workhub-release-assistant",
                        "version": "1.0",
                    },
                },
            },
        )
        initialize.raise_for_status()
        parse_mcp_response(initialize)
        session_id = initialize.headers.get("mcp-session-id")
        if session_id:
            headers["Mcp-Session-Id"] = session_id
        initialized = await client.post(
            MCP_URL,
            headers=headers,
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        )
        initialized.raise_for_status()
        called = await client.post(
            MCP_URL,
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            },
        )
        called.raise_for_status()
        body = parse_mcp_response(called)
    if body.get("error"):
        raise RuntimeError(str(body["error"]))
    return body.get("result")


async def model_completion(messages: list[dict[str, Any]]) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if LITELLM_MASTER_KEY:
        headers["Authorization"] = f"Bearer {LITELLM_MASTER_KEY}"
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "tools": MCP_TOOL_DEFINITIONS,
        "tool_choice": "auto",
        "temperature": 0,
    }
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            f"{LITELLM_URL.rstrip('/')}/v1/chat/completions",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        body = response.json()
    return body["choices"][0]["message"]


async def infer(state: AgentState) -> AgentState:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_message(state["citations"])},
        *state["prior_messages"],
        {"role": "user", "content": state["prompt"]},
    ]
    tool_events: list[dict[str, Any]] = []
    for _ in range(3):
        message = await model_completion(messages)
        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            state["response"] = str(message.get("content") or "").strip()
            break
        messages.append(message)
        for tool_call in tool_calls:
            function = tool_call.get("function") or {}
            name = str(function.get("name") or "")
            try:
                arguments = json.loads(function.get("arguments") or "{}")
            except json.JSONDecodeError:
                arguments = {}
            if not isinstance(arguments, dict):
                arguments = {}
            if name not in MCP_TOOL_NAMES:
                allowed, reason, result = False, "tool is not allow-listed", None
            else:
                allowed, reason = await authorize_tool(
                    state["actor"],
                    state["conversation_id"],
                    state["workflow_id"],
                    name,
                    arguments,
                )
                if allowed:
                    trusted_arguments = dict(arguments)
                    trusted_arguments.update(
                        {
                            "conversation_id": state["conversation_id"],
                            "actor": state["actor"],
                            "workflow_id": state["workflow_id"],
                        }
                    )
                    result = await call_mcp_tool(name, trusted_arguments)
                else:
                    result = None
            tool_events.append(
                {
                    "name": name,
                    "allowed": allowed,
                    "reason": reason,
                    "result": result,
                }
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": str(tool_call.get("id") or uuid.uuid4().hex),
                    "content": json.dumps(
                        result if allowed else {"error": "denied", "reason": reason}
                    ),
                }
            )
    if not state["response"]:
        raise RuntimeError("assistant did not return a final response")
    if state["citations"]:
        sources = "\n".join(
            f"[{item['number']}] {item['title']} ({item['locator']})"
            for item in state["citations"]
        )
        state["response"] = f"{state['response']}\n\nSources\n{sources}"
    state["tool_events"] = tool_events
    return state


async def persist(state: AgentState) -> AgentState:
    handoff = state.get("handoff")
    if handoff:
        state["handoff_id"] = await create_handoff(
            state["conversation_id"],
            state["actor"],
            handoff["team"],
            handoff["reason"],
            state["workflow_id"],
        )
    for event in state["tool_events"]:
        if event["name"] == "record_release_handoff" and event["allowed"]:
            content = (
                event.get("result", {}).get("content", [])
                if event.get("result")
                else []
            )
            for item in content:
                try:
                    parsed = json.loads(item.get("text", "{}"))
                except (AttributeError, json.JSONDecodeError):
                    continue
                if parsed.get("handoff_id"):
                    state["handoff_id"] = str(parsed["handoff_id"])
    await save_conversation(state)
    return state


builder = StateGraph(AgentState)
builder.add_node("retrieve", retrieve)
builder.add_node("infer", infer)
builder.add_node("persist", persist)
builder.add_edge(START, "retrieve")
builder.add_edge("retrieve", "infer")
builder.add_edge("infer", "persist")
builder.add_edge("persist", END)
graph = builder.compile()

app = FastAPI(title="Orion WorkHub Release Assistant", version="1.0.0")


def authenticate_service(authorization: str | None) -> None:
    scheme, _, credential = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not secrets.compare_digest(
        credential, AGENT_API_KEY
    ):
        raise HTTPException(status_code=401, detail="service authentication required")


@app.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "live"}


@app.get("/health/ready")
async def ready() -> dict[str, Any]:
    try:
        await redis_client.ping()
        async with httpx.AsyncClient(timeout=5) as client:
            litellm = await client.get(f"{LITELLM_URL.rstrip('/')}/health/liveliness")
            litellm.raise_for_status()
            qdrant = await client.get(f"{QDRANT_URL.rstrip('/')}/readyz")
            qdrant.raise_for_status()
    except (httpx.HTTPError, redis_exceptions.RedisError, ValueError) as exc:
        raise HTTPException(
            status_code=503, detail="assistant dependency is unavailable"
        ) from exc
    return {
        "status": "ready",
        "model": MODEL_NAME,
        "collections": list(QDRANT_COLLECTIONS),
        "durable_state": "redis",
    }


def requested_handoff(metadata: dict[str, Any]) -> dict[str, str] | None:
    handoff = metadata.get("handoff")
    if not isinstance(handoff, dict):
        return None
    team = str(handoff.get("team") or "").strip()
    reason = str(handoff.get("reason") or "").strip()
    if not team or not reason or len(team) > 128 or len(reason) > 1000:
        raise HTTPException(
            status_code=422, detail="handoff requires a valid team and reason"
        )
    return {"team": team, "reason": reason}


async def run_agent(
    prompt: str,
    actor: str,
    conversation_id: str | None,
    metadata: dict[str, Any],
) -> AgentState:
    state: AgentState = {
        "prompt": prompt,
        "actor": actor,
        "conversation_id": conversation_id or f"conversation-{uuid.uuid4().hex}",
        "workflow_id": f"workflow-{uuid.uuid4().hex}",
        "prior_messages": [],
        "citations": [],
        "response": "",
        "tool_events": [],
        "handoff": requested_handoff(metadata),
        "handoff_id": None,
    }
    try:
        return await graph.ainvoke(state)
    except (
        httpx.HTTPError,
        redis_exceptions.RedisError,
        json.JSONDecodeError,
        KeyError,
        IndexError,
        TypeError,
        ValueError,
        RuntimeError,
    ) as exc:
        raise HTTPException(
            status_code=503, detail="assistant workflow is unavailable"
        ) from exc


@app.post("/v1/chat")
async def chat(
    request: PromptRequest, authorization: str | None = Header(default=None)
) -> dict[str, Any]:
    authenticate_service(authorization)
    result = await run_agent(
        request.prompt, request.user, request.conversation_id, request.metadata
    )
    return {
        "model": MODEL_NAME,
        "response": result["response"],
        "conversation_id": result["conversation_id"],
        "workflow_id": result["workflow_id"],
        "citations": result["citations"],
        "handoff_id": result["handoff_id"],
        "tool_events": [
            {"name": event["name"], "allowed": event["allowed"]}
            for event in result["tool_events"]
        ],
    }


@app.post("/v1/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest, authorization: str | None = Header(default=None)
) -> Any:
    authenticate_service(authorization)
    prompt = next(
        (
            message.content
            for message in reversed(request.messages)
            if message.role == "user"
        ),
        None,
    )
    if prompt is None:
        raise HTTPException(status_code=422, detail="a user message is required")
    result = await run_agent(
        prompt,
        request.user or "workhub-user",
        request.conversation_id
        or str(request.metadata.get("conversation_id") or "")
        or None,
        request.metadata,
    )
    completion_id = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())
    body = {
        "id": completion_id,
        "object": "chat.completion",
        "created": created,
        "model": MODEL_NAME,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": result["response"]},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "conversation_id": result["conversation_id"],
        "workflow_id": result["workflow_id"],
        "citations": result["citations"],
        "handoff_id": result["handoff_id"],
    }
    if not request.stream:
        return body

    async def stream_response():
        chunks = [
            {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": MODEL_NAME,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"role": "assistant", "content": result["response"]},
                        "finish_reason": None,
                    }
                ],
            },
            {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": MODEL_NAME,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            },
        ]
        for chunk in chunks:
            yield f"data: {json.dumps(chunk, separators=(',', ':'))}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(stream_response(), media_type="text/event-stream")
