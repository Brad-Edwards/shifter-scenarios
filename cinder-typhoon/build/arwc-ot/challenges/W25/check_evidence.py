#!/usr/bin/env python3
"""Compare W25 answers with trusted controller and historian evidence."""

from __future__ import annotations

import datetime as dt
import json
import math
import pathlib
import re
from typing import Any


HERE = pathlib.Path(__file__).resolve().parent
CONTRACT = json.loads((HERE / "contract.json").read_text())
UTC = dt.timezone.utc
SHA256 = re.compile(r"^[0-9a-f]{64}$")


class EvidenceError(ValueError):
    pass


def _exact(value: Any, fields: set[str], label: str) -> None:
    if not isinstance(value, dict) or set(value) != fields:
        raise EvidenceError(f"{label} fields do not match the contract")


def _time(value: Any, label: str = "time") -> dt.datetime:
    if not isinstance(value, str):
        raise EvidenceError(f"{label} must be an ISO 8601 string")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise EvidenceError(f"{label} must be valid ISO 8601") from error
    if parsed.tzinfo is None:
        raise EvidenceError(f"{label} must include a UTC offset")
    return parsed.astimezone(UTC)


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EvidenceError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise EvidenceError(f"{label} must be finite")
    return result


def _product(snapshot: dict[str, Any]) -> tuple[dt.datetime, list[dict[str, Any]], list[dict[str, Any]]]:
    _exact(snapshot, {"schema", "asset", "captured_at", "source_digest", "configuration", "samples", "commands"}, "product snapshot")
    if snapshot["schema"] != CONTRACT["product_snapshot"]["schema"] or snapshot["asset"] != CONTRACT["asset"]:
        raise EvidenceError("product snapshot is for another schema or asset")
    captured = _time(snapshot["captured_at"], "captured_at")
    if not isinstance(snapshot["source_digest"], str) or not SHA256.fullmatch(snapshot["source_digest"]):
        raise EvidenceError("product snapshot digest is missing")
    expected_configuration = {
        "project_revision": CONTRACT["project_revision"],
        "installed_limits": CONTRACT["installed_limits"],
        "authorized_work": CONTRACT["authorized_work"],
    }
    if snapshot["configuration"] != expected_configuration:
        raise EvidenceError("image-owned controller and work configuration does not match")
    if not isinstance(snapshot["samples"], list) or not isinstance(snapshot["commands"], list):
        raise EvidenceError("product samples and command decisions are required")
    return captured, snapshot["samples"], snapshot["commands"]


def _rows(samples: list[dict[str, Any]], variable: str) -> list[dict[str, Any]]:
    result = []
    for row in samples:
        _exact(row, {"variable", "source_time", "value", "unit", "quality"}, "product sample")
        if row["variable"] != variable:
            continue
        _time(row["source_time"], "sample source_time")
        _number(row["value"], variable)
        result.append(row)
    return sorted(result, key=lambda item: _time(item["source_time"]))


def _point(samples: list[dict[str, Any]], variable: str, observed: dt.datetime) -> dict[str, Any]:
    rows = _rows(samples, variable)
    if not rows:
        raise EvidenceError(f"product sample is missing for {variable}")
    row = min(rows, key=lambda item: abs((_time(item["source_time"]) - observed).total_seconds()))
    if abs((_time(row["source_time"]) - observed).total_seconds()) > CONTRACT["product_snapshot"]["maximum_point_distance_seconds"]:
        raise EvidenceError(f"{variable} has no sample near the observation")
    if row["quality"] != CONTRACT["product_snapshot"]["accepted_quality"]:
        raise EvidenceError(f"{variable} does not have good process quality")
    return row


def _value(samples: list[dict[str, Any]], variable: str, observed: dt.datetime) -> float:
    return _number(_point(samples, variable, observed)["value"], variable)


def _near(actual: float, expected: float, tolerance: str, label: str) -> None:
    if abs(actual - expected) > CONTRACT["tolerance"][tolerance]:
        raise EvidenceError(f"{label} is outside the product tolerance")


