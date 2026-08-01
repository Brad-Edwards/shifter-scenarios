import os

import httpx
from mcp.server.fastmcp import FastMCP


AGENT_URL = os.getenv("AGENT_URL", "http://orion-agent.orion-platform.svc:8080")
mcp = FastMCP("orion-assistant", host="0.0.0.0", port=8081)


@mcp.tool()
async def ask_orion(prompt: str) -> str:
    """Send a neutral prompt to the admitted Orion assistant model."""
    async with httpx.AsyncClient(timeout=95) as client:
        response = await client.post(
            f"{AGENT_URL.rstrip('/')}/v1/chat", json={"prompt": prompt}
        )
        response.raise_for_status()
        return response.json()["response"]


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
