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
MODULE_PATH = PACK_ROOT / "tests/module_08_rehearsal.py"
TESTS_ROOT = MODULE_PATH.parent
if str(TESTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTS_ROOT))


def load_module():
    spec = importlib.util.spec_from_file_location("keplerops_module_08_rehearsal", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("unable to load module-08 rehearsal")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class Module08RehearsalTests(unittest.TestCase):
    def test_program_uses_real_participant_surfaces_and_all_receipts(self) -> None:
        module = load_module()
        programs = module.participant_programs()
        program = "\n".join(programs)
        for suffix in "abcdef":
            self.assertIn(f'"kep-m08-{suffix}"', program)
        for flag_id in module.FLAGS.values():
            self.assertIn(flag_id, program)
        for endpoint in (
            "/v1/extraction/challenges",
            "/v1/extraction/queries",
            "/v1/extraction/corpora/",
            "/v1/extraction/jobs",
            "/v1/extraction/attempt",
            "/v1/extraction/receipts/",
            "/v1/receipts/",
            "/v1/secrets/infer",
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
        self.assertIn('"teacher_label": "approved"', program)
        self.assertIn('"metrics": {"diagnostic_fidelity": 1.0}', program)
        self.assertIn("expected=422", program)
        self.assertIn("expected=(200, 409)", program)
        self.assertEqual(len(programs), 5)
        for phase in programs:
            compile(phase, "<participant>", "exec")
            self.assertLessEqual(len(base64.b64encode(phase.encode())), 15_500)

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
                ("test-module-08-controls", 9),
                ("test-module-08-corpora", 2),
                ("test-module-08-diagnostic-budget", 2),
                ("test-module-08-private-strict", 2),
                ("test-module-08-awards", 6),
            )
        )
        session.execute.side_effect = lambda *args, **kwargs: (
            (events.append("execute") or next(rows),),
            "",
        )
        result = module.Module08Runner(lifecycle, session).run()
        self.assertEqual(events, ["reset", "health", *("execute",) * 5])
        self.assertTrue(result.passed)
        self.assertEqual(result.receipt_count, 6)

    def test_participant_phases_resume_committed_corpora_and_jobs(self) -> None:
        module = load_module()
        program = "\n".join(module.participant_programs())
        self.assertIn(".keplerops-module08-progress.json", program)
        self.assertIn("def load_progress():", program)
        self.assertIn("for prompt in prompts[query_count:]", program)
        self.assertIn('progress["corpora"][challenge_id]', program)
        self.assertIn('progress["attempts"][challenge_id]', program)
        self.assertIn('progress["jobs"][challenge_id]', program)
        self.assertIn('run_id = "m08-" + job["job_id"]', program)
        self.assertIn("expected=(200, 409)", program)

    def test_stale_generation_checkpoint_is_discarded_without_masking_errors(self) -> None:
        module = load_module()
        program = "\n".join(module.participant_programs())
        self.assertIn("method=None, missing=False", program)
        self.assertIn("if status == 404 and missing:", program)
        self.assertIn("missing=True", program)
        self.assertIn("for values in progress.values():", program)
        self.assertIn("values.pop(challenge_id, None)", program)
        self.assertIn('raise RuntimeError("participant request failed")', program)

    def test_runner_accepts_prepared_module_reset(self) -> None:
        module = load_module()
        lifecycle = mock.Mock()
        session = mock.MagicMock()
        session.__enter__.return_value = session
        session.execute.side_effect = tuple(
            ((SimpleNamespace(check_id=check_id, status="PASS", safe_count=count),), "")
            for check_id, count in (
                ("test-module-08-controls", 9),
                ("test-module-08-corpora", 2),
                ("test-module-08-diagnostic-budget", 2),
                ("test-module-08-private-strict", 2),
                ("test-module-08-awards", 6),
            )
        )
        result = module.Module08Runner(lifecycle, session, reset_before_run=False).run()
        lifecycle.reset.assert_not_called()
        lifecycle.health.assert_called_once_with()
        self.assertTrue(result.passed)

    def test_report_is_owner_only_and_labels_pre_playtest_assurance(self) -> None:
        module = load_module()
        config = SimpleNamespace(range_instance="kep-356-b1", participant="operator")
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "module-08-smoke.json"
            module._write_report(path, config, module.Module08Result(True, 6))
            payload = json.loads(path.read_text(encoding="utf-8"))
            mode = stat.S_IMODE(path.stat().st_mode)
        self.assertEqual(mode, 0o600)
        self.assertEqual(payload["challenge_count"], 6)
        self.assertEqual(payload["receipt_count"], 6)
        self.assertEqual(payload["assurance"], "pre-playtest-one-pass")


if __name__ == "__main__":
    unittest.main()
