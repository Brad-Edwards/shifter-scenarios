#!/usr/bin/env python3
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import importlib.util
import json
import pathlib
import unittest

HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("w17_check_evidence", HERE / "check_evidence.py")
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load W17 evidence evaluator")
check_evidence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_evidence)

BASE = dt.datetime(2026, 11, 13, 12, 0, tzinfo=dt.timezone.utc)
VALUES = {
    "LevelM": 8.0, "UsableVolumeML": 14.0,
    "PositionPct": 40.0, "PositionBPct": 60.0,
    "FlowM3s": 0.2, "FlowBM3s": 0.3, "TotalFlowM3s": 0.5,
    "RequestedTargetPct": 40.0, "RequestedTargetBPct": 60.0,
    "RequestedFlowM3s": 0.5, "AutoMode": 0, "Owner": 1,
    "IoHealthy": 1, "PermissiveA": 1, "PermissiveB": 1,
}


def timestamp(seconds: int) -> str:
    return (BASE + dt.timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")


def snapshot() -> dict:
    samples = []
    for second in range(0, 21):
        for variable, value in VALUES.items():
            samples.append({"variable": variable, "source_time": timestamp(second),
                            "value": value, "unit": "", "quality": "Good"})
    instrument = check_evidence.CONTRACT["instrument"]
    return {
        "schema": "arwc.native-product-observation/v1",
        "asset": "AST-CRR-017",
        "captured_at": timestamp(21),
        "source_digest": hashlib.sha256(json.dumps(samples, sort_keys=True).encode()).hexdigest(),
        "catalog": {"FlowBM3s": {"node_id": instrument["node_id"],
                                     "series": instrument["historian_series"],
                                     "unit": instrument["unit"]}},
        "samples": samples,
    }


def evaluate_product_evidence(card: str, submission: dict, product: dict) -> dict:
    """Name the read-only evaluator boundary for the coverage ledger."""

    return check_evidence.evaluate(card, submission, product)


def submissions() -> dict[str, dict]:
    return {
        "W17.1": {
            "asset": "AST-CRR-017", "observed_at": timestamp(10),
            "measured": {"level_m": 8.0, "usable_volume_ml": 14.0,
                         "outlet_a_position_pct": 40.0, "outlet_b_position_pct": 60.0,
                         "outlet_a_flow_m3s": 0.2, "outlet_b_flow_m3s": 0.3,
                         "total_flow_m3s": 0.5},
            "accepted_settings": {"outlet_a_position_pct": 40.0,
                                  "outlet_b_position_pct": 60.0,
                                  "total_flow_m3s": 0.5},
        },
        "W17.2": {"asset": "AST-CRR-017", "observed_at": timestamp(10),
                   "mode": "manual", "owner": "hmi", "field_data": "healthy",
                   "permissive_a": True, "permissive_b": True},
        "W17.3": dict(check_evidence.CONTRACT["instrument"]),
        "W17.4": {"asset": "AST-CRR-017", "start": timestamp(0), "end": timestamp(20),
                   "hmi_variable": "FlowBM3s",
                   "opcua_node": "nsu=urn:arwc:crr:tags;s=CRR.FlowBM3s",
                   "historian_series": "flow_b_m3s",
                   "summary": {"first_flow_m3s": 0.3, "last_flow_m3s": 0.3,
                               "minimum_flow_m3s": 0.3, "maximum_flow_m3s": 0.3,
                               "sample_count": 21}},
    }


class W17ContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.product = snapshot()
        self.submissions = submissions()

    def test_all_four_cards_use_native_product_records(self) -> None:
        with self.subTest(card="W17.1 the reservoir's present tense"):
            result = evaluate_product_evidence("W17.1", self.submissions["W17.1"], self.product)
            self.assertTrue(result["satisfied"])
        with self.subTest(card="W17.2 the mode the plant is in"):
            result = evaluate_product_evidence("W17.2", self.submissions["W17.2"], self.product)
            self.assertTrue(result["satisfied"])
        with self.subTest(card="W17.3 the instrument in the note"):
            result = evaluate_product_evidence("W17.3", self.submissions["W17.3"], self.product)
            self.assertTrue(result["satisfied"])
        with self.subTest(card="W17.4 the first live trace"):
            result = evaluate_product_evidence("W17.4", self.submissions["W17.4"], self.product)
            self.assertTrue(result["satisfied"])

    def test_participant_cannot_supply_product_evidence(self) -> None:
        with self.assertRaises(check_evidence.EvidenceError):
            check_evidence.evaluate("W17.1", {"product_snapshot": self.product}, self.product)

    def test_wrong_quality_is_rejected(self) -> None:
        for row in self.product["samples"]:
            if row["variable"] == "FlowBM3s":
                row["quality"] = "FieldUnavailable"
        submission = {"asset": "AST-CRR-017", "start": timestamp(0), "end": timestamp(20),
                      "hmi_variable": "FlowBM3s",
                      "opcua_node": "nsu=urn:arwc:crr:tags;s=CRR.FlowBM3s",
                      "historian_series": "flow_b_m3s",
                      "summary": {"first_flow_m3s": 0.3, "last_flow_m3s": 0.3,
                                  "minimum_flow_m3s": 0.3, "maximum_flow_m3s": 0.3,
                                  "sample_count": 21}}
        with self.assertRaises(check_evidence.EvidenceError):
            check_evidence.evaluate("W17.4", submission, self.product)

    def test_missing_independent_series_is_rejected(self) -> None:
        self.product["samples"] = [row for row in self.product["samples"] if row["variable"] != "PositionBPct"]
        submission = {"asset": "AST-CRR-017", "start": timestamp(0), "end": timestamp(20),
                      "hmi_variable": "FlowBM3s",
                      "opcua_node": "nsu=urn:arwc:crr:tags;s=CRR.FlowBM3s",
                      "historian_series": "flow_b_m3s",
                      "summary": {"first_flow_m3s": 0.3, "last_flow_m3s": 0.3,
                                  "minimum_flow_m3s": 0.3, "maximum_flow_m3s": 0.3,
                                  "sample_count": 21}}
        with self.assertRaises(check_evidence.EvidenceError):
            check_evidence.evaluate("W17.4", submission, self.product)

    def test_wrong_asset_and_stale_observation_are_rejected(self) -> None:
        wrong_asset = copy.deepcopy(self.submissions["W17.1"])
        wrong_asset["asset"] = "AST-OTHER-001"
        with self.assertRaises(check_evidence.EvidenceError):
            check_evidence.evaluate("W17.1", wrong_asset, self.product)

        stale = copy.deepcopy(self.submissions["W17.1"])
        stale["observed_at"] = timestamp(600)
        with self.assertRaises(check_evidence.EvidenceError):
            check_evidence.evaluate("W17.1", stale, self.product)

    def test_read_only_reset_contract_leaves_product_state_unchanged(self) -> None:
        before = copy.deepcopy(self.product)
        first = check_evidence.evaluate("W17.4", self.submissions["W17.4"], self.product)
        second = check_evidence.evaluate("W17.4", self.submissions["W17.4"], self.product)
        self.assertEqual(first, second)
        self.assertEqual(self.product, before)


if __name__ == "__main__":
    unittest.main()
