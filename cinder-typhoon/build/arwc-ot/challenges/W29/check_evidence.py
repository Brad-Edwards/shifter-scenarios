#!/usr/bin/env python3
"""Compare W29 answers with corporate records and native process history."""

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


def _near(actual: Any, expected: float, label: str) -> None:
    if abs(_number(actual, label) - expected) > CONTRACT["tolerance_ml"]:
        raise EvidenceError(f"{label} does not match product evidence")


def _corporate_expected() -> dict[str, dict[str, Any]]:
    common = {"planning_window": CONTRACT["planning_window"], "asset": CONTRACT["asset"]}
    return {
        "tariff": {**CONTRACT["tariff"], **common},
        "allocation": {**CONTRACT["allocation"], **common},
        "report": {**CONTRACT["report"], **common},
    }


def _product(snapshot: dict[str, Any]) -> tuple[dt.datetime, list[dict[str, Any]]]:
    _exact(snapshot, {
        "schema", "asset", "captured_at", "source_digest", "corporate_digest",
        "corporate", "samples",
    }, "product snapshot")
    if snapshot["schema"] != CONTRACT["product_snapshot"]["schema"] or snapshot["asset"] != CONTRACT["asset"]:
        raise EvidenceError("product snapshot is for another schema or asset")
    for field in ("source_digest", "corporate_digest"):
        if not isinstance(snapshot[field], str) or not SHA256.fullmatch(snapshot[field]):
            raise EvidenceError(f"{field} is missing")
    if snapshot["corporate"] != _corporate_expected():
        raise EvidenceError("corporate product records do not match the planning contract")
    if not isinstance(snapshot["samples"], list) or not snapshot["samples"]:
        raise EvidenceError("native usable-volume samples are required")
    captured = _time(snapshot["captured_at"], "captured_at")
    if not _time(CONTRACT["tariff"]["effective_from"], "tariff effective_from") <= captured < _time(CONTRACT["tariff"]["effective_to"], "tariff effective_to"):
        raise EvidenceError("product capture is outside the planning window")
    return captured, snapshot["samples"]


def _sample(samples: list[dict[str, Any]], observed: dt.datetime, captured: dt.datetime) -> dict[str, Any]:
    rows = []
    for row in samples:
        _exact(row, {
            "variable", "source_time", "collected_time", "ingested_at",
            "value", "unit", "quality",
        }, "historian sample")
        if row["variable"] != CONTRACT["product_snapshot"]["variable"]:
            continue
        source = _time(row["source_time"], "source_time")
        collected = _time(row["collected_time"], "collected_time")
        ingested = _time(row["ingested_at"], "ingested_at")
        value = _number(row["value"], "usable volume")
        if row["unit"] != "ML":
            raise EvidenceError("usable volume must be recorded in ML")
        if not CONTRACT["product_snapshot"]["minimum_usable_volume_ml"] <= value <= CONTRACT["product_snapshot"]["maximum_usable_volume_ml"]:
            raise EvidenceError("usable volume is outside the installed product range")
        if collected < source or (collected - source).total_seconds() > CONTRACT["product_snapshot"]["maximum_collection_delay_seconds"]:
            raise EvidenceError("usable-volume collection time is invalid")
        if ingested < collected or (ingested - collected).total_seconds() > CONTRACT["product_snapshot"]["maximum_ingestion_delay_seconds"]:
            raise EvidenceError("usable-volume ingestion time is invalid")
        rows.append((source, row))
    if not rows:
        raise EvidenceError("UsableVolumeML product history is missing")
    if abs((captured - observed).total_seconds()) > CONTRACT["product_snapshot"]["maximum_capture_age_seconds"]:
        raise EvidenceError("claimed observation is stale relative to product capture")
    source, row = min(rows, key=lambda item: abs((item[0] - observed).total_seconds()))
    if abs((source - observed).total_seconds()) > CONTRACT["product_snapshot"]["maximum_point_distance_seconds"]:
        raise EvidenceError("no usable-volume sample is near the claimed observation")
    if row["quality"] != CONTRACT["product_snapshot"]["accepted_quality"]:
        raise EvidenceError("usable-volume sample does not have good process quality")
    return row


def _state(value: float) -> str:
    if value > CONTRACT["tolerance_ml"]:
        return "positive"
    if value < -CONTRACT["tolerance_ml"]:
        return "negative"
    return "zero"


def _direction(value: float) -> str:
    if value > CONTRACT["tolerance_ml"]:
        return "report_above_later_process_value"
    if value < -CONTRACT["tolerance_ml"]:
        return "report_below_later_process_value"
    return "aligned_within_tolerance"


