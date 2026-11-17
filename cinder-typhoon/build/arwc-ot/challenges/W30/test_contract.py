from __future__ import annotations

import copy
import datetime as dt
import importlib.util
import pathlib
import unittest


HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("w30_evidence", HERE / "check_evidence.py")
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load W30 evidence evaluator")
evidence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evidence)

BASE = dt.datetime(2026, 11, 13, 22, 0, tzinfo=dt.timezone.utc)
TIMES = [(BASE + dt.timedelta(seconds=index)).isoformat().replace("+00:00", "Z") for index in range(11)]
REQUEST_ID = "c5e58877-663a-4c5f-98a5-fd04e28eae5c"
REMOTE_SEQUENCE = 20
RESTORE_SEQUENCE = 31


def rows(variable, values, unit="boolean"):
    return [
        {"variable": variable, "source_time": when, "value": value, "unit": unit, "quality": "Good"}
        for when, value in zip(TIMES, values, strict=True)
    ]


remote_phase = [0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0]
positions = [20, 20, 25, 30, 30, 30, 25, 20, 20, 20, 20]
flows = [0.10, 0.10, 0.125, 0.15, 0.15, 0.15, 0.125, 0.10, 0.10, 0.10, 0.10]
owner = [1, 1, 2, 2, 2, 2, 1, 1, 1, 1, 1]
hmi_sequence = [30, 30, 30, 30, 30, 30, 31, 31, 31, 31, 31]

SAMPLES = []
for variable, values, unit in (
    ("ProjectRevision", [364] * 11, "revision"),
    ("IoHealthy", [1] * 11, "boolean"),
    ("Owner", owner, "enum"),
    ("AutoMode", remote_phase, "boolean"),
    ("HmiRemoteEnabled", remote_phase, "boolean"),
    ("PermissiveA", [1] * 11, "boolean"), ("PermissiveB", [1] * 11, "boolean"),
    ("MovingA", [0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0], "boolean"),
    ("MovingB", [0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0], "boolean"),
    ("TravelFaultA", [0] * 11, "boolean"), ("TravelFaultB", [0] * 11, "boolean"),
    ("RemoteSeen", [19, 19] + [20] * 9, "count"),
    ("RemoteAccepted", [19, 19] + [20] * 9, "count"),
    ("RemoteRejected", [0] * 11, "count"), ("RemoteRejectReason", [0] * 11, "enum"),
    ("HmiSeen", hmi_sequence, "count"), ("HmiAccepted", hmi_sequence, "count"),
    ("HmiRejected", [7] * 11, "count"), ("HmiRejectReason", [0] * 11, "enum"),
    ("RequestedTargetPct", [20] * 11, "%"), ("RequestedTargetBPct", [20] * 11, "%"),
    ("RequestedFlowM3s", [0.2, 0.2] + [0.3] * 4 + [0.2] * 5, "m3/s"),
    ("PositionPct", positions, "%"), ("PositionBPct", positions, "%"),
    ("FlowM3s", flows, "m3/s"), ("FlowBM3s", flows, "m3/s"),
    ("TotalFlowM3s", [value * 2 for value in flows], "m3/s"),
):
    SAMPLES.extend(rows(variable, values, unit))

REQUEST = {
    "id": REQUEST_ID,
    "asset": "AST-CRR-017",
    "mode": "automatic",
    "position_a_pct": 20.0,
    "position_b_pct": 20.0,
    "total_flow_m3s": 0.3,
    "expires_at": (BASE + dt.timedelta(seconds=91)).timestamp(),
}
DISPATCH = [
    {"time": TIMES[index], "id": REQUEST_ID, "principal": "operator", "sequence": REMOTE_SEQUENCE,
     "status": status, "detail": detail, "request": copy.deepcopy(REQUEST),
     "origin": "Authenticated MQTT dispatcher and observed PLC feedback"}
    for index, status, detail in (
        (1, "received", {"origin": "durable dispatcher receipt"}),
        (1, "dispatch_intent", {"sequence": REMOTE_SEQUENCE, "origin": "dispatcher journal"}),
        (2, "dispatched", {"sequence": REMOTE_SEQUENCE, "origin": "OPC UA sequence write"}),
        (3, "plc_accepted", {"sequence": REMOTE_SEQUENCE, "origin": "native PLC decision"}),
        (4, "completed", {"sequence": REMOTE_SEQUENCE, "origin": "observed equipment feedback",
                           "position_a_pct": 30.0, "position_b_pct": 30.0,
                           "flow_a_m3s": 0.15, "flow_b_m3s": 0.15}),
    )
]

