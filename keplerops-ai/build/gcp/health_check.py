#!/usr/bin/env python3
"""Reduce Terraform state to a value-sparse KeplerOps health report."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Iterable


class HealthError(ValueError):
    """A bounded health failure that does not echo Terraform values."""


def _resources(module: dict[str, Any]) -> Iterable[dict[str, Any]]:
    yield from module.get("resources", [])
    for child in module.get("child_modules", []):
        yield from _resources(child)


def load_expectations(path: Path) -> tuple[set[str], set[str], set[str]]:
    """Load authoritative physical-host and logical-workload inventories."""

    try:
        realization = json.loads(path.read_text(encoding="utf-8"))
        hosts = realization["physical_hosts"]
        workloads = realization["workloads"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise HealthError("SDL realization invalid") from exc
    if (
        not isinstance(hosts, dict)
        or not isinstance(workloads, dict)
        or not hosts
        or not workloads
        or any(not isinstance(name, str) or not name for name in (*hosts, *workloads))
    ):
        raise HealthError("SDL realization inventory invalid")
    range_workloads = {
        name
        for name, workload in workloads.items()
        if isinstance(workload, dict) and workload.get("deployment_cell") == "range-cell"
    }
    if not range_workloads:
        raise HealthError("SDL range workload inventory invalid")
    return set(hosts), set(workloads), range_workloads


def assess_state(
    document: dict[str, Any],
    *,
    expected_hosts: set[str],
    expected_workloads: set[str],
    expected_range_workloads: set[str],
) -> dict[str, Any]:
    try:
        root = document["values"]["root_module"]
    except (KeyError, TypeError) as exc:
        raise HealthError("terraform state shape invalid") from exc
    resources = list(_resources(root))
    instances: list[dict[str, Any]] = []
    for resource in resources:
        if (
            resource.get("type") != "google_compute_instance"
            or resource.get("name") != "range_host"
        ):
            continue
        values = resource.get("values")
        if not isinstance(values, dict):
            raise HealthError("host inventory invalid")
        status = values.get("current_status")
        if status != "RUNNING":
            raise HealthError("host not running")
        instances.append(values)
    if len(instances) != 1:
        raise HealthError("host inventory incomplete")
    participant_values = instances[0]

    addresses = [
        row.get("values")
        for row in resources
        if row.get("type") == "google_compute_address"
        and row.get("name") == "participant"
        and isinstance(row.get("values"), dict)
    ]
    if len(addresses) != 1:
        raise HealthError("participant address binding invalid")
    address = addresses[0]
    participant_address = address.get("address")
    interfaces = (participant_values or {}).get("network_interface", [])
    address_bound = any(
        access.get("nat_ip") == participant_address
        for interface in interfaces if isinstance(interface, dict)
        for access in interface.get("access_config", []) if isinstance(access, dict)
    )
    if (
        address.get("address_type") != "EXTERNAL"
        or not isinstance(participant_address, str)
        or not participant_address
        or not address_bound
    ):
        raise HealthError("participant address binding invalid")
    forbidden_cell_types = {
        "google_artifact_registry_repository",
        "google_compute_firewall",
        "google_compute_network",
        "google_compute_subnetwork",
    }
    if any(resource.get("type") in forbidden_cell_types for resource in resources):
        raise HealthError("range state owns deployment-cell resources")
    return {
        "schema_version": 2,
        "operation": "health",
        "status": "ready",
        "host_count": 1,
        "logical_host_count": len(expected_hosts),
        "logical_workload_count": len(expected_workloads),
        "range_workload_count": len(expected_range_workloads),
        "cell_resources_external": True,
        "timestamp": int(time.time()),
    }


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".health-", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(report, handle, sort_keys=True)
            handle.write("\n")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--realization", type=Path, required=True)
    args = parser.parse_args()
    raw = sys.stdin.buffer.read(32 * 1024 * 1024 + 1)
    if len(raw) > 32 * 1024 * 1024:
        raise HealthError("terraform state exceeds size limit")
    try:
        document = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HealthError("terraform state is invalid JSON") from exc
    expected_hosts, expected_workloads, expected_range_workloads = load_expectations(
        args.realization
    )
    report = assess_state(
        document,
        expected_hosts=expected_hosts,
        expected_workloads=expected_workloads,
        expected_range_workloads=expected_range_workloads,
    )
    write_report(args.output, report)
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except HealthError as error:
        print(f"error: {error}")
        raise SystemExit(2) from None
