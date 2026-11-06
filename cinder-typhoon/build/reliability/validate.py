#!/usr/bin/env python3
"""Validate the credential-free Cinder single-participant reliability report."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


CINDER_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT = Path(__file__).with_name("report.json")
THRESHOLDS_PATH = Path(__file__).with_name("thresholds.json")
CANDIDATE_PATH = CINDER_ROOT / "build/participant-runner/candidate.json"
RELEASE_PATH = CINDER_ROOT / "build/release/manifest.json"

DIGEST = re.compile(r"^[0-9a-f]{64}$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")
PHASES = {
    "training": ("cinder-training-golden", "e2-standard-2", 6, 0),
    "keplerops": ("cinder-keplerops-golden", "e2-standard-4", 18, 1),
    "arwc": ("cinder-arwc-golden", "e2-standard-4", 19, 0),
}
OPERATIONS = {
    "training": "all",
    "keplerops": "delivery-diagnostic",
    "arwc": "ending",
}
ASSERTIONS = {
    "candidate_identity_verified",
    "challenge_traffic_passed",
    "configured_services_ready",
    "credential_free_report",
    "pristine_start_state_verified",
    "repeatable_pristine_resets",
    "resource_limits_passed",
    "retained_state_after_host_restart",
    "retained_state_after_service_restart",
    "transition_verified",
}
LIMIT_KEYS = {
    "max_container_restarts",
    "max_failed_system_units",
    "max_host_recovery_seconds",
    "max_load_1_per_vcpu",
    "max_oom_events",
    "max_pristine_startup_seconds",
    "max_service_recovery_seconds",
    "min_memory_available_mib",
    "min_root_disk_available_mib",
}
FORBIDDEN_TEXT = re.compile(
    r"password|authorization|bearer|cookie|private[_-]?key|secret|token|\.operator|/var/tmp",
    re.IGNORECASE,
)


class ValidationError(ValueError):
    """The reliability evidence is incomplete, stale, or outside a limit."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def exact_keys(value: Any, keys: set[str], context: str) -> dict[str, Any]:
    require(isinstance(value, dict), f"{context}: object required")
    require(set(value) == keys, f"{context}: fields differ from the contract")
    return value


def number(value: Any, context: str) -> float:
    require(isinstance(value, (int, float)) and not isinstance(value, bool), f"{context}: number required")
    require(value >= 0, f"{context}: value must not be negative")
    return float(value)


def integer(value: Any, context: str) -> int:
    require(isinstance(value, int) and not isinstance(value, bool), f"{context}: integer required")
    require(value >= 0, f"{context}: value must not be negative")
    return value


