"""Contract checks for the focused Module 02 package rehearsal."""

from __future__ import annotations

import sys
import unittest
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from live_rehearsal import CheckResult  # noqa: E402
from module_02_package_rehearsal import (  # noqa: E402
    CHALLENGES,
    Module02PackageLifecycle,
    Module02PackageRunner,
    participant_program,
    replay_program,
)


@dataclass
class FakeLifecycle:
    scoped_resets: int = 0

    def reset_context_state(self) -> None:
        self.scoped_resets += 1


class FakeSession:
    def __init__(self) -> None:
        self.calls = 0

    def execute(self, _program, *, expected_markers, return_clipboard):
        self.calls += 1
        if return_clipboard or expected_markers != (3 if self.calls == 1 else 1):
            raise AssertionError("unexpected session contract")
        if self.calls == 1:
            return (
                (
                    CheckResult("test-m02-package-controls", "PASS", 0, 4),
                    CheckResult("test-m02-package-paths", "PASS", 0, 2),
                    CheckResult("test-m02-package-awards", "PASS", 0, 2),
                ),
                "",
            )
        return ((CheckResult("test-m02-package-replay", "PASS", 0, 2),), "")


class Module02PackageRehearsalTests(unittest.TestCase):
    def test_program_proves_real_package_surfaces_and_negatives(self) -> None:
        source = participant_program()
        for challenge_id in CHALLENGES:
            self.assertIn(challenge_id, source)
        for marker in (
            "publish-keplerops-runtime",
            "/v1/evasion/runtime-dependencies",
            "/v1/evasion/sandbox-evaluations",
            '"sha256:" + "0" * 64',
            '"rtp-" + "0" * 24',
            '"challenge_id": "kep-m02-a"',
            "expected=422",
            "expected=404",
            '"profile": "analysis", "decision": "deny", "effect": False',
            '"profile": "worker", "decision": "allow", "effect": True',
        ):
            self.assertIn(marker, source)

    def test_replay_republishes_and_proves_both_receipts(self) -> None:
        source = replay_program()
        self.assertIn("publish-keplerops-runtime", source)
        self.assertIn("flag-masquerading-ai-runtime", source)
        self.assertIn("flag-sandbox-aware-payload", source)
        self.assertIn("test-m02-package-replay", source)
        self.assertNotIn("expected=422", source)
        self.assertNotIn('"rtp-" + "0" * 24', source)

    def test_scoped_reset_is_the_complete_package_dependency_closure(self) -> None:
        expected = {
            "dataset-store-01",
            "inference-gateway",
            "repo-ticket-01",
            "telemetry-proof-01",
        }
        self.assertEqual(set(Module02PackageLifecycle.scoped_assets), expected)
        self.assertEqual(set(Module02PackageLifecycle.quiesce_assets), expected)
        self.assertEqual(set(Module02PackageLifecycle.reset_assets), expected)
        self.assertEqual(set(Module02PackageLifecycle.verify_assets), expected)

    def test_runner_uses_one_scoped_reset_and_one_replay(self) -> None:
        lifecycle = FakeLifecycle()
        session = FakeSession()
        result = Module02PackageRunner(lifecycle, session).run()
        self.assertTrue(result.passed)
        self.assertEqual(lifecycle.scoped_resets, 1)
        self.assertEqual(session.calls, 2)


if __name__ == "__main__":
    unittest.main()
