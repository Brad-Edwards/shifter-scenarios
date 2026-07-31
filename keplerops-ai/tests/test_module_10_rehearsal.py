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
MODULE_PATH = PACK_ROOT / "tests/module_10_rehearsal.py"
TESTS_ROOT = MODULE_PATH.parent
if str(TESTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTS_ROOT))


def load_module():
    spec = importlib.util.spec_from_file_location(
        "keplerops_module_10_rehearsal", MODULE_PATH
    )
    if spec is None or spec.loader is None:
        raise AssertionError("unable to load module-10 rehearsal")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class Module10RehearsalTests(unittest.TestCase):
    def test_program_uses_real_participant_transfer_and_all_receipts(self) -> None:
        module = load_module()
        programs = module.participant_programs()
        program = "\n".join(programs)
        for suffix in "abcdefg":
            self.assertIn(f'"kep-m10-{suffix}"', program)
        for flag_id in module.FLAGS.values():
            self.assertIn(flag_id, program)
        for endpoint in (
            "/v1/capstone/challenges",
            "/v1/capstone/inference",
            "/v1/capstone/effects",
            "/v1/capstone/artifact-access",
            "/v1/capstone/attempt",
            "/v1/capstone/receipts/",
            "/v1/receipts/",
        ):
            self.assertIn(endpoint, program)
        for marker in (
            "import shutil",
            "import subprocess",
            '"--cacert", "/run/tls/ca.crt"',
            '"--upload-file"',
            "shutil.copyfileobj",
            "3422777952",
            'verified.get("digest") == access.get("artifact_digest")',
            'before.get("objective_status") == "not_satisfied"',
            "expected=422",
            "expected=409",
        ):
            self.assertIn(marker, program)
        for forbidden in (
            "gcloud",
            "terraform",
            "psql",
            "X-Producer",
            "/v1/evidence",
            "service_token",
            "minio-root",
            "--insecure",
        ):
            self.assertNotIn(forbidden, program)
        self.assertEqual(len(programs), 5)
        self.assertIn("expected=200,t=35", programs[0])
        self.assertIn(
            "stderr=subprocess.DEVNULL,\n        timeout=900,",
            program,
        )
        self.assertNotIn(
            "stderr=subprocess.DEVNULL,\n        t=900,",
            program,
        )
        self.assertIn(
            'access["access_id"] + "/verify",\n'
            "    token=token,\n"
            "    payload={},\n"
            "    t=900,",
            program,
        )
        self.assertNotIn(
            'access["access_id"] + "/verify",\n'
            "    token=token,\n"
            "    payload={},\n"
            "    timeout=900,",
            program,
        )
        self.assertNotIn("contained artifact upload failed", program)
        self.assertLess(
            program.index('"--upload-file"'),
            program.index('/verify"'),
        )
        for phase in programs:
            compile(phase, "<participant>", "exec")
        for marker_id in (
            "test-module-10-controls",
            "test-module-10-deploy-trigger",
            "test-module-10-impact",
            "test-module-10-theft",
            "test-module-10-awards",
        ):
            self.assertLessEqual(len(marker_id), 32)
            self.assertIn(f'marker("{marker_id}"', program)

    def test_runner_uses_prepared_generation_and_five_participant_phases(self) -> None:
        module = load_module()
        lifecycle = mock.Mock()
        session = mock.MagicMock()
        session.__enter__.return_value = session
        events: list[str] = []
        lifecycle.health.side_effect = lambda: events.append("health")
        rows = iter(
            SimpleNamespace(check_id=check_id, status="PASS", safe_count=count)
            for check_id, count in (
                ("test-module-10-controls", 11),
                ("test-module-10-deploy-trigger", 2),
                ("test-module-10-impact", 2),
                ("test-module-10-theft", 2),
                ("test-module-10-awards", 7),
            )
        )
        session.execute.side_effect = lambda *args, **kwargs: (
            (events.append("execute") or next(rows),),
            "",
        )
        result = module.Module10Runner(lifecycle, session).run()
        self.assertEqual(events, ["health", *("execute",) * 5])
        lifecycle.reset.assert_not_called()
        self.assertTrue(result.passed)
        self.assertEqual(result.receipt_count, 7)

    def test_report_is_owner_only_and_does_not_claim_manual_proof(self) -> None:
        module = load_module()
        config = SimpleNamespace(range_instance="kep-356-b1", participant="operator")
        result = module.Module10Result(
            True,
            7,
            (module.Module10PhaseResult("test-module-10-awards", "PASS", 7),),
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "module-10-smoke.json"
            module._write_report(path, config, result)
            payload = json.loads(path.read_text(encoding="utf-8"))
            mode = stat.S_IMODE(path.stat().st_mode)
        self.assertEqual(mode, 0o600)
        self.assertEqual(payload["assurance"], "pre-playtest-one-pass")
        self.assertNotIn("manual", payload)
        self.assertNotIn("golden", payload)


if __name__ == "__main__":
    unittest.main()
