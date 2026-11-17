#!/usr/bin/env python3
from __future__ import annotations

import copy
import datetime as dt
import importlib.util
import pathlib
import unittest


HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("w33_evidence", HERE / "check_evidence.py")
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load W33 evidence evaluator")
evidence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evidence)

BASE = dt.datetime(2026, 11, 13, 12, 0, tzinfo=dt.timezone.utc)
CALIBRATION_ID = "963fdbe4-68d2-418f-ad5e-89a806a90fe6"
REQUEST_IDS = [f"{index:08x}-1234-4abc-8def-{index:012x}" for index in range(1, 13)]
RELEASES = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.35, 0.30, 0.25, 0.20, 0.15, 0.10]
ALTERNATE = [0.35] * 12


def stamp(seconds: float) -> str:
    return (BASE + dt.timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")


def sample(variable: str, seconds: float, value: float, unit: str = "boolean", quality: str = "Good") -> dict:
    return {"variable": variable, "source_time": stamp(seconds), "value": value,
            "unit": unit, "quality": quality}


def request(request_id: str, flow: float, expires: float) -> dict:
    return {"id": request_id, "asset": "AST-CRR-017", "mode": "automatic",
            "position_a_pct": 20.0, "position_b_pct": 20.0,
            "total_flow_m3s": flow, "expires_at": (BASE + dt.timedelta(seconds=expires)).timestamp()}


def transitions(request_id: str, sequence: int, flow: float, start: float) -> list[dict]:
    body = request(request_id, flow, start + 90)
    rows = []
    for offset, status in ((0, "received"), (0.5, "dispatch_intent"), (1, "dispatched"),
                           (2, "plc_accepted"), (6, "completed")):
        rows.append({"time": stamp(start + offset), "id": request_id, "principal": "operator",
                     "sequence": sequence, "status": status, "detail": {"status": status},
                     "request": copy.deepcopy(body),
                     "origin": "Authenticated MQTT dispatcher and observed PLC feedback"})
    return rows


SAMPLES = [sample("TotalFlowM3s", second, 0.3, "m3/s") for second in range(4, 9)]
DISPATCH = transitions(CALIBRATION_ID, 20, 0.3, 0)
COMMANDS = [{"source_time": stamp(2), "channel": "dispatcher", "decision": "accepted",
             "sequence": 20, "native_status": "Good"}]

for index, (request_id, flow) in enumerate(zip(REQUEST_IDS, RELEASES, strict=True)):
    start = 20 + index * 10
    sequence = 30 + index
    DISPATCH.extend(transitions(request_id, sequence, flow, start))
    COMMANDS.append({"source_time": stamp(start + 2), "channel": "dispatcher",
                     "decision": "accepted", "sequence": sequence, "native_status": "Good"})
    for second in range(start + 2, start + 7):
        SAMPLES.append(sample("TotalFlowM3s", second, flow, "m3/s"))

RESTORE_TIME = 141
FINAL_TIME = 145
COMMANDS.append({"source_time": stamp(RESTORE_TIME), "channel": "HMI", "decision": "accepted",
                 "sequence": 90, "native_status": "Good"})
for variable, value, unit in (
    ("HmiAccepted", 90, "count"), ("Owner", 1, "enum"), ("AutoMode", 0, "boolean"),
    ("HmiRemoteEnabled", 0, "boolean"), ("IoHealthy", 1, "boolean"),
    ("PermissiveA", 1, "boolean"), ("PermissiveB", 1, "boolean"),
    ("MovingA", 0, "boolean"), ("MovingB", 0, "boolean"),
    ("TravelFaultA", 0, "boolean"), ("TravelFaultB", 0, "boolean"),
    ("PositionPct", 20.0, "%"), ("PositionBPct", 20.0, "%"),
    ("FlowM3s", 0.1, "m3/s"), ("FlowBM3s", 0.1, "m3/s"),
    ("TotalFlowM3s", 0.2, "m3/s"),
):
    SAMPLES.append(sample(variable, FINAL_TIME, value, unit))
SAMPLES.append(sample("UsableVolumeML", 20, 13.92, "ML"))

CORPORATE = {
    "tariff": {"record_id": "TAR-CRR-DP3-R4", "revision": 4,
                "planning_window": "ALLOC-2026-DP3", "asset": "AST-CRR-017",
                "currency": "USD", "unit": "USD/ML", "rate": 2400.0,
                "effective_from": "2026-11-01T00:00:00Z", "effective_to": "2026-12-01T00:00:00Z"},
    "allocation": {"record_id": "ALLOC-2026-DP3-R9", "revision": 9,
                   "planning_window": "ALLOC-2026-DP3", "asset": "AST-CRR-017",
                   "unit": "ML", "committed_volume": 12.0,
                   "effective_from": "2026-11-01T00:00:00Z", "effective_to": "2026-12-01T00:00:00Z"},
}

SNAPSHOT = {
    "schema": "arwc.native-schedule-observation/v1", "asset": "AST-CRR-017",
    "captured_at": stamp(150), "source_digest": "a" * 64, "corporate_digest": "b" * 64,
    "configuration": {"project_revision": 364, "dispatcher": copy.deepcopy(evidence.CONTRACT["dispatcher"])},
    "samples": SAMPLES, "commands": COMMANDS, "dispatch": DISPATCH, "corporate": CORPORATE,
}

FORECAST = {
    "asset": "AST-CRR-017", "request_id": CALIBRATION_ID,
    "plc_accepted_at": stamp(2), "settled_start": stamp(4), "settled_end": stamp(8),
    "requested_total_flow_m3s": 0.3, "mean_total_flow_m3s": 0.3,
    "response_delay_seconds": 2.0, "flow_gain": 1.0, "good_sample_count": 5,
}
SCHEDULE = {
    "schema": "arwc.operating-schedule/v1", "instruction": "CRR-OP-W33-R1",
    "asset": "AST-CRR-017", "interval_seconds": 300,
    "reservoir_release_m3s": RELEASES, "alternate_supply_m3s": ALTERNATE,
}
CARD_2 = {"forecast": FORECAST, "schedule": SCHEDULE}
COMMISSIONING = {
    "asset": "AST-CRR-017", "forecast": FORECAST, "schedule": SCHEDULE,
    "request_ids": REQUEST_IDS, "started_at": stamp(20), "completed_at": stamp(136),
    "restore_sequence": 90, "restore_accepted_at": stamp(RESTORE_TIME),
    "final_observed_at": stamp(FINAL_TIME),
    "interpretation": "measured_twelve_step_commissioning_run_with_local_handback",
}
CARD_4 = {
    "commissioning": COMMISSIONING, "observed_mean_total_flow_m3s": RELEASES,
    "projected_reservoir_volume_ml": 0.81, "starting_usable_volume_ml": 13.92,
    "remaining_usable_volume_ml": 13.11, "committed_volume_ml": 12.0,
    "projected_shortfall_ml": 0.0, "tariff_rate_per_ml": 2400.0,
    "projected_liability_usd": 0.0,
    "interpretation": "measured_commissioning_evidence_with_projected_one_hour_effect",
}


def evaluate_product_evidence(card: str, submission: dict, product: dict) -> dict:
    """Name the product-owned evaluator boundary for the coverage ledger."""

    return evidence.evaluate(card, submission, product)


def evaluate_after_participant_action(card: str, submission: dict, product: dict) -> dict:
    """Evaluate the product snapshot after the bounded commissioning work."""

    return evidence.evaluate(card, submission, product)


class ContractTests(unittest.TestCase):
    def test_all_cards_use_native_product_records(self):
        with self.subTest(card="W33.1"):
            result = evaluate_product_evidence(
                "W33.1", copy.deepcopy(FORECAST), copy.deepcopy(SNAPSHOT),
            )
            self.assertTrue(result["satisfied"])
        with self.subTest(card="W33.2"):
            result = evaluate_product_evidence(
                "W33.2", copy.deepcopy(CARD_2), copy.deepcopy(SNAPSHOT),
            )
            self.assertTrue(result["satisfied"])
        with self.subTest(card="W33.3"):
            result = evaluate_after_participant_action(
                "W33.3", copy.deepcopy(COMMISSIONING), copy.deepcopy(SNAPSHOT),
            )
            self.assertTrue(result["satisfied"])
        with self.subTest(card="W33.4"):
            result = evaluate_product_evidence(
                "W33.4", copy.deepcopy(CARD_4), copy.deepcopy(SNAPSHOT),
            )
            self.assertTrue(result["satisfied"])

    def test_infeasible_schedule_is_rejected(self):
        submission = copy.deepcopy(CARD_2)
        submission["schedule"]["alternate_supply_m3s"] = [0.0] * 12
        with self.assertRaises(evidence.EvidenceError):
            evidence.evaluate("W33.2", submission, copy.deepcopy(SNAPSHOT))

    def test_missing_dispatch_stage_or_bad_quality_is_rejected(self):
        missing = copy.deepcopy(SNAPSHOT)
        missing["dispatch"] = [row for row in missing["dispatch"]
                               if not (row["id"] == REQUEST_IDS[5] and row["status"] == "plc_accepted")]
        with self.assertRaises(evidence.EvidenceError):
            evidence.evaluate("W33.3", copy.deepcopy(COMMISSIONING), missing)
        bad_quality = copy.deepcopy(SNAPSHOT)
        next(row for row in bad_quality["samples"]
             if row["variable"] == "TotalFlowM3s" and row["source_time"] == stamp(76))["quality"] = "FieldUnavailable"
        with self.assertRaises(evidence.EvidenceError):
            evidence.evaluate("W33.3", copy.deepcopy(COMMISSIONING), bad_quality)

    def test_unrestored_site_or_invented_projection_is_rejected(self):
        unrestored = copy.deepcopy(SNAPSHOT)
        next(row for row in unrestored["samples"]
             if row["variable"] == "Owner" and row["source_time"] == stamp(FINAL_TIME))["value"] = 2
        with self.assertRaises(evidence.EvidenceError):
            evidence.evaluate("W33.3", copy.deepcopy(COMMISSIONING), unrestored)
        invented = copy.deepcopy(CARD_4)
        invented["projected_reservoir_volume_ml"] = 0.82
        with self.assertRaises(evidence.EvidenceError):
            evidence.evaluate("W33.4", invented, copy.deepcopy(SNAPSHOT))

    def test_participant_cannot_supply_product_evidence(self):
        submission = copy.deepcopy(CARD_4)
        submission["product_snapshot"] = copy.deepcopy(SNAPSHOT)
        with self.assertRaises(evidence.EvidenceError):
            evidence.evaluate("W33.4", submission, copy.deepcopy(SNAPSHOT))

    def test_evaluation_does_not_mutate_the_product_snapshot(self):
        product = copy.deepcopy(SNAPSHOT)
        before = copy.deepcopy(product)
        evidence.evaluate("W33.4", copy.deepcopy(CARD_4), product)
        self.assertEqual(product, before)


if __name__ == "__main__":
    unittest.main()
