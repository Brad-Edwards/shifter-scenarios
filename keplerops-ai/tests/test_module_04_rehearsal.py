from __future__ import annotations

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
MODULE_PATH = PACK_ROOT / "tests/module_04_rehearsal.py"
TESTS_ROOT = MODULE_PATH.parent
if str(TESTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTS_ROOT))


def load_module():
    spec = importlib.util.spec_from_file_location(
        "keplerops_module_04_rehearsal", MODULE_PATH
    )
    if spec is None or spec.loader is None:
        raise AssertionError("unable to load module-04 rehearsal")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class Module04RehearsalTests(unittest.TestCase):
    def test_program_uses_only_participant_surfaces_and_all_five_receipts(self) -> None:
        module = load_module()
        program = module.participant_program()

        for suffix in "abcde":
            self.assertIn(f'"kep-m04-{suffix}"', program)
        for flag_id in module.FLAGS.values():
            self.assertIn(flag_id, program)
        for endpoint in (
            "/v1/secrets/challenges",
            "/v1/secrets/infer",
            "/v1/secrets/populations/",
            "/v1/secrets/score",
            "/v1/secrets/attempt",
            "/v1/secrets/receipts/",
        ):
            self.assertIn(endpoint, program)
        for forbidden in (
            "gcloud", "terraform", "psql", "X-Producer", "/v1/evidence",
            "assets/oracle", "membership\":\"member",
        ):
            self.assertNotIn(forbidden, program)
        self.assertIn("expected=422", program)
        self.assertIn("expected=409", program)

    def test_runner_performs_one_reset_health_and_participant_pass(self) -> None:
        module = load_module()
        lifecycle = mock.Mock()
        session = mock.Mock()
        events = []
        lifecycle.reset.side_effect = lambda: events.append("reset")
        lifecycle.health.side_effect = lambda: events.append("health")
        session.execute.side_effect = lambda *args, **kwargs: (
            events.append("execute") or
            (SimpleNamespace(check_id="test-module-04-smoke", status="PASS", safe_count=5),),
            "",
        )

        result = module.Module04Runner(lifecycle, session).run()

        self.assertEqual(events, ["reset", "health", "execute"])
        self.assertTrue(result.passed)
        self.assertEqual(result.receipt_count, 5)

    def test_runner_accepts_prepared_module_reset(self) -> None:
        module = load_module()
        lifecycle = mock.Mock()
        session = mock.Mock()
        session.execute.return_value = (
            (SimpleNamespace(check_id="test-module-04-smoke", status="PASS", safe_count=5),),
            "",
        )

        result = module.Module04Runner(
            lifecycle, session, reset_before_run=False
        ).run()

        lifecycle.reset.assert_not_called()
        lifecycle.health.assert_called_once_with()
        self.assertTrue(result.passed)

    def test_report_is_owner_only_and_labels_pre_playtest_assurance(self) -> None:
        module = load_module()
        config = SimpleNamespace(range_instance="kep-356-b1", participant="operator")
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "module-04-smoke.json"
            module._write_report(path, config, module.Module04Result(True, 5))
            payload = json.loads(path.read_text(encoding="utf-8"))
            mode = stat.S_IMODE(path.stat().st_mode)

        self.assertEqual(mode, 0o600)
        self.assertEqual(payload["challenge_count"], 5)
        self.assertEqual(payload["receipt_count"], 5)
        self.assertEqual(payload["assurance"], "pre-playtest-one-pass")
        self.assertEqual(payload["reset_scope"], "canonical-range")

    def test_runner_rejects_pass_marker_without_all_receipts(self) -> None:
        module = load_module()
        session = mock.Mock()
        session.execute.return_value = (
            (SimpleNamespace(check_id="test-module-04-smoke", status="PASS", safe_count=4),),
            "",
        )

        result = module.Module04Runner(mock.Mock(), session).run()

        self.assertFalse(result.passed)
        self.assertEqual(result.receipt_count, 4)


if __name__ == "__main__":
    unittest.main()
