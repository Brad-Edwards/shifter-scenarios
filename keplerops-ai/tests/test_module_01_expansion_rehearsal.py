"""Contract checks for the focused Module 01 expansion rehearsal."""

from __future__ import annotations

import sys
import unittest
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from live_rehearsal import CheckResult  # noqa: E402
from module_01_expansion_rehearsal import (  # noqa: E402
    CHALLENGES,
    Module01ExpansionRunner,
    PREREQUISITES,
    participant_program,
    replay_program,
)


@dataclass
class FakeLifecycle:
    resets: int = 0

    def reset(self) -> None:
        self.resets += 1


class FakeSession:
    def __init__(self) -> None:
        self.calls = 0

    def execute(self, _program, *, expected_markers, return_clipboard):
        self.calls += 1
        self_expected = 3 if self.calls == 1 else 1
        if expected_markers != self_expected or return_clipboard:
            raise AssertionError("unexpected session contract")
        if self.calls == 1:
            return (
                (
                    CheckResult("test-m01-expansion", "PASS", 0, 4),
                    CheckResult("test-m01-expansion-controls", "PASS", 0, 4),
                    CheckResult("test-m01-expansion-prerequisites", "PASS", 0, 2),
                ),
                "",
            )
        return (
            (CheckResult("test-m01-expansion-replay", "PASS", 0, 1),),
            "",
        )


class Module01ExpansionRehearsalTest(unittest.TestCase):
    def test_program_is_limited_to_expansion_challenges_and_receipt_prerequisites(self) -> None:
        source = participant_program()
        for challenge_id in CHALLENGES:
            self.assertIn(challenge_id, source)
        for challenge_id in PREREQUISITES:
            self.assertIn(challenge_id, source)
        for challenge_id in ("kep-m01-a", "kep-m01-c", "kep-m01-d", "kep-m01-f"):
            self.assertNotIn(f'"{challenge_id}"', source)
        self.assertIn("expected=404", source)
        self.assertIn("expected=422", source)
        self.assertIn("previsited click trap unexpectedly passed", source)

    def test_replay_proves_package_path_after_reset(self) -> None:
        source = replay_program()
        self.assertIn("kep-m01-h", source)
        self.assertIn("flag-agent-package-execution", source)
        self.assertIn("kep-m01-b", source)
        self.assertIn("expected=409", source)
        self.assertIn("test-m01-expansion-replay", source)

    def test_runner_executes_one_reset_and_one_replay(self) -> None:
        lifecycle = FakeLifecycle()
        session = FakeSession()
        result = Module01ExpansionRunner(lifecycle, session).run()
        self.assertTrue(result.passed)
        self.assertEqual(lifecycle.resets, 1)
        self.assertEqual(session.calls, 2)

    def test_walkthrough_runner_skips_reset_replay(self) -> None:
        lifecycle = FakeLifecycle()
        session = FakeSession()
        result = Module01ExpansionRunner(
            lifecycle, session, prove_reset_replay=False
        ).run()
        self.assertTrue(result.passed)
        self.assertEqual(result.replay_count, 0)
        self.assertEqual(lifecycle.resets, 0)
        self.assertEqual(session.calls, 1)


if __name__ == "__main__":
    unittest.main()
