from __future__ import annotations

import asyncio
import math
import unittest
from unittest.mock import AsyncMock, patch

import agent_service
from fastapi import HTTPException


def state() -> agent_service.AgentState:
    return {
        "prompt": "Summarize release policy ORION-RELEASE-POLICY-2026.",
        "actor": "release.engineer",
        "conversation_id": "conversation-1",
        "workflow_id": "workflow-1",
        "prior_messages": [],
        "citations": [
            {
                "number": 1,
                "collection": "orion_partner_intake",
                "point_id": "42",
                "source_id": "ORION-RELEASE-POLICY-2026",
                "title": "Orion Release Policy",
                "locator": "workhub/orion-release-policy.md",
                "score": 0.9,
                "excerpt": "A candidate needs evaluation and release approval.",
            }
        ],
        "response": "",
        "tool_events": [],
        "handoff": None,
        "handoff_id": None,
    }


class AgentServiceTests(unittest.TestCase):
    def test_service_authentication_rejects_an_invalid_credential(self) -> None:
        with self.assertRaises(HTTPException):
            agent_service.authenticate_service("Bearer invalid")
        agent_service.authenticate_service(f"Bearer {agent_service.AGENT_API_KEY}")

    def test_feature_hash_is_normalized_and_deterministic(self) -> None:
        first = agent_service.feature_hash("Orion release approval")
        second = agent_service.feature_hash("Orion release approval")
        self.assertEqual(first, second)
        self.assertEqual(len(first), agent_service.VECTOR_SIZE)
        self.assertAlmostEqual(math.sqrt(sum(value * value for value in first)), 1.0)

    def test_source_prompt_names_collection_and_source(self) -> None:
        prompt = agent_service.system_message(state()["citations"])
        self.assertIn("orion_partner_intake", prompt)
        self.assertIn("ORION-RELEASE-POLICY-2026", prompt)
        self.assertIn("[1]", prompt)

    def test_qdrant_query_points_response_is_unwrapped(self) -> None:
        points = agent_service.qdrant_points(
            {"result": {"points": [{"id": 42, "payload": {"text": "release"}}]}}
        )
        self.assertEqual(points[0]["id"], 42)

    def test_opa_precedes_allowed_mcp_call(self) -> None:
        calls: list[str] = []

        async def authorize(*_args, **_kwargs):
            calls.append("opa")
            return True, "allowed"

        async def invoke(*_args, **_kwargs):
            calls.append("mcp")
            return {"content": [{"type": "text", "text": "source context"}]}

        completions = AsyncMock(
            side_effect=[
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call-1",
                            "function": {
                                "name": "lookup_release_context",
                                "arguments": '{"reference":"ORION-RELEASE-POLICY-2026"}',
                            },
                        }
                    ],
                },
                {"role": "assistant", "content": "Approval is required [1]."},
            ]
        )
        with (
            patch.object(agent_service, "model_completion", completions),
            patch.object(agent_service, "authorize_tool", authorize),
            patch.object(agent_service, "call_mcp_tool", invoke),
        ):
            result = asyncio.run(agent_service.infer(state()))

        self.assertEqual(calls, ["opa", "mcp"])
        self.assertTrue(result["tool_events"][0]["allowed"])
        self.assertIn("Sources", result["response"])

    def test_denied_tool_never_reaches_mcp(self) -> None:
        completions = AsyncMock(
            side_effect=[
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call-1",
                            "function": {
                                "name": "record_release_handoff",
                                "arguments": '{"team":"finance","reason":"approve transfer"}',
                            },
                        }
                    ],
                },
                {"role": "assistant", "content": "That action is not permitted."},
            ]
        )
        with (
            patch.object(agent_service, "model_completion", completions),
            patch.object(
                agent_service,
                "authorize_tool",
                AsyncMock(return_value=(False, "actor is not permitted")),
            ),
            patch.object(agent_service, "call_mcp_tool", AsyncMock()) as invoke,
        ):
            result = asyncio.run(agent_service.infer(state()))

        invoke.assert_not_awaited()
        self.assertFalse(result["tool_events"][0]["allowed"])

    def test_librechat_stream_uses_openai_chunks(self) -> None:
        expected = state()
        expected["response"] = (
            "Release Engineering owns the review.\n\nSources\n[1] Policy"
        )
        request = agent_service.ChatCompletionRequest(
            model="orion-assistant",
            messages=[{"role": "user", "content": "Who owns the review?"}],
            user="release.engineer",
            conversation_id="conversation-1",
            stream=True,
        )

        async def collect() -> list[str]:
            with patch.object(
                agent_service, "run_agent", AsyncMock(return_value=expected)
            ):
                response = await agent_service.chat_completions(
                    request, f"Bearer {agent_service.AGENT_API_KEY}"
                )
            return [chunk async for chunk in response.body_iterator]

        chunks = asyncio.run(collect())
        self.assertTrue(any("chat.completion.chunk" in chunk for chunk in chunks))
        self.assertEqual(chunks[-1], "data: [DONE]\n\n")


if __name__ == "__main__":
    unittest.main()
