#!/usr/bin/env python3
"""Compare W18 submissions with trusted native catalog and history records."""

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


def _time(value: Any, name: str = "time") -> dt.datetime:
    if not isinstance(value, str):
        raise EvidenceError(f"{name} must be an ISO 8601 string")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise EvidenceError(f"{name} must be valid ISO 8601") from error
    if parsed.tzinfo is None:
        raise EvidenceError(f"{name} must include a UTC offset")
    return parsed.astimezone(UTC)


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EvidenceError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise EvidenceError(f"{name} must be finite")
    return result


def _exact(value: dict[str, Any], fields: set[str], label: str) -> None:
    if not isinstance(value, dict) or set(value) != fields:
        raise EvidenceError(f"{label} fields do not match the contract")


def _product(snapshot: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    _exact(snapshot, {"schema", "asset", "captured_at", "source_digest", "catalog", "samples"}, "product snapshot")
    if snapshot["schema"] != "arwc.native-tag-observation/v1":
        raise EvidenceError("product snapshot schema does not match")
    if snapshot["asset"] != CONTRACT["asset"]:
        raise EvidenceError("product snapshot is for another asset")
    _time(snapshot["captured_at"], "captured_at")
    if not isinstance(snapshot["source_digest"], str) or not SHA256.fullmatch(snapshot["source_digest"]):
        raise EvidenceError("product snapshot digest is missing")
    if not isinstance(snapshot["catalog"], list) or not isinstance(snapshot["samples"], list):
        raise EvidenceError("product catalog and samples are required")

    catalog: dict[str, dict[str, Any]] = {}
    for entry in snapshot["catalog"]:
        _exact(entry, {"variable", "series", "node_id", "unit", "register_sha256", "definition", "scaling"}, "catalog entry")
        if not isinstance(entry["variable"], str) or entry["variable"] in catalog:
            raise EvidenceError("product catalog contains an invalid or duplicate variable")
        if not isinstance(entry["register_sha256"], str) or not SHA256.fullmatch(entry["register_sha256"]):
            raise EvidenceError("catalog register digest is invalid")
        if not isinstance(entry["definition"], dict) or not isinstance(entry["scaling"], dict):
            raise EvidenceError("catalog definition and scaling are required")
        catalog[entry["variable"]] = entry

    for row in snapshot["samples"]:
        _exact(row, {"variable", "source_time", "collected_time", "ingested_at", "value", "unit", "transport_quality", "process_quality", "node_id", "register_sha256"}, "product sample")
        _time(row["source_time"], "source_time")
        _time(row["collected_time"], "collected_time")
        _time(row["ingested_at"], "ingested_at")
        _number(row["value"], row["variable"])
    return catalog, snapshot["samples"]


def _rows(samples: list[dict[str, Any]], variable: str) -> list[dict[str, Any]]:
    return sorted(
        (row for row in samples if row["variable"] == variable),
        key=lambda row: _time(row["source_time"]),
    )


def _good_rows(samples: list[dict[str, Any]], variable: str) -> list[dict[str, Any]]:
    accepted = CONTRACT["provenance"]["accepted_process_quality"]
    return [row for row in _rows(samples, variable) if row["process_quality"] == accepted]


def _register_input(catalog: dict[str, dict[str, Any]], variable: str, raw_variable: str) -> dict[str, Any]:
    entry = catalog.get(variable)
    if entry is None:
        raise EvidenceError(f"native catalog is missing {variable}")
    inputs = entry["scaling"].get("inputs")
    if not isinstance(inputs, list):
        raise EvidenceError("native catalog lacks the Modbus input register")
    matches = [item for item in inputs if isinstance(item, dict) and item.get("variable") == raw_variable]
    if len(matches) != 1:
        raise EvidenceError("native catalog does not uniquely identify the raw register")
    return matches[0]


def _card_1(submission: dict[str, Any], catalog: dict[str, dict[str, Any]], samples: list[dict[str, Any]]) -> dict[str, Any]:
    _exact(submission, {"asset", "register_id", "project_revision", "register_sha256", "variables"}, "W18.1 submission")
    register = CONTRACT["register"]
    if submission["asset"] != CONTRACT["asset"] or submission["register_id"] != register["id"]:
        raise EvidenceError("W18.1 identifies another asset or register")
    if submission["variables"] != register["required_variables"]:
        raise EvidenceError("W18.1 does not identify the required native points")
    required = [catalog.get(variable) for variable in register["required_variables"]]
    if any(entry is None for entry in required):
        raise EvidenceError("W18.1 required point is absent from the native catalog")
    digests = {entry["register_sha256"] for entry in required if entry is not None}
    if digests != {submission["register_sha256"]}:
        raise EvidenceError("W18.1 register digest does not match the native catalog")
    revisions = _good_rows(samples, "ProjectRevision")
    if not revisions:
        raise EvidenceError("W18.1 lacks a current product-owned project revision")
    actual_revision = int(round(_number(revisions[-1]["value"], "ProjectRevision")))
    if submission["project_revision"] != register["project_revision"] or actual_revision != submission["project_revision"]:
        raise EvidenceError("W18.1 register revision does not match the running controller")
    return {"register_sha256": submission["register_sha256"], "project_revision": actual_revision}


def _card_2(submission: dict[str, Any], catalog: dict[str, dict[str, Any]]) -> dict[str, Any]:
    expected = CONTRACT["register"]["focus_point"]
    if submission != expected:
        raise EvidenceError("W18.2 register interpretation does not match the engineering record")
    entry = catalog.get(expected["plc_value"])
    if entry is None:
        raise EvidenceError("W18.2 point is absent from the native catalog")
    if entry["node_id"] != expected["opcua_node_id"] or entry["series"] != expected["historian_series"] or entry["unit"] != expected["engineering_unit"]:
        raise EvidenceError("W18.2 native point identity disagrees with the register")
    raw = _register_input(catalog, expected["plc_value"], expected["raw_variable"])
    required = {
        "offset": expected["pdu_offset"], "iec": expected["iec_address"],
        "type": expected["raw_type"], "counts_per_unit": expected["counts_per_unit"],
        "unit": expected["engineering_unit"],
    }
    if any(raw.get(field) != value for field, value in required.items()):
        raise EvidenceError("W18.2 native Modbus scaling disagrees with the register")
    functions = entry["scaling"].get("functions", {})
    if functions.get("inputs") != expected["function_code"]:
        raise EvidenceError("W18.2 native function code disagrees with the register")
    return {"variable": expected["plc_value"], "node_id": entry["node_id"], "series": entry["series"]}


def _largest_gap(samples: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any], float]:
    rows = _good_rows(samples, CONTRACT["provenance"]["variable"])
    if len(rows) < 2:
        raise EvidenceError("W18.3 lacks two good product samples")
    pairs = [(before, after, (_time(after["source_time"]) - _time(before["source_time"])).total_seconds())
             for before, after in zip(rows, rows[1:], strict=False)]
    before, after, seconds = max(pairs, key=lambda pair: pair[2])
    if seconds < CONTRACT["provenance"]["minimum_gap_seconds"]:
        raise EvidenceError("W18.3 product history contains no qualifying acquisition gap")
    for row in (before, after):
        if not (_time(row["source_time"]) <= _time(row["collected_time"]) <= _time(row["ingested_at"])):
            raise EvidenceError("W18.3 product timestamps violate source/collection/ingestion order")
    return before, after, seconds


