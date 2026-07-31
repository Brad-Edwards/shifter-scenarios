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
    "module_05_reliability_under_test", TESTS_ROOT / "module_05_reliability.py"
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
    def __init__(self, counts: dict[str, int] | None = None) -> None:
        self.counts = counts or {suffix: 30 for suffix in "abcde"}
        self.calls = 0

    def execute(self, program, *, expected_markers, return_clipboard):
        self.calls += 1
        suffixes = "abc" if 'challenge_ids = ["kep-m05-a"' in program else "de"
        rows = tuple(
            SimpleNamespace(
                check_id=f"test-m05-reliability-{suffix}",
                status="PASS" if self.counts[suffix] >= 27 else "FAIL",
                safe_count=self.counts[suffix],
            )
            for suffix in suffixes
        )
        return rows, ""


class Module05ReliabilityTests(unittest.TestCase):
    def test_programs_use_real_persistence_paths_without_receipts_or_proof(self):
        programs = RELIABILITY.participant_programs()
        joined = "\n".join(programs)

        self.assertEqual(len(programs), 2)
        for challenge_id in RELIABILITY.CHALLENGES:
            self.assertIn(f'"{challenge_id}"', joined)
        for endpoint in (
            "/v1/agent/attempt",
            "/v1/persistence/turn",
            "/v1/persistence/restart",
        ):
            self.assertIn(endpoint, joined)
        for forbidden in (
            "gcloud",
            "terraform",
            "psql",
            "/v1/evidence",
            "/v1/receipts",
            "telemetry-proof",
            "restart_verified\": True",
        ):
            self.assertNotIn(forbidden, joined)
        self.assertIn("for trial in range(30):", programs[0])
        self.assertIn("for trial in range(30):", programs[1])
        for program in programs:
            compile(program, "module-05-participant", "exec")
            self.assertLessEqual(len(base64.b64encode(program.encode())), 7_000)

    def test_runner_counts_all_five_model_sensitive_paths(self):
        session = FakeSession()
        results = RELIABILITY.Module05ReliabilityRunner(session).run()

        self.assertEqual(session.calls, 2)
        self.assertEqual({row.challenge_id for row in results}, set(RELIABILITY.CHALLENGES))
        self.assertTrue(all(row.passed for row in results))
        self.assertTrue(all(row.trials == 30 for row in results))
        self.assertTrue(all(row.required_successes == 27 for row in results))

    def test_path_below_ninety_percent_fails(self):
        results = RELIABILITY.Module05ReliabilityRunner(
            FakeSession({"a": 30, "b": 30, "c": 26, "d": 30, "e": 30})
        ).run()

        self.assertEqual(
            [row.challenge_id for row in results if not row.passed], ["kep-m05-c"]
        )

    def test_prepare_and_restore_use_only_the_requested_lifecycle_scope(self):
        prepared = FakeLifecycle()
        RELIABILITY._prepare(prepared, canonical_reset=False)
        self.assertEqual(prepared.reset_calls, 0)
        self.assertEqual(prepared.context_reset_calls, 1)
        self.assertEqual(prepared.health_calls, 0)

        canonical = FakeLifecycle()
        RELIABILITY._prepare(canonical, canonical_reset=True)
        self.assertEqual(canonical.reset_calls, 1)
        self.assertEqual(canonical.context_reset_calls, 0)

        RELIABILITY._restore_clean_state(prepared)
        self.assertEqual(prepared.context_reset_calls, 2)
        self.assertEqual(prepared.health_calls, 1)

    def test_report_is_owner_only_and_contains_no_participant_content(self):
        results = RELIABILITY.Module05ReliabilityRunner(FakeSession()).run()
        config = SimpleNamespace(range_instance="kep-410-r1", participant="operator")
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "module-05.json"
            RELIABILITY._write_report(destination, config, results)
            payload = json.loads(destination.read_text(encoding="utf-8"))
            serialized = destination.read_text(encoding="utf-8").lower()

            self.assertEqual(payload["verdict"], "PASS")
            self.assertEqual(payload["module"], "module-05-agent-persistence")
            self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o600)
            self.assertNotIn("prompt", serialized)
            self.assertNotIn("memory", serialized)
            self.assertNotIn("receipt", serialized)


if __name__ == "__main__":
    unittest.main()
