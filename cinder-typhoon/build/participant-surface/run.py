#!/usr/bin/env python3
"""Run the participant-surface observer inside a local phase container."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from compare import compare
from validate import load, validate


ROOT = Path(__file__).resolve().parent
PHASES = {
    "training": ("cinder-training-kali", "cinder", "/home/cinder"),
    "keplerops": ("cinder-keplerops-k-dev", "rowan", "/home/rowan"),
    "arwc": ("cinder-arwc-connector", "fieldlink", "/var/lib/fieldlink-connector"),
}


def observation_plan(authored: dict) -> dict:
    """Return only the probe targets needed inside the participant context."""
    return {
        "phase": authored["phase"],
        "state": authored["state"],
        "participant": {"uid": authored["participant"]["uid"]},
        "filesystem": {
            "roots": [
                {"path": root["path"], "opaque": root["opaque"]}
                for root in authored["filesystem"]["roots"]
            ],
            "forbidden_paths": [
                {"path": item["path"]}
                for item in authored["filesystem"]["forbidden_paths"]
            ],
        },
        "tools": [{"name": item["name"]} for item in authored["tools"]],
        "network": {
            "dns": [{"name": item["name"]} for item in authored["network"]["dns"]],
            "listeners": [
                {"host": item["host"], "port": item["port"]}
                for item in authored["network"]["listeners"]
            ],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True, choices=sorted(PHASES))
    parser.add_argument("--observed-output", type=Path)
    parser.add_argument("--snapshot", action="store_true", help="emit observation without comparison")
    arguments = parser.parse_args()

    manifest_path = ROOT / "manifests" / f"{arguments.phase}.json"
    authored = load(manifest_path)
    container, user, workdir = PHASES[arguments.phase]
    observer = (ROOT / "observe.py").read_text()
    command = [
        "docker", "exec", "-i", "--user", user, "--workdir", workdir,
        container, "python3", "-c", observer,
    ]
    result = subprocess.run(
        command,
        input=json.dumps(observation_plan(authored)),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        print(result.stderr, file=sys.stderr, end="")
        return result.returncode
    observed = json.loads(result.stdout)
    validate(observed)
    if arguments.observed_output:
        arguments.observed_output.write_text(json.dumps(observed, indent=2, sort_keys=True) + "\n")
    elif arguments.snapshot:
        print(json.dumps(observed, indent=2, sort_keys=True))
    if arguments.snapshot:
        return 0
    failures = compare(authored, observed)
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print(f"PASS: {arguments.phase} participant surface matches authored manifest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