def _card_3(submission: dict[str, Any], samples: list[dict[str, Any]]) -> dict[str, Any]:
    fields = {
        "variable", "before_source_time", "before_collected_time", "before_ingested_at",
        "after_source_time", "after_collected_time", "after_ingested_at", "gap_seconds",
        "before_transport_quality", "before_process_quality", "after_transport_quality",
        "after_process_quality", "unit", "interpretation",
    }
    _exact(submission, fields, "W18.3 submission")
    before, after, seconds = _largest_gap(samples)
    expected = {
        "variable": CONTRACT["provenance"]["variable"],
        "before_transport_quality": before["transport_quality"],
        "before_process_quality": before["process_quality"],
        "after_transport_quality": after["transport_quality"],
        "after_process_quality": after["process_quality"],
        "unit": before["unit"],
        "interpretation": CONTRACT["provenance"]["interpretation"],
    }
    if any(submission[field] != value for field, value in expected.items()):
        raise EvidenceError("W18.3 provenance interpretation does not match product history")
    for prefix, row in (("before", before), ("after", after)):
        for field in ("source_time", "collected_time", "ingested_at"):
            if _time(submission[f"{prefix}_{field}"]) != _time(row[field]):
                raise EvidenceError(f"W18.3 {prefix} {field} does not match product history")
    if abs(_number(submission["gap_seconds"], "gap_seconds") - seconds) > 0.001:
        raise EvidenceError("W18.3 gap duration does not match product history")
    if before["unit"] != after["unit"]:
        raise EvidenceError("W18.3 product unit is not stable across the selected gap")
    return {"variable": expected["variable"], "gap_seconds": seconds}


