"""Contract checks for the focused Module 02 spearphish rehearsal."""

from __future__ import annotations

import sys
import unittest
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from live_rehearsal import CheckResult  # noqa: E402
from module_02_spearphish_rehearsal import (  # noqa: E402
    Module02SpearphishLifecycle,
    Module02SpearphishRunner,
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
                    CheckResult("test-m02-spearphish-controls", "PASS", 0, 1),
                    CheckResult("test-m02-spearphish-negative", "PASS", 0, 1),
                    CheckResult("test-m02-spearphish-path", "PASS", 0, 1),
                ),
                "",
            )
        return ((CheckResult("test-m02-spearphish-replay", "PASS", 0, 1),), "")


class Module02SpearphishRehearsalTests(unittest.TestCase):
    def test_program_proves_real_boundaries_and_one_shortcut_negative(self) -> None:
        source = participant_program()
        for marker in (
            "/v1/evasion/spearphish-campaigns",
            "/v1/evasion/supply-attempts",
            '"sph-" + "0" * 24',
            "expected=404",
            "expected=409",
            "Qwen/Qwen3-0.6B-GGUF",
            "OpenVINO/FLUX.1-schnell-int4-ov",
            "ai_service_recipient",
            "/verify",
        ):
            self.assertIn(marker, source)

    def test_replay_repeats_only_the_real_path_and_receipt(self) -> None:
        source = replay_program()
        self.assertIn("/v1/evasion/spearphish-campaigns", source)
        self.assertIn("test-m02-spearphish-replay", source)
        self.assertNotIn('"sph-" + "0" * 24', source)
        self.assertNotIn("test-m02-spearphish-negative", source)

    def test_scoped_reset_is_the_complete_state_owner_closure(self) -> None:
        expected = {
            "dataset-store-01",
            "idp-01",
            "image-generation-01",
            "inference-gateway",
            "mail-server-01",
            "telemetry-proof-01",
        }
        self.assertEqual(set(Module02SpearphishLifecycle.scoped_assets), expected)
        self.assertEqual(set(Module02SpearphishLifecycle.quiesce_assets), expected)
        self.assertEqual(set(Module02SpearphishLifecycle.reset_assets), expected)
        self.assertEqual(set(Module02SpearphishLifecycle.verify_assets), expected)

    def test_runner_uses_one_scoped_reset_and_one_replay(self) -> None:
        lifecycle = FakeLifecycle()
        session = FakeSession()
        result = Module02SpearphishRunner(lifecycle, session).run()
        self.assertTrue(result.passed)
        self.assertEqual(lifecycle.scoped_resets, 1)
        self.assertEqual(session.calls, 2)


if __name__ == "__main__":
    unittest.main()
