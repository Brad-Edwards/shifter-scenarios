import copy
import datetime as dt
import importlib.util
import pathlib
import unittest


HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("w25_evidence", HERE / "check_evidence.py")
evidence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evidence)

BASE = dt.datetime(2026, 11, 13, 20, 0, tzinfo=dt.timezone.utc)
TIMES = [(BASE + dt.timedelta(seconds=index)).isoformat().replace("+00:00", "Z") for index in range(9)]
POSITIONS_A = [20, 20, 25, 30, 30, 30, 25, 20, 20]
POSITIONS_B = [20, 20, 15, 10, 10, 10, 15, 20, 20]
SEQUENCES = [9, 10, 10, 10, 10, 11, 11, 11, 11]
TARGET_A = [20, 30, 30, 30, 30, 20, 20, 20, 20]
TARGET_B = [20, 10, 10, 10, 10, 20, 20, 20, 20]
MOVING = [0, 1, 1, 0, 0, 1, 1, 0, 0]


def rows(variable, values, unit="boolean"):
    return [
        {"variable": variable, "source_time": when, "value": value, "unit": unit, "quality": "Good"}
        for when, value in zip(TIMES, values, strict=True)
    ]


SAMPLES = []
for variable, values, unit in (
    ("ProjectRevision", [364] * 9, "revision"),
    ("IoHealthy", [1] * 9, "boolean"), ("LowLevelAlarm", [0] * 9, "boolean"),
    ("HmiStop", [0] * 9, "boolean"), ("TravelFaultA", [0] * 9, "boolean"),
    ("TravelFaultB", [0] * 9, "boolean"), ("Armed", [1] * 9, "boolean"),
    ("Owner", [1] * 9, "enum"), ("AutoMode", [0] * 9, "boolean"),
    ("PermissiveA", [1] * 9, "boolean"), ("PermissiveB", [1] * 9, "boolean"),
    ("MovingA", MOVING, "boolean"), ("MovingB", MOVING, "boolean"),
    ("HmiSeen", SEQUENCES, "count"), ("HmiAccepted", SEQUENCES, "count"),
    ("HmiRejected", [7] * 9, "count"), ("HmiRejectReason", [0] * 9, "enum"),
    ("RequestedTargetPct", TARGET_A, "%"), ("RequestedTargetBPct", TARGET_B, "%"),
    ("RequestedFlowM3s", [0.2] * 9, "m3/s"),
    ("PositionPct", POSITIONS_A, "%"), ("PositionBPct", POSITIONS_B, "%"),
    ("FlowM3s", [value * 0.005 for value in POSITIONS_A], "m3/s"),
    ("FlowBM3s", [value * 0.005 for value in POSITIONS_B], "m3/s"),
    ("TotalFlowM3s", [0.2] * 9, "m3/s"),
):
    SAMPLES.extend(rows(variable, values, unit))

SNAPSHOT = {
    "schema": "arwc.native-bounded-movement-observation/v1", "asset": "AST-CRR-017",
    "captured_at": TIMES[-1], "source_digest": "a" * 64,
    "configuration": {
        "project_revision": 364,
        "installed_limits": {"manual_position_pct": [0.0, 100.0], "automatic_total_flow_m3s": [0.0, 1.0], "per_outlet_capacity_m3s": 0.5},
        "authorized_work": {
            "mode": "manual",
            "baseline": {"outlet_a_position_pct": 20.0, "outlet_b_position_pct": 20.0, "total_flow_m3s": 0.2},
            "observation": {"outlet_a_position_pct": 30.0, "outlet_b_position_pct": 10.0, "total_flow_m3s": 0.2},
            "restore": {"outlet_a_position_pct": 20.0, "outlet_b_position_pct": 20.0, "total_flow_m3s": 0.2},
        },
    },
    "samples": SAMPLES,
    "commands": [
        {"source_time": TIMES[1], "channel": "HMI", "decision": "accepted", "sequence": 10, "native_status": "Good"},
        {"source_time": TIMES[5], "channel": "HMI", "decision": "accepted", "sequence": 11, "native_status": "Good"},
    ],
}

