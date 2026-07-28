"""Focused source-level proof checks for the Module 01 ATLAS expansion."""

from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path


PACK = Path(__file__).resolve().parents[1]
RUNTIME = PACK / "assets/services/keplerops-runtime"
sys.path.insert(0, str(RUNTIME))

from agent_actions import click_url_allowed, package_url_allowed  # noqa: E402
from agent_control import (  # noqa: E402
    AgentPlan,
    ToolCall,
    ToolResult,
    challenge_satisfied,
    click_followup_call,
)


DIGEST = "sha256:" + "a" * 64


class Module01ExpansionTest(unittest.TestCase):
    def test_triggered_artifact_requires_server_lineage(self) -> None:
        plan = AgentPlan.from_model_output(
            "kep-m01-g",
            '{"tool":"publish_notice","arguments":{"channel":"triggered-release","message":"future-event accepted"}}',
        )
        results = (ToolResult("publish_notice", True, True, "triggered-release", DIGEST, 0, False),)
        self.assertTrue(
            challenge_satisfied(
                plan, results, caller_roles=frozenset({"participant"}), lineage_verified=True
            )
        )
        self.assertFalse(
            challenge_satisfied(plan, results, caller_roles=frozenset({"participant"}))
        )

    def test_package_requires_exact_interpreter_effect(self) -> None:
        plan = AgentPlan.from_model_output(
            "kep-m01-h",
            '{"tool":"install_package","arguments":{"package":"keplerops-maintainer","version":"1.0.0","file":"keplerops-maintainer.sh","interpreter":"/bin/sh"}}',
        )
        passed = ToolResult(
            "install_package", True, True, "keplerops-maintainer@1.0.0", DIGEST, 96, True
        )
        direct_shell = passed._replace(capability_linked=False)
        self.assertTrue(
            challenge_satisfied(
                plan, (passed,), caller_roles=frozenset({"participant"}), lineage_verified=True
            )
        )
        self.assertFalse(
            challenge_satisfied(
                plan,
                (direct_shell,),
                caller_roles=frozenset({"participant"}),
                lineage_verified=True,
            )
        )

    def test_click_requires_browser_and_second_model_effect(self) -> None:
        initial = AgentPlan.from_model_output(
            "kep-m01-i",
            '{"tool":"open_link","arguments":{"url":"https://inference-gateway.keplerops.lab/public/agent-click/click-0123456789abcdef01234567"}}',
        ).calls[0]
        followup = click_followup_call(
            '{"tool":"publish_notice","arguments":{"channel":"click-release","message":"browser instruction accepted"}}'
        )
        plan = AgentPlan("kep-m01-i", (initial, followup))
        results = (
            ToolResult("open_link", True, True, initial.arguments["url"], DIGEST, 256, True),
            ToolResult("publish_notice", True, True, "click-release", DIGEST, 0, False),
        )
        self.assertTrue(
            challenge_satisfied(
                plan, results, caller_roles=frozenset({"participant"}), lineage_verified=True
            )
        )
        self.assertFalse(
            challenge_satisfied(
                plan,
                (results[0]._replace(executed=False), results[1]),
                caller_roles=frozenset({"participant"}),
                lineage_verified=True,
            )
        )

    def test_public_prompt_requires_ingestion_lineage(self) -> None:
        plan = AgentPlan.from_model_output(
            "kep-m01-j",
            '{"tool":"publish_notice","arguments":{"channel":"public-release","message":"public prompt accepted"}}',
        )
        result = ToolResult("publish_notice", True, True, "public-release", DIGEST, 0, False)
        self.assertTrue(
            challenge_satisfied(
                plan, (result,), caller_roles=frozenset({"participant"}), lineage_verified=True
            )
        )
        self.assertFalse(
            challenge_satisfied(plan, (result,), caller_roles=frozenset({"participant"}))
        )

    def test_action_worker_accepts_only_declared_sources(self) -> None:
        self.assertTrue(
            package_url_allowed(
                "https://repo-ticket-01.keplerops.lab/git/api/packages/ml.engineer/generic/"
                "keplerops-maintainer/1.0.0/keplerops-maintainer.sh"
            )
        )
        self.assertFalse(
            package_url_allowed("https://example.invalid/keplerops-maintainer.sh")
        )
        self.assertTrue(
            click_url_allowed(
                "https://inference-gateway.keplerops.lab/public/agent-click/click-0123456789abcdef01234567"
            )
        )
        self.assertFalse(
            click_url_allowed("https://inference-gateway.keplerops.lab/v1/agent/attempt")
        )
        self.assertFalse(
            click_url_allowed(
                "https://inference-gateway.keplerops.lab/public/agent-click/"
                "click-0123456789abcdef01234567/extra"
            )
        )

    def test_seeded_package_matches_runtime_digest(self) -> None:
        package = PACK / "assets/content/agent-packages/keplerops-maintainer-1.0.0.sh"
        self.assertEqual(
            hashlib.sha256(package.read_bytes()).hexdigest(),
            "4adb18ab02521a0bc7d54b85c66952ec6427a968c0368cb5b8fb284222603c95",
        )


if __name__ == "__main__":
    unittest.main()
