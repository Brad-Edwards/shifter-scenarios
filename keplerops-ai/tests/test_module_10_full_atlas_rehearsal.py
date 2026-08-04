from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


PACK_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PACK_ROOT / "tests/module_10_full_atlas_programs.py"
TESTS_ROOT = MODULE_PATH.parent
if str(TESTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTS_ROOT))
if str(PACK_ROOT) not in sys.path:
    sys.path.insert(0, str(PACK_ROOT))


def load_module():
    spec = importlib.util.spec_from_file_location(
        "keplerops_module_10_full_atlas_programs", MODULE_PATH
    )
    if spec is None or spec.loader is None:
        raise AssertionError("unable to load module-10 full-ATLAS programs")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class Module10FullAtlasRehearsalTests(unittest.TestCase):
    def test_runner_reconstructs_real_capstone_state_when_missing(self) -> None:
        module = load_module()
        controls_program = module.participant_programs()[0]

        self.assertIn("def ensure_capstone_base_prerequisites()", controls_program)
        self.assertIn("def build_capstone_state()", controls_program)
        self.assertIn('job.get("status") == "succeeded"', controls_program)
        self.assertIn('job.get("status") != "queued"', controls_program)
        self.assertIn('"/v1/backdoor/promotions"', controls_program)
        self.assertIn('"/v1/backdoor/reloads"', controls_program)
        self.assertIn('"/v1/capstone/inference"', controls_program)
        self.assertIn('"/v1/capstone/effects"', controls_program)
        self.assertIn('"/v1/adversarial/artifacts"', controls_program)
        self.assertIn("for attempt in range(4)", controls_program)
        self.assertIn("identity token unavailable", controls_program)
        self.assertNotIn("def read_capstone_state()", controls_program)


if __name__ == "__main__":
    unittest.main()
