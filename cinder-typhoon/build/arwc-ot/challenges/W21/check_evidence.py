#!/usr/bin/env python3
"""Compare W21 submissions with trusted native project and runtime evidence."""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import re
from typing import Any


HERE = pathlib.Path(__file__).resolve().parent
CONTRACT = json.loads((HERE / "contract.json").read_text())
SHA256 = re.compile(r"^[0-9a-f]{64}$")
MD5 = re.compile(r"^[0-9a-f]{32}$")
UTC = dt.timezone.utc


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


def _product(snapshot: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    _exact(snapshot, {"schema", "asset", "captured_at", "source_digest", "saved_project", "runtime"}, "product snapshot")
    if snapshot["schema"] != CONTRACT["product_snapshot"]["schema"] or snapshot["asset"] != CONTRACT["asset"]:
        raise EvidenceError("product snapshot is for another schema or asset")
    captured = _time(snapshot["captured_at"], "captured_at")
    if not isinstance(snapshot["source_digest"], str) or not SHA256.fullmatch(snapshot["source_digest"]):
        raise EvidenceError("product snapshot digest is missing")
    saved = snapshot["saved_project"]
    runtime = snapshot["runtime"]
    _exact(saved, {"name", "participant_path", "main_program", "language", "project_revision", "task_interval", "device_target", "runtime_host", "project_sha256"}, "saved project")
    _exact(runtime, {"observed_at", "target", "host", "program_md5", "program_matches_saved_project", "state", "connected", "forced_variables", "live_project_revision"}, "runtime observation")
    observed = _time(runtime["observed_at"], "runtime observed_at")
    age = abs((captured - observed).total_seconds())
    if age > CONTRACT["product_snapshot"]["maximum_runtime_age_seconds"]:
        raise EvidenceError("runtime observation is stale relative to the product snapshot")
    if not isinstance(saved["project_sha256"], str) or not SHA256.fullmatch(saved["project_sha256"]):
        raise EvidenceError("saved project digest is invalid")
    if not isinstance(runtime["program_md5"], str) or not MD5.fullmatch(runtime["program_md5"]):
        raise EvidenceError("runtime program identity is invalid")
    expected = CONTRACT["project"]
    if any(saved.get(field) != value for field, value in expected.items()):
        raise EvidenceError("saved native project does not match the commissioned project")
    return saved, runtime


def _card_1(submission: dict[str, Any], saved: dict[str, Any]) -> dict[str, Any]:
    fields = {"project", "participant_path", "main_program", "language", "project_revision", "task_interval", "device_target", "runtime_host"}
    _exact(submission, fields, "W21.1 submission")
    expected = {
        "project": saved["name"],
        "participant_path": saved["participant_path"],
        "main_program": saved["main_program"],
        "language": saved["language"],
        "project_revision": saved["project_revision"],
        "task_interval": saved["task_interval"],
        "device_target": saved["device_target"],
        "runtime_host": saved["runtime_host"],
    }
    if submission != expected:
        raise EvidenceError("W21.1 does not match the saved native project")
    return {"project": saved["name"], "project_revision": saved["project_revision"], "project_sha256": saved["project_sha256"]}


def _card_2(submission: dict[str, Any], saved: dict[str, Any], runtime: dict[str, Any]) -> dict[str, Any]:
    fields = {"asset", "project", "program_md5", "program_matches_saved_project", "runtime_state", "live_project_revision", "relationship"}
    _exact(submission, fields, "W21.2 submission")
    required = CONTRACT["running_program"]
    expected = {
        "asset": CONTRACT["asset"],
        "project": saved["name"],
        "program_md5": runtime["program_md5"],
        "program_matches_saved_project": True,
        "runtime_state": required["required_state"],
        "live_project_revision": saved["project_revision"],
        "relationship": required["relationship"],
    }
    if submission != expected:
        raise EvidenceError("W21.2 project/runtime reconciliation does not match product evidence")
    if runtime["target"] != saved["device_target"] or runtime["host"] != saved["runtime_host"]:
        raise EvidenceError("debug session is connected to another runtime target")
    if runtime["connected"] is not True or runtime["program_matches_saved_project"] is not True:
        raise EvidenceError("saved project is not proven to match the running program")
    if runtime["state"] != required["required_state"]:
        raise EvidenceError("controller is not running")
    if runtime["live_project_revision"] != saved["project_revision"]:
        raise EvidenceError("live ProjectRevision disagrees with the saved project")
    if runtime["forced_variables"] != required["required_forced_variables"]:
        raise EvidenceError("active forces prevent a clean running-project conclusion")
    return {
        "project": saved["name"], "program_md5": runtime["program_md5"],
        "project_revision": runtime["live_project_revision"], "state": runtime["state"],
    }


def evaluate(card: str, submission: dict[str, Any], product_snapshot: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(submission, dict) or "product_snapshot" in submission:
        raise EvidenceError("participant input cannot supply product evidence")
    saved, runtime = _product(product_snapshot)
    evaluators = {
        "W21.1": lambda: _card_1(submission, saved),
        "W21.2": lambda: _card_2(submission, saved, runtime),
    }
    if card not in evaluators:
        raise EvidenceError("card is outside W21")
    return {
        "schema": "arwc.challenge-result/v1",
        "card": card,
        "satisfied": True,
        "product_source_digest": product_snapshot["source_digest"],
        "evidence": evaluators[card](),
    }
