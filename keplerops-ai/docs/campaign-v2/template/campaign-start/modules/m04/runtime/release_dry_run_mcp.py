from __future__ import annotations

import hashlib
import json
import os
import urllib.request

from mcp.server.fastmcp import FastMCP


OPA_URL = os.getenv("M04_RELEASE_POLICY_URL", "http://m04-release-policy:8181").rstrip("/")
mcp = FastMCP("orion-release-dry-run", host="0.0.0.0", port=8081)


@mcp.tool()
def deployment_plan_dry_run(
    candidate: str,
    environment: str,
    requested_action: str,
    event_id: str,
    actor: str,
    workflow_id: str,
) -> dict[str, object]:
    policy_input = {
        "schema": "keplerops.orion.release-dry-run/v1",
        "candidate": candidate,
        "environment": environment,
        "requested_action": requested_action,
        "event_id": event_id,
        "actor": actor,
        "workflow_id": workflow_id,
    }
    request = urllib.request.Request(
        f"{OPA_URL}/v1/data/keplerops/m04/release_dry_run/decision",
        data=json.dumps({"input": policy_input}, separators=(",", ":")).encode(),
        method="POST", headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        decision = json.load(response).get("result")
    if not isinstance(decision, dict) or decision.get("allow") is not True:
        raise ValueError("release dry-run policy denied the fixed non-production plan")
    plan = {
        "candidate": candidate,
        "environment": environment,
        "steps": [
            "resolve signed candidate metadata",
            "render non-production deployment manifest",
            "compare release-risk readiness constraints",
        ],
        "apply": False,
    }
    return {
        "schema": "keplerops.orion.deployment-plan-dry-run-receipt/v1",
        "tool": "deployment_plan_dry_run",
        "event_id": event_id,
        "workflow_id": workflow_id,
        "policy_decision": decision,
        "plan": plan,
        "plan_sha256": hashlib.sha256(
            json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "production_mutation": False,
        "owner": "release-dry-run-mcp",
    }


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
