#!/usr/bin/env python3
"""Run one reviewed W33 commissioning schedule through the site dispatcher."""

from __future__ import annotations

import argparse
import getpass
import json
import pathlib
import select
import subprocess
import time
import uuid


REQUEST_TOPIC = "arwc/crr/commands/operator"
OUTCOME_TOPIC = "arwc/crr/outcomes/operator"
TERMINAL = {"completed", "plc_rejected", "superseded", "uncertain", "expired"}


def number_list(value: object, name: str, maximum: float) -> list[float]:
    if not isinstance(value, list) or len(value) != 12:
        raise ValueError(f"{name} must contain twelve values")
    values = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError(f"{name} values must be numbers")
        item = float(item)
        if not 0.0 <= item <= maximum:
            raise ValueError(f"{name} value is outside its operating range")
        values.append(item)
    if any(abs(values[index] - values[index - 1]) > 0.1000001 for index in range(1, 12)):
        raise ValueError(f"{name} exceeds the 0.10 m3/s step limit")
    return values


def load_schedule(path: pathlib.Path) -> tuple[dict, list[float]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "schema", "instruction", "asset", "interval_seconds",
        "reservoir_release_m3s", "alternate_supply_m3s",
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError("schedule fields do not match the published template")
    if (
        value["schema"] != "arwc.operating-schedule/v1"
        or value["instruction"] != "CRR-OP-W33-R1"
        or value["asset"] != "AST-CRR-017"
        or value["interval_seconds"] != 300
    ):
        raise ValueError("schedule identity does not match CRR-OP-W33-R1")
    releases = number_list(value["reservoir_release_m3s"], "reservoir release", 0.8)
    number_list(value["alternate_supply_m3s"], "alternate supply", 0.5)
    return value, releases


def wait_for_terminal(process: subprocess.Popen[str], request_id: str, timeout: float) -> list[dict]:
    deadline = time.monotonic() + timeout
    outcomes = []
    while time.monotonic() < deadline:
        ready, _, _ = select.select([process.stdout], [], [], min(1.0, deadline - time.monotonic()))
        if not ready:
            continue
        line = process.stdout.readline()
        if not line:
            raise RuntimeError("MQTT outcome subscription ended")
        try:
            outcome = json.loads(line)
        except json.JSONDecodeError:
            continue
        if outcome.get("id") != request_id:
            continue
        outcomes.append(outcome)
        if outcome.get("status") in TERMINAL:
            return outcomes
    raise RuntimeError(f"request {request_id} did not reach a terminal product state")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("schedule", type=pathlib.Path)
    parser.add_argument("--receipt", type=pathlib.Path, default=pathlib.Path("w33-commissioning-receipt.json"))
    arguments = parser.parse_args()
    schedule, releases = load_schedule(arguments.schedule)
    password = getpass.getpass("MQTT operator password from CairnReach/Connections/README.md: ")
    common = [
        "-h", "mosquitto", "-p", "8883", "--cafile",
        "/home/fieldlink/CairnReach/Connections/mqtt-ca.pem",
        "-u", "operator", "-P", password, "-q", "1",
    ]
    subscriber = subprocess.Popen(
        ["mosquitto_sub", *common, "-t", OUTCOME_TOPIC],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    receipt = {"schema": "arwc.commissioning-receipt/v1", "schedule": schedule, "requests": []}
    try:
        time.sleep(0.5)
        if subscriber.poll() is not None:
            raise RuntimeError(subscriber.stderr.read().strip() or "MQTT subscription failed")
        for index, flow in enumerate(releases, start=1):
            request_id = str(uuid.uuid4())
            request = {
                "id": request_id,
                "asset": "AST-CRR-017",
                "mode": "automatic",
                "position_a_pct": 20.0,
                "position_b_pct": 20.0,
                "total_flow_m3s": flow,
                "expires_at": time.time() + 90,
            }
            subprocess.run(
                ["mosquitto_pub", *common, "-t", REQUEST_TOPIC, "-m", json.dumps(request, separators=(",", ":"))],
                check=True,
            )
            outcomes = wait_for_terminal(subscriber, request_id, 100)
            terminal = outcomes[-1].get("status")
            receipt["requests"].append({"interval": index, "request": request, "outcomes": outcomes})
            arguments.receipt.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
            if terminal != "completed":
                raise RuntimeError(f"interval {index} stopped at product state {terminal}; inspect and reconcile")
            print(f"interval {index}/12 completed at {flow:.3f} m3/s")
    finally:
        subscriber.terminate()
        try:
            subscriber.wait(timeout=3)
        except subprocess.TimeoutExpired:
            subscriber.kill()
    print(f"Commissioning receipt written to {arguments.receipt}; restore manual A20/B20 in FUXA now.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
