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
SPEC = importlib.util.spec_from_file_location("w18_check_evidence", HERE / "check_evidence.py")
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load W18 evidence evaluator")
check_evidence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_evidence)

BASE = dt.datetime(2026, 11, 13, 12, 0, tzinfo=dt.timezone.utc)
VALUES = {
    "LevelM": 8.0, "PositionPct": 40.0, "PositionBPct": 60.0,
    "FlowM3s": 0.2, "FlowBM3s": 0.3, "ProjectRevision": 364,
}
SERIES = {
    "LevelM": ("level_m", "m"), "PositionPct": ("position_pct", "%"),
    "PositionBPct": ("position_b_pct", "%"), "FlowM3s": ("flow_m3s", "m3/s"),
    "FlowBM3s": ("flow_b_m3s", "m3/s"), "ProjectRevision": ("project_revision", "revision"),
}


def timestamp(seconds: float) -> str:
    return (BASE + dt.timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")


def scaling() -> dict:
    return {
        "inputs": [
            {"offset": 0, "iec": "%IW0", "variable": "LevelRaw", "type": "UINT", "unit": "m", "counts_per_unit": 1000},
            {"offset": 1, "iec": "%IW1", "variable": "PositionRaw", "type": "UINT", "unit": "%", "counts_per_unit": 100},
            {"offset": 2, "iec": "%IW2", "variable": "FlowRaw", "type": "UINT", "unit": "m3/s", "counts_per_unit": 10000},
            {"offset": 3, "iec": "%IW3", "variable": "Heartbeat", "type": "UINT", "unit": "count", "counts_per_unit": 1},
            {"offset": 4, "iec": "%IW4", "variable": "PositionBRaw", "type": "UINT", "unit": "%", "counts_per_unit": 100},
            {"offset": 5, "iec": "%IW5", "variable": "FlowBRaw", "type": "UINT", "unit": "m3/s", "counts_per_unit": 10000},
        ],
        "functions": {"inputs": 4, "discrete_inputs": 2, "outputs": 16, "coils": 15},
    }


def snapshot() -> dict:
    register_digest = hashlib.sha256(b"CRR-IO-R364").hexdigest()
    catalog = []
    for variable, (series, unit) in SERIES.items():
        catalog.append({
            "variable": variable, "series": series,
            "node_id": f"nsu=urn:arwc:crr:tags;s=CRR.{variable}",
            "unit": unit, "register_sha256": register_digest,
            "definition": {"variable": variable, "type": "REAL", "unit": unit, "table": series},
            "scaling": scaling(),
        })
    samples = []
    for second in (*range(0, 5), *range(20, 25)):
        for variable, value in VALUES.items():
            series, unit = SERIES[variable]
            samples.append({
                "variable": variable, "source_time": timestamp(second),
                "collected_time": timestamp(second + 0.1), "ingested_at": timestamp(second + 0.2),
                "value": value, "unit": unit, "transport_quality": "Good",
                "process_quality": "Good",
                "node_id": f"nsu=urn:arwc:crr:tags;s=CRR.{variable}",
                "register_sha256": register_digest,
            })
    return {
        "schema": "arwc.native-tag-observation/v1", "asset": "AST-CRR-017",
        "captured_at": timestamp(25),
        "source_digest": hashlib.sha256(json.dumps({"catalog": catalog, "samples": samples}, sort_keys=True).encode()).hexdigest(),
        "catalog": catalog, "samples": samples,
    }


def evaluate_product_evidence(card: str, submission: dict, product: dict) -> dict:
    """Name the read-only evaluator boundary for the coverage ledger."""

    return check_evidence.evaluate(card, submission, product)


def submissions(product: dict) -> dict[str, dict]:
    register_digest = product["catalog"][0]["register_sha256"]
    return {
        "W18.1": {
            "asset": "AST-CRR-017", "register_id": "CRR-IO-R364",
            "project_revision": 364, "register_sha256": register_digest,
            "variables": ["FlowBM3s", "FlowM3s", "LevelM", "PositionBPct", "PositionPct"],
        },
        "W18.2": copy.deepcopy(check_evidence.CONTRACT["register"]["focus_point"]),
        "W18.3": {
            "variable": "FlowBM3s",
            "before_source_time": timestamp(4), "before_collected_time": timestamp(4.1),
            "before_ingested_at": timestamp(4.2), "after_source_time": timestamp(20),
            "after_collected_time": timestamp(20.1), "after_ingested_at": timestamp(20.2),
            "gap_seconds": 16.0, "before_transport_quality": "Good",
            "before_process_quality": "Good", "after_transport_quality": "Good",
            "after_process_quality": "Good", "unit": "m3/s",
            "interpretation": "source_gap_with_unchanged_engineering_unit",
        },
        "W18.4": {
            "asset": "AST-CRR-017", "outlet_group": "OG-CRR-02",
            "reference": {"instrument": "FIT-CRR-204B", "variable": "FlowBM3s", "source": "W17.OBS"},
            "mapping": copy.deepcopy(check_evidence.CONTRACT["mapping"]["outlets"]),
        },
    }


class W18ContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.product = snapshot()
        self.submissions = submissions(self.product)

    def test_all_four_cards_use_native_product_records(self) -> None:
        with self.subTest(card="W18.1 the tag export"):
            self.assertTrue(evaluate_product_evidence("W18.1", self.submissions["W18.1"], self.product)["satisfied"])
        with self.subTest(card="W18.2 the scale kept elsewhere"):
            self.assertTrue(evaluate_product_evidence("W18.2", self.submissions["W18.2"], self.product)["satisfied"])
        with self.subTest(card="W18.3 three clocks and a gap"):
            self.assertTrue(evaluate_product_evidence("W18.3", self.submissions["W18.3"], self.product)["satisfied"])
        with self.subTest(card="W18.4 which outlet answers"):
            self.assertTrue(evaluate_product_evidence("W18.4", self.submissions["W18.4"], self.product)["satisfied"])

    def test_participant_cannot_supply_product_evidence(self) -> None:
        with self.assertRaises(check_evidence.EvidenceError):
            check_evidence.evaluate("W18.1", {"product_snapshot": self.product}, self.product)

    def test_catalog_digest_and_scaling_must_match_product(self) -> None:
        wrong_digest = copy.deepcopy(self.submissions["W18.1"])
        wrong_digest["register_sha256"] = "0" * 64
        with self.assertRaises(check_evidence.EvidenceError):
            check_evidence.evaluate("W18.1", wrong_digest, self.product)
        for entry in self.product["catalog"]:
            if entry["variable"] == "FlowBM3s":
                entry["scaling"]["inputs"][5]["counts_per_unit"] = 8000
        with self.assertRaises(check_evidence.EvidenceError):
            check_evidence.evaluate("W18.2", self.submissions["W18.2"], self.product)

    def test_gap_requires_product_timestamps_and_good_quality(self) -> None:
        wrong_time = copy.deepcopy(self.submissions["W18.3"])
        wrong_time["after_ingested_at"] = timestamp(21)
        with self.assertRaises(check_evidence.EvidenceError):
            check_evidence.evaluate("W18.3", wrong_time, self.product)

        no_gap = copy.deepcopy(self.product)
        no_gap["samples"] = [
            row for row in no_gap["samples"]
            if (check_evidence._time(row["source_time"]) - BASE).total_seconds() < 5
        ]
        with self.assertRaises(check_evidence.EvidenceError):
            check_evidence.evaluate("W18.3", self.submissions["W18.3"], no_gap)

        bad_quality = copy.deepcopy(self.product)
        for row in bad_quality["samples"]:
            if row["variable"] == "FlowBM3s" and row["source_time"] == timestamp(20):
                row["process_quality"] = "FieldUnavailable"
        with self.assertRaises(check_evidence.EvidenceError):
            check_evidence.evaluate("W18.3", self.submissions["W18.3"], bad_quality)

    def test_swapped_outlet_mapping_is_rejected(self) -> None:
        swapped = copy.deepcopy(self.submissions["W18.4"])
        swapped["mapping"][0]["instrument"], swapped["mapping"][1]["instrument"] = (
            swapped["mapping"][1]["instrument"], swapped["mapping"][0]["instrument"],
        )
        with self.assertRaises(check_evidence.EvidenceError):
            check_evidence.evaluate("W18.4", swapped, self.product)

    def test_outlet_mapping_requires_time_aligned_product_series(self) -> None:
        misaligned = copy.deepcopy(self.product)
        for row in misaligned["samples"]:
            if row["variable"] == "PositionBPct":
                row["source_time"] = (
                    check_evidence._time(row["source_time"]) + dt.timedelta(seconds=100)
                ).isoformat()
                row["collected_time"] = (
                    check_evidence._time(row["collected_time"]) + dt.timedelta(seconds=100)
                ).isoformat()
                row["ingested_at"] = (
                    check_evidence._time(row["ingested_at"]) + dt.timedelta(seconds=100)
                ).isoformat()
        with self.assertRaises(check_evidence.EvidenceError):
            check_evidence.evaluate("W18.4", self.submissions["W18.4"], misaligned)

    def test_read_only_reset_contract_leaves_product_state_unchanged(self) -> None:
        before = copy.deepcopy(self.product)
        first = check_evidence.evaluate("W18.4", self.submissions["W18.4"], self.product)
        second = check_evidence.evaluate("W18.4", self.submissions["W18.4"], self.product)
        self.assertEqual(first, second)
        self.assertEqual(self.product, before)


if __name__ == "__main__":
    unittest.main()
