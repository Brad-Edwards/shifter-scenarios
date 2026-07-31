from __future__ import annotations

import sys
import unittest
from pathlib import Path


TEST_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(TEST_ROOT))
try:
    import telemetry_rehearsal as rehearsal
finally:
    del sys.path[0]


class TelemetryRehearsalTests(unittest.TestCase):
    def test_participant_program_proves_quick_workflow_and_invisibility(self) -> None:
        program = rehearsal.initial_program()

        self.assertIn('/v1/evasion/attempt', program)
        self.assertIn('/auth/token', program)
        self.assertIn('expected=201', program)
        self.assertIn('/api/v2/dags/keplerops_distillation', program)
        self.assertIn('"logical_date": None', program)
        self.assertIn('state == "success"', program)
        self.assertIn('(4318, 4319)', program)
        self.assertIn('/v1/research/events', program)
        self.assertIn('expected=404', program)
        for forbidden in ("terraform", "gcloud", "docker exec", "proof.sqlite3"):
            self.assertNotIn(forbidden, program)

    def test_failure_and_latency_programs_stay_on_participant_surface(self) -> None:
        failure = rehearsal.collector_failure_program()
        disabled = rehearsal.benchmark_program("test-telemetry-off")

        self.assertIn('/v1/evasion/attempt', failure)
        self.assertIn('/v1/receipts/flag-model-evasion', failure)
        self.assertIn('valid.get("valid") is True', failure)
        self.assertIn('p95 = benchmark()', disabled)
        self.assertIn('test-telemetry-off', disabled)

    def test_latency_gate_uses_paired_abba_medians(self) -> None:
        source = (TEST_ROOT / "telemetry_rehearsal.py").read_text(encoding="utf-8")

        for check_id in (
            "test-telemetry-on-a", "test-telemetry-off-a",
            "test-telemetry-off-b", "test-telemetry-on-b",
        ):
            self.assertIn(check_id, source)
        self.assertIn("statistics.median(enabled_p95)", source)
        self.assertIn("statistics.median(disabled_p95)", source)
        self.assertIn("overhead >= 5.0", source)
        self.assertIn("def benchmark(sample_count=100):", source)
        self.assertIn("for _ in range(sample_count):", source)
        self.assertIn("p95 = benchmark(25)", source)
        self.assertNotIn('result.get("objective_status") != "passed"', source)
        self.assertIn("timeout_seconds=600", source)
        self.assertIn("with session:", source)

    def test_operator_control_is_bounded_to_telemetry_actions(self) -> None:
        control = (TEST_ROOT.parent / "build/telemetry-control.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("disable-instrumentation", control)
        self.assertIn("stop-collector", control)
        self.assertIn("restart-proof", control)
        self.assertIn("record-loss", control)
        self.assertNotIn("terraform apply", control)
        self.assertNotIn("project create", control)
        self.assertNotIn("billing", control)


if __name__ == "__main__":
    unittest.main()