CARD_1 = {
    "instruction": "CRR-OP-W25-R1", "asset": "AST-CRR-017", "project_revision": 364,
    "installed_limits": copy.deepcopy(SNAPSHOT["configuration"]["installed_limits"]),
    "authorized_work": copy.deepcopy(SNAPSHOT["configuration"]["authorized_work"]),
}
CARD_2 = {
    "asset": "AST-CRR-017", "observed_at": TIMES[0],
    "chain": ["IoHealthy", "AvailableARaw", "AvailableBRaw", "RemoteARaw", "RemoteBRaw", "LowLevelAlarm", "HmiStop", "TravelFaultA", "TravelFaultB", "Armed", "PermissiveA", "PermissiveB"],
    "live": {"io_healthy": True, "low_level": False, "operator_stop": False, "travel_fault_a": False, "travel_fault_b": False, "armed": True, "owner": 1, "mode": 0, "permissive_a": True, "permissive_b": True},
    "may_proceed": True,
}
CARD_3 = {
    "asset": "AST-CRR-017", "sequence": 10, "accepted_at": TIMES[1], "settled_at": TIMES[3],
    "owner": "hmi", "requested": copy.deepcopy(SNAPSHOT["configuration"]["authorized_work"]["observation"]),
    "interpretation": "accepted_then_measured_feedback",
}
CARD_4 = {
    "asset": "AST-CRR-017", "movement_sequence": 10, "restore_sequence": 11,
    "start": TIMES[0], "end": TIMES[-1], "final_observed_at": TIMES[-1],
    "summary": {"position_a_min_pct": 20, "position_a_max_pct": 30, "position_b_min_pct": 10,
                "position_b_max_pct": 20, "total_flow_min_m3s": 0.2, "total_flow_max_m3s": 0.2,
                "sample_count": 9},
}


def evaluate_product_evidence(card: str, submission: dict, product: dict) -> dict:
    """Name the product-owned evaluator boundary for the coverage ledger."""

    return evidence.evaluate(card, submission, product)


def evaluate_after_participant_action(card: str, submission: dict, product: dict) -> dict:
    """Evaluate product evidence captured after the authorized FUXA action."""

    return evidence.evaluate(card, submission, product)


class ContractTests(unittest.TestCase):
    def test_positive_cards_use_product_evidence(self):
        with self.subTest(card="W25.1 the operating envelope"):
            self.assertTrue(evaluate_product_evidence("W25.1", copy.deepcopy(CARD_1), copy.deepcopy(SNAPSHOT))["satisfied"])
        with self.subTest(card="W25.2 conditions before movement"):
            self.assertTrue(evaluate_product_evidence("W25.2", copy.deepcopy(CARD_2), copy.deepcopy(SNAPSHOT))["satisfied"])
        with self.subTest(card="W25.3 accepted is not actuated"):
            self.assertTrue(evaluate_after_participant_action("W25.3", copy.deepcopy(CARD_3), copy.deepcopy(SNAPSHOT))["satisfied"])
        with self.subTest(card="W25.4 a sequence the process can follow"):
            self.assertTrue(evaluate_after_participant_action("W25.4", copy.deepcopy(CARD_4), copy.deepcopy(SNAPSHOT))["satisfied"])

    def test_wrong_quality_or_unrestored_state_is_rejected(self):
        bad_quality = copy.deepcopy(SNAPSHOT)
        next(row for row in bad_quality["samples"] if row["variable"] == "PositionPct" and row["source_time"] == TIMES[3])["quality"] = "FieldUnavailable"
        with self.assertRaises(evidence.EvidenceError):
            evidence.evaluate("W25.3", copy.deepcopy(CARD_3), bad_quality)
        unrestored = copy.deepcopy(SNAPSHOT)
        next(row for row in unrestored["samples"] if row["variable"] == "RequestedTargetPct" and row["source_time"] == TIMES[-1])["value"] = 30
        with self.assertRaises(evidence.EvidenceError):
            evidence.evaluate("W25.4", copy.deepcopy(CARD_4), unrestored)

    def test_missing_acceptance_or_wrong_configuration_is_rejected(self):
        no_acceptance = copy.deepcopy(SNAPSHOT)
        no_acceptance["commands"] = no_acceptance["commands"][1:]
        with self.assertRaises(evidence.EvidenceError):
            evidence.evaluate("W25.3", copy.deepcopy(CARD_3), no_acceptance)
        wrong_configuration = copy.deepcopy(SNAPSHOT)
        wrong_configuration["configuration"]["authorized_work"]["observation"]["outlet_a_position_pct"] = 31
        with self.assertRaises(evidence.EvidenceError):
            evidence.evaluate("W25.1", copy.deepcopy(CARD_1), wrong_configuration)

    def test_bad_native_acceptance_status_is_rejected(self):
        bad_status = copy.deepcopy(SNAPSHOT)
        bad_status["commands"][1]["native_status"] = "BadNotConnected"
        with self.assertRaises(evidence.EvidenceError):
            evidence.evaluate("W25.4", copy.deepcopy(CARD_4), bad_status)

    def test_participant_cannot_supply_product_evidence(self):
        submission = copy.deepcopy(CARD_4)
        submission["product_snapshot"] = copy.deepcopy(SNAPSHOT)
        with self.assertRaises(evidence.EvidenceError):
            evidence.evaluate("W25.4", submission, copy.deepcopy(SNAPSHOT))

    def test_completion_restores_baseline_without_mutating_product_evidence(self):
        product_before = copy.deepcopy(SNAPSHOT)
        result = evidence.evaluate("W25.4", copy.deepcopy(CARD_4), SNAPSHOT)
        self.assertTrue(result["evidence"]["baseline_restored"])
        self.assertEqual(SNAPSHOT, product_before)


if __name__ == "__main__":
    unittest.main()
