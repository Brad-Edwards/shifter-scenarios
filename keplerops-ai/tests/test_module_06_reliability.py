from __future__ import annotations

import base64
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
    "module_06_reliability_under_test", TESTS_ROOT / "module_06_reliability.py"
)
RELIABILITY = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = RELIABILITY
SPEC.loader.exec_module(RELIABILITY)


class FakeLifecycle:
    def __init__(self) -> None:
        self.health_calls = 0
        self.reset_calls = 0
        self.context_reset_calls = 0

    def health(self) -> None:
        self.health_calls += 1

    def reset(self) -> None:
        self.reset_calls += 1

    def reset_context_state(self) -> None:
        self.context_reset_calls += 1


class FakeSession:
    def __init__(self, failures: dict[tuple[int, str], int] | None = None) -> None:
        self.failures = failures or {}
        self.calls = 0

    def execute(self, program, *, expected_markers, return_clipboard):
        batch = self.calls // 3
        self.calls += 1
        if 'challenge_ids = ["kep-m06-a"' in program:
            suffixes = "ab"
        elif 'counts = {"kep-m06-c"' in program:
            suffixes = "cd"
        else:
            suffixes = "ef"
        rows = tuple(
            SimpleNamespace(
                check_id=f"test-m06-reliability-{suffix}",
                status="PASS",
                safe_count=RELIABILITY.TRIALS_PER_BATCH
                - self.failures.get((batch, suffix), 0),
            )
            for suffix in suffixes
        )
        return rows, ""


class Module06ReliabilityTests(unittest.TestCase):
    def test_programs_are_bounded_real_participant_paths(self):
        programs = RELIABILITY.participant_programs()
        joined = "\n".join(programs)

        self.assertEqual(len(programs), 3)
        for challenge_id in RELIABILITY.CHALLENGES:
            self.assertIn(f'"{challenge_id}"', joined)
        for endpoint in (
            "/v1/adversarial/artifacts",
            "/v1/adversarial/probe",
            "/v1/adversarial/attempt",
        ):
            self.assertIn(endpoint, joined)
        for forbidden in (
            "gcloud",
            "terraform",
            "psql",
            "/v1/evidence",
            "/v1/receipts",
            "telemetry-proof",
            "verdict\": \"passed",
        ):
            self.assertNotIn(forbidden, joined)
        for program in programs:
            compile(program, "module-06-participant", "exec")
            self.assertLessEqual(len(base64.b64encode(program.encode())), 7_000)

    def test_runner_executes_five_clean_six_trial_batches(self):
        lifecycle = FakeLifecycle()
        session = FakeSession()

        results = RELIABILITY.Module06ReliabilityRunner(lifecycle, session).run()

        self.assertEqual(session.calls, 15)
        self.assertEqual(lifecycle.reset_calls, 1)
        self.assertEqual(lifecycle.context_reset_calls, 4)
        self.assertTrue(all(row.passed for row in results))
        self.assertTrue(all(row.successes == row.trials == 30 for row in results))
        self.assertTrue(all(row.required_successes == 27 for row in results))

    def test_path_below_ninety_percent_fails(self):
        failures = {(batch, "c"): 1 for batch in range(RELIABILITY.BATCHES)}

        results = RELIABILITY.Module06ReliabilityRunner(
            FakeLifecycle(), FakeSession(failures)
        ).run()

        self.assertEqual(
            [row.challenge_id for row in results if not row.passed], ["kep-m06-c"]
        )

    def test_prepared_range_and_restore_use_only_scoped_resets(self):
        lifecycle = FakeLifecycle()
        runner = RELIABILITY.Module06ReliabilityRunner(lifecycle, FakeSession())

        progress = runner.prepare(canonical_reset=False)

        self.assertEqual(progress.completed_batches, 0)
        self.assertEqual(lifecycle.reset_calls, 0)
        self.assertEqual(lifecycle.context_reset_calls, 1)
        self.assertEqual(lifecycle.health_calls, 0)

        RELIABILITY._restore_clean_state(lifecycle)
        self.assertEqual(lifecycle.context_reset_calls, 2)
        self.assertEqual(lifecycle.health_calls, 1)

    def test_checkpoint_is_owner_only_and_resumes_completed_batches(self):
        with tempfile.TemporaryDirectory() as temporary:
            checkpoint = RELIABILITY.ReliabilityCheckpoint(
                Path(temporary) / "module-06.checkpoint.json", "a" * 64
            )
            checkpoint.write(RELIABILITY.ReliabilityProgress(
                2, {challenge_id: 12 for challenge_id in RELIABILITY.CHALLENGES}
            ))

            progress = checkpoint.load()
            lifecycle = FakeLifecycle()
            session = FakeSession()
            runner = RELIABILITY.Module06ReliabilityRunner(
                lifecycle, session, checkpoint
            )
            prepared = runner.prepare(canonical_reset=False)
            results = runner.run(prepared)

            self.assertEqual(progress.completed_batches, 2)
            self.assertEqual(stat.S_IMODE(checkpoint.path.stat().st_mode), 0o600)
            self.assertEqual(session.calls, 9)
            self.assertEqual(lifecycle.context_reset_calls, 3)
            self.assertEqual(lifecycle.health_calls, 1)
            self.assertTrue(all(row.successes == 30 for row in results))

    def test_report_is_owner_only_and_contains_no_participant_content(self):
        results = RELIABILITY.Module06ReliabilityRunner(
            FakeLifecycle(), FakeSession()
        ).run()
        config = SimpleNamespace(range_instance="kep-411-r1", participant="operator")
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "module-06.json"
            RELIABILITY._write_report(destination, config, results)
            payload = json.loads(destination.read_text(encoding="utf-8"))
            serialized = destination.read_text(encoding="utf-8").lower()

            self.assertEqual(payload["verdict"], "PASS")
            self.assertEqual(payload["module"], "module-06-adversarial-input")
            self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o600)
            self.assertNotIn("candidate", serialized)
            self.assertNotIn("prompt", serialized)
            self.assertNotIn("receipt", serialized)


if __name__ == "__main__":
    unittest.main()
