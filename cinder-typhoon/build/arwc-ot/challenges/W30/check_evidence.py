#!/usr/bin/env python3
"""Compare W30 submissions with trusted dispatcher, PLC, and historian evidence."""

from __future__ import annotations

import datetime as dt
import json
import math
import pathlib
import re
import uuid
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


def _time(value: Any, label: str) -> dt.datetime:
    if not isinstance(value, str):
        raise EvidenceError(f"{label} must be an ISO 8601 string")
    try:
        result = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise EvidenceError(f"{label} must be valid ISO 8601") from error
    if result.tzinfo is None:
        raise EvidenceError(f"{label} must include a UTC offset")
    return result.astimezone(UTC)


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EvidenceError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise EvidenceError(f"{label} must be finite")
    return result


def _integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise EvidenceError(f"{label} must be an integer")
    return value


def _request_id(value: Any) -> str:
    if not isinstance(value, str):
        raise EvidenceError("request_id must be a UUID string")
    try:
        parsed = uuid.UUID(value)
    except ValueError as error:
        raise EvidenceError("request_id must be a valid UUID") from error
    if str(parsed) != value or parsed.version != 4:
        raise EvidenceError("request_id must be a canonical UUIDv4")
    return value


def _near(actual: Any, expected: float, tolerance: str, label: str) -> None:
    if abs(_number(actual, label) - expected) > CONTRACT["tolerance"][tolerance]:
        raise EvidenceError(f"{label} is outside the product tolerance")


def _configuration() -> dict[str, Any]:
    return {
        "project_revision": CONTRACT["project_revision"],
        "dispatcher": CONTRACT["dispatcher"],
        "authorized_work": CONTRACT["authorized_work"],
    }


