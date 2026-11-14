#!/usr/bin/env python3
"""Evaluate W33 against native dispatch, PLC, historian, and corporate records."""

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


def _integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise EvidenceError(f"{label} must be an integer")
    return value


def _uuid(value: Any, label: str = "request_id") -> str:
    if not isinstance(value, str):
        raise EvidenceError(f"{label} must be a UUID string")
    try:
        parsed = uuid.UUID(value)
    except ValueError as error:
        raise EvidenceError(f"{label} must be a valid UUID") from error
    if str(parsed) != value or parsed.version != 4:
        raise EvidenceError(f"{label} must be a canonical UUIDv4")
    return value


def _near(actual: Any, expected: float, tolerance: str, label: str) -> None:
    if abs(_number(actual, label) - expected) > CONTRACT["tolerance"][tolerance]:
        raise EvidenceError(f"{label} does not match product evidence")


def _configuration() -> dict[str, Any]:
    return {
        "project_revision": CONTRACT["project_revision"],
        "dispatcher": CONTRACT["dispatcher"],
    }


def _corporate() -> dict[str, Any]:
    source = CONTRACT["corporate"]
    return {
        "tariff": {
            "record_id": source["tariff"],
            "revision": source["tariff_revision"],
            "planning_window": source["planning_window"],
            "asset": CONTRACT["asset"],
            "currency": source["currency"],
            "unit": source["tariff_unit"],
            "rate": source["tariff_rate_per_ml"],
            "effective_from": source["effective_from"],
            "effective_to": source["effective_to"],
        },
        "allocation": {
            "record_id": source["allocation"],
            "revision": source["allocation_revision"],
            "planning_window": source["planning_window"],
            "asset": CONTRACT["asset"],
            "unit": source["volume_unit"],
            "committed_volume": source["committed_volume_ml"],
            "effective_from": source["effective_from"],
            "effective_to": source["effective_to"],
        },
    }