def timestamp(value: Any, context: str) -> datetime:
    require(isinstance(value, str), f"{context}: timestamp required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValidationError(f"{context}: invalid timestamp") from error
    require(parsed.tzinfo is not None, f"{context}: timezone required")
    return parsed


def digest_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path, context: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValidationError(f"{context}: cannot read JSON: {error}") from error


def validate_thresholds(value: Any) -> dict[str, Any]:
    threshold = exact_keys(value, {"schema_version", "defined_at", "candidate_id", "limits"}, "thresholds")
    require(threshold["schema_version"] == 1, "thresholds: schema version must be 1")
    require(isinstance(threshold["candidate_id"], str) and threshold["candidate_id"], "thresholds: candidate ID required")
    timestamp(threshold["defined_at"], "thresholds.defined_at")
    limits = exact_keys(threshold["limits"], LIMIT_KEYS, "thresholds.limits")
    for key, value in limits.items():
        number(value, f"thresholds.limits.{key}")
    return threshold


def validate_service_state(
    value: Any,
    context: str,
    limits: dict[str, Any],
    expected: int,
    successful_one_shots: int,
) -> dict[str, Any]:
    state = exact_keys(
        value,
        {"expected", "running", "successful_one_shots", "restarts", "unhealthy"},
        context,
    )
    for key in state:
        integer(state[key], f"{context}.{key}")
    require(state["expected"] == expected, f"{context}: unexpected service count")
    require(state["successful_one_shots"] == successful_one_shots, f"{context}: one-shot state is wrong")
    require(state["running"] + state["successful_one_shots"] == expected, f"{context}: configured services are incomplete")
    require(state["restarts"] <= limits["max_container_restarts"], f"{context}: restart limit exceeded")
    require(state["unhealthy"] == 0, f"{context}: unhealthy service present")
    return state


def validate_recovery(
    value: Any,
    context: str,
    limits: dict[str, Any],
    limit_name: str,
    expected: int,
    successful_one_shots: int,
) -> None:
    recovery = exact_keys(value, {"elapsed_seconds", "services", "retained_state"}, context)
    elapsed = number(recovery["elapsed_seconds"], f"{context}.elapsed_seconds")
    require(elapsed <= limits[limit_name], f"{context}: recovery time limit exceeded")
    validate_service_state(recovery["services"], f"{context}.services", limits, expected, successful_one_shots)
    require(recovery["retained_state"] is True, f"{context}: required state was not retained")


def validate_report(value: Any, cinder_root: Path = CINDER_ROOT) -> dict[str, Any]:
    report = exact_keys(
        value,
        {"schema_version", "report_kind", "status", "candidate", "thresholds", "run", "campaign_path", "phases", "assertions"},
        "report",
    )
    require(report["schema_version"] == 1, "report: schema version must be 1")
    require(report["report_kind"] == "single-participant-reliability", "report: report kind is wrong")
    require(report["status"] == "passed", "report: qualification did not pass")

    candidate_path = cinder_root / "build/participant-runner/candidate.json"
    release_path = cinder_root / "build/release/manifest.json"
    thresholds_path = cinder_root / "build/reliability/thresholds.json"
    candidate_record = load_json(candidate_path, "candidate record")
    release_record = load_json(release_path, "release manifest")
    threshold_record = validate_thresholds(load_json(thresholds_path, "thresholds"))

    candidate = exact_keys(
        report["candidate"],
        {"candidate_id", "source_commit", "candidate_manifest_sha256", "release_manifest_sha256"},
        "report.candidate",
    )
    require(candidate["candidate_id"] == candidate_record.get("candidate_id"), "report: candidate ID is stale")
    require(candidate["source_commit"] == candidate_record.get("source_commit"), "report: source commit is stale")
    require(COMMIT.fullmatch(str(candidate["source_commit"])) is not None, "report: invalid source commit")
    require(candidate["candidate_manifest_sha256"] == digest_file(candidate_path), "report: candidate digest is stale")
    require(candidate["release_manifest_sha256"] == digest_file(release_path), "report: release digest is stale")
    require(release_record.get("source_commit") == candidate["source_commit"], "report: release source commit differs")
    release_candidate = release_record.get("candidate")
    require(isinstance(release_candidate, dict), "report: release candidate binding is missing")
    require(release_candidate.get("path") == "build/participant-runner/candidate.json", "report: release candidate path differs")
    require(release_candidate.get("sha256") == candidate["candidate_manifest_sha256"], "report: release candidate digest differs")
    require(threshold_record["candidate_id"] == candidate["candidate_id"], "report: thresholds target another candidate")

    thresholds = exact_keys(report["thresholds"], {"path", "sha256", "defined_at"}, "report.thresholds")
    require(thresholds["path"] == "build/reliability/thresholds.json", "report: threshold path is wrong")
    require(thresholds["sha256"] == digest_file(thresholds_path), "report: threshold digest is stale")
    require(thresholds["defined_at"] == threshold_record["defined_at"], "report: threshold timestamp differs")
    limits = threshold_record["limits"]

    run = exact_keys(report["run"], {"run_id", "project", "zone", "started_at", "finished_at"}, "report.run")
    require(isinstance(run["run_id"], str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,79}", run["run_id"]) is not None, "report: invalid run ID")
    require(run["project"] == "prod-mgau4w", "report: GCP project is wrong")
    require(run["zone"] == "us-central1-a", "report: GCP zone is wrong")
    started = timestamp(run["started_at"], "report.run.started_at")
    finished = timestamp(run["finished_at"], "report.run.finished_at")
    require(timestamp(threshold_record["defined_at"], "thresholds.defined_at") <= started, "report: thresholds were defined after the run started")
    require(started <= finished, "report: run finished before it started")

    campaign = exact_keys(
        report["campaign_path"],
        {"transition", "training", "keplerops", "arwc", "retained_state"},
        "report.campaign_path",
    )
    require(campaign["transition"] == "diagnostic-execution", "report: unexpected transition")
    require(campaign["retained_state"] is True, "report: campaign state was not retained")
    for phase, operation in OPERATIONS.items():
        acceptance = exact_keys(
            campaign[phase],
            {"operation", "result", "elapsed_seconds", "report_sha256"},
            f"report.campaign_path.{phase}",
        )
        require(acceptance["operation"] == operation, f"report: wrong {phase} operation")
        require(acceptance["result"] == "passed", f"report: {phase} acceptance did not pass")
        number(acceptance["elapsed_seconds"], f"report.campaign_path.{phase}.elapsed_seconds")
        require(DIGEST.fullmatch(str(acceptance["report_sha256"])) is not None, f"report: invalid {phase} report digest")

    phases = exact_keys(report["phases"], set(PHASES), "report.phases")
    for phase, (instance, machine_type, expected, one_shots) in PHASES.items():
        context = f"report.phases.{phase}"
        phase_value = exact_keys(
            phases[phase],
            {"instance", "machine_type", "initial_startup_seconds", "service_recovery", "host_recovery", "resets", "resources"},
            context,
        )
        require(phase_value["instance"] == instance, f"{context}: instance is wrong")
        require(phase_value["machine_type"] == machine_type, f"{context}: machine type is wrong")
        startup = number(phase_value["initial_startup_seconds"], f"{context}.initial_startup_seconds")
        require(startup <= limits["max_pristine_startup_seconds"], f"{context}: startup time limit exceeded")
        validate_recovery(phase_value["service_recovery"], f"{context}.service_recovery", limits, "max_service_recovery_seconds", expected, one_shots)
        validate_recovery(phase_value["host_recovery"], f"{context}.host_recovery", limits, "max_host_recovery_seconds", expected, one_shots)

        resets = phase_value["resets"]
        require(isinstance(resets, list) and len(resets) == 2, f"{context}: exactly two resets required")
        reset_hashes: list[tuple[str, str]] = []
        for index, reset_value in enumerate(resets, start=1):
            reset = exact_keys(
                reset_value,
                {"sequence", "elapsed_seconds", "participant_surface_sha256", "service_state_sha256", "services"},
                f"{context}.resets[{index - 1}]",
            )
            require(reset["sequence"] == index, f"{context}: reset sequence is wrong")
            reset_elapsed = number(reset["elapsed_seconds"], f"{context}.resets[{index - 1}].elapsed_seconds")
            require(reset_elapsed <= limits["max_pristine_startup_seconds"], f"{context}: reset time limit exceeded")
            for field in ("participant_surface_sha256", "service_state_sha256"):
                require(DIGEST.fullmatch(str(reset[field])) is not None, f"{context}: invalid {field}")
            validate_service_state(reset["services"], f"{context}.resets[{index - 1}].services", limits, expected, one_shots)
            reset_hashes.append((reset["participant_surface_sha256"], reset["service_state_sha256"]))
        require(reset_hashes[0] == reset_hashes[1], f"{context}: pristine resets are not repeatable")

        resources = exact_keys(
            phase_value["resources"],
            {"vcpus", "load_1", "memory_available_mib", "root_disk_available_mib", "failed_system_units", "oom_events"},
            f"{context}.resources",
        )
        vcpus = integer(resources["vcpus"], f"{context}.resources.vcpus")
        require(vcpus > 0, f"{context}: vCPU count must be positive")
        load_1 = number(resources["load_1"], f"{context}.resources.load_1")
        require(load_1 <= vcpus * limits["max_load_1_per_vcpu"], f"{context}: load limit exceeded")
        require(integer(resources["memory_available_mib"], f"{context}.resources.memory_available_mib") >= limits["min_memory_available_mib"], f"{context}: available memory below limit")
        require(integer(resources["root_disk_available_mib"], f"{context}.resources.root_disk_available_mib") >= limits["min_root_disk_available_mib"], f"{context}: available disk below limit")
        require(integer(resources["failed_system_units"], f"{context}.resources.failed_system_units") <= limits["max_failed_system_units"], f"{context}: failed system-unit limit exceeded")
        require(integer(resources["oom_events"], f"{context}.resources.oom_events") <= limits["max_oom_events"], f"{context}: OOM-event limit exceeded")

    assertions = exact_keys(report["assertions"], ASSERTIONS, "report.assertions")
    require(all(value is True for value in assertions.values()), "report: an assertion did not pass")
    require(FORBIDDEN_TEXT.search(json.dumps(report, sort_keys=True)) is None, "report: credential or operator-only text is present")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    arguments = parser.parse_args()
    try:
        report = validate_report(load_json(arguments.report, "reliability report"))
    except ValidationError as error:
        print(f"FAIL: {error}")
        return 1
    print(
        "PASS: Cinder single-participant reliability; "
        f"run={report['run']['run_id']}; candidate={report['candidate']['candidate_id']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