SNAPSHOT = {
    "schema": "arwc.native-remote-operation-observation/v1",
    "asset": "AST-CRR-017",
    "captured_at": TIMES[-1],
    "source_digest": "a" * 64,
    "configuration": {
        "project_revision": 364,
        "dispatcher": copy.deepcopy(evidence.CONTRACT["dispatcher"]),
        "authorized_work": copy.deepcopy(evidence.CONTRACT["authorized_work"]),
    },
    "samples": SAMPLES,
    "commands": [
        {"source_time": TIMES[3], "channel": "dispatcher", "decision": "accepted",
         "sequence": REMOTE_SEQUENCE, "native_status": "Good"},
        {"source_time": TIMES[6], "channel": "HMI", "decision": "accepted",
         "sequence": RESTORE_SEQUENCE, "native_status": "Good"},
    ],
    "dispatch": DISPATCH,
}

CARD_1 = {
    "instruction": "CRR-OP-W30-R1",
    "asset": "AST-CRR-017",
    "project_revision": 364,
    "delivery": {
        "schema": "arwc.remote-request/v1",
        "request_topic": "arwc/crr/commands/operator",
        "outcome_topic": "arwc/crr/outcomes/operator",
        "principal": "operator",
        "qos": 1,
        "retain": False,
    },
    "request": {
        "id_strategy": "fresh_uuid_v4_at_execution",
        "asset": "AST-CRR-017",
        "mode": "automatic",
        "position_a_pct": 20.0,
        "position_b_pct": 20.0,
        "total_flow_m3s": 0.3,
        "expiry_format": "numeric_unix_epoch_seconds_utc",
        "expiry_seconds": 90,
    },
    "successful_states": ["received", "dispatch_intent", "dispatched", "plc_accepted", "completed"],
    "retry": {
        "duplicate": "same_uuid_same_payload_returns_recorded_state_without_another_plc_operation",
        "conflict": "same_uuid_changed_payload_is_conflict",
        "uncertain": "inspect_and_reconcile_never_automatic_retry",
    },
    "restore": copy.deepcopy(evidence.CONTRACT["authorized_work"]["restore"]),
}

CARD_2 = {
    "asset": "AST-CRR-017",
    "request_id": REQUEST_ID,
    "remote_sequence": REMOTE_SEQUENCE,
    "received_at": TIMES[1],
    "completed_at": TIMES[4],
    "restore_sequence": RESTORE_SEQUENCE,
    "restore_accepted_at": TIMES[6],
    "final_observed_at": TIMES[9],
    "interval_start": TIMES[0],
    "interval_end": TIMES[10],
    "interpretation": "durable_receipt_plc_acceptance_measured_completion_local_handback",
}


def evaluate_product_evidence(card: str, submission: dict, product: dict) -> dict:
    """Name the product-owned evaluator boundary for the coverage ledger."""

    return evidence.evaluate(card, submission, product)


def evaluate_after_participant_action(card: str, submission: dict, product: dict) -> dict:
    """Evaluate the range snapshot after the participant's authorized work."""

    return evidence.evaluate(card, submission, product)


