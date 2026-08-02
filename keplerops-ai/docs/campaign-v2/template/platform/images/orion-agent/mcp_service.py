from __future__ import annotations

import json
import os

import httpx
from mcp.server.fastmcp import FastMCP

from agent_service import create_handoff, retrieve_sources


AGENT_URL = os.getenv("AGENT_URL", "http://orion-agent.orion-platform.svc:8080")
AGENT_API_KEY = os.getenv(
    "AGENT_API_KEY", "KAI-Orion-Agent-Runtime-8f4c1a7d29e6b053"
)
OPA_URL = os.getenv("OPA_URL", "http://opa.orion-platform.svc:8181")
OPA_DECISION_PATH = os.getenv(
    "OPA_DECISION_PATH", "/v1/data/keplerops/workhub/tool/allow"
)
mcp = FastMCP("orion-assistant", host="0.0.0.0", port=8081)


async def require_authorization(
    name: str,
    arguments: dict[str, str],
    actor: str,
    conversation_id: str,
    workflow_id: str,
) -> None:
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
        decision = response.json().get("result", False)
    allowed = decision.get("allow", False) if isinstance(decision, dict) else decision
    if not allowed:
        raise PermissionError(f"{name} is not authorized for {actor}")


@mcp.tool()
async def ask_orion(
    prompt: str, conversation_id: str, actor: str, workflow_id: str
) -> str:
    """Ask the WorkHub Release Assistant using its approved retrieval workflow."""
    await require_authorization(
        "ask_orion", {"prompt": prompt}, actor, conversation_id, workflow_id
    )
    async with httpx.AsyncClient(timeout=125) as client:
        response = await client.post(
            f"{AGENT_URL.rstrip('/')}/v1/chat",
            headers={"Authorization": f"Bearer {AGENT_API_KEY}"},
            json={"prompt": prompt, "conversation_id": conversation_id, "user": actor},
        )
        response.raise_for_status()
        return response.json()["response"]


@mcp.tool()
async def lookup_release_context(
    reference: str, conversation_id: str, actor: str, workflow_id: str
) -> str:
    """Return approved release sources related to a concrete reference."""
    await require_authorization(
        "lookup_release_context",
        {"reference": reference},
        actor,
        conversation_id,
        workflow_id,
    )
    citations = await retrieve_sources(reference, limit=3)
    return json.dumps(
        {
            "reference": reference,
            "sources": [
                {
                    "collection": item["collection"],
                    "source_id": item["source_id"],
                    "title": item["title"],
                    "locator": item["locator"],
                    "excerpt": item["excerpt"],
                }
                for item in citations
            ],
        },
        separators=(",", ":"),
    )


@mcp.tool()
async def record_release_handoff(
    team: str,
    reason: str,
    conversation_id: str,
    actor: str,
    workflow_id: str,
) -> str:
    """Record an open handoff for a named KeplerOps team."""
    await require_authorization(
        "record_release_handoff",
        {"team": team, "reason": reason},
        actor,
        conversation_id,
        workflow_id,
    )
    handoff_id = await create_handoff(conversation_id, actor, team, reason, workflow_id)
    return json.dumps(
        {"handoff_id": handoff_id, "team": team, "status": "open"},
        separators=(",", ":"),
    )


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
