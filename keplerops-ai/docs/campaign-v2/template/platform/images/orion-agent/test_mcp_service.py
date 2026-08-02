from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

import mcp_service


class McpServiceTests(unittest.TestCase):
    def test_authorization_precedes_source_lookup(self) -> None:
        calls: list[str] = []

        async def authorize(*_args, **_kwargs):
            calls.append("opa")

        async def retrieve(*_args, **_kwargs):
            calls.append("qdrant")
            return []

        with (
            patch.object(mcp_service, "require_authorization", authorize),
            patch.object(mcp_service, "retrieve_sources", retrieve),
        ):
            asyncio.run(
                mcp_service.lookup_release_context(
                    "ORION-RELEASE-POLICY-2026",
                    "conversation-1",
                    "release.engineer",
                    "workflow-1",
                )
            )

        self.assertEqual(calls, ["opa", "qdrant"])

    def test_denied_source_lookup_does_not_reach_qdrant(self) -> None:
        denied = AsyncMock(side_effect=PermissionError("denied"))
        retrieve = AsyncMock()
        with (
            patch.object(mcp_service, "require_authorization", denied),
            patch.object(mcp_service, "retrieve_sources", retrieve),
        ):
            with self.assertRaises(PermissionError):
                asyncio.run(
                    mcp_service.lookup_release_context(
                        "ORION-RELEASE-POLICY-2026",
                        "conversation-1",
                        "finance.operator",
                        "workflow-1",
                    )
                )

        retrieve.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
