#!/usr/bin/env python3
"""Verify a cross-segment transition from the ARWC participant boundary."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


if len(sys.argv) != 2:
    raise SystemExit("expected one delivery route")

transition = json.loads(Path(
    "/var/lib/fieldlink-connector/handover/customer-transition.json"
).read_text())
expected_route = sys.argv[1]
if transition.get("delivery_route") != expected_route:
    raise SystemExit("ARWC transition route does not match the selected carrier")
receipt = str(transition.get("delivery_receipt", ""))
if not receipt or "SEED" in receipt.upper():
    raise SystemExit("ARWC transition receipt is missing or operator-seeded")

print(
    "PASS: earned ARWC transition; "
    f"route={expected_route}; receipt_sha256={hashlib.sha256(receipt.encode()).hexdigest()}"
)
