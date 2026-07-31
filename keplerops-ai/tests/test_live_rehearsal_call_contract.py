from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


PACK_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PACK_ROOT / "tests/live_rehearsal.py"
TESTS_ROOT = MODULE_PATH.parent
if str(TESTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTS_ROOT))


def load_module():
    spec = importlib.util.spec_from_file_location(
        "keplerops_live_rehearsal_contract", MODULE_PATH
    )
    if spec is None or spec.loader is None:
        raise AssertionError("unable to load live rehearsal module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class LiveRehearsalCallContractTests(unittest.TestCase):
    def test_participant_call_accepts_multiple_expected_statuses(self) -> None:
        module = load_module()
        program = module.initial_participant_program()

        self.assertIn("expected_statuses =", program)
        self.assertIn("if status in expected_statuses:", program)


if __name__ == "__main__":
    unittest.main()
