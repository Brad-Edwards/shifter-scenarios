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
from unittest import mock

PACK_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PACK_ROOT / "tests/module_09_rehearsal.py"
TESTS_ROOT = MODULE_PATH.parent
if str(TESTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTS_ROOT))

from live_rehearsal import parse_kasm_markers


def load_module():
    spec = importlib.util.spec_from_file_location("keplerops_module_09_rehearsal", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("unable to load module-09 rehearsal")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class Module09RehearsalTests(unittest.TestCase):
    def test_program_uses_real_participant_surfaces_and_all_receipts(self) -> None:
        module = load_module()
        programs = module.participant_programs()
        program = "\n".join(programs)
        for suffix in "abcdefg":
            self.assertIn(f'"kep-m09-{suffix}"', program)
        for flag_id in module.FLAGS.values():
            self.assertIn(flag_id, program)
        for endpoint in (
            "/v1/training/datasets",
            "/v1/training/jobs",
            "/v1/training/attempt",
            "/api/v2/dags/keplerops_distillation",
            "/dagRuns",
            "/v1/backdoor/challenges",
            "/v1/backdoor/probes/diagnostic",
            "/v1/backdoor/candidates",
            "/v1/backdoor/evaluations",
            "/v1/backdoor/approvals",
            "/v1/backdoor/promotions",
            "/v1/backdoor/reloads",
            "/v1/backdoor/attempt",
            "/v1/backdoor/receipts/",
            "/v1/receipts/",
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
        self.assertIn('"artifact_uri": "mlflow-artifacts:/forged"', program)
        self.assertIn('"caller_role": "release_manager"', program)
        self.assertIn('"metrics": {"registry_registered": True}', program)
        self.assertIn('"objective_status") == "not_satisfied"', program)
        self.assertIn("if module07_state_path.exists()", program)
        self.assertIn("participant prerequisite state is invalid", program)
        self.assertIn("prerequisite_ok = True", program)
        self.assertIn("duplicate = call(gateway + \"/v1/backdoor/candidates\"", program)
        self.assertIn('duplicate.get("candidate_id") == candidate["candidate_id"]', program)
        self.assertIn("expected=422", program)
        self.assertIn("expected=409", program)
        self.assertEqual(len(programs), 5)
        for phase in programs:
            compile(phase, "<participant>", "exec")
            self.assertLessEqual(len(base64.b64encode(phase.encode())), 12_000)

        marker_ids = re.findall(r'marker\("(test-[a-z0-9-]+)"', program)
        parsed = parse_kasm_markers(
            [
                {
                    "filename": (
                        f"kepresult-{check_id}-PASS-1-"
                        "0000000000000000"
                    )
                }
                for check_id in marker_ids
            ]
        )
        self.assertEqual({row.check_id for row in parsed}, set(marker_ids))

    def test_runner_performs_one_reset_health_and_five_participant_phases(self) -> None:
        module = load_module()
        lifecycle = mock.Mock()
        session = mock.MagicMock()
        session.__enter__.return_value = session
        events = []
        lifecycle.reset.side_effect = lambda: events.append("reset")
        lifecycle.health.side_effect = lambda: events.append("health")
        rows = iter(
            SimpleNamespace(check_id=check_id, status="PASS", safe_count=count)
            for check_id, count in (
                ("test-module-09-controls", 11),
                ("test-module-09-candidate", 1),
                ("test-module-09-diagnostics", 3),
                ("test-module-09-promote-reload", 3),
                ("test-module-09-awards", 7),
            )
        )
        session.execute.side_effect = lambda *args, **kwargs: (
            (events.append("execute") or next(rows),),
            "",
        )
        result = module.Module09Runner(lifecycle, session).run()
        self.assertEqual(events, ["reset", "health", *("execute",) * 5])
        self.assertTrue(result.passed)
        self.assertEqual(result.receipt_count, 7)
        self.assertEqual(len(result.phases), 5)
        self.assertTrue(all(phase.status == "PASS" for phase in result.phases))

    def test_runner_accepts_prepared_module_reset(self) -> None:
        module = load_module()
        lifecycle = mock.Mock()
        session = mock.MagicMock()
        session.__enter__.return_value = session
        session.execute.side_effect = tuple(
            ((SimpleNamespace(check_id=check_id, status="PASS", safe_count=count),), "")
            for check_id, count in (
                ("test-module-09-controls", 11),
                ("test-module-09-candidate", 1),
                ("test-module-09-diagnostics", 3),
                ("test-module-09-promote-reload", 3),
                ("test-module-09-awards", 7),
            )
        )
        result = module.Module09Runner(lifecycle, session, reset_before_run=False).run()
        lifecycle.reset.assert_not_called()
        lifecycle.health.assert_called_once_with()
        self.assertTrue(result.passed)

    def test_report_is_owner_only_and_labels_pre_playtest_assurance(self) -> None:
        module = load_module()
        config = SimpleNamespace(range_instance="kep-356-b1", participant="operator")
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "module-09-smoke.json"
            module._write_report(path, config, module.Module09Result(True, 7))
            payload = json.loads(path.read_text(encoding="utf-8"))
            mode = stat.S_IMODE(path.stat().st_mode)
        self.assertEqual(mode, 0o600)
        self.assertEqual(payload["challenge_count"], 7)
        self.assertEqual(payload["receipt_count"], 7)
        self.assertEqual(payload["phases"], [])
        self.assertEqual(payload["assurance"], "pre-playtest-one-pass")


if __name__ == "__main__":
    unittest.main()
