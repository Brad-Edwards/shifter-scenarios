#!/usr/bin/env python3
"""Materialize company policy context through OPA's native Data API."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from company_state_common import (
    OWNER,
    assert_readback,
    load_corpus,
    normalized_readback,
    require_records,
)

CONTENT_ID = "company-policy-state"
DATA_PATH = "/v1/data/keplerops/company_state"
SELECTIONS = (
    ("tickets", "ticket-kep-155"),
    ("approvals", "approval-orion-18-review"),
    ("commits", "commit-policy-refresh"),
)


def build_document(path: Path) -> dict[str, Any]:
    records = require_records(load_corpus(path), SELECTIONS)
    return {
        "schema_version": 1,
        "owner": OWNER,
        "content_id": CONTENT_ID,
        "records": records,
        "readback": normalized_readback(CONTENT_ID, records),
    }


def _request(method: str, url: str, payload: dict[str, Any] | None = None) -> Any:
    encoded = None
    headers: dict[str, str] = {}
    if payload is not None:
        encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        headers["Content-Type"] = "application/json"
    request = Request(url, data=encoded, headers=headers, method=method)
    try:
        with urlopen(request, timeout=5) as response:
            body = response.read()
    except HTTPError as error:
        if error.code == 404:
            return None
        raise
    return json.loads(body) if body else None


def observed_records(document: dict[str, Any]) -> list[dict[str, Any]]:
    if document.get("owner") != OWNER or document.get("content_id") != CONTENT_ID:
        raise RuntimeError("ownership collision: OPA data.keplerops.company_state")
    rows = document.get("records")
    if not isinstance(rows, list):
        raise TypeError("OPA company policy readback is invalid")
    return rows


def readback(
    expected: dict[str, Any],
    transport: Callable[[str, str, dict[str, Any] | None], Any] = _request,
    *,
    base_url: str,
) -> dict[str, Any]:
    response = transport("GET", base_url.rstrip("/") + DATA_PATH, None)
    if not isinstance(response, dict) or not isinstance(response.get("result"), dict):
        raise TypeError("OPA company policy document is unavailable")
    return assert_readback(expected["readback"], observed_records(response["result"]))


def seed(
    expected: dict[str, Any],
    transport: Callable[[str, str, dict[str, Any] | None], Any] = _request,
    *,
    base_url: str,
) -> dict[str, Any]:
    url = base_url.rstrip("/") + DATA_PATH
    existing = transport("GET", url, None)
    if isinstance(existing, dict) and "result" in existing:
        observed_records(existing["result"])
    transport("PUT", url, expected)
    return readback(expected, transport, base_url=base_url)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("seed", "readback", "plan"))
    parser.add_argument("--company-state", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8181")
    args = parser.parse_args()
    document = build_document(args.company_state)
    if args.command == "seed":
        result = seed(document, base_url=args.base_url)
    elif args.command == "readback":
        result = readback(document, base_url=args.base_url)
    else:
        result = document
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