def _product(snapshot: dict[str, Any]) -> tuple[dt.datetime, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    _exact(snapshot, {
        "schema", "asset", "captured_at", "source_digest", "configuration",
        "samples", "commands", "dispatch",
    }, "product snapshot")
    if snapshot["schema"] != CONTRACT["product_snapshot"]["schema"] or snapshot["asset"] != CONTRACT["asset"]:
        raise EvidenceError("product snapshot is for another schema or asset")
    if not isinstance(snapshot["source_digest"], str) or not SHA256.fullmatch(snapshot["source_digest"]):
        raise EvidenceError("product snapshot digest is missing")
    if snapshot["configuration"] != _configuration():
        raise EvidenceError("installed dispatcher, project, or work configuration does not match")
    if not all(isinstance(snapshot[field], list) for field in ("samples", "commands", "dispatch")):
        raise EvidenceError("product samples, commands, and dispatch records are required")
    return _time(snapshot["captured_at"], "captured_at"), snapshot["samples"], snapshot["commands"], snapshot["dispatch"]


def _rows(samples: list[dict[str, Any]], variable: str) -> list[dict[str, Any]]:
    result = []
    for row in samples:
        _exact(row, {"variable", "source_time", "value", "unit", "quality"}, "product sample")
        if row["variable"] != variable:
            continue
        _time(row["source_time"], "sample source_time")
        _number(row["value"], variable)
        result.append(row)
    return sorted(result, key=lambda item: _time(item["source_time"], "sample source_time"))


def _point(samples: list[dict[str, Any]], variable: str, observed: dt.datetime) -> dict[str, Any]:
    rows = _rows(samples, variable)
    if not rows:
        raise EvidenceError(f"product sample is missing for {variable}")
    row = min(rows, key=lambda item: abs((_time(item["source_time"], "sample source_time") - observed).total_seconds()))
    distance = abs((_time(row["source_time"], "sample source_time") - observed).total_seconds())
    if distance > CONTRACT["product_snapshot"]["maximum_point_distance_seconds"]:
        raise EvidenceError(f"{variable} has no sample near the observation")
    if row["quality"] != CONTRACT["product_snapshot"]["accepted_quality"]:
        raise EvidenceError(f"{variable} does not have good process quality")
    return row


def _value(samples: list[dict[str, Any]], variable: str, observed: dt.datetime) -> float:
    return _number(_point(samples, variable, observed)["value"], variable)


def _commands(commands: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for row in commands:
        _exact(row, {"source_time", "channel", "decision", "sequence", "native_status"}, "product command")
        _time(row["source_time"], "command source_time")
        _integer(row["sequence"], "command sequence")
        result.append(row)
    return sorted(result, key=lambda item: _time(item["source_time"], "command source_time"))


def _accepted(commands: list[dict[str, Any]], channel: str, sequence: int, observed: dt.datetime) -> dict[str, Any]:
    matches = [
        row for row in _commands(commands)
        if row["channel"] == channel and row["decision"] == "accepted" and row["sequence"] == sequence
    ]
    if len(matches) != 1:
        raise EvidenceError(f"exactly one native {channel} acceptance is required")
    row = matches[0]
    if abs((_time(row["source_time"], "command source_time") - observed).total_seconds()) > CONTRACT["product_snapshot"]["maximum_point_distance_seconds"]:
        raise EvidenceError(f"native {channel} acceptance is outside the claimed interval")
    if row["native_status"] not in ("Good", "The operation succeeded. StatusGood (0x0)"):
        raise EvidenceError(f"native {channel} acceptance has bad status")
    return row


def _dispatch_rows(rows: list[dict[str, Any]], request_id: str) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        _exact(row, {"time", "id", "principal", "sequence", "status", "detail", "request", "origin"}, "dispatcher transition")
        _time(row["time"], "dispatcher time")
        if row["id"] != request_id:
            continue
        if row["principal"] != CONTRACT["dispatcher"]["principal"]:
            raise EvidenceError("dispatcher principal does not match the installed contract")
        _integer(row["sequence"], "dispatcher sequence")
        if not isinstance(row["detail"], dict) or not isinstance(row["request"], dict):
            raise EvidenceError("dispatcher detail and request must be product records")
        if row["origin"] != "Authenticated MQTT dispatcher and observed PLC feedback":
            raise EvidenceError("dispatcher record has the wrong product origin")
        result.append(row)
    return sorted(result, key=lambda item: _time(item["time"], "dispatcher time"))


def _planned_request() -> dict[str, Any]:
    dispatcher = CONTRACT["dispatcher"]
    remote = CONTRACT["authorized_work"]["remote"]
    return {
        "instruction": CONTRACT["instruction"],
        "asset": CONTRACT["asset"],
        "project_revision": CONTRACT["project_revision"],
        "delivery": {
            "schema": dispatcher["schema"],
            "request_topic": dispatcher["request_topic"],
            "outcome_topic": dispatcher["outcome_topic"],
            "principal": dispatcher["principal"],
            "qos": dispatcher["qos"],
            "retain": dispatcher["retain"],
        },
        "request": {
            "id_strategy": "fresh_uuid_v4_at_execution",
            "asset": CONTRACT["asset"],
            "mode": remote["mode"],
            "position_a_pct": remote["position_a_pct"],
            "position_b_pct": remote["position_b_pct"],
            "total_flow_m3s": remote["total_flow_m3s"],
            "expiry_format": dispatcher["expiry_format"],
            "expiry_seconds": dispatcher["expiry_seconds"],
        },
        "successful_states": dispatcher["successful_states"],
        "retry": {
            "duplicate": dispatcher["duplicate_rule"],
            "conflict": dispatcher["conflict_rule"],
            "uncertain": dispatcher["uncertain_rule"],
        },
        "restore": CONTRACT["authorized_work"]["restore"],
    }


def _card_1(submission: dict[str, Any], captured: dt.datetime, samples: list[dict[str, Any]]) -> dict[str, Any]:
    if submission != _planned_request():
        raise EvidenceError("W30.1 does not match the installed request and restoration contract")
    if round(_value(samples, "ProjectRevision", captured)) != CONTRACT["project_revision"]:
        raise EvidenceError("running project revision does not match the operating instruction")
    return {"instruction": CONTRACT["instruction"], "request_prepared": True, "product_action_issued": False}


def _actual_request(request: dict[str, Any], request_id: str, received: dt.datetime) -> None:
    if set(request) != set(CONTRACT["dispatcher"]["request_fields"]):
        raise EvidenceError("recorded dispatcher request fields do not match the contract")
    if request["id"] != request_id or request["asset"] != CONTRACT["asset"]:
        raise EvidenceError("recorded dispatcher identity or asset does not match")
    remote = CONTRACT["authorized_work"]["remote"]
    for field in ("mode", "position_a_pct", "position_b_pct", "total_flow_m3s"):
        if request[field] != remote[field]:
            raise EvidenceError("recorded dispatcher request is outside the approved work")
    expires = _number(request["expires_at"], "expires_at")
    remaining = expires - received.timestamp()
    if remaining <= 0 or remaining > CONTRACT["dispatcher"]["maximum_expiry_seconds"]:
        raise EvidenceError("recorded dispatcher expiry is outside the installed limit")


def _healthy_remote(samples: list[dict[str, Any]], observed: dt.datetime, sequence: int) -> None:
    for variable, expected in (
        ("RemoteSeen", sequence), ("RemoteAccepted", sequence), ("RemoteRejectReason", 0),
        ("Owner", 2), ("AutoMode", 1), ("HmiRemoteEnabled", 1), ("IoHealthy", 1),
        ("PermissiveA", 1), ("PermissiveB", 1), ("MovingA", 0), ("MovingB", 0),
        ("TravelFaultA", 0), ("TravelFaultB", 0),
    ):
        if round(_value(samples, variable, observed)) != expected:
            raise EvidenceError(f"remote completion {variable} does not match product state")
    remote = CONTRACT["authorized_work"]["remote"]
    for variable, expected, tolerance in (
        ("FlowM3s", remote["expected_flow_per_outlet_m3s"], "outlet_flow_m3s"),
        ("FlowBM3s", remote["expected_flow_per_outlet_m3s"], "outlet_flow_m3s"),
        ("TotalFlowM3s", remote["total_flow_m3s"], "total_flow_m3s"),
    ):
        _near(_value(samples, variable, observed), expected, tolerance, f"remote {variable}")


def _restored(samples: list[dict[str, Any]], observed: dt.datetime, sequence: int) -> None:
    for variable, expected in (
        ("HmiSeen", sequence), ("HmiAccepted", sequence), ("HmiRejectReason", 0),
        ("Owner", 1), ("AutoMode", 0), ("HmiRemoteEnabled", 0), ("IoHealthy", 1),
        ("PermissiveA", 1), ("PermissiveB", 1), ("MovingA", 0), ("MovingB", 0),
        ("TravelFaultA", 0), ("TravelFaultB", 0),
    ):
        if round(_value(samples, variable, observed)) != expected:
            raise EvidenceError(f"restored {variable} does not match product state")
    restore = CONTRACT["authorized_work"]["restore"]
    for variable, expected, tolerance in (
        ("RequestedTargetPct", restore["position_a_pct"], "position_pct"),
        ("RequestedTargetBPct", restore["position_b_pct"], "position_pct"),
        ("RequestedFlowM3s", restore["total_flow_m3s"], "total_flow_m3s"),
        ("PositionPct", restore["position_a_pct"], "position_pct"),
        ("PositionBPct", restore["position_b_pct"], "position_pct"),
        ("FlowM3s", 0.1, "outlet_flow_m3s"),
        ("FlowBM3s", 0.1, "outlet_flow_m3s"),
        ("TotalFlowM3s", restore["total_flow_m3s"], "total_flow_m3s"),
    ):
        _near(_value(samples, variable, observed), expected, tolerance, f"restored {variable}")


def _trace(samples: list[dict[str, Any]], start: dt.datetime, end: dt.datetime) -> int:
    variables = ("PositionPct", "PositionBPct", "FlowM3s", "FlowBM3s", "TotalFlowM3s")
    selected = {
        variable: [row for row in _rows(samples, variable) if start <= _time(row["source_time"], "sample source_time") <= end]
        for variable in variables
    }
    if any(len(rows) < CONTRACT["product_snapshot"]["minimum_trace_samples"] for rows in selected.values()):
        raise EvidenceError("W30.2 product history is too short")
    if any(row["quality"] != CONTRACT["product_snapshot"]["accepted_quality"] for rows in selected.values() for row in rows):
        raise EvidenceError("W30.2 product history contains non-good evidence")
    times = set.intersection(*(
        {_time(row["source_time"], "sample source_time") for row in rows}
        for rows in selected.values()
    ))
    if len(times) < CONTRACT["product_snapshot"]["minimum_trace_samples"]:
        raise EvidenceError("W30.2 has too few time-aligned product samples")
    return len(times)


def _card_2(submission: dict[str, Any], captured: dt.datetime, samples: list[dict[str, Any]], commands: list[dict[str, Any]], dispatch: list[dict[str, Any]]) -> dict[str, Any]:
    _exact(submission, {
        "asset", "request_id", "remote_sequence", "received_at", "completed_at",
        "restore_sequence", "restore_accepted_at", "final_observed_at", "interval_start",
        "interval_end", "interpretation",
    }, "W30.2 submission")
    if submission["asset"] != CONTRACT["asset"] or submission["interpretation"] != "durable_receipt_plc_acceptance_measured_completion_local_handback":
        raise EvidenceError("W30.2 asset or interpretation does not match")
    request_id = _request_id(submission["request_id"])
    remote_sequence = _integer(submission["remote_sequence"], "remote_sequence")
    restore_sequence = _integer(submission["restore_sequence"], "restore_sequence")
    if remote_sequence == restore_sequence:
        raise EvidenceError("remote and local sequences must remain distinct")
    received = _time(submission["received_at"], "received_at")
    completed = _time(submission["completed_at"], "completed_at")
    restore_accepted = _time(submission["restore_accepted_at"], "restore_accepted_at")
    final = _time(submission["final_observed_at"], "final_observed_at")
    start = _time(submission["interval_start"], "interval_start")
    end = _time(submission["interval_end"], "interval_end")
    if not start <= received < completed < restore_accepted <= final <= end <= captured:
        raise EvidenceError("W30.2 operation and handback interval is invalid")

    transitions = _dispatch_rows(dispatch, request_id)
    expected_states = CONTRACT["dispatcher"]["successful_states"]
    if [row["status"] for row in transitions] != expected_states:
        raise EvidenceError("dispatcher did not record the exact successful transition path")
    if any(row["sequence"] != remote_sequence for row in transitions):
        raise EvidenceError("dispatcher transition sequences do not agree")
    if _time(transitions[0]["time"], "dispatcher time") != received or _time(transitions[-1]["time"], "dispatcher time") != completed:
        raise EvidenceError("claimed dispatcher times do not match product history")
    _actual_request(transitions[0]["request"], request_id, received)
    if any(row["request"] != transitions[0]["request"] for row in transitions):
        raise EvidenceError("dispatcher transition request payload changed")
    detail = transitions[-1]["detail"]
    if detail.get("origin") != "observed equipment feedback" or detail.get("sequence") != remote_sequence:
        raise EvidenceError("dispatcher completion does not come from measured equipment feedback")
    remote = CONTRACT["authorized_work"]["remote"]
    _near(detail.get("flow_a_m3s"), remote["expected_flow_per_outlet_m3s"], "outlet_flow_m3s", "dispatcher outlet A flow")
    _near(detail.get("flow_b_m3s"), remote["expected_flow_per_outlet_m3s"], "outlet_flow_m3s", "dispatcher outlet B flow")

    _accepted(commands, "dispatcher", remote_sequence, completed)
    _accepted(commands, "HMI", restore_sequence, restore_accepted)
    _healthy_remote(samples, completed, remote_sequence)
    _restored(samples, final, restore_sequence)
    sample_count = _trace(samples, start, end)
    return {
        "request_id": request_id,
        "remote_sequence": remote_sequence,
        "restore_sequence": restore_sequence,
        "samples": sample_count,
        "baseline_restored": True,
    }


def evaluate(card: str, submission: dict[str, Any], product_snapshot: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(submission, dict) or "product_snapshot" in submission:
        raise EvidenceError("participant input cannot supply product evidence")
    captured, samples, commands, dispatch = _product(product_snapshot)
    evaluators = {
        "W30.1": lambda: _card_1(submission, captured, samples),
        "W30.2": lambda: _card_2(submission, captured, samples, commands, dispatch),
    }
    if card not in evaluators:
        raise EvidenceError("card is outside W30")
    return {
        "schema": "arwc.challenge-result/v1",
        "card": card,
        "satisfied": True,
        "product_source_digest": product_snapshot["source_digest"],
        "evidence": evaluators[card](),
    }
