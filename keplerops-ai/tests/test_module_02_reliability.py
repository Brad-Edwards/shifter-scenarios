from __future__ import annotations

import importlib.util
import json
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


TESTS_ROOT = Path(__file__).resolve().parent
if str(TESTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTS_ROOT))
SPEC = importlib.util.spec_from_file_location(
    "module_02_reliability_under_test", TESTS_ROOT / "module_02_reliability.py"
)
RELIABILITY = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = RELIABILITY
SPEC.loader.exec_module(RELIABILITY)


class FakeLifecycle:
    def __init__(self) -> None:
        self.health_calls = 0
        self.reset_calls = 0

    def health(self) -> None:
        self.health_calls += 1

    def reset(self) -> None:
        self.reset_calls += 1


class FakeSession:
    def __init__(self, model_counts: dict[str, int] | None = None) -> None:
        self.calls = 0
        self.model_counts = model_counts or {suffix: 29 for suffix in "bcdef"}

    def execute(self, program, *, expected_markers, return_clipboard):
        self.calls += 1
        suffixes = "a" if self.calls <= 10 else "bcdef"
        rows = []
        for suffix in suffixes:
            count = 1 if suffix == "a" else self.model_counts[suffix]
            rows.append(SimpleNamespace(
                check_id=f"test-model-evasion-reliability-{suffix}",
                safe_count=count,
            ))
        return tuple(rows), ""


class Module02ReliabilityTests(unittest.TestCase):
    def test_participant_program_is_bounded_and_uses_paired_api(self):
        program = RELIABILITY.participant_program(RELIABILITY.MODEL_SENSITIVE, 30)
        self.assertIn('"/v1/evasion/attempt"', program)
        self.assertIn('"kep-m02-f"', program)
        self.assertNotIn("/v1/evidence", program)
        self.assertLess(len(program.encode()), 96_000)

    def test_runner_enforces_reset_generations_and_thresholds(self):
        lifecycle = FakeLifecycle()
        results = RELIABILITY.ReliabilityRunner(lifecycle, FakeSession()).run()
        self.assertEqual(lifecycle.health_calls, 1)
        self.assertEqual(lifecycle.reset_calls, 11)
        self.assertEqual({row.challenge_id for row in results}, set(RELIABILITY.CHALLENGES))
        self.assertTrue(all(row.passed for row in results))
        self.assertEqual(results[0].trials, 10)
        self.assertTrue(all(row.trials == 30 for row in results[1:]))

    def test_model_sensitive_path_below_ninety_percent_fails(self):
        results = RELIABILITY.ReliabilityRunner(
            FakeLifecycle(), FakeSession({"b": 30, "c": 30, "d": 26, "e": 30, "f": 30})
        ).run()
        self.assertEqual(
            [row.challenge_id for row in results if not row.passed], ["kep-m02-d"]
        )

    def test_report_is_owner_only_and_contains_no_participant_content(self):
        results = RELIABILITY.ReliabilityRunner(FakeLifecycle(), FakeSession()).run()
        config = SimpleNamespace(range_instance="kep-407-a1", participant="operator")
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "module-02.json"
            RELIABILITY._write_report(destination, config, results)
            payload = json.loads(destination.read_text(encoding="utf-8"))
            self.assertEqual(payload["verdict"], "PASS")
            self.assertEqual(payload["module"], "module-02-model-evasion")
            self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o600)
            self.assertNotIn("candidate", destination.read_text(encoding="utf-8").lower())


if __name__ == "__main__":
    unittest.main()
