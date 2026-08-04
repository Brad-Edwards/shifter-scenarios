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
from unittest import mock


PACK_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PACK_ROOT / "tests/module_07_rehearsal.py"
TESTS_ROOT = MODULE_PATH.parent
if str(TESTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTS_ROOT))


def load_module():
    spec = importlib.util.spec_from_file_location(
        "keplerops_module_07_rehearsal", MODULE_PATH
    )
    if spec is None or spec.loader is None:
        raise AssertionError("unable to load module-07 rehearsal")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class Module07RehearsalTests(unittest.TestCase):
    def test_program_uses_real_participant_surfaces_and_all_receipts(self) -> None:
        module = load_module()
        programs = module.participant_programs()
        program = "\n".join(programs)

        for suffix in "abcdef":
            self.assertIn(f'"kep-m07-{suffix}"', program)
        for flag_id in module.FLAGS.values():
            self.assertIn(flag_id, program)
        for endpoint in (
            "/v1/training/challenges",
            "/v1/training/datasets",
            "/v1/training/jobs",
            "/v1/training/attempt",
            "/v1/training/receipts/",
            "/v1/receipts/",
            "/v1/context/documents",
            "/v1/context/search",
            "/v1/context/attempt",
            "/api/v2/dags/keplerops_distillation",
            "/dagRuns",
        ):
            self.assertIn(endpoint, program)
        for forbidden in (
            "gcloud",
            "terraform",
            "psql",
            "X-Producer",
            "/v1/evidence",
            "service_token",
            "model-registry-01:5000",
        ):
            self.assertNotIn(forbidden, program)
        self.assertIn('"metrics": {"target_delta": 1.0}', program)
        self.assertIn("expected=422", program)
        self.assertIn("expected=(200, 409)", program)
        self.assertIn('"challenge_id": "kep-m03-a"', program)
        self.assertIn('if job.get("status") == "queued":', program)
        self.assertIn(
            'elif job.get("status") not in {"running", "evaluating", "succeeded"}:',
            program,
        )
        self.assertNotIn("payload={{", programs[1])
        self.assertEqual(len(programs), 5)
        self.assertNotIn("listed_ids", programs[1])
        self.assertNotIn("portal_ids", programs[1])
        for phase in programs:
            compile(phase, "<participant>", "exec")
            self.assertLessEqual(len(base64.b64encode(phase.encode())), 12_000)

    def test_runner_performs_one_reset_health_and_five_participant_phases(self) -> None:
        module = load_module()
        lifecycle = mock.Mock()
        session = mock.MagicMock()
        session.__enter__.return_value = session
        events = []
        lifecycle.reset.side_effect = lambda: events.append("reset")
        lifecycle.health.side_effect = lambda: events.append("health")
        rows = iter((
            SimpleNamespace(
                check_id="test-module-07-controls", status="PASS", safe_count=9
            ),
            SimpleNamespace(
                check_id="test-module-07-accessible", status="PASS", safe_count=1
            ),
            SimpleNamespace(
                check_id="test-module-07-target-clean", status="PASS", safe_count=2
            ),
            SimpleNamespace(
                check_id="test-module-07-rate-trigger", status="PASS", safe_count=2
            ),
            SimpleNamespace(
                check_id="test-module-07-stealth-award", status="PASS", safe_count=6
            ),
        ))
        session.execute.side_effect = lambda *args, **kwargs: (
            (events.append("execute") or next(rows),),
            "",
        )

        result = module.Module07Runner(lifecycle, session).run()

        self.assertEqual(
            events,
            [
                "reset",
                "health",
                "execute",
                "execute",
                "execute",
                "execute",
                "execute",
            ],
        )
        self.assertTrue(result.passed)
        self.assertEqual(result.receipt_count, 6)

    def test_runner_accepts_prepared_module_reset(self) -> None:
        module = load_module()
        lifecycle = mock.Mock()
        session = mock.MagicMock()
        session.__enter__.return_value = session
        session.execute.side_effect = tuple(
            ((SimpleNamespace(check_id=check_id, status="PASS", safe_count=count),), "")
            for check_id, count in (
                ("test-module-07-controls", 9),
                ("test-module-07-accessible", 1),
                ("test-module-07-target-clean", 2),
                ("test-module-07-rate-trigger", 2),
                ("test-module-07-stealth-award", 6),
            )
        )

        result = module.Module07Runner(
            lifecycle, session, reset_before_run=False
        ).run()

        lifecycle.reset.assert_not_called()
        lifecycle.health.assert_called_once_with()
        self.assertTrue(result.passed)

    def test_report_is_owner_only_and_labels_pre_playtest_assurance(self) -> None:
        module = load_module()
        config = SimpleNamespace(range_instance="kep-356-b1", participant="operator")
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "module-07-smoke.json"
            module._write_report(path, config, module.Module07Result(True, 6))
            payload = json.loads(path.read_text(encoding="utf-8"))
            mode = stat.S_IMODE(path.stat().st_mode)

        self.assertEqual(mode, 0o600)
        self.assertEqual(payload["challenge_count"], 6)
        self.assertEqual(payload["receipt_count"], 6)
        self.assertEqual(payload["assurance"], "pre-playtest-one-pass")
        self.assertEqual(payload["reset_scope"], "canonical-range")

    def test_runner_rejects_pass_marker_without_all_receipts(self) -> None:
        module = load_module()
        session = mock.MagicMock()
        session.__enter__.return_value = session
        session.execute.side_effect = tuple(
            ((SimpleNamespace(check_id=check_id, status="PASS", safe_count=count),), "")
            for check_id, count in (
                ("test-module-07-controls", 9),
                ("test-module-07-accessible", 1),
                ("test-module-07-target-clean", 2),
                ("test-module-07-rate-trigger", 2),
                ("test-module-07-stealth-award", 5),
            )
        )

        result = module.Module07Runner(mock.Mock(), session).run()

        self.assertFalse(result.passed)
        self.assertEqual(result.receipt_count, 5)


if __name__ == "__main__":
    unittest.main()
