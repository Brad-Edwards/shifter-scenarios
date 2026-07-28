from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_ROOT = PACK_ROOT / "assets/services/keplerops-runtime"
sys.path.insert(0, str(RUNTIME_ROOT))

from green_activity.service import GreenActivityService
from raes_contracts.runtime_state import ApplyResult, RuntimeSnapshot


class FakeEngine:
    def __init__(self) -> None:
        self.runs = 0
        self.controls: list[tuple[str, int | None]] = []

    def run_next_due(self) -> ApplyResult:
        self.runs += 1
        return ApplyResult(success=True, snapshot=RuntimeSnapshot())

    def control(self, action: str, *, reset_generation: int | None = None) -> ApplyResult:
        self.controls.append((action, reset_generation))
        return ApplyResult(success=True, snapshot=RuntimeSnapshot())

    def status(self) -> dict[str, object]:
        return {
            "lifecycle": "running",
            "accepting_new_work": True,
            "in_flight": 0,
            "reset_generation": 65,
            "attempted_actions": self.runs,
        }

    def seconds_until_next_due(self) -> float:
        return 3600


class GreenActivityServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        token_file = Path(self.tempdir.name) / "service-token"
        token_file.write_text("operator-token\n", encoding="utf-8")
        self.engine = FakeEngine()
        self.service = GreenActivityService(self.engine, token_file=token_file)

    def test_authenticates_control_and_exposes_raes_readback(self) -> None:
        self.assertEqual(self.service.health()["status"], "ok")
        with self.assertRaises(PermissionError):
            self.service.run_once("wrong-token")
        self.assertEqual(
            self.service.run_once("operator-token")["attempted_actions"],
            1,
        )
        self.assertTrue(self.service.control("drain", "operator-token")["success"])
        self.assertEqual(self.engine.controls, [("drain", None)])

    def test_reset_requires_explicit_generation(self) -> None:
        with self.assertRaises(ValueError):
            self.service.control("reset", "operator-token")
        self.service.control("reset", "operator-token", reset_generation=66)

        self.assertEqual(self.engine.controls[-1], ("reset", 66))
