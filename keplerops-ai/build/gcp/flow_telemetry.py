#!/usr/bin/env python3
"""Sanitize tenant VPC/firewall logs and augment one research export bundle."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import ipaddress
import json
import os
from pathlib import Path
from typing import Any, Sequence


NANOSECONDS_PER_SECOND = 1_000_000_000
WINDOW_PADDING_SECONDS = 60


def canonical(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")


def owner_write(path: Path, body: bytes) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    path.chmod(0o600)


def load_events(path: Path) -> list[dict[str, Any]]:
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    if not events or any(not isinstance(row, dict) for row in events):
        raise ValueError("flow telemetry: invalid session events")
    sessions = {row.get("session_id") for row in events}
    runs = {row.get("study_run_id") for row in events}
    generations = {row.get("reset_generation") for row in events}
    if len(sessions) != 1 or len(runs) != 1 or len(generations) != 1:
        raise ValueError("flow telemetry: mixed session bundle")
    return events


def rfc3339(nanoseconds: int) -> str:
    instant = dt.datetime.fromtimestamp(nanoseconds / 1_000_000_000, tz=dt.timezone.utc)
    return instant.isoformat(timespec="microseconds").replace("+00:00", "Z")


def session_window(
    events: list[dict[str, Any]],
    *,
    max_lookback_seconds: int | None = None,
) -> tuple[str, str]:
    occurred = [row["occurred_at"] for row in events]
    if any(not isinstance(value, int) or value < 0 for value in occurred):
        raise ValueError("flow telemetry: invalid session clocks")
    if max_lookback_seconds is not None and max_lookback_seconds < WINDOW_PADDING_SECONDS:
        raise ValueError("flow telemetry: invalid lookback")
    end = max(occurred) + WINDOW_PADDING_SECONDS * NANOSECONDS_PER_SECOND
    start = max(0, min(occurred) - WINDOW_PADDING_SECONDS * NANOSECONDS_PER_SECOND)
    if max_lookback_seconds is not None:
        start = max(start, end - max_lookback_seconds * NANOSECONDS_PER_SECOND)
    return rfc3339(start), rfc3339(end)


def window_batches(
    start: str,
    end: str,
    *,
    batch_seconds: int,
) -> list[tuple[str, str]]:
    if batch_seconds <= 0:
        raise ValueError("flow telemetry: invalid batch interval")
    start_ns = parse_timestamp(start)
    end_ns = parse_timestamp(end)
    if end_ns < start_ns:
        raise ValueError("flow telemetry: invalid batch window")
    batch_ns = batch_seconds * NANOSECONDS_PER_SECOND
    current = start_ns
    batches = []
    while current < end_ns:
        batch_end = min(end_ns, current + batch_ns)
        batches.append((rfc3339(current), rfc3339(batch_end)))
        current = batch_end
    if not batches:
        batches.append((rfc3339(start_ns), rfc3339(end_ns)))
    return batches


def parse_timestamp(value: object) -> int:
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError("flow telemetry: invalid log timestamp")
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("flow telemetry: timezone required")
    return int(parsed.timestamp() * 1_000_000_000)


def inventory_map(path: Path) -> dict[str, str]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("flow telemetry: invalid inventory")
    result = {}
    for asset_id, row in value.items():
        if not isinstance(asset_id, str) or not isinstance(row, dict):
            raise ValueError("flow telemetry: invalid inventory")
        address = str(ipaddress.ip_address(row["internal_ip"]))
        if address in result:
            raise ValueError("flow telemetry: duplicate inventory address")
        result[address] = asset_id
    return result


def _load_raw_logs(raw_paths: Path | Sequence[Path]) -> list[dict[str, Any]]:
    paths = [raw_paths] if isinstance(raw_paths, Path) else list(raw_paths)
    raw_logs: list[dict[str, Any]] = []
    for raw_path in paths:
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError("flow telemetry: log array required")
        raw_logs.extend(entry for entry in raw if isinstance(entry, dict))
    return raw_logs


def flow_rows(
    raw_paths: Path | Sequence[Path],
    inventory_path: Path,
    session_event: dict[str, Any],
) -> list[dict[str, Any]]:
    inventory = inventory_map(inventory_path)
    normalized = []
    for entry in _load_raw_logs(raw_paths):
        payload = entry.get("jsonPayload")
        connection = payload.get("connection") if isinstance(payload, dict) else None
        if not isinstance(connection, dict):
            continue
        source_ip = connection.get("src_ip")
        destination_ip = connection.get("dest_ip")
        if not isinstance(source_ip, str) or not isinstance(destination_ip, str):
            continue
        source_asset = inventory.get(source_ip)
        destination_asset = inventory.get(destination_ip)
        if source_asset is None and destination_asset is None:
            continue
        occurred_at = parse_timestamp(entry.get("timestamp"))
        observed_at = parse_timestamp(entry.get("receiveTimestamp", entry.get("timestamp")))
        disposition = str(payload.get("disposition", "ALLOWED")).lower()
        normalized.append(
            {
                "occurred_at": occurred_at,
                "observed_at": observed_at,
                "source_asset": source_asset or "external",
                "destination_asset": destination_asset or "external",
                "source_port": int(connection.get("src_port", 0)),
                "destination_port": int(connection.get("dest_port", 0)),
                "network_protocol": str(connection.get("protocol", "unknown")).lower(),
                "network_disposition": disposition,
                "byte_count": int(payload.get("bytes_sent", 0)),
                "packet_count": int(payload.get("packets_sent", 0)),
            }
        )
    unique = {
        canonical(row).decode("utf-8"): row
        for row in normalized
    }
    rows = [unique[key] for key in sorted(unique)]
    result = []
    for sequence, row in enumerate(rows, 1):
        material = canonical(row)
        digest = hashlib.sha256(material).hexdigest()
        denied = row["network_disposition"] == "denied"
        result.append(
            {
                "schema_version": 1,
                "event_id": "evt-" + digest[:32],
                "event_name": "network.egress_denied" if denied else "network.flow_observed",
                "occurred_at": row["occurred_at"],
                "observed_at": row["observed_at"],
                "clock_source": "gcp_logging",
                "study_run_id": session_event["study_run_id"],
                "session_id": session_event["session_id"],
                "trace_id": digest[:32],
                "source_id": "gcp-flow-logs",
                "source_sequence": sequence,
                "reset_generation": session_event["reset_generation"],
                "status": "rejected" if denied else "recorded",
                "sampling_rate": 1.0 if denied else 0.5,
                "capture_status": "complete" if denied else "sampled",
                **row,
            }
        )
    return result


def augment(
    bundle: Path,
    raw: Path | Sequence[Path],
    inventory: Path,
    capture_status: str,
    *,
    batch_count: int | None = None,
    failed_batch_count: int | None = None,
) -> None:
    events_path = bundle / "events.jsonl"
    events = load_events(events_path)
    flows = (
        flow_rows(raw, inventory, events[0])
        if capture_status in {"captured", "partial"}
        else []
    )
    flows_path = bundle / "network-flows.jsonl"
    owner_write(flows_path, b"".join(canonical(row) + b"\n" for row in flows))
    all_events = events + flows
    all_events.sort(
        key=lambda row: (
            row["study_run_id"], row["session_id"], row["occurred_at"],
            row["observed_at"], row["source_id"], row["source_sequence"], row["event_id"],
        )
    )
    owner_write(events_path, b"".join(canonical(row) + b"\n" for row in all_events))
    missingness_path = bundle / "missingness.json"
    missingness = json.loads(missingness_path.read_text(encoding="utf-8"))
    missingness["accepted"] += len(flows)
    missingness["network_flow"] = {
        "capture_status": capture_status,
        "record_count": len(flows),
        "sampling_rate": 0.5,
    }
    if batch_count is not None:
        missingness["network_flow"]["batch_count"] = batch_count
    if failed_batch_count is not None:
        missingness["network_flow"]["failed_batch_count"] = failed_batch_count
    missingness["status"] = (
        "complete"
        if capture_status == "captured"
        and missingness.get("dropped", 0) == 0
        and missingness.get("sequence_gaps", 0) == 0
        else "incomplete"
    )
    owner_write(missingness_path, canonical(missingness) + b"\n")
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["members"] = {
        path.name: "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(bundle.iterdir(), key=lambda item: item.name)
        if path.name not in {"manifest.json", "checksums.sha256"}
    }
    owner_write(manifest_path, canonical(manifest) + b"\n")
    checksum_lines = [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
        for path in sorted(bundle.iterdir(), key=lambda item: item.name)
        if path.name != "checksums.sha256"
    ]
    owner_write(bundle / "checksums.sha256", "".join(checksum_lines).encode("ascii"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    window = subparsers.add_parser("window")
    window.add_argument("--events", type=Path, required=True)
    window.add_argument("--max-lookback-seconds", type=int)
    batches = subparsers.add_parser("batches")
    batches.add_argument("--start", required=True)
    batches.add_argument("--end", required=True)
    batches.add_argument("--batch-seconds", type=int, required=True)
    augment_parser = subparsers.add_parser("augment")
    augment_parser.add_argument("--bundle", type=Path, required=True)
    augment_parser.add_argument("--raw", type=Path, action="append", required=True)
    augment_parser.add_argument("--inventory", type=Path, required=True)
    augment_parser.add_argument(
        "--capture-status", choices=("captured", "partial", "unavailable"), required=True
    )
    augment_parser.add_argument("--batch-count", type=int)
    augment_parser.add_argument("--failed-batch-count", type=int)
    args = parser.parse_args()
    if args.command == "window":
        start, end = session_window(
            load_events(args.events),
            max_lookback_seconds=args.max_lookback_seconds,
        )
        print(start)
        print(end)
        return 0
    if args.command == "batches":
        for start, end in window_batches(
            args.start,
            args.end,
            batch_seconds=args.batch_seconds,
        ):
            print(f"{start}\t{end}")
        return 0
    augment(
        args.bundle,
        args.raw,
        args.inventory,
        args.capture_status,
        batch_count=args.batch_count,
        failed_batch_count=args.failed_batch_count,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