def _card_1(submission: dict[str, Any]) -> dict[str, Any]:
    _exact(submission, {"planning_window", "asset", "tariff", "allocation"}, "W29.1 submission")
    expected = {
        "planning_window": CONTRACT["planning_window"], "asset": CONTRACT["asset"],
        "tariff": CONTRACT["tariff"], "allocation": CONTRACT["allocation"],
    }
    if submission != expected:
        raise EvidenceError("W29.1 does not match the current tariff and allocation")
    return {"tariff": CONTRACT["tariff"]["record_id"], "allocation": CONTRACT["allocation"]["record_id"]}


def _card_2(submission: dict[str, Any], captured: dt.datetime, samples: list[dict[str, Any]]) -> dict[str, Any]:
    _exact(submission, {
        "planning_window", "asset", "observed_at", "process_quality",
        "measured_usable_volume_ml", "committed_ml", "uncommitted_margin_ml", "margin_state",
    }, "W29.2 submission")
    if submission["planning_window"] != CONTRACT["planning_window"] or submission["asset"] != CONTRACT["asset"]:
        raise EvidenceError("W29.2 planning window or asset does not match")
    observed = _time(submission["observed_at"], "observed_at")
    row = _sample(samples, observed, captured)
    measured = _number(row["value"], "product usable volume")
    committed = CONTRACT["allocation"]["committed_ml"]
    margin = measured - committed
    if submission["process_quality"] != row["quality"]:
        raise EvidenceError("W29.2 process quality does not match product evidence")
    _near(submission["measured_usable_volume_ml"], measured, "measured usable volume")
    _near(submission["committed_ml"], committed, "committed allocation")
    _near(submission["uncommitted_margin_ml"], margin, "uncommitted margin")
    if submission["margin_state"] != _state(margin):
        raise EvidenceError("W29.2 margin classification is wrong")
    return {"observed_at": submission["observed_at"], "uncommitted_margin_ml": margin, "margin_state": _state(margin)}


def _card_3(submission: dict[str, Any], captured: dt.datetime, samples: list[dict[str, Any]]) -> dict[str, Any]:
    _exact(submission, {
        "planning_window", "asset", "report_id", "report_as_of", "reported_ml",
        "observed_at", "measured_usable_volume_ml", "signed_paper_variance_ml",
        "direction", "time_basis", "conclusion",
    }, "W29.3 submission")
    if submission["planning_window"] != CONTRACT["planning_window"] or submission["asset"] != CONTRACT["asset"]:
        raise EvidenceError("W29.3 planning window or asset does not match")
    report = CONTRACT["report"]
    if submission["report_id"] != report["record_id"] or submission["report_as_of"] != report["as_of"]:
        raise EvidenceError("W29.3 report identity or time does not match")
    observed = _time(submission["observed_at"], "observed_at")
    if observed <= _time(report["as_of"], "report as_of"):
        raise EvidenceError("W29.3 requires a later native process observation")
    row = _sample(samples, observed, captured)
    measured = _number(row["value"], "product usable volume")
    variance = report["reported_ml"] - measured
    _near(submission["reported_ml"], report["reported_ml"], "reported usable volume")
    _near(submission["measured_usable_volume_ml"], measured, "measured usable volume")
    _near(submission["signed_paper_variance_ml"], variance, "signed paper variance")
    if submission["direction"] != _direction(variance):
        raise EvidenceError("W29.3 variance direction is wrong")
    if submission["time_basis"] != "different_as_of_times" or submission["conclusion"] != "paper_report_is_not_current_process_truth":
        raise EvidenceError("W29.3 overstates what the two time bases prove")
    return {"signed_paper_variance_ml": variance, "direction": _direction(variance), "planning_basis_verified": True}


def evaluate(card: str, submission: dict[str, Any], product_snapshot: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(submission, dict) or "product_snapshot" in submission:
        raise EvidenceError("participant input cannot supply product evidence")
    captured, samples = _product(product_snapshot)
    evaluators = {
        "W29.1": lambda: _card_1(submission),
        "W29.2": lambda: _card_2(submission, captured, samples),
        "W29.3": lambda: _card_3(submission, captured, samples),
    }
    if card not in evaluators:
        raise EvidenceError("card is outside W29")
    return {
        "schema": "arwc.challenge-result/v1", "card": card, "satisfied": True,
        "product_source_digest": product_snapshot["source_digest"], "evidence": evaluators[card](),
    }
