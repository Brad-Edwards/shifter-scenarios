from __future__ import annotations

import json
import secrets
from typing import Any

from domain import SessionClaims
from keplerops_runtime.foundation.telemetry import _capture
from keplerops_runtime.modules.platform_proof import bearer_from_file, platform_request


AGENT_UNAVAILABLE = "platform agent unavailable"
SEED_AGENT_ID = "platform-agent-alpha"
HASH_TEXT_TOOL = "hash_text@1.0.0"


def _agent_headers(*, admin: bool) -> dict[str, str]:
    if admin:
        return {
            "X-Platform-Admin-Token": bearer_from_file(
                "platform_agent_admin_token_file", AGENT_UNAVAILABLE
            )
        }
    return {
        "X-Agent-Id": SEED_AGENT_ID,
        "X-Agent-Token": bearer_from_file(
            "platform_agent_seed_token_file", AGENT_UNAVAILABLE
        ),
    }


async def run_agentic_budget_probe(
    session: SessionClaims, object_id: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    version = f"10.0.{secrets.randbelow(1_000_000)}"
    config = await platform_request(
        "POST",
        service_key="platform-agent",
        base_url_field="platform_agent_url",
        unavailable=AGENT_UNAVAILABLE,
        path="/v1/configurations",
        headers=_agent_headers(admin=True),
        payload={
            "agent_id": SEED_AGENT_ID,
            "version": version,
            "max_steps": 3,
            "tool_timeout_ms": 1000,
            "allowed_tools": ["identity_metadata@1.0.0", HASH_TEXT_TOOL],
            "worker_profile": "disposable-linux-v1",
        },
        expected=(201,),
    )
    await platform_request(
        "POST",
        service_key="platform-agent",
        base_url_field="platform_agent_url",
        unavailable=AGENT_UNAVAILABLE,
        path=f"/v1/configurations/{version}/activate?agent_id={SEED_AGENT_ID}",
        headers=_agent_headers(admin=True),
    )
    plan = [
        {"tool": "identity_metadata@1.0.0", "arguments": {}},
        {"tool": HASH_TEXT_TOOL, "arguments": {"text": object_id}},
        {"tool": HASH_TEXT_TOOL, "arguments": {"text": version}},
    ]
    _capture(session, signal="tool_call", content=json.dumps(plan, separators=(",", ":")))
    run = await platform_request(
        "POST",
        service_key="platform-agent",
        base_url_field="platform_agent_url",
        unavailable=AGENT_UNAVAILABLE,
        path="/v1/agent/runs",
        headers=_agent_headers(admin=False),
        payload={"plan": plan},
        expected=(201,),
    )
    _capture(
        session,
        signal="tool_result",
        content=json.dumps(run, separators=(",", ":"), sort_keys=True),
    )
    return config, run
