from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


PACK_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PACK_ROOT / "tests/module_07_full_atlas_rehearsal.py"
TESTS_ROOT = MODULE_PATH.parent
if str(TESTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTS_ROOT))
if str(PACK_ROOT) not in sys.path:
    sys.path.insert(0, str(PACK_ROOT))


def load_module():
    spec = importlib.util.spec_from_file_location(
        "keplerops_module_07_full_atlas_rehearsal", MODULE_PATH
    )
    if spec is None or spec.loader is None:
        raise AssertionError("unable to load module-07 full-ATLAS rehearsal")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class Module07FullAtlasRehearsalTests(unittest.TestCase):
    def test_awards_phase_seeds_real_prerequisite_evidence_before_receipts(self) -> None:
        module = load_module()
        award_program = module.participant_programs()[2]

        self.assertIn('dataset("kep-m07-a"', award_program)
        self.assertIn('train("kep-m07-b"', award_program)
        self.assertIn('attempt("kep-m07-b"', award_program)
        self.assertIn(f"range({module.TRAINING_JOB_POLL_SECONDS})", award_program)
        self.assertNotIn("range(120)", award_program)
        self.assertIn("seed_prerequisites()", award_program)
        self.assertLess(
            award_program.index("seed_prerequisites()"),
            award_program.index('gateway + "/v1/training/receipts/"'),
        )


if __name__ == "__main__":
    unittest.main()
