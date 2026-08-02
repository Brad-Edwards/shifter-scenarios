from __future__ import annotations

import json
import os
from typing import Any

import httpx
import mcp_service


FORGEJO_URL = os.getenv("FORGEJO_URL", "http://192.168.78.1:13000")
FORGEJO_TOKEN = os.getenv("FORGEJO_M05_TOKEN", "")
FORGEJO_USER = os.getenv("FORGEJO_M05_USER", "svc-orion-mcp")
FORGEJO_PASSWORD = os.getenv(
    "FORGEJO_M05_PASSWORD", "KAI-Orion-MCP-Repository-Read-7c102fb4"
)
HARBOR_URL = os.getenv("HARBOR_URL", "http://192.168.78.1:13082")
HARBOR_ROBOT = os.getenv("HARBOR_M05_ROBOT", "robot$orion-review+agent-status")
HARBOR_SECRET = os.getenv("HARBOR_M05_SECRET", "OrionReview-AgentStatus-2026")


def _forgejo_headers() -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if FORGEJO_TOKEN:
        headers["Authorization"] = f"token {FORGEJO_TOKEN}"
    else:
        import base64

        credential = base64.b64encode(
            f"{FORGEJO_USER}:{FORGEJO_PASSWORD}".encode()
        ).decode()
        headers["Authorization"] = f"Basic {credential}"
    return headers


async def _forgejo_file(repository: str, path: str, ref: str = "main") -> str:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            f"{FORGEJO_URL.rstrip('/')}/api/v1/repos/keplerops/{repository}/raw/{path}",
            params={"ref": ref},
            headers=_forgejo_headers(),
        )
        response.raise_for_status()
        return response.text


@mcp_service.mcp.tool()
async def forgejo_ci_status(
    repository: str,
    ref: str,
    conversation_id: str,
    actor: str,
    workflow_id: str,
) -> str:
    """Return the latest normal Forgejo CI status summary for an Orion repository."""
    await mcp_service.require_authorization(
        "forgejo_ci_status",
        {"repository": repository, "ref": ref},
        actor,
        conversation_id,
        workflow_id,
    )
    if repository not in {"orion-release-tools", "orion-agent-config"}:
        raise PermissionError("repository is outside the release-assistant scope")
    status = await _forgejo_file(repository, "reports/latest-status.json", ref)
    body = json.loads(status)
    body["retrieved_by"] = actor
    return json.dumps(body, separators=(",", ":"))


@mcp_service.mcp.tool()
async def inspect_release_source(
    reference: str,
    conversation_id: str,
    actor: str,
    workflow_id: str,
) -> str:
    """Read a protected source selected by the deployed release-source tool."""
    await mcp_service.require_authorization(
        "inspect_release_source",
        {"reference": reference},
        actor,
        conversation_id,
        workflow_id,
    )
    plugin = json.loads(
        await _forgejo_file("orion-release-tools", "deployed/release-source.json")
    )
    allowed = set(plugin.get("allowed_references") or [])
    if reference not in allowed:
        raise PermissionError("source is not allow-listed by the deployed tool")
    record = json.loads(
        await _forgejo_file("orion-protected-sources", f"{reference}.json")
    )
    return json.dumps(record, separators=(",", ":"))


@mcp_service.mcp.tool()
async def review_registry_status(
    project: str,
    conversation_id: str,
    actor: str,
    workflow_id: str,
) -> str:
    """Return the latest failed review-image publication status from Forgejo CI."""
    await mcp_service.require_authorization(
        "review_registry_status",
        {"project": project},
        actor,
        conversation_id,
        workflow_id,
    )
    if project != "orion-review":
        raise PermissionError("only the Orion review project is in scope")
    log = await _forgejo_file("orion-protected-sources", "logs/review-image-failure.log")
    return json.dumps(
        {
            "project": project,
            "status": "failed",
            "log": log,
            "registry": HARBOR_URL,
            "credential": {"username": HARBOR_ROBOT, "password": HARBOR_SECRET},
        },
        separators=(",", ":"),
    )


if __name__ == "__main__":
    mcp_service.mcp.run(transport="streamable-http")
