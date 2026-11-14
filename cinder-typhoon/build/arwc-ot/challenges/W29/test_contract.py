#!/usr/bin/env python3
from __future__ import annotations

import copy
import datetime as dt
import importlib.util
import pathlib
import unittest


HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("w29_evidence", HERE / "check_evidence.py")
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load W29 evidence evaluator")
evidence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evidence)

BASE = dt.datetime(2026, 11, 13, 20, 0, tzinfo=dt.timezone.utc)


def timestamp(seconds: int) -> str:
    return (BASE + dt.timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")


CORPORATE = {
    "tariff": {**copy.deepcopy(evidence.CONTRACT["tariff"]), "planning_window": "ALLOC-2026-DP3", "asset": "AST-CRR-017"},
    "allocation": {**copy.deepcopy(evidence.CONTRACT["allocation"]), "planning_window": "ALLOC-2026-DP3", "asset": "AST-CRR-017"},
    "report": {**copy.deepcopy(evidence.CONTRACT["report"]), "planning_window": "ALLOC-2026-DP3", "asset": "AST-CRR-017"},
}
SNAPSHOT = {
    "schema": "arwc.native-allocation-reconciliation/v1", "asset": "AST-CRR-017",
    "captured_at": timestamp(2), "source_digest": "a" * 64, "corporate_digest": "b" * 64,
    "corporate": CORPORATE,
    "samples": [{
        "variable": "UsableVolumeML", "source_time": timestamp(1),
        "collected_time": timestamp(1), "ingested_at": timestamp(2),
        "value": 13.92, "unit": "ML", "quality": "Good",
    }],
}
CARD_1 = {
    "planning_window": "ALLOC-2026-DP3", "asset": "AST-CRR-017",
    "tariff": copy.deepcopy(evidence.CONTRACT["tariff"]),
    "allocation": copy.deepcopy(evidence.CONTRACT["allocation"]),
}
CARD_2 = {
    "planning_window": "ALLOC-2026-DP3", "asset": "AST-CRR-017", "observed_at": timestamp(1),
    "process_quality": "Good", "measured_usable_volume_ml": 13.92, "committed_ml": 12.0,
    "uncommitted_margin_ml": 1.92, "margin_state": "positive",
}
CARD_3 = {
    "planning_window": "ALLOC-2026-DP3", "asset": "AST-CRR-017",
    "report_id": "RPT-CRR-DP3-R7", "report_as_of": "2026-11-09T00:00:00Z",
    "reported_ml": 13.4, "observed_at": timestamp(1), "measured_usable_volume_ml": 13.92,
    "signed_paper_variance_ml": -0.52, "direction": "report_below_later_process_value",
    "time_basis": "different_as_of_times", "conclusion": "paper_report_is_not_current_process_truth",
}


def evaluate_product_evidence(card: str, submission: dict, product: dict) -> dict:
    """Name the read-only evaluator boundary for the coverage ledger."""

    return evidence.evaluate(card, submission, product)


class ContractTests(unittest.TestCase):
    def test_all_three_cards_use_corporate_and_native_product_records(self):
        with self.subTest(card="W29.1 the price of this planning window"):
            self.assertTrue(evaluate_product_evidence("W29.1", copy.deepcopy(CARD_1), copy.deepcopy(SNAPSHOT))["satisfied"])
        with self.subTest(card="W29.2 what reserve remains uncommitted"):
            self.assertTrue(evaluate_product_evidence("W29.2", copy.deepcopy(CARD_2), copy.deepcopy(SNAPSHOT))["satisfied"])
        with self.subTest(card="W29.3 paper truth"):
            self.assertTrue(evaluate_product_evidence("W29.3", copy.deepcopy(CARD_3), copy.deepcopy(SNAPSHOT))["satisfied"])

    def test_bad_quality_or_stale_observation_is_rejected(self):
        bad_quality = copy.deepcopy(SNAPSHOT)
        bad_quality["samples"][0]["quality"] = "FieldUnavailable"
        with self.assertRaises(evidence.EvidenceError):
            evidence.evaluate("W29.2", copy.deepcopy(CARD_2), bad_quality)
        stale = copy.deepcopy(CARD_2)
        stale["observed_at"] = timestamp(300)
        with self.assertRaises(evidence.EvidenceError):
            evidence.evaluate("W29.2", stale, copy.deepcopy(SNAPSHOT))

    def test_wrong_corporate_record_or_signed_variance_is_rejected(self):
        wrong_record = copy.deepcopy(SNAPSHOT)
        wrong_record["corporate"]["allocation"]["committed_ml"] = 11.0
        with self.assertRaises(evidence.EvidenceError):
            evidence.evaluate("W29.1", copy.deepcopy(CARD_1), wrong_record)
        wrong_sign = copy.deepcopy(CARD_3)
        wrong_sign["signed_paper_variance_ml"] = 0.52
        wrong_sign["direction"] = "report_above_later_process_value"
        with self.assertRaises(evidence.EvidenceError):
            evidence.evaluate("W29.3", wrong_sign, copy.deepcopy(SNAPSHOT))

    def test_participant_cannot_supply_product_evidence(self):
        submission = copy.deepcopy(CARD_3)
        submission["product_snapshot"] = copy.deepcopy(SNAPSHOT)
        with self.assertRaises(evidence.EvidenceError):
            evidence.evaluate("W29.3", submission, copy.deepcopy(SNAPSHOT))

    def test_read_only_reset_contract_leaves_product_state_unchanged(self):
        product = copy.deepcopy(SNAPSHOT)
        before = copy.deepcopy(product)
        first = evidence.evaluate("W29.3", copy.deepcopy(CARD_3), product)
        second = evidence.evaluate("W29.3", copy.deepcopy(CARD_3), product)
        self.assertEqual(first, second)
        self.assertEqual(product, before)


if __name__ == "__main__":
    unittest.main()