def _card_4(submission: dict[str, Any], catalog: dict[str, dict[str, Any]], samples: list[dict[str, Any]]) -> dict[str, Any]:
    _exact(submission, {"asset", "outlet_group", "reference", "mapping"}, "W18.4 submission")
    expected_mapping = CONTRACT["mapping"]
    focus = CONTRACT["register"]["focus_point"]
    if submission["asset"] != CONTRACT["asset"] or submission["outlet_group"] != expected_mapping["outlet_group"]:
        raise EvidenceError("W18.4 identifies another asset or outlet group")
    if submission["reference"] != {"instrument": focus["instrument"], "variable": focus["plc_value"], "source": "W17.OBS"}:
        raise EvidenceError("W18.4 does not use the verified W17 observation")
    if submission["mapping"] != expected_mapping["outlets"]:
        raise EvidenceError("W18.4 outlet mapping does not match the engineering evidence")

    variables: list[str] = []
    for outlet in expected_mapping["outlets"]:
        variables.extend((outlet["position_value"], outlet["flow_value"]))
        position = catalog.get(outlet["position_value"])
        flow = catalog.get(outlet["flow_value"])
        if (
            position is None or
            position["node_id"] != outlet["position_node_id"] or
            position["series"] != outlet["position_series"]
        ):
            raise EvidenceError("W18.4 position identity disagrees with the native catalog")
        if (
            flow is None or
            flow["node_id"] != outlet["flow_node_id"] or
            flow["series"] != outlet["flow_series"]
        ):
            raise EvidenceError("W18.4 flow identity disagrees with the native catalog")
        position_raw = _register_input(catalog, outlet["position_value"], outlet["position_raw"])
        flow_raw = _register_input(catalog, outlet["flow_value"], outlet["flow_raw"])
        if position_raw.get("offset") != outlet["position_offset"] or position_raw.get("iec") != outlet["position_iec"]:
            raise EvidenceError("W18.4 position channel disagrees with the native register")
        if flow_raw.get("offset") != outlet["flow_offset"] or flow_raw.get("iec") != outlet["flow_iec"]:
            raise EvidenceError("W18.4 flow channel disagrees with the native register")

    rows_by_variable = {variable: _good_rows(samples, variable) for variable in variables}
    if any(not rows for rows in rows_by_variable.values()):
        raise EvidenceError("W18.4 lacks a required good product series")
    tolerance = float(expected_mapping["alignment_tolerance_seconds"])
    anchors = reversed(rows_by_variable[expected_mapping["outlets"][1]["flow_value"]])
    observed_at: dt.datetime | None = None
    for anchor in anchors:
        anchor_time = _time(anchor["source_time"])
        aligned: dict[str, dict[str, Any]] = {}
        for variable, rows in rows_by_variable.items():
            nearest = min(rows, key=lambda row: abs((_time(row["source_time"]) - anchor_time).total_seconds()))
            if abs((_time(nearest["source_time"]) - anchor_time).total_seconds()) > tolerance:
                break
            aligned[variable] = nearest
        if len(aligned) != len(variables):
            continue
        consistent = True
        for outlet in expected_mapping["outlets"]:
            position_value = _number(aligned[outlet["position_value"]]["value"], outlet["position_value"])
            flow_value = _number(aligned[outlet["flow_value"]]["value"], outlet["flow_value"])
            if abs(flow_value - position_value * 0.005) > 0.01:
                consistent = False
                break
        if consistent:
            observed_at = anchor_time
            break
    if observed_at is None:
        raise EvidenceError("W18.4 lacks a time-aligned, physically consistent product observation")
    return {"outlet_group": expected_mapping["outlet_group"], "observed_at": observed_at.isoformat()}


def evaluate(card: str, submission: dict[str, Any], product_snapshot: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(submission, dict) or "product_snapshot" in submission:
        raise EvidenceError("participant input cannot supply product evidence")
    catalog, samples = _product(product_snapshot)
    evaluators = {
        "W18.1": lambda: _card_1(submission, catalog, samples),
        "W18.2": lambda: _card_2(submission, catalog),
        "W18.3": lambda: _card_3(submission, samples),
        "W18.4": lambda: _card_4(submission, catalog, samples),
    }
    if card not in evaluators:
        raise EvidenceError("card is outside W18")
    return {
        "schema": "arwc.challenge-result/v1",
        "card": card,
        "satisfied": True,
        "product_source_digest": product_snapshot["source_digest"],
        "evidence": evaluators[card](),
    }
