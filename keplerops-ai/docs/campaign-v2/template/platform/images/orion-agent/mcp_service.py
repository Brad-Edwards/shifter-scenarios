from __future__ import annotations

import json
import os

import httpx
from mcp.server.fastmcp import FastMCP

from agent_service import create_handoff, retrieve_sources
from campaign_m01 import (
    apply_review_followup as m01_apply_review_followup,
    approve_nonproduction_candidate as m01_approve_nonproduction_candidate,
    create_release_brief as m01_create_release_brief,
    lookup_release_calendar as m01_lookup_release_calendar,
    send_external_review_bundle as m01_send_external_review_bundle,
)


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


@mcp.tool()
async def create_release_brief(
    title: str, content: str, conversation_id: str, actor: str, workflow_id: str
) -> str:
    """Create an Orion draft in WorkHub from the assistant's generated brief."""
    await require_authorization(
        "create_release_brief", {"title": title, "content": content}, actor, conversation_id, workflow_id
    )
    return await m01_create_release_brief(actor, title, content)


@mcp.tool()
async def lookup_release_calendar(
    candidate: str, conversation_id: str, actor: str, workflow_id: str
) -> str:
    """Read one CalDAV event and create its normal WorkHub readiness case."""
    await require_authorization(
        "lookup_release_calendar", {"candidate": candidate}, actor, conversation_id, workflow_id
    )
    return await m01_lookup_release_calendar(actor, candidate)


@mcp.tool()
async def approve_nonproduction_candidate(
    candidate: str, validation_run_id: str, conversation_id: str, actor: str, workflow_id: str
) -> str:
    """Approve one validated non-production candidate through OPA and WorkHub."""
    await require_authorization(
        "approve_nonproduction_candidate",
        {"candidate": candidate, "validation_run_id": validation_run_id},
        actor,
        conversation_id,
        workflow_id,
    )
    return await m01_approve_nonproduction_candidate(actor, candidate, validation_run_id)


@mcp.tool()
async def apply_review_followup(
    issue_id: int, source_sha256: str, conversation_id: str, actor: str, workflow_id: str
) -> str:
    """Apply a WorkHub transition only from one exact indexed source."""
    await require_authorization(
        "apply_review_followup",
        {"issue_id": issue_id, "source_sha256": source_sha256},
        actor,
        conversation_id,
        workflow_id,
    )
    return await m01_apply_review_followup(actor, issue_id, source_sha256)


@mcp.tool()
async def send_external_review_bundle(
    source_sha256: str, conversation_id: str, actor: str, workflow_id: str
) -> str:
    """Mail the bounded release bundle to the actor's registered Cinder mailbox."""
    await require_authorization(
        "send_external_review_bundle",
        {"source_sha256": source_sha256},
        actor,
        conversation_id,
        workflow_id,
    )
    return await m01_send_external_review_bundle(actor, source_sha256)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
