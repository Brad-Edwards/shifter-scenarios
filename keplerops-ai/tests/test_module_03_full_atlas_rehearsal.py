from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


PACK_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PACK_ROOT / "tests/module_03_full_atlas_rehearsal.py"
TESTS_ROOT = MODULE_PATH.parent
if str(TESTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTS_ROOT))
if str(PACK_ROOT) not in sys.path:
    sys.path.insert(0, str(PACK_ROOT))


def load_module():
    spec = importlib.util.spec_from_file_location(
        "keplerops_module_03_full_atlas_rehearsal", MODULE_PATH
    )
    if spec is None or spec.loader is None:
        raise AssertionError("unable to load module-03 full-ATLAS rehearsal")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class Module03FullAtlasRehearsalTests(unittest.TestCase):
    def test_controls_tolerate_already_satisfied_prepared_receipts(self) -> None:
        module = load_module()
        controls_program = module.participant_programs()[0]

        self.assertIn(
            'expected=(200, 409)',
            controls_program,
        )

    def test_awards_phase_counts_missing_receipts_without_crashing(self) -> None:
        module = load_module()
        awards_program = module.participant_programs()[3]

        self.assertIn("def verify_receipt(flag_id):", awards_program)
        self.assertIn('expected=(200, 409)', awards_program)
        self.assertIn('if "receipt" not in issued:', awards_program)


if __name__ == "__main__":
    unittest.main()
