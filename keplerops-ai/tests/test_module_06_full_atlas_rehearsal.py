from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


PACK_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PACK_ROOT / "tests/module_06_full_atlas_rehearsal.py"
TESTS_ROOT = MODULE_PATH.parent
if str(TESTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTS_ROOT))
if str(PACK_ROOT) not in sys.path:
    sys.path.insert(0, str(PACK_ROOT))


def load_module():
    spec = importlib.util.spec_from_file_location(
        "keplerops_module_06_full_atlas_rehearsal", MODULE_PATH
    )
    if spec is None or spec.loader is None:
        raise AssertionError("unable to load module-06 full-ATLAS rehearsal")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class Module06FullAtlasRehearsalTests(unittest.TestCase):
    def test_awards_phase_seeds_cross_module_prerequisites_before_receipts(self) -> None:
        module = load_module()
        award_program = module.participant_programs()[4]

        self.assertIn('"challenge_id": "kep-m03-a"', award_program)
        self.assertIn('"challenge_id": "kep-m06-a"', award_program)
        self.assertIn("seed_prerequisites()", award_program)
        self.assertLess(
            award_program.index("seed_prerequisites()"),
            award_program.index('gateway + "/v1/adversarial/receipts/"'),
        )

    def test_hardware_edge_acquisition_is_out_of_software_scope(self) -> None:
        module = load_module()

        self.assertNotIn("kep-m06-m", module.CHALLENGES)
        self.assertNotIn("kep-m06-m", module.FLAGS)
        self.assertEqual(len(module.CHALLENGES), 15)


if __name__ == "__main__":
    unittest.main()
