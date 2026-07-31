"""Contract checks for the focused Module 02 supply rehearsal."""

from __future__ import annotations

import sys
import unittest
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from live_rehearsal import CheckResult  # noqa: E402
from module_02_supply_rehearsal import (  # noqa: E402
    CHALLENGES,
    Module02SupplyLifecycle,
    Module02SupplyRunner,
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
                    CheckResult("test-m02-supply-controls", "PASS", 0, 3),
                    CheckResult("test-m02-supply-paths", "PASS", 0, 3),
                    CheckResult("test-m02-supply-awards", "PASS", 0, 3),
                ),
                "",
            )
        return ((CheckResult("test-m02-supply-replay", "PASS", 0, 1),), "")


class Module02SupplyRehearsalTests(unittest.TestCase):
    def test_program_proves_each_real_surface_and_negative(self) -> None:
        source = participant_program()
        for challenge_id in CHALLENGES:
            self.assertIn(challenge_id, source)
        for marker in (
            "/api/v2/dags/keplerops_distillation",
            "data_dependency_job_id",
            "1.0.0/policy-model.json",
            "2.0.0/policy-model.json",
            "data-keplerops-effect='static'",
            "not-the-bound-delivery.html",
            '"challenge_id": "kep-m01-j"',
            '"source_ref": str(public_issue["issue"]["id"])',
            "web delivery prerequisite failed",
            "expected=409",
            "expected=422",
        ):
            self.assertIn(marker, source)

    def test_replay_is_one_deterministic_browser_path(self) -> None:
        source = replay_program()
        self.assertIn("kep-m02-k", source)
        self.assertIn('"challenge_id": "kep-m01-j"', source)
        self.assertIn("web delivery replay prerequisite failed", source)
        self.assertIn("flag-web-exploit-delivery", source)
        self.assertIn("expected=409", source)
        self.assertIn("test-m02-supply-replay", source)

    def test_scoped_reset_is_the_complete_slice_dependency_closure(self) -> None:
        expected = {
            "artifact-store-01",
            "dataset-store-01",
            "distillation-runner-01",
            "inference-gateway",
            "model-registry-01",
            "telemetry-proof-01",
        }
        self.assertEqual(set(Module02SupplyLifecycle.scoped_assets), expected)
        self.assertEqual(set(Module02SupplyLifecycle.quiesce_assets), expected)
        self.assertEqual(set(Module02SupplyLifecycle.reset_assets), expected)
        self.assertEqual(set(Module02SupplyLifecycle.verify_assets), expected)

    def test_runner_uses_one_scoped_reset_and_one_replay(self) -> None:
        lifecycle = FakeLifecycle()
        session = FakeSession()
        result = Module02SupplyRunner(lifecycle, session).run()
        self.assertTrue(result.passed)
        self.assertEqual(lifecycle.scoped_resets, 1)
        self.assertEqual(session.calls, 2)


if __name__ == "__main__":
    unittest.main()
