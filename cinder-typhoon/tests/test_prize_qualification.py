from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(TEST_ROOT))
import test_prize_evaluator


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load test module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


QUALIFICATION_PATH = Path(
    os.environ.get(
        "CINDER_PRIZE_QUALIFICATION_PATH",
        ROOT / "build" / "prize-qualification" / "qualify.py",
    )
)
UI_PATH = Path(os.environ.get("CINDER_PRIZE_UI_PATH", ROOT / "ctfd" / "prize_ui.py"))
qualification = _load_module("cinder_prize_qualification_tests", QUALIFICATION_PATH)
prize_ui = _load_module("cinder_prize_ui_tests", UI_PATH)


ORIGIN = "https://event.example.test"
VIEW_TIME = "2026-06-01T12:30:00Z"


class PrizeQualificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = qualification.StagingFixture()
        cls.candidate_path = ROOT / "build" / "prize-qualification" / "candidate.json"
        cls.summary_path = ROOT / "build" / "prize-qualification" / "summary.json"

    def test_candidate_pins_every_automation_input_and_rejects_drift(self) -> None:
        candidate = json.loads(self.candidate_path.read_text(encoding="utf-8"))
        qualification.validate_candidate(candidate, self.fixture)
        self.assertEqual(candidate["participant_history_count"], 320)
        self.assertEqual(candidate["lifecycle"]["slot_count"], 50)
        self.assertEqual(
            {row["path"] for row in candidate["automation"]},
            set(qualification.AUTOMATION_PATHS),
        )
        changed = deepcopy(candidate)
        changed["automation"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(qualification.QualificationError, "pinned"):
            qualification.validate_candidate(changed, self.fixture)

    def test_rendered_participant_and_staff_claim_flow_escapes_untrusted_alias(
        self,
    ) -> None:
        base = test_prize_evaluator.PrizeEvaluatorFixture()
        source = deepcopy(base.source)
        source["participants"][0]["public_alias"] = '<script>alert("alias")</script>'
        snapshot = test_prize_evaluator.prize_inputs.build_prize_input(
            base.policy,
            source,
        )
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "prizes.sqlite3"
            test_prize_evaluator.prize_evaluator.evaluate_snapshot(
                policy=base.policy,
                snapshot=snapshot,
                state_path=state,
                seed=test_prize_evaluator.SEED,
                nomination_input=base.nominations,
            )
            claims = prize_ui.prize_claims
            service = claims.PrizeClaimService(
                config=claims.build_claim_config(
                    policy=base.policy,
                    snapshot=snapshot,
                    public_origin=ORIGIN,
                ),
                state_path=state,
                token_key=b"u" * 32,
            )
            ui = prize_ui.PrizeEventUI(service)
            participant = prize_ui.AuthenticatedParticipant(
                event_id=test_prize_evaluator.EVENT_ID,
                participant_id=base.participant_ids[0],
                session_id="qualified-participant-session",
                origin=ORIGIN,
            )
            page = ui.participant_page(participant, issue_code=True, now=VIEW_TIME)
            code = qualification._claim_code(page)
            staff = prize_ui.AuthenticatedEventStaff(
                event_id=test_prize_evaluator.EVENT_ID,
                staff_id="qualified-staff",
                can_manage_prizes=True,
                is_event_admin=True,
                origin=ORIGIN,
            )
            request_id = str(UUID(int=7_000_000))
            receipt = ui.claim_receipt(
                staff,
                claim_code=code,
                pack_number=1,
                request_id=request_id,
                now=VIEW_TIME,
            )
            self.assertNotIn("<script>", receipt)
            self.assertIn("&lt;script&gt;", receipt)
            operator = ui.operator_page(
                staff,
                csrf_token='csrf"><script>alert(1)</script>',
                request_id=str(UUID(int=7_000_001)),
            )
            self.assertEqual(operator.count("<tr>"), 51)
            self.assertIn('max="50"', operator)
            self.assertNotIn('csrf"><script>', operator)
            self.assertIn("csrf&quot;&gt;&lt;script&gt;", operator)
            self.assertNotIn(base.participant_ids[0], page)
            with self.assertRaisesRegex(prize_ui.PrizeUIError, "claim service"):
                prize_ui.PrizeEventUI(object())
            with self.assertRaisesRegex(prize_ui.PrizeUIError, "request UUID"):
                ui.operator_page(staff, csrf_token="csrf", request_id="not-a-uuid")

    def test_committed_summary_is_reproducible_and_credential_free(self) -> None:
        expected = json.loads(self.summary_path.read_text(encoding="utf-8"))
        actual = qualification.qualify(self.candidate_path)
        self.assertEqual(actual, expected)
        self.assertEqual(actual["status"], "passed")
        self.assertEqual(actual["participant_history_count"], 320)
        self.assertEqual(actual["claimed_pack_count"], 50)
        self.assertTrue(all(actual["assertions"].values()))
        qualification._assert_credential_free(actual)

    def test_credential_free_summary_rejects_private_identity(self) -> None:
        changed = json.loads(self.summary_path.read_text(encoding="utf-8"))
        changed["private_identity"] = test_prize_evaluator.EVENT_ID
        with self.assertRaisesRegex(
            qualification.QualificationError,
            "participant identity",
        ):
            qualification._assert_credential_free(changed)

    def test_day_of_runbook_contains_only_handover_monitoring_and_recovery(
        self,
    ) -> None:
        runbook = (
            ROOT / "build" / "prize-qualification" / "day-of-runbook.md"
        ).read_text(encoding="utf-8")
        for required in (
            "Keep the authorized 50-slot operator dashboard open.",
            "Scan or enter that value",
            "reasoned custody correction",
            "Do not calculate winners",
        ):
            self.assertIn(required, runbook)
        for forbidden in ("=RANK(", "RAND()", "random.org", "CSV export"):
            self.assertNotIn(forbidden, runbook)


if __name__ == "__main__":
    unittest.main()
