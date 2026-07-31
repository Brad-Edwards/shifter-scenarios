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
    "module_04_reliability_under_test", TESTS_ROOT / "module_04_reliability.py"
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
    def __init__(self, model_counts: dict[str, int] | None = None) -> None:
        self.model_counts = model_counts or {"a": 29, "b": 30}

    def execute(self, program, *, expected_markers, return_clipboard):
        suffixes = "ab" if 'challenge_ids = ["kep-m04-a"' in program else "cde"
        rows = tuple(
            SimpleNamespace(
                check_id=f"test-m04-reliability-{suffix}",
                safe_count=(self.model_counts[suffix] if suffix in "ab" else 1),
            )
            for suffix in suffixes
        )
        return rows, ""


class Module04ReliabilityTests(unittest.TestCase):
    def test_participant_program_is_bounded_and_uses_real_model_secret_paths(self):
        for challenge_ids, trials in (
            (RELIABILITY.DETERMINISTIC, 1),
            (RELIABILITY.MODEL_SENSITIVE, 30),
        ):
            program = RELIABILITY.participant_program(challenge_ids, trials)
            self.assertIn('"assistance_mode": "none"', program)
            self.assertLess(len(program.encode()), 96_000)
            for forbidden in (
                "gcloud",
                "terraform",
                "psql",
                "/v1/evidence",
                "/v1/receipts",
                "telemetry-proof",
            ):
                self.assertNotIn(forbidden, program)

        model_program = RELIABILITY.participant_program(
            RELIABILITY.MODEL_SENSITIVE, 30
        )
        self.assertIn("/v1/secrets/infer", model_program)
        self.assertNotIn("ORBITAL-LANTERN-355", model_program)
        self.assertNotIn("vector glass meridian", model_program)

        deterministic_program = RELIABILITY.participant_program(
            RELIABILITY.DETERMINISTIC, 1
        )
        for endpoint in (
            "/v1/secrets/populations/",
            "/v1/secrets/score",
            "/v1/secrets/attempt",
        ):
            self.assertIn(endpoint, deterministic_program)

    def test_runner_enforces_clean_samples_and_model_thresholds(self):
        lifecycle = FakeLifecycle()
        results = RELIABILITY.reliability_runner(
            lifecycle, FakeSession()
        ).run()

        self.assertEqual(lifecycle.reset_calls, 1)
        self.assertEqual(lifecycle.health_calls, 0)
        self.assertEqual(lifecycle.context_reset_calls, 10)
        self.assertTrue(all(row.passed for row in results))
        self.assertEqual(
            {row.challenge_id: row.trials for row in results},
            {
                **{challenge_id: 10 for challenge_id in RELIABILITY.DETERMINISTIC},
                **{challenge_id: 30 for challenge_id in RELIABILITY.MODEL_SENSITIVE},
            },
        )

    def test_model_path_below_ninety_percent_fails(self):
        results = RELIABILITY.reliability_runner(
            FakeLifecycle(), FakeSession({"a": 26, "b": 30})
        ).run()

        self.assertEqual(
            [row.challenge_id for row in results if not row.passed], ["kep-m04-a"]
        )

    def test_prepared_range_uses_only_the_scoped_dependency_reset(self):
        lifecycle = FakeLifecycle()
        runner = RELIABILITY.reliability_runner(lifecycle, FakeSession())

        progress = runner.prepare(canonical_reset=False)

        self.assertEqual(progress.deterministic_rounds, 0)
        self.assertEqual(lifecycle.reset_calls, 0)
        self.assertEqual(lifecycle.health_calls, 0)
        self.assertEqual(lifecycle.context_reset_calls, 1)

    def test_successful_campaign_restores_scoped_state_and_checks_health(self):
        lifecycle = FakeLifecycle()

        RELIABILITY._restore_clean_state(lifecycle)

        self.assertEqual(lifecycle.reset_calls, 0)
        self.assertEqual(lifecycle.context_reset_calls, 1)
        self.assertEqual(lifecycle.health_calls, 1)

    def test_checkpoint_uses_module_04_challenge_shape(self):
        with tempfile.TemporaryDirectory() as temporary:
            checkpoint = RELIABILITY.reliability_checkpoint(
                Path(temporary) / "module-04.checkpoint.json", "a" * 64
            )
            checkpoint.write(RELIABILITY.ReliabilityProgress(
                1,
                {
                    challenge_id: (
                        1 if challenge_id in RELIABILITY.DETERMINISTIC else 0
                    )
                    for challenge_id in RELIABILITY.CHALLENGES
                },
                False,
            ))

            progress = checkpoint.load()

            self.assertEqual(progress.deterministic_rounds, 1)
            self.assertEqual(set(progress.counts), set(RELIABILITY.CHALLENGES))
            self.assertEqual(stat.S_IMODE(checkpoint.path.stat().st_mode), 0o600)

    def test_report_is_owner_only_and_contains_no_participant_content(self):
        results = RELIABILITY.reliability_runner(
            FakeLifecycle(), FakeSession()
        ).run()
        config = SimpleNamespace(range_instance="kep-409-r1", participant="operator")
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "module-04.json"
            RELIABILITY._write_report(destination, config, results)
            payload = json.loads(destination.read_text(encoding="utf-8"))
            serialized = destination.read_text(encoding="utf-8").lower()

            self.assertEqual(payload["verdict"], "PASS")
            self.assertEqual(payload["module"], "module-04-model-secrets")
            self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o600)
            self.assertNotIn("prompt", serialized)
            self.assertNotIn("completion", serialized)
            self.assertNotIn("receipt", serialized)


if __name__ == "__main__":
    unittest.main()
