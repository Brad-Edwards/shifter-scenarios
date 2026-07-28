#!/usr/bin/env python3
"""Seed ordinary operations through an isolated native OTLP logs pipeline."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from company_state_common import (
    OWNER,
    assert_readback,
    load_corpus,
    normalized_readback,
    require_records,
)

CONTENT_ID = "company-operational-telemetry"
OTLP_ENDPOINT = "http://127.0.0.1:4320/v1/logs"
SELECTIONS = (
    ("operations", "operation-backup-0422"),
    ("operations", "operation-index-refresh-0424"),
    ("operations", "operation-release-health-0502"),
    ("operations", "operation-storage-warning-0509"),
    ("operations", "operation-index-refresh-0515"),
)


def _attribute(key: str, value: str) -> dict[str, Any]:
    return {"key": key, "value": {"stringValue": value}}


def build_plan(path: Path) -> dict[str, Any]:
    records = require_records(load_corpus(path), SELECTIONS)
    log_records: list[dict[str, Any]] = []
    for record in records:
        source = record["source"]
        occurred_at = datetime.fromisoformat(
            source["occurred_at"].replace("Z", "+00:00")
        )
        log_records.append(
            {
                "timeUnixNano": str(int(occurred_at.timestamp() * 1_000_000_000)),
                "observedTimeUnixNano": str(
                    int(occurred_at.timestamp() * 1_000_000_000)
                ),
                "severityNumber": 13 if source["kind"] == "storage-warning" else 9,
                "severityText": (
                    "WARN" if source["kind"] == "storage-warning" else "INFO"
                ),
                "body": {"stringValue": json.dumps(source, sort_keys=True)},
                "attributes": [
                    _attribute("keplerops.company_state.object_id", record["id"]),
                    _attribute(
                        "keplerops.company_state.object_type", record["object_type"]
                    ),
                    _attribute(
                        "keplerops.company_state.source_digest",
                        record["source_digest"],
                    ),
                ],
            }
        )
    payload = {
        "resourceLogs": [
            {
                "resource": {
                    "attributes": [
                        _attribute("service.name", "keplerops-company-operations"),
                        _attribute("keplerops.company_state.owner", OWNER),
                        _attribute("keplerops.company_state.content_id", CONTENT_ID),
                    ]
                },
                "scopeLogs": [
                    {
                        "scope": {
                            "name": "keplerops.company-state",
                            "version": "1",
                        },
                        "logRecords": log_records,
                    }
                ],
            }
        ]
    }
    return {
        "payload": payload,
        "readback": normalized_readback(CONTENT_ID, records),
    }


def _attributes(rows: list[dict[str, Any]]) -> dict[str, str]:
    output: dict[str, str] = {}
    for row in rows:
        value = row.get("value", {})
        if isinstance(row.get("key"), str) and isinstance(value, dict):
            scalar = value.get("stringValue")
            if isinstance(scalar, str):
                output[row["key"]] = scalar
    return output


def records_from_exports(  # NOSONAR - nested OTLP envelopes require one traversal.
    path: Path,
) -> list[dict[str, Any]]:
    observed: list[dict[str, Any]] = []
    # The proof-service entrypoint fixes this collector-owned export path.
    for line in path.read_text(encoding="utf-8").splitlines():  # NOSONAR
        envelope = json.loads(line)
        for resource_logs in envelope.get("resourceLogs", []):
            resource = _attributes(
                resource_logs.get("resource", {}).get("attributes", [])
            )
            if resource.get("keplerops.company_state.owner") != OWNER:
                raise RuntimeError("ownership collision: telemetry company-state file")
            if resource.get("keplerops.company_state.content_id") != CONTENT_ID:
                raise RuntimeError("telemetry company-state content id mismatch")
            for scope_logs in resource_logs.get("scopeLogs", []):
                for log_record in scope_logs.get("logRecords", []):
                    attributes = _attributes(log_record.get("attributes", []))
                    observed.append(
                        {
                            "id": attributes.get("keplerops.company_state.object_id"),
                            "object_type": attributes.get(
                                "keplerops.company_state.object_type"
                            ),
                            "source_digest": attributes.get(
                                "keplerops.company_state.source_digest"
                            ),
                        }
                    )
    return observed


def prepare(path: Path) -> None:
    if not path.exists():
        return
    records_from_exports(path)
    path.unlink()  # NOSONAR - same collector-owned export path.


def loopback_otlp_endpoint(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "::1", "localhost"}
        or parsed.port is None
        or parsed.path != "/v1/logs"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("OTLP endpoint must be an explicit loopback /v1/logs URL")
    return value


def send(payload: dict[str, Any], endpoint: str = OTLP_ENDPOINT) -> None:
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    request = Request(  # NOSONAR - endpoint is constrained to loopback above.
        loopback_otlp_endpoint(endpoint),
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=5) as response:
        if response.status not in (200, 202):
            raise RuntimeError("OTLP company operations ingestion failed")


def readback(expected: dict[str, Any], path: Path) -> dict[str, Any]:
    return assert_readback(expected, records_from_exports(path))


def wait_for_readback(
    expected: dict[str, Any], path: Path, *, timeout_seconds: int = 30
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            if path.exists():
                return readback(expected, path)
        except (json.JSONDecodeError, RuntimeError) as error:
            last_error = error
        time.sleep(0.25)
    raise RuntimeError("company operations OTLP readback timed out") from last_error


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "seed", "readback", "plan"))
    parser.add_argument("--company-state", type=Path, required=True)
    parser.add_argument("--export", type=Path, required=True)
    parser.add_argument("--endpoint", default=OTLP_ENDPOINT)
    args = parser.parse_args()
    plan = build_plan(args.company_state)
    if args.command == "prepare":
        prepare(args.export)
        return
    if args.command == "seed":
        send(plan["payload"], args.endpoint)
        result = wait_for_readback(plan["readback"], args.export)
    elif args.command == "readback":
        result = readback(plan["readback"], args.export)
    else:
        result = plan
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
