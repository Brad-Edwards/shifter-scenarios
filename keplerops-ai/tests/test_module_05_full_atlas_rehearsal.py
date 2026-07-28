from __future__ import annotations

import importlib.util
import ast
import json
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


PACK_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PACK_ROOT / "tests/module_05_full_atlas_rehearsal.py"
TESTS_ROOT = MODULE_PATH.parent
if str(TESTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTS_ROOT))
if str(PACK_ROOT) not in sys.path:
    sys.path.insert(0, str(PACK_ROOT))


def load_module():
    spec = importlib.util.spec_from_file_location(
        "keplerops_module_05_full_atlas_rehearsal", MODULE_PATH
    )
    if spec is None or spec.loader is None:
        raise AssertionError("unable to load module-05 full-ATLAS rehearsal")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class Module05FullAtlasRehearsalTests(unittest.TestCase):
    def test_identity_phase_preserves_gateway_bearer_token(self) -> None:
        module = load_module()
        _, identity_phase, *_ = module.participant_programs()
        tree = ast.parse(identity_phase)

        token_assignments_after_login = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name) and target.id == "token"
        ]

        self.assertEqual(len(token_assignments_after_login), 1)

    def test_main_writes_report_for_successful_existing_range(self) -> None:
        module = load_module()
        result = module.Module05FullAtlasResult(
            passed=True,
            receipt_count=len(module.CHALLENGES),
            phases=(
                module.Module05FullAtlasPhaseResult(
                    "test-m05-fa-controls", "PASS", 16
                ),
                module.Module05FullAtlasPhaseResult(
                    "test-m05-fa-identity", "PASS", 4
                ),
                module.Module05FullAtlasPhaseResult(
                    "test-m05-fa-workers", "PASS", 5
                ),
                module.Module05FullAtlasPhaseResult(
                    "test-m05-fa-awards", "PASS", len(module.CHALLENGES)
                ),
            ),
        )

        with tempfile.TemporaryDirectory() as temporary:
            operator_root = Path(temporary)
            fake_config = SimpleNamespace(
                range_instance="kep-482-r3",
                participant="operator",
                use_existing_range=True,
                retain_until_phase_e=True,
            )
            fake_lifecycle = mock.Mock()
            fake_lifecycle.operator_root = operator_root
            fake_lifecycle.terraform_output.return_value = "https://participant.local"

            with (
                mock.patch.object(module.RunConfig, "from_namespace", return_value=fake_config),
                mock.patch.object(module, "CommandLifecycle", return_value=fake_lifecycle),
                mock.patch.object(module, "PlaywrightKasmSession", return_value=mock.Mock()),
                mock.patch.object(module.Module05FullAtlasRunner, "run", return_value=result),
                mock.patch.object(
                    sys,
                    "argv",
                    [
                        "module_05_full_atlas_rehearsal.py",
                        "--project-id", "prod-ksqdkj",
                        "--range-instance", "kep-482-r3",
                        "--participant", "operator",
                        "--participant-source-cidr", "203.0.113.10/32",
                        "--use-existing-range",
                        "--retain-until-phase-e",
                    ],
                ),
            ):
                self.assertEqual(module.main(), 0)

            report = operator_root / "module-05-full-atlas-smoke.json"
            payload = json.loads(report.read_text(encoding="utf-8"))
            mode = stat.S_IMODE(report.stat().st_mode)

        self.assertEqual(payload["verdict"], "PASS")
        self.assertEqual(payload["challenge_count"], len(module.CHALLENGES))
        self.assertEqual(payload["receipt_count"], len(module.CHALLENGES))
        self.assertEqual(payload["reset_scope"], "canonical-range")
        self.assertEqual(mode, 0o600)


if __name__ == "__main__":
    unittest.main()
