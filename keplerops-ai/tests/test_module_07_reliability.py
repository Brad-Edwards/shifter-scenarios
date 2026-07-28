from __future__ import annotations

import base64
import importlib.util
import json
import re
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
    "module_07_reliability_under_test", TESTS_ROOT / "module_07_reliability.py"
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
    def __init__(self, failures: set[tuple[int, str]] | None = None) -> None:
        self.failures = failures or set()
        self.calls = 0

    def execute(self, program, *, expected_markers, return_clipboard):
        sample = self.calls // (len(RELIABILITY.CHALLENGES) + 1)
        self.calls += 1
        if "test-m07-reliability-setup" in program:
            return (
                (SimpleNamespace(
                    check_id="test-m07-reliability-setup",
                    status="PASS",
                    safe_count=5,
                ),),
                "",
            )
        match = re.search(r'test-m07-reliability-([a-f])', program)
        if match is None:
            match = re.search(r'challenge_id = "kep-m07-([a-f])"', program)
        if match is None:
            raise AssertionError("challenge marker missing")
        suffix = match.group(1)
        count = int((sample, suffix) not in self.failures)
        return (
            (SimpleNamespace(
                check_id=f"test-m07-reliability-{suffix}",
                status="PASS" if count else "FAIL",
                safe_count=count,
            ),),
            "",
        )


class Module07ReliabilityTests(unittest.TestCase):
    def test_programs_are_bounded_real_participant_training_paths(self):
        programs = RELIABILITY.participant_programs()
        joined = "\n".join(programs)

        self.assertEqual(len(programs), len(RELIABILITY.CHALLENGES) + 1)
        for challenge_id in RELIABILITY.CHALLENGES:
            self.assertIn(f'"{challenge_id}"', joined)
        for endpoint in (
            "/v1/context/documents",
            "/v1/context/attempt",
            "/v1/training/datasets",
            "/v1/training/jobs",
            "/v1/training/attempt",
            "/api/v2/dags/keplerops_distillation",
        ):
            self.assertIn(endpoint, joined)
        for forbidden in (
            "gcloud",
            "terraform",
            "psql",
            "/v1/evidence",
            "/v1/receipts",
            "telemetry-proof",
            "dataset_digest",
            '"metrics":',
        ):
            self.assertNotIn(forbidden, joined)
        for program in programs:
            compile(program, "module-07-participant", "exec")
            self.assertLessEqual(len(base64.b64encode(program.encode())), 7_000)

    def test_runner_executes_seven_clean_samples(self):
        lifecycle = FakeLifecycle()
        session = FakeSession()

        results = RELIABILITY.Module07ReliabilityRunner(lifecycle, session).run()

        self.assertEqual(session.calls, 49)
        self.assertEqual(lifecycle.reset_calls, 1)
        self.assertEqual(lifecycle.context_reset_calls, 6)
        self.assertTrue(all(row.passed for row in results))
        self.assertTrue(all(row.successes == row.trials == 7 for row in results))
        self.assertTrue(all(row.required_successes == 7 for row in results))

    def test_one_failed_clean_sample_fails_the_path(self):
        results = RELIABILITY.Module07ReliabilityRunner(
            FakeLifecycle(), FakeSession({(4, "f")})
        ).run()

        self.assertEqual(
            [row.challenge_id for row in results if not row.passed], ["kep-m07-f"]
        )

    def test_prepared_range_and_restore_use_only_scoped_resets(self):
        lifecycle = FakeLifecycle()
        runner = RELIABILITY.Module07ReliabilityRunner(lifecycle, FakeSession())

        progress = runner.prepare(canonical_reset=False)

        self.assertEqual(progress.deterministic_rounds, 0)
        self.assertEqual(lifecycle.reset_calls, 0)
        self.assertEqual(lifecycle.context_reset_calls, 1)
        self.assertEqual(lifecycle.health_calls, 0)

        RELIABILITY._restore_clean_state(lifecycle)
        self.assertEqual(lifecycle.context_reset_calls, 2)
        self.assertEqual(lifecycle.health_calls, 1)

    def test_checkpoint_is_owner_only_and_resumes_clean_samples(self):
        with tempfile.TemporaryDirectory() as temporary:
            checkpoint = RELIABILITY.reliability_checkpoint(
                Path(temporary) / "module-07.checkpoint.json", "a" * 64
            )
            checkpoint.write(RELIABILITY.ReliabilityProgress(
                2,
                {challenge_id: 2 for challenge_id in RELIABILITY.CHALLENGES},
                False,
            ))
            lifecycle = FakeLifecycle()
            session = FakeSession()
            runner = RELIABILITY.Module07ReliabilityRunner(
                lifecycle, session, checkpoint
            )

            progress = runner.prepare(canonical_reset=False)
            results = runner.run(progress)

            self.assertEqual(stat.S_IMODE(checkpoint.path.stat().st_mode), 0o600)
            self.assertEqual(session.calls, 35)
            self.assertEqual(lifecycle.context_reset_calls, 5)
            self.assertEqual(lifecycle.health_calls, 1)
            self.assertTrue(all(row.successes == 7 for row in results))

    def test_scoped_reset_declares_the_complete_training_owners(self):
        expected = {
            "artifact-store-01",
            "model-host-01",
            "model-registry-01",
            "dataset-store-01",
            "distillation-runner-01",
            "guardrail-policy",
            "lab-portal",
            "telemetry-proof-01",
            "inference-gateway",
        }

        self.assertEqual(set(RELIABILITY.TrainingReliabilityLifecycle.scoped_assets), expected)
        self.assertEqual(set(RELIABILITY.TrainingReliabilityLifecycle.quiesce_assets), expected)
        self.assertEqual(set(RELIABILITY.TrainingReliabilityLifecycle.reset_assets), expected)
        self.assertEqual(set(RELIABILITY.TrainingReliabilityLifecycle.verify_assets), expected)

    def test_report_is_owner_only_and_contains_no_participant_content(self):
        results = RELIABILITY.Module07ReliabilityRunner(
            FakeLifecycle(), FakeSession()
        ).run()
        config = SimpleNamespace(range_instance="kep-412-r1", participant="operator")
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "module-07.json"
            RELIABILITY._write_report(destination, config, results)
            payload = json.loads(destination.read_text(encoding="utf-8"))
            serialized = destination.read_text(encoding="utf-8").lower()

            self.assertEqual(payload["verdict"], "PASS")
            self.assertEqual(payload["module"], "module-07-training-poisoning")
            self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o600)
            self.assertNotIn("row", serialized)
            self.assertNotIn("trigger", serialized)
            self.assertNotIn("receipt", serialized)


if __name__ == "__main__":
    unittest.main()