def _product(snapshot: dict[str, Any]) -> tuple[dt.datetime, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    _exact(snapshot, {
        "schema", "asset", "captured_at", "source_digest", "corporate_digest",
        "configuration", "samples", "commands", "dispatch", "corporate",
    }, "product snapshot")
    if snapshot["schema"] != CONTRACT["product_snapshot"]["schema"] or snapshot["asset"] != CONTRACT["asset"]:
        raise EvidenceError("product snapshot is for another schema or asset")
    for field in ("source_digest", "corporate_digest"):
        if not isinstance(snapshot[field], str) or not SHA256.fullmatch(snapshot[field]):
            raise EvidenceError(f"{field} is missing")
    if snapshot["configuration"] != _configuration():
        raise EvidenceError("installed dispatcher or controller revision does not match")
    if snapshot["corporate"] != _corporate():
        raise EvidenceError("corporate planning records do not match the W33 basis")
    for field in ("samples", "commands", "dispatch"):
        if not isinstance(snapshot[field], list):
            raise EvidenceError(f"product {field} must be a list")
    return (_time(snapshot["captured_at"], "captured_at"), snapshot["samples"],
            snapshot["commands"], snapshot["dispatch"])


def _sample_rows(samples: list[dict[str, Any]], variable: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in samples:
        _exact(row, {"variable", "source_time", "value", "unit", "quality"}, "product sample")
        source = _time(row["source_time"], "sample source_time")
        _number(row["value"], row["variable"])
        if row["variable"] == variable:
            rows.append({**row, "_time": source})
    return sorted(rows, key=lambda row: row["_time"])


def _good_rows(samples: list[dict[str, Any]], variable: str, start: dt.datetime, end: dt.datetime) -> list[dict[str, Any]]:
    rows = [
        row for row in _sample_rows(samples, variable)
        if start <= row["_time"] <= end and row["quality"] == CONTRACT["product_snapshot"]["accepted_quality"]
    ]
    if not rows:
        raise EvidenceError(f"no good {variable} history exists in the claimed interval")
    return rows


def _point(samples: list[dict[str, Any]], variable: str, observed: dt.datetime) -> float:
    rows = _sample_rows(samples, variable)
    if not rows:
        raise EvidenceError(f"product history is missing {variable}")
    row = min(rows, key=lambda item: abs((item["_time"] - observed).total_seconds()))
    if abs((row["_time"] - observed).total_seconds()) > CONTRACT["product_snapshot"]["maximum_point_distance_seconds"]:
        raise EvidenceError(f"no {variable} sample is near the claimed observation")
    if row["quality"] != CONTRACT["product_snapshot"]["accepted_quality"]:
        raise EvidenceError(f"{variable} does not have good process quality")
    return _number(row["value"], variable)


def _command_rows(commands: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in commands:
        _exact(row, {"source_time", "channel", "decision", "sequence", "native_status"}, "product command")
        result.append({**row, "_time": _time(row["source_time"], "command source_time")})
        _integer(row["sequence"], "command sequence")
    return sorted(result, key=lambda row: row["_time"])


def _native_acceptance(commands: list[dict[str, Any]], channel: str, sequence: int, observed: dt.datetime) -> None:
    rows = [row for row in _command_rows(commands)
            if row["channel"] == channel and row["decision"] == "accepted" and row["sequence"] == sequence]
    if len(rows) != 1:
        raise EvidenceError(f"exactly one native {channel} acceptance is required")
    if abs((rows[0]["_time"] - observed).total_seconds()) > CONTRACT["product_snapshot"]["maximum_point_distance_seconds"]:
        raise EvidenceError(f"native {channel} acceptance is outside the product interval")
    if rows[0]["native_status"] not in ("Good", "The operation succeeded. StatusGood (0x0)"):
        raise EvidenceError(f"native {channel} acceptance has bad status")


def _dispatch_rows(dispatch: list[dict[str, Any]], request_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in dispatch:
        _exact(row, {"time", "id", "principal", "sequence", "status", "detail", "request", "origin"}, "dispatcher transition")
        observed = _time(row["time"], "dispatcher time")
        if row["id"] != request_id:
            continue
        if row["principal"] != CONTRACT["dispatcher"]["principal"]:
            raise EvidenceError("dispatcher principal is wrong")
        if row["origin"] != "Authenticated MQTT dispatcher and observed PLC feedback":
            raise EvidenceError("dispatcher product origin is wrong")
        _integer(row["sequence"], "dispatcher sequence")
        if not isinstance(row["detail"], dict) or not isinstance(row["request"], dict):
            raise EvidenceError("dispatcher product record is incomplete")
        rows.append({**row, "_time": observed})
    return sorted(rows, key=lambda row: row["_time"])


def _successful_request(dispatch: list[dict[str, Any]], request_id: str, expected_flow: float | None = None) -> dict[str, Any]:
    rows = _dispatch_rows(dispatch, request_id)
    if [row["status"] for row in rows] != CONTRACT["dispatcher"]["successful_states"]:
        raise EvidenceError("dispatcher did not record the exact successful transition path")
    if len({row["sequence"] for row in rows}) != 1:
        raise EvidenceError("dispatcher transition sequences do not agree")
    request = rows[0]["request"]
    if set(request) != set(CONTRACT["dispatcher"]["request_fields"]):
        raise EvidenceError("dispatcher request fields do not match the site contract")
    if request["id"] != request_id or request["asset"] != CONTRACT["asset"] or request["mode"] != "automatic":
        raise EvidenceError("dispatcher request identity, asset, or mode is wrong")
    if request["position_a_pct"] != 20.0 or request["position_b_pct"] != 20.0:
        raise EvidenceError("dispatcher request changed the reviewed manual-position fields")
    flow = _number(request["total_flow_m3s"], "request total flow")
    if expected_flow is not None:
        _near(flow, expected_flow, "calculation", "request total flow")
    if any(row["request"] != request for row in rows):
        raise EvidenceError("dispatcher request changed during its transition path")
    return {"rows": rows, "request": request, "sequence": rows[0]["sequence"],
            "plc_accepted": rows[3]["_time"], "completed": rows[4]["_time"], "flow": flow}


def _calibration(submission: dict[str, Any], samples: list[dict[str, Any]], dispatch: list[dict[str, Any]]) -> dict[str, Any]:
    _exact(submission, {
        "asset", "request_id", "plc_accepted_at", "settled_start", "settled_end",
        "requested_total_flow_m3s", "mean_total_flow_m3s", "response_delay_seconds",
        "flow_gain", "good_sample_count",
    }, "W33.1 submission")
    if submission["asset"] != CONTRACT["asset"]:
        raise EvidenceError("W33.1 is for another asset")
    request_id = _uuid(submission["request_id"])
    operation = _successful_request(dispatch, request_id, CONTRACT["forecast"]["calibration_total_flow_m3s"])
    accepted = _time(submission["plc_accepted_at"], "plc_accepted_at")
    start = _time(submission["settled_start"], "settled_start")
    end = _time(submission["settled_end"], "settled_end")
    if accepted != operation["plc_accepted"] or not accepted <= start <= end:
        raise EvidenceError("W33.1 timing does not match the dispatcher record")
    in_tolerance = [
        row for row in _sample_rows(samples, "TotalFlowM3s")
        if row["_time"] >= accepted
        and row["quality"] == CONTRACT["product_snapshot"]["accepted_quality"]
        and abs(_number(row["value"], "TotalFlowM3s") - operation["flow"]) <= CONTRACT["forecast"]["settled_tolerance_m3s"]
    ]
    if not in_tolerance:
        raise EvidenceError("no good in-tolerance flow response follows PLC acceptance")
    if start != in_tolerance[0]["_time"]:
        raise EvidenceError("settled_start is not the first good in-tolerance response")
    settled = _good_rows(samples, "TotalFlowM3s", start, end)
    if len(settled) < CONTRACT["forecast"]["minimum_settled_samples"]:
        raise EvidenceError("W33.1 has too few settled product samples")
    if any(abs(_number(row["value"], "TotalFlowM3s") - operation["flow"]) > CONTRACT["forecast"]["settled_tolerance_m3s"] for row in settled):
        raise EvidenceError("W33.1 settled interval includes out-of-tolerance flow")
    mean = sum(_number(row["value"], "TotalFlowM3s") for row in settled) / len(settled)
    gain = mean / operation["flow"]
    delay = (start - accepted).total_seconds()
    _near(submission["requested_total_flow_m3s"], operation["flow"], "calculation", "requested total flow")
    _near(submission["mean_total_flow_m3s"], mean, "calculation", "mean total flow")
    _near(submission["response_delay_seconds"], delay, "calculation", "response delay")
    _near(submission["flow_gain"], gain, "calculation", "flow gain")
    if _integer(submission["good_sample_count"], "good_sample_count") != len(settled):
        raise EvidenceError("good_sample_count does not match product history")
    return {"request_id": request_id, "response_delay_seconds": delay,
            "flow_gain": gain, "good_sample_count": len(settled)}


def _numbers(value: Any, name: str, count: int, maximum: float) -> list[float]:
    if not isinstance(value, list) or len(value) != count:
        raise EvidenceError(f"{name} must have {count} values")
    result = [_number(item, name) for item in value]
    if any(item < 0 or item > maximum for item in result):
        raise EvidenceError(f"{name} is outside the operating bounds")
    if any(abs(result[index] - result[index - 1]) > CONTRACT["schedule"]["maximum_step_m3s"] + 1e-9 for index in range(1, count)):
        raise EvidenceError(f"{name} exceeds the ramp limit")
    return result


def _schedule(value: Any, flow_gain: float) -> dict[str, Any]:
    _exact(value, {"schema", "instruction", "asset", "interval_seconds", "reservoir_release_m3s", "alternate_supply_m3s"}, "operating schedule")
    spec = CONTRACT["schedule"]
    if (value["schema"] != spec["schema"] or value["instruction"] != CONTRACT["instruction"]
            or value["asset"] != CONTRACT["asset"] or value["interval_seconds"] != spec["interval_seconds"]):
        raise EvidenceError("operating schedule identity does not match W33")
    releases = _numbers(value["reservoir_release_m3s"], "reservoir release", spec["interval_count"], spec["maximum_release_m3s"])
    alternate = _numbers(value["alternate_supply_m3s"], "alternate supply", spec["interval_count"], spec["maximum_alternate_m3s"])
    buffers = [spec["initial_buffer_m3"]]
    for release, supply, demand in zip(releases, alternate, spec["planned_demand_m3s"], strict=True):
        buffers.append(buffers[-1] + spec["interval_seconds"] * (flow_gain * release + supply - demand))
    volume = sum(spec["interval_seconds"] * flow_gain * release for release in releases) / 1000.0
    if any(buffer < spec["minimum_buffer_m3"] or buffer > spec["maximum_buffer_m3"] for buffer in buffers):
        raise EvidenceError("operating schedule exceeds the buffer envelope")
    if not spec["minimum_final_buffer_m3"] <= buffers[-1] <= spec["maximum_final_buffer_m3"]:
        raise EvidenceError("operating schedule misses the final buffer envelope")
    if not spec["minimum_projected_volume_ml"] <= volume <= spec["maximum_projected_volume_ml"]:
        raise EvidenceError("operating schedule misses the reservoir-volume objective")
    return {"schedule": value, "releases": releases, "alternate": alternate,
            "buffers_m3": buffers, "projected_volume_ml": volume, "flow_gain": flow_gain}


def _card_2(submission: dict[str, Any], samples: list[dict[str, Any]], dispatch: list[dict[str, Any]]) -> dict[str, Any]:
    _exact(submission, {"forecast", "schedule"}, "W33.2 submission")
    calibration = _calibration(submission["forecast"], samples, dispatch)
    planned = _schedule(submission["schedule"], calibration["flow_gain"])
    return {"forecast_request_id": calibration["request_id"],
            "projected_reservoir_volume_ml": planned["projected_volume_ml"],
            "final_buffer_m3": planned["buffers_m3"][-1], "feasible": True}


def _commissioning(submission: dict[str, Any], samples: list[dict[str, Any]], commands: list[dict[str, Any]], dispatch: list[dict[str, Any]]) -> dict[str, Any]:
    _exact(submission, {
        "asset", "forecast", "schedule", "request_ids", "started_at", "completed_at",
        "restore_sequence", "restore_accepted_at", "final_observed_at", "interpretation",
    }, "W33.3 submission")
    if submission["asset"] != CONTRACT["asset"] or submission["interpretation"] != "measured_twelve_step_commissioning_run_with_local_handback":
        raise EvidenceError("W33.3 asset or interpretation is wrong")
    calibration = _calibration(submission["forecast"], samples, dispatch)
    planned = _schedule(submission["schedule"], calibration["flow_gain"])
    request_ids = submission["request_ids"]
    if not isinstance(request_ids, list) or len(request_ids) != CONTRACT["schedule"]["interval_count"]:
        raise EvidenceError("W33.3 requires twelve request IDs")
    request_ids = [_uuid(item, "request_ids item") for item in request_ids]
    if len(set(request_ids)) != len(request_ids):
        raise EvidenceError("commissioning requests must have distinct identities")
    started = _time(submission["started_at"], "started_at")
    completed = _time(submission["completed_at"], "completed_at")
    restore_time = _time(submission["restore_accepted_at"], "restore_accepted_at")
    final = _time(submission["final_observed_at"], "final_observed_at")
    if not started < completed < restore_time <= final:
        raise EvidenceError("commissioning and handback times are not ordered")
    operations = [_successful_request(dispatch, request_id, release)
                  for request_id, release in zip(request_ids, planned["releases"], strict=True)]
    if operations[0]["rows"][0]["_time"] != started or operations[-1]["completed"] != completed:
        raise EvidenceError("commissioning interval does not match product dispatch history")
    if any(operations[index]["completed"] >= operations[index + 1]["rows"][0]["_time"] for index in range(len(operations) - 1)):
        raise EvidenceError("commissioning requests overlap or are out of order")
    if len({operation["sequence"] for operation in operations}) != len(operations):
        raise EvidenceError("commissioning requests reused a PLC sequence")
    for operation in operations:
        _native_acceptance(commands, "dispatcher", operation["sequence"], operation["plc_accepted"])
        _near(_point(samples, "TotalFlowM3s", operation["completed"]), operation["flow"], "total_flow_m3s", "completed total flow")
    restore_sequence = _integer(submission["restore_sequence"], "restore_sequence")
    _native_acceptance(commands, "HMI", restore_sequence, restore_time)
    for variable, expected in (("HmiAccepted", restore_sequence), ("Owner", 1), ("AutoMode", 0),
                               ("HmiRemoteEnabled", 0), ("IoHealthy", 1),
                               ("PermissiveA", 1), ("PermissiveB", 1),
                               ("MovingA", 0), ("MovingB", 0),
                               ("TravelFaultA", 0), ("TravelFaultB", 0)):
        if round(_point(samples, variable, final)) != expected:
            raise EvidenceError(f"final {variable} does not match the handback baseline")
    for variable, expected, tolerance in (("PositionPct", 20.0, "position_pct"),
                                          ("PositionBPct", 20.0, "position_pct"),
                                          ("FlowM3s", 0.1, "outlet_flow_m3s"),
                                          ("FlowBM3s", 0.1, "outlet_flow_m3s"),
                                          ("TotalFlowM3s", 0.2, "total_flow_m3s")):
        _near(_point(samples, variable, final), expected, tolerance, f"final {variable}")
    return {"request_ids": request_ids, "completed_steps": len(operations),
            "baseline_restored": True, "restore_sequence": restore_sequence,
            "operations": operations}


def _card_4(submission: dict[str, Any], samples: list[dict[str, Any]], commands: list[dict[str, Any]], dispatch: list[dict[str, Any]]) -> dict[str, Any]:
    _exact(submission, {
        "commissioning", "observed_mean_total_flow_m3s", "projected_reservoir_volume_ml",
        "starting_usable_volume_ml", "remaining_usable_volume_ml", "committed_volume_ml",
        "projected_shortfall_ml", "tariff_rate_per_ml", "projected_liability_usd", "interpretation",
    }, "W33.4 submission")
    if submission["interpretation"] != "measured_commissioning_evidence_with_projected_one_hour_effect":
        raise EvidenceError("W33.4 must distinguish measured evidence from projection")
    commissioned = _commissioning(submission["commissioning"], samples, commands, dispatch)
    means: list[float] = []
    for operation in commissioned["operations"]:
        end = operation["completed"]
        start = end - dt.timedelta(seconds=CONTRACT["product_snapshot"]["settled_window_seconds"])
        rows = _good_rows(samples, "TotalFlowM3s", start, end)
        means.append(sum(_number(row["value"], "TotalFlowM3s") for row in rows) / len(rows))
    observed = submission["observed_mean_total_flow_m3s"]
    if not isinstance(observed, list) or len(observed) != len(means):
        raise EvidenceError("W33.4 requires twelve measured step means")
    for index, (claimed, actual) in enumerate(zip(observed, means, strict=True), start=1):
        _near(claimed, actual, "calculation", f"step {index} mean flow")
    interval = CONTRACT["schedule"]["interval_seconds"]
    projected_volume = sum(interval * value for value in means) / 1000.0
    first_request = commissioned["operations"][0]["rows"][0]["_time"]
    starting_volume = _point(samples, "UsableVolumeML", first_request)
    remaining = starting_volume - projected_volume
    committed = CONTRACT["corporate"]["committed_volume_ml"]
    shortfall = max(0.0, committed - remaining)
    rate = CONTRACT["corporate"]["tariff_rate_per_ml"]
    liability = shortfall * rate
    for field, expected in (("projected_reservoir_volume_ml", projected_volume),
                            ("starting_usable_volume_ml", starting_volume),
                            ("remaining_usable_volume_ml", remaining),
                            ("committed_volume_ml", committed),
                            ("projected_shortfall_ml", shortfall),
                            ("tariff_rate_per_ml", rate),
                            ("projected_liability_usd", liability)):
        _near(submission[field], expected, "calculation", field)
    return {"measured_steps": len(means), "projected_reservoir_volume_ml": projected_volume,
            "projected_shortfall_ml": shortfall, "projected_liability_usd": liability,
            "baseline_restored": True}


def evaluate(card: str, submission: dict[str, Any], product_snapshot: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(submission, dict) or "product_snapshot" in submission:
        raise EvidenceError("participant input cannot supply product evidence")
    captured, samples, commands, dispatch = _product(product_snapshot)
    evaluators = {
        "W33.1": lambda: _calibration(submission, samples, dispatch),
        "W33.2": lambda: _card_2(submission, samples, dispatch),
        "W33.3": lambda: _commissioning(submission, samples, commands, dispatch),
        "W33.4": lambda: _card_4(submission, samples, commands, dispatch),
    }
    if card not in evaluators:
        raise EvidenceError("card is outside W33")
    if captured < max((_time(row["time"], "dispatcher time") for row in dispatch), default=captured):
        raise EvidenceError("product capture predates dispatcher history")
    return {"schema": "arwc.challenge-result/v1", "card": card, "satisfied": True,
            "product_source_digest": product_snapshot["source_digest"], "evidence": evaluators[card]()}