def _commands(commands: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for row in commands:
        _exact(row, {"source_time", "channel", "decision", "sequence", "native_status"}, "product command")
        _time(row["source_time"], "command source_time")
        if isinstance(row["sequence"], bool) or not isinstance(row["sequence"], int):
            raise EvidenceError("command sequence must be an integer")
        result.append(row)
    return sorted(result, key=lambda item: _time(item["source_time"]))


def _accepted(commands: list[dict[str, Any]], sequence: int, observed: dt.datetime) -> dict[str, Any]:
    matches = [row for row in _commands(commands) if row["channel"] == "HMI" and row["decision"] == "accepted" and row["sequence"] == sequence]
    if len(matches) != 1:
        raise EvidenceError("exactly one native HMI acceptance is required")
    row = matches[0]
    if abs((_time(row["source_time"]) - observed).total_seconds()) > CONTRACT["product_snapshot"]["maximum_point_distance_seconds"]:
        raise EvidenceError("accepted sequence is outside the claimed interval")
    if row["native_status"] not in ("Good", "The operation succeeded. StatusGood (0x0)"):
        raise EvidenceError("accepted sequence has bad native status")
    return row


def _card_1(submission: dict[str, Any], captured: dt.datetime, samples: list[dict[str, Any]]) -> dict[str, Any]:
    _exact(submission, {"instruction", "asset", "project_revision", "installed_limits", "authorized_work"}, "W25.1 submission")
    expected = {
        "instruction": CONTRACT["instruction"], "asset": CONTRACT["asset"],
        "project_revision": CONTRACT["project_revision"],
        "installed_limits": CONTRACT["installed_limits"],
        "authorized_work": CONTRACT["authorized_work"],
    }
    if submission != expected:
        raise EvidenceError("W25.1 does not match the installed limits and authorized work")
    if round(_value(samples, "ProjectRevision", captured)) != CONTRACT["project_revision"]:
        raise EvidenceError("running project revision does not match the operating instruction")
    return {"instruction": CONTRACT["instruction"], "project_revision": CONTRACT["project_revision"]}


def _card_2(submission: dict[str, Any], samples: list[dict[str, Any]]) -> dict[str, Any]:
    _exact(submission, {"asset", "observed_at", "chain", "live", "may_proceed"}, "W25.2 submission")
    if submission["asset"] != CONTRACT["asset"] or submission["chain"] != CONTRACT["permissive_chain"]:
        raise EvidenceError("W25.2 asset or permissive chain does not match")
    observed = _time(submission["observed_at"], "observed_at")
    fields = {
        "io_healthy": ("IoHealthy", True), "low_level": ("LowLevelAlarm", False),
        "operator_stop": ("HmiStop", False), "travel_fault_a": ("TravelFaultA", False),
        "travel_fault_b": ("TravelFaultB", False), "armed": ("Armed", True),
        "owner": ("Owner", 1), "mode": ("AutoMode", 0),
        "permissive_a": ("PermissiveA", True), "permissive_b": ("PermissiveB", True),
    }
    live = submission["live"]
    if not isinstance(live, dict) or set(live) != set(fields):
        raise EvidenceError("W25.2 live fields do not match the contract")
    for field, (variable, expected) in fields.items():
        actual = round(_value(samples, variable, observed))
        required = int(expected) if isinstance(expected, bool) else expected
        if actual != required or live[field] != expected:
            raise EvidenceError(f"W25.2 {field} does not match live product state")
    if submission["may_proceed"] is not True:
        raise EvidenceError("healthy movement conditions must be interpreted as proceed")
    return {"observed_at": submission["observed_at"], "may_proceed": True}


def _card_3(submission: dict[str, Any], samples: list[dict[str, Any]], commands: list[dict[str, Any]]) -> dict[str, Any]:
    _exact(submission, {"asset", "sequence", "accepted_at", "settled_at", "owner", "requested", "interpretation"}, "W25.3 submission")
    if submission["asset"] != CONTRACT["asset"] or submission["owner"] != "hmi" or submission["interpretation"] != "accepted_then_measured_feedback":
        raise EvidenceError("W25.3 ownership or interpretation is wrong")
    if submission["requested"] != CONTRACT["authorized_work"]["observation"]:
        raise EvidenceError("W25.3 request is outside the authorized movement")
    sequence = submission["sequence"]
    if isinstance(sequence, bool) or not isinstance(sequence, int):
        raise EvidenceError("W25.3 sequence must be an integer")
    accepted_at = _time(submission["accepted_at"], "accepted_at")
    settled_at = _time(submission["settled_at"], "settled_at")
    if settled_at <= accepted_at:
        raise EvidenceError("physical feedback must follow acceptance")
    _accepted(commands, sequence, accepted_at)
    for variable, expected in (("HmiSeen", sequence), ("HmiAccepted", sequence),
                               ("HmiRejectReason", 0), ("Owner", 1), ("AutoMode", 0),
                               ("Armed", 1), ("PermissiveA", 1), ("PermissiveB", 1)):
        if round(_value(samples, variable, accepted_at)) != expected:
            raise EvidenceError(f"W25.3 {variable} does not prove accepted HMI ownership")
    for variable, expected in (("RequestedTargetPct", 30.0), ("RequestedTargetBPct", 10.0), ("RequestedFlowM3s", 0.2)):
        tolerance = "total_flow_m3s" if variable == "RequestedFlowM3s" else "position_pct"
        _near(_value(samples, variable, accepted_at), expected, tolerance, variable)
    for variable, expected, tolerance in (("PositionPct", 30.0, "position_pct"), ("PositionBPct", 10.0, "position_pct"),
                                          ("FlowM3s", 0.15, "outlet_flow_m3s"), ("FlowBM3s", 0.05, "outlet_flow_m3s"),
                                          ("TotalFlowM3s", 0.2, "total_flow_m3s")):
        _near(_value(samples, variable, settled_at), expected, tolerance, variable)
    return {"sequence": sequence, "accepted_at": submission["accepted_at"], "settled_at": submission["settled_at"]}


def _card_4(submission: dict[str, Any], samples: list[dict[str, Any]], commands: list[dict[str, Any]]) -> dict[str, Any]:
    _exact(submission, {"asset", "movement_sequence", "restore_sequence", "start", "end", "final_observed_at", "summary"}, "W25.4 submission")
    if submission["asset"] != CONTRACT["asset"]:
        raise EvidenceError("W25.4 uses another asset")
    movement, restore = submission["movement_sequence"], submission["restore_sequence"]
    if any(isinstance(value, bool) or not isinstance(value, int) for value in (movement, restore)) or movement == restore:
        raise EvidenceError("W25.4 requires two distinct integer sequences")
    start, end = _time(submission["start"], "start"), _time(submission["end"], "end")
    final = _time(submission["final_observed_at"], "final_observed_at")
    if not start < end or not start <= final <= end:
        raise EvidenceError("W25.4 interval is invalid")
    movement_row = next((row for row in _commands(commands) if row["channel"] == "HMI" and row["decision"] == "accepted" and row["sequence"] == movement), None)
    restore_row = next((row for row in _commands(commands) if row["channel"] == "HMI" and row["decision"] == "accepted" and row["sequence"] == restore), None)
    if movement_row is None or restore_row is None or not (start <= _time(movement_row["source_time"]) < _time(restore_row["source_time"]) <= end):
        raise EvidenceError("W25.4 does not contain ordered movement and restoration acceptances")
    if any(row["native_status"] not in ("Good", "The operation succeeded. StatusGood (0x0)") for row in (movement_row, restore_row)):
        raise EvidenceError("W25.4 contains an acceptance with bad native status")
    variables = ("PositionPct", "PositionBPct", "FlowM3s", "FlowBM3s", "TotalFlowM3s")
    selected = {
        variable: [row for row in _rows(samples, variable) if start <= _time(row["source_time"]) <= end]
        for variable in variables
    }
    if any(len(rows) < CONTRACT["product_snapshot"]["minimum_trace_samples"] for rows in selected.values()):
        raise EvidenceError("W25.4 history is too short")
    if any(row["quality"] != CONTRACT["product_snapshot"]["accepted_quality"] for rows in selected.values() for row in rows):
        raise EvidenceError("W25.4 history contains non-good product evidence")
    by_time = {variable: {_time(row["source_time"]): _number(row["value"], variable) for row in rows} for variable, rows in selected.items()}
    times = sorted(set.intersection(*(set(rows) for rows in by_time.values())))
    if len(times) < CONTRACT["product_snapshot"]["minimum_trace_samples"]:
        raise EvidenceError("W25.4 has too few time-aligned product samples")
    values = {variable: [by_time[variable][when] for when in times] for variable in variables}
    if not any(abs(a - 30.0) <= 0.5 and abs(b - 10.0) <= 0.5 for a, b in zip(values["PositionPct"], values["PositionBPct"], strict=True)):
        raise EvidenceError("W25.4 history does not show the authorized observation target")
    summary = submission["summary"]
    _exact(summary, {"position_a_min_pct", "position_a_max_pct", "position_b_min_pct", "position_b_max_pct", "total_flow_min_m3s", "total_flow_max_m3s", "sample_count"}, "W25.4 summary")
    expected_summary = {
        "position_a_min_pct": min(values["PositionPct"]), "position_a_max_pct": max(values["PositionPct"]),
        "position_b_min_pct": min(values["PositionBPct"]), "position_b_max_pct": max(values["PositionBPct"]),
        "total_flow_min_m3s": min(values["TotalFlowM3s"]), "total_flow_max_m3s": max(values["TotalFlowM3s"]),
        "sample_count": len(times),
    }
    if summary["sample_count"] != expected_summary["sample_count"]:
        raise EvidenceError("W25.4 sample count does not match product history")
    for field in set(expected_summary) - {"sample_count"}:
        tolerance = "total_flow_m3s" if field.startswith("total_flow") else "position_pct"
        _near(_number(summary[field], field), expected_summary[field], tolerance, field)
    final_expected = {
        "RequestedTargetPct": (20.0, "position_pct"), "RequestedTargetBPct": (20.0, "position_pct"),
        "RequestedFlowM3s": (0.2, "total_flow_m3s"), "PositionPct": (20.0, "position_pct"),
        "PositionBPct": (20.0, "position_pct"), "FlowM3s": (0.1, "outlet_flow_m3s"),
        "FlowBM3s": (0.1, "outlet_flow_m3s"), "TotalFlowM3s": (0.2, "total_flow_m3s"),
    }
    for variable, (expected, tolerance) in final_expected.items():
        _near(_value(samples, variable, final), expected, tolerance, variable)
    for variable, expected in (("HmiSeen", restore), ("HmiAccepted", restore), ("HmiRejectReason", 0), ("Owner", 1), ("AutoMode", 0),
                               ("Armed", 1), ("IoHealthy", 1), ("PermissiveA", 1), ("PermissiveB", 1),
                               ("MovingA", 0), ("MovingB", 0), ("TravelFaultA", 0), ("TravelFaultB", 0)):
        if round(_value(samples, variable, final)) != expected:
            raise EvidenceError(f"W25.4 final {variable} does not match the restored baseline")
    return {"movement_sequence": movement, "restore_sequence": restore, "samples": len(times), "baseline_restored": True}


def evaluate(card: str, submission: dict[str, Any], product_snapshot: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(submission, dict) or "product_snapshot" in submission:
        raise EvidenceError("participant input cannot supply product evidence")
    captured, samples, commands = _product(product_snapshot)
    evaluators = {
        "W25.1": lambda: _card_1(submission, captured, samples),
        "W25.2": lambda: _card_2(submission, samples),
        "W25.3": lambda: _card_3(submission, samples, commands),
        "W25.4": lambda: _card_4(submission, samples, commands),
    }
    if card not in evaluators:
        raise EvidenceError("card is outside W25")
    return {
        "schema": "arwc.challenge-result/v1", "card": card, "satisfied": True,
        "product_source_digest": product_snapshot["source_digest"], "evidence": evaluators[card](),
    }