class ContractTests(unittest.TestCase):
    def test_both_cards_use_the_installed_contract_and_product_evidence(self):
        with self.subTest(card="W30.1 bind the plan to the plant"):
            result = evaluate_product_evidence("W30.1", copy.deepcopy(CARD_1), copy.deepcopy(SNAPSHOT))
            self.assertTrue(result["satisfied"])
            self.assertFalse(result["evidence"]["product_action_issued"])
        with self.subTest(card="W30.2 operate and hand back"):
            result = evaluate_after_participant_action("W30.2", copy.deepcopy(CARD_2), copy.deepcopy(SNAPSHOT))
            self.assertTrue(result["satisfied"])
            self.assertTrue(result["evidence"]["baseline_restored"])

    def test_wrong_plan_or_running_revision_is_rejected(self):
        wrong_plan = copy.deepcopy(CARD_1)
        wrong_plan["request"]["total_flow_m3s"] = 0.4
        with self.assertRaises(evidence.EvidenceError):
            evidence.evaluate("W30.1", wrong_plan, copy.deepcopy(SNAPSHOT))
        wrong_revision = copy.deepcopy(SNAPSHOT)
        next(row for row in wrong_revision["samples"] if row["variable"] == "ProjectRevision" and row["source_time"] == TIMES[-1])["value"] = 363
        with self.assertRaises(evidence.EvidenceError):
            evidence.evaluate("W30.1", copy.deepcopy(CARD_1), wrong_revision)

    def test_missing_or_reordered_dispatch_stage_is_rejected(self):
        missing = copy.deepcopy(SNAPSHOT)
        missing["dispatch"] = [row for row in missing["dispatch"] if row["status"] != "plc_accepted"]
        with self.assertRaises(evidence.EvidenceError):
            evidence.evaluate("W30.2", copy.deepcopy(CARD_2), missing)
        reordered = copy.deepcopy(SNAPSHOT)
        reordered["dispatch"][2], reordered["dispatch"][3] = reordered["dispatch"][3], reordered["dispatch"][2]
        reordered["dispatch"][2]["time"], reordered["dispatch"][3]["time"] = TIMES[2], TIMES[3]
        with self.assertRaises(evidence.EvidenceError):
            evidence.evaluate("W30.2", copy.deepcopy(CARD_2), reordered)

    def test_bad_quality_or_unrestored_state_is_rejected(self):
        bad_quality = copy.deepcopy(SNAPSHOT)
        next(row for row in bad_quality["samples"] if row["variable"] == "FlowM3s" and row["source_time"] == TIMES[4])["quality"] = "FieldUnavailable"
        with self.assertRaises(evidence.EvidenceError):
            evidence.evaluate("W30.2", copy.deepcopy(CARD_2), bad_quality)
        unrestored = copy.deepcopy(SNAPSHOT)
        next(row for row in unrestored["samples"] if row["variable"] == "Owner" and row["source_time"] == TIMES[9])["value"] = 2
        with self.assertRaises(evidence.EvidenceError):
            evidence.evaluate("W30.2", copy.deepcopy(CARD_2), unrestored)

    def test_expired_or_changed_product_request_is_rejected(self):
        expired = copy.deepcopy(SNAPSHOT)
        for row in expired["dispatch"]:
            row["request"]["expires_at"] = BASE.timestamp()
        with self.assertRaises(evidence.EvidenceError):
            evidence.evaluate("W30.2", copy.deepcopy(CARD_2), expired)
        changed = copy.deepcopy(SNAPSHOT)
        changed["dispatch"][-1]["request"]["total_flow_m3s"] = 0.4
        with self.assertRaises(evidence.EvidenceError):
            evidence.evaluate("W30.2", copy.deepcopy(CARD_2), changed)

    def test_participant_cannot_supply_product_evidence(self):
        submission = copy.deepcopy(CARD_2)
        submission["product_snapshot"] = copy.deepcopy(SNAPSHOT)
        with self.assertRaises(evidence.EvidenceError):
            evidence.evaluate("W30.2", submission, copy.deepcopy(SNAPSHOT))

    def test_completion_does_not_mutate_product_evidence(self):
        product = copy.deepcopy(SNAPSHOT)
        before = copy.deepcopy(product)
        evidence.evaluate("W30.2", copy.deepcopy(CARD_2), product)
        self.assertEqual(product, before)


if __name__ == "__main__":
    unittest.main()
