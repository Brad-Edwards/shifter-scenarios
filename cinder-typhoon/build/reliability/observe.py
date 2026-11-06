#!/usr/bin/env python3
"""Collect credential-free service and host reliability facts on a golden."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time


ROOT = Path("/opt/cinder-typhoon")
PHASES = {
    "training": (ROOT / "build/training/compose.yaml", 6, frozenset()),
    "keplerops": (
        ROOT / "build/keplerops/compose.yaml", 18, frozenset({"k-dev-seed"}),
    ),
    "arwc": (ROOT / "build/arwc/compose.yaml", 19, frozenset()),
}


class ObservationError(RuntimeError):
    """The golden did not reach the required service state."""


def run(arguments: list[str], *, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        arguments, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=False, timeout=timeout,
    )


def compose_rows(compose: Path) -> list[dict]:
    completed = run([
        "docker", "compose", "-f", str(compose), "ps", "--all", "--format", "json",
    ])
    if completed.returncode:
        raise ObservationError("Compose service state cannot be read")
    text = completed.stdout.strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, list) else [parsed]
    except json.JSONDecodeError:
        try:
            return [json.loads(line) for line in text.splitlines() if line.strip()]
        except json.JSONDecodeError as error:
            raise ObservationError("Compose returned invalid service state") from error


def service_state(phase: str) -> tuple[dict, str, list[str], bool]:
    compose, expected, one_shots = PHASES[phase]
    rows = compose_rows(compose)
    records = []
    for row in rows:
        name = row.get("Name")
        service = row.get("Service")
        if not isinstance(name, str) or not isinstance(service, str):
            raise ObservationError("Compose service identity is incomplete")
        inspected = run(["docker", "inspect", name])
        if inspected.returncode:
            raise ObservationError("A configured container cannot be inspected")
        value = json.loads(inspected.stdout)[0]
        state = value["State"]
        health = state.get("Health", {}).get("Status", "")
        records.append({
            "service": service,
            "status": state["Status"],
            "exit_code": state["ExitCode"],
            "health": health,
            "restarts": value["RestartCount"],
            "image": value["Image"],
        })
    records.sort(key=lambda item: item["service"])
    running = sum(item["status"] == "running" for item in records)
    successful_one_shots = sum(
        item["service"] in one_shots
        and item["status"] == "exited"
        and item["exit_code"] == 0
        for item in records
    )
    summary = {
        "expected": expected,
        "running": running,
        "successful_one_shots": successful_one_shots,
        "restarts": sum(item["restarts"] for item in records),
        "unhealthy": sum(item["health"] == "unhealthy" for item in records),
    }
    ready = (
        len(records) == expected
        and running + successful_one_shots == expected
        and summary["unhealthy"] == 0
        and all(item["health"] in {"", "healthy"} for item in records)
    )
    digest = hashlib.sha256(
        json.dumps(records, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    running_services = [
        item["service"] for item in records if item["status"] == "running"
    ]
    return summary, digest, running_services, ready


def resource_state() -> dict:
    memory = Path("/proc/meminfo").read_text(encoding="utf-8")
    match = re.search(r"^MemAvailable:\s+(\d+)\s+kB$", memory, re.MULTILINE)
    if match is None:
        raise ObservationError("Available memory cannot be read")
    disk = os.statvfs("/")
    failed = run(["systemctl", "--failed", "--no-legend", "--plain", "--no-pager"])
    if failed.returncode:
        raise ObservationError("Failed system units cannot be read")
    failed_units = [line for line in failed.stdout.splitlines() if line.strip()]
    kernel = run(["journalctl", "--dmesg", "--boot", "--no-pager", "-o", "cat"])
    if kernel.returncode:
        raise ObservationError("Kernel OOM events cannot be read")
    oom_events = sum(
        re.search(r"out of memory|oom-kill|killed process", line, re.IGNORECASE)
        is not None
        for line in kernel.stdout.splitlines()
    )
    return {
        "vcpus": os.cpu_count() or 0,
        "load_1": round(os.getloadavg()[0], 3),
        "memory_available_mib": int(match.group(1)) // 1024,
        "root_disk_available_mib": disk.f_bavail * disk.f_frsize // (1024 * 1024),
        "failed_system_units": len(failed_units),
        "oom_events": oom_events,
    }


def participant_surface(phase: str, require_pristine: bool) -> str | None:
    command = [
        "python3", str(ROOT / "build/participant-surface/run.py"), "--phase", phase,
    ]
    if require_pristine:
        checked = run(command, timeout=60)
        if checked.returncode:
            raise ObservationError("Participant surface is not pristine")
        contract = ROOT / "build/participant-surface/manifests" / f"{phase}.json"
        return hashlib.sha256(contract.read_bytes()).hexdigest()
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=sorted(PHASES), required=True)
    parser.add_argument("--restart-services", action="store_true")
    parser.add_argument("--require-pristine", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()

    started = time.monotonic()
    if arguments.restart_services:
        _, _, running_services, _ = service_state(arguments.phase)
        compose = PHASES[arguments.phase][0]
        restarted = run(
            ["docker", "compose", "-f", str(compose), "restart", *running_services],
            timeout=arguments.timeout_seconds,
        )
        if restarted.returncode:
            raise ObservationError("Long-running services could not be restarted")

    deadline = time.monotonic() + arguments.timeout_seconds
    while True:
        services, state_digest, _, ready = service_state(arguments.phase)
        if ready:
            break
        if time.monotonic() >= deadline:
            raise ObservationError("Configured services did not become ready")
        time.sleep(2)

    surface_digest = participant_surface(arguments.phase, arguments.require_pristine)
    report = {
        "phase": arguments.phase,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "services": services,
        "service_state_sha256": state_digest,
        "participant_surface_sha256": surface_digest,
        "resources": resource_state(),
    }
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.output:
        arguments.output.write_text(encoded, encoding="utf-8")
        arguments.output.chmod(0o600)
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
