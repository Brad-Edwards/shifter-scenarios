#!/usr/bin/env python3
"""Compare a W17 participant observation with trusted native-product records."""

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


def _time(value: Any) -> dt.datetime:
    if not isinstance(value, str):
        raise EvidenceError("time must be an ISO 8601 string")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise EvidenceError("time must be valid ISO 8601") from error
    if parsed.tzinfo is None:
        raise EvidenceError("time must include a UTC offset")
    return parsed.astimezone(UTC)


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EvidenceError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise EvidenceError(f"{name} must be finite")
    return result


def _exact(value: dict[str, Any], fields: set[str], label: str) -> None:
    if set(value) != fields:
        raise EvidenceError(f"{label} fields do not match the contract")


def _product(snapshot: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    _exact(snapshot, {"schema", "asset", "captured_at", "source_digest", "catalog", "samples"}, "product snapshot")
    if snapshot["schema"] != CONTRACT["product_snapshot"]["schema"]:
        raise EvidenceError("product snapshot schema does not match")
    if snapshot["asset"] != CONTRACT["asset"]:
        raise EvidenceError("product snapshot is for another asset")
    _time(snapshot["captured_at"])
    if not isinstance(snapshot["source_digest"], str) or not SHA256.fullmatch(snapshot["source_digest"]):
        raise EvidenceError("product snapshot digest is missing")
    if not isinstance(snapshot["catalog"], dict) or not isinstance(snapshot["samples"], list):
        raise EvidenceError("product catalog and samples are required")
    return snapshot["samples"], snapshot["catalog"]


def _rows(samples: list[dict[str, Any]], variable: str) -> list[dict[str, Any]]:
    result = []
    for row in samples:
        _exact(row, {"variable", "source_time", "value", "unit", "quality"}, "product sample")
        if row["variable"] != variable:
            continue
        _time(row["source_time"])
        _number(row["value"], variable)
        result.append(row)
    return sorted(result, key=lambda row: _time(row["source_time"]))


def _point(samples: list[dict[str, Any]], variable: str, observed_at: dt.datetime) -> dict[str, Any]:
    candidates = _rows(samples, variable)
    if not candidates:
        raise EvidenceError(f"product sample is missing for {variable}")
    row = min(candidates, key=lambda item: abs((_time(item["source_time"]) - observed_at).total_seconds()))
    distance = abs((_time(row["source_time"]) - observed_at).total_seconds())
    if distance > CONTRACT["product_snapshot"]["maximum_point_distance_seconds"]:
        raise EvidenceError(f"{variable} has no sample in the observation interval")
    if row["quality"] != CONTRACT["product_snapshot"]["accepted_quality"]:
        raise EvidenceError(f"{variable} does not have good process quality")
    return row


def _matches(submitted: Any, row: dict[str, Any], variable: str) -> None:
    actual = _number(row["value"], variable)
    claimed = _number(submitted, variable)
    if abs(actual - claimed) > CONTRACT["tolerance"][variable]:
        raise EvidenceError(f"{variable} does not match product history")


def _card_1(submission: dict[str, Any], samples: list[dict[str, Any]]) -> dict[str, Any]:
    _exact(submission, {"asset", "observed_at", "measured", "accepted_settings"}, "W17.1 submission")
    if submission["asset"] != CONTRACT["asset"]:
        raise EvidenceError("W17.1 uses another asset")
    observed = _time(submission["observed_at"])
    measured = submission["measured"]
    accepted = submission["accepted_settings"]
    measured_fields = {
        "level_m": "LevelM", "usable_volume_ml": "UsableVolumeML",
        "outlet_a_position_pct": "PositionPct", "outlet_b_position_pct": "PositionBPct",
        "outlet_a_flow_m3s": "FlowM3s", "outlet_b_flow_m3s": "FlowBM3s",
        "total_flow_m3s": "TotalFlowM3s",
    }
    accepted_fields = {
        "outlet_a_position_pct": "RequestedTargetPct",
        "outlet_b_position_pct": "RequestedTargetBPct",
        "total_flow_m3s": "RequestedFlowM3s",
    }
    if not isinstance(measured, dict) or not isinstance(accepted, dict):
        raise EvidenceError("W17.1 measured and accepted settings must be objects")
    _exact(measured, set(measured_fields), "W17.1 measured")
    _exact(accepted, set(accepted_fields), "W17.1 accepted settings")
    for field, variable in measured_fields.items():
        _matches(measured[field], _point(samples, variable, observed), variable)
    for field, variable in accepted_fields.items():
        _matches(accepted[field], _point(samples, variable, observed), variable)
    return {"observed_at": submission["observed_at"], "variables": sorted([*measured_fields.values(), *accepted_fields.values()])}


def _card_2(submission: dict[str, Any], samples: list[dict[str, Any]]) -> dict[str, Any]:
    _exact(submission, {"asset", "observed_at", "mode", "owner", "field_data", "permissive_a", "permissive_b"}, "W17.2 submission")
    if submission["asset"] != CONTRACT["asset"]:
        raise EvidenceError("W17.2 uses another asset")
    observed = _time(submission["observed_at"])
    product = {
        variable: int(round(_number(_point(samples, variable, observed)["value"], variable)))
        for variable in ("AutoMode", "Owner", "IoHealthy", "PermissiveA", "PermissiveB")
    }
    expected = {
        "mode": {0: "manual", 1: "automatic_flow"}.get(product["AutoMode"]),
        "owner": {0: "unowned", 1: "hmi", 2: "dispatcher"}.get(product["Owner"]),
        "field_data": {0: "unavailable", 1: "healthy"}.get(product["IoHealthy"]),
        "permissive_a": bool(product["PermissiveA"]),
        "permissive_b": bool(product["PermissiveB"]),
    }
    if any(submission[field] != value for field, value in expected.items()):
        raise EvidenceError("W17.2 operating state does not match product history")
    return {"observed_at": submission["observed_at"], "state": expected}


def _card_3(submission: dict[str, Any], catalog: dict[str, Any]) -> dict[str, Any]:
    _exact(submission, {"instrument", "variable", "node_id", "historian_series", "unit"}, "W17.3 submission")
    expected = CONTRACT["instrument"]
    if submission != expected:
        raise EvidenceError("W17.3 instrument binding does not match the engineering reference")
    entry = catalog.get(expected["variable"])
    if not isinstance(entry, dict):
        raise EvidenceError("W17.3 product tag is absent from the native catalog")
    required = {"node_id": expected["node_id"], "series": expected["historian_series"], "unit": expected["unit"]}
    if any(entry.get(field) != value for field, value in required.items()):
        raise EvidenceError("W17.3 product catalog disagrees with the engineering reference")
    return {"instrument": expected["instrument"], "product_catalog": required}


def _card_4(submission: dict[str, Any], samples: list[dict[str, Any]]) -> dict[str, Any]:
    _exact(submission, {"asset", "start", "end", "hmi_variable", "opcua_node", "historian_series", "summary"}, "W17.4 submission")
    instrument = CONTRACT["instrument"]
    if submission["asset"] != CONTRACT["asset"] or submission["hmi_variable"] != instrument["variable"] or submission["opcua_node"] != instrument["node_id"] or submission["historian_series"] != instrument["historian_series"]:
        raise EvidenceError("W17.4 does not bind the same point across products")
    start, end = _time(submission["start"]), _time(submission["end"])
    seconds = (end - start).total_seconds()
    policy = CONTRACT["product_snapshot"]
    if seconds < policy["minimum_trace_seconds"] or seconds > policy["maximum_trace_seconds"]:
        raise EvidenceError("W17.4 interval is outside the bounded observation window")
    selected: dict[str, list[dict[str, Any]]] = {}
    for variable in ("FlowBM3s", "PositionBPct"):
        selected[variable] = [row for row in _rows(samples, variable) if start <= _time(row["source_time"]) <= end]
        if len(selected[variable]) < policy["minimum_trace_samples"]:
            raise EvidenceError(f"W17.4 has too few {variable} samples")
        if any(row["quality"] != policy["accepted_quality"] for row in selected[variable]):
            raise EvidenceError(f"W17.4 {variable} trace contains non-good product evidence")
    flow_by_time = {_time(row["source_time"]): row for row in selected["FlowBM3s"]}
    position_by_time = {_time(row["source_time"]): row for row in selected["PositionBPct"]}
    paired_times = sorted(set(flow_by_time) & set(position_by_time))
    if len(paired_times) < policy["minimum_trace_samples"]:
        raise EvidenceError("W17.4 has too few time-aligned field samples")
    flows = [_number(flow_by_time[when]["value"], "FlowBM3s") for when in paired_times]
    positions = [_number(position_by_time[when]["value"], "PositionBPct") for when in paired_times]
    for flow, position in zip(flows, positions, strict=True):
        if abs(flow - position * 0.005) > 0.01:
            raise EvidenceError("W17.4 field position and measured flow are inconsistent")
    summary = submission["summary"]
    if not isinstance(summary, dict):
        raise EvidenceError("W17.4 summary must be an object")
    _exact(summary, {"first_flow_m3s", "last_flow_m3s", "minimum_flow_m3s", "maximum_flow_m3s", "sample_count"}, "W17.4 summary")
    expected = {
        "first_flow_m3s": flows[0], "last_flow_m3s": flows[-1],
        "minimum_flow_m3s": min(flows), "maximum_flow_m3s": max(flows),
        "sample_count": len(flows),
    }
    if summary["sample_count"] != expected["sample_count"]:
        raise EvidenceError("W17.4 sample count does not match product history")
    for field in ("first_flow_m3s", "last_flow_m3s", "minimum_flow_m3s", "maximum_flow_m3s"):
        if abs(_number(summary[field], field) - expected[field]) > CONTRACT["tolerance"]["FlowBM3s"]:
            raise EvidenceError(f"W17.4 {field} does not match product history")
    return {"start": submission["start"], "end": submission["end"], "samples": len(flows)}


def evaluate(card: str, submission: dict[str, Any], product_snapshot: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(submission, dict) or "product_snapshot" in submission:
        raise EvidenceError("participant input cannot supply product evidence")
    samples, catalog = _product(product_snapshot)
    evaluators = {
        "W17.1": lambda: _card_1(submission, samples),
        "W17.2": lambda: _card_2(submission, samples),
        "W17.3": lambda: _card_3(submission, catalog),
        "W17.4": lambda: _card_4(submission, samples),
    }
    if card not in evaluators:
        raise EvidenceError("card is outside W17")
    flags = {
        "W17.1": "FLAG{33a22dd3dae3a5a9}",
        "W17.2": "FLAG{a6a4563e676656d3}",
        "W17.3": "FLAG{29af64987ad77321}",
        "W17.4": "FLAG{a61eaf28fdd2f12c}",
    }
    return {
        "schema": "arwc.challenge-result/v1",
        "card": card,
        "satisfied": True,
        "product_source_digest": product_snapshot["source_digest"],
        "evidence": evaluators[card](),
        "flag": flags[card],
    }
