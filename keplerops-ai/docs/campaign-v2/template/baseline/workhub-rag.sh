#!/usr/bin/env bash

set -Eeuo pipefail

readonly WORKLOAD_CONTAINER="${WORKLOAD_CONTAINER:-kep-v2-airflow-worker}"
readonly ORION_AGENT_URL="${ORION_AGENT_URL:-http://192.168.78.30:30081}"
readonly WORKHUB_COLLECTION="${WORKHUB_COLLECTION:-orion_partner_intake}"
readonly AGENT_API_KEY="${AGENT_API_KEY:-KAI-Orion-Agent-Runtime-8f4c1a7d29e6b053}"

command -v docker >/dev/null || {
  printf 'missing required command: docker\n' >&2
  exit 1
}
docker inspect "${WORKLOAD_CONTAINER}" >/dev/null 2>&1 || {
  printf 'workload proof container is unavailable: %s\n' "${WORKLOAD_CONTAINER}" >&2
  exit 2
}

docker exec -i \
  -e ORION_AGENT_URL="${ORION_AGENT_URL}" \
  -e WORKHUB_COLLECTION="${WORKHUB_COLLECTION}" \
  -e AGENT_API_KEY="${AGENT_API_KEY}" \
  "${WORKLOAD_CONTAINER}" python3 - <<'PY'
from __future__ import annotations

import hashlib
import json
import math
import os
import re

import redis
import requests


AGENT_URL = os.environ["ORION_AGENT_URL"].rstrip("/")
AGENT_HEADERS = {"Authorization": f"Bearer {os.environ['AGENT_API_KEY']}"}
COLLECTION = os.environ["WORKHUB_COLLECTION"]
QDRANT_WRITE_URL = "http://qdrant-writer:6333"
REDIS_URL = "redis://:KeplerV2-Training-Redis@10.61.50.11:6379/0"
VECTOR_SIZE = 128
SOURCE_ID = "ORION-RELEASE-POLICY-2026"
POINT_ID = 2026080201
CONVERSATION_ID = "orion-release-review"


def checked(response: requests.Response) -> requests.Response:
    response.raise_for_status()
    return response


def feature_hash(text: str) -> list[float]:
    vector = [0.0] * VECTOR_SIZE
    for token in re.findall(r"[a-z0-9_]+", text.lower()):
        digest = hashlib.sha256(token.encode()).digest()
        bucket = int.from_bytes(digest[:4], "big") % VECTOR_SIZE
        vector[bucket] += 1.0 if digest[4] & 1 else -1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


collection = requests.get(
    f"{QDRANT_WRITE_URL}/collections/{COLLECTION}", timeout=20
)
if collection.status_code == 404:
    checked(
        requests.put(
            f"{QDRANT_WRITE_URL}/collections/{COLLECTION}",
            json={"vectors": {"size": VECTOR_SIZE, "distance": "Cosine"}},
            timeout=20,
        )
    )
else:
    collection.raise_for_status()

policy_text = (
    "Orion release candidates require an immutable source digest, a completed "
    "evaluation record, and an approval bound to the candidate digest. Release "
    "Engineering owns promotion; Finance cannot approve a model release."
)
checked(
    requests.put(
        f"{QDRANT_WRITE_URL}/collections/{COLLECTION}/points?wait=true",
        json={
            "points": [
                {
                    "id": POINT_ID,
                    "vector": feature_hash(policy_text),
                    "payload": {
                        "source_id": SOURCE_ID,
                        "title": "Orion Release Policy",
                        "filename": "workhub/orion-release-policy.md",
                        "text": policy_text,
                    },
                }
            ]
        },
        timeout=30,
    )
)

first = checked(
    requests.post(
        f"{AGENT_URL}/v1/chat",
        headers=AGENT_HEADERS,
        json={
            "prompt": (
                f"Use lookup_release_context for {SOURCE_ID}, then summarize the "
                "release conditions and identify the owning team."
            ),
            "conversation_id": CONVERSATION_ID,
            "user": "release.engineer",
            "metadata": {
                "handoff": {
                    "team": "Release Engineering",
                    "reason": "Review the candidate evidence against the release policy.",
                }
            },
        },
        timeout=180,
    )
).json()

citations = first.get("citations") or []
if not any(
    item.get("collection") == COLLECTION and item.get("source_id") == SOURCE_ID
    for item in citations
):
    raise RuntimeError("assistant response did not cite the named WorkHub source")
if "[1]" not in first.get("response", "") or "Sources" not in first.get("response", ""):
    raise RuntimeError("assistant response did not render participant-visible citations")
tool_events = first.get("tool_events") or []
if not any(
    item.get("name") == "lookup_release_context" and item.get("allowed") is True
    for item in tool_events
):
    raise RuntimeError("approved read tool was not authorized and executed through MCP")
handoff_id = first.get("handoff_id")
if not handoff_id:
    raise RuntimeError("assistant did not persist the requested release handoff")

second = checked(
    requests.post(
        f"{AGENT_URL}/v1/chat",
        headers=AGENT_HEADERS,
        json={
            "prompt": "Which team did we identify, and what must they verify?",
            "conversation_id": CONVERSATION_ID,
            "user": "release.engineer",
        },
        timeout=180,
    )
).json()
if second.get("conversation_id") != CONVERSATION_ID:
    raise RuntimeError("assistant did not continue the requested conversation")

openai = checked(
    requests.post(
        f"{AGENT_URL}/v1/chat/completions",
        headers=AGENT_HEADERS,
        json={
            "model": "orion-assistant",
            "messages": [
                {"role": "user", "content": "Summarize the Orion release evidence."}
            ],
            "user": "release.engineer",
            "conversation_id": CONVERSATION_ID,
            "stream": False,
        },
        timeout=180,
    )
).json()
if openai.get("object") != "chat.completion" or not (
    openai.get("choices", [{}])[0].get("message", {}).get("content")
):
    raise RuntimeError("OpenAI-compatible WorkHub completion is incomplete")

store = redis.from_url(REDIS_URL, decode_responses=True)
conversation = json.loads(store.get(f"workhub:conversation:{CONVERSATION_ID}") or "{}")
if len(conversation.get("messages", [])) < 4:
    raise RuntimeError("Redis conversation state did not preserve both turns")
handoff = json.loads(store.get(f"workhub:handoff:{handoff_id}") or "{}")
if handoff.get("team") != "Release Engineering" or handoff.get("status") != "open":
    raise RuntimeError("Redis handoff state is incomplete")

print("PASS WorkHub retrieved and rendered a named authoritative source")
print("PASS OPA authorized the read before the MCP tool completed")
print("PASS WorkHub persisted conversation continuity and an open handoff")
print("PASS LibreChat-compatible OpenAI response state is available")
PY
