#!/usr/bin/env python3
"""Assemble trusted W21 evidence from the native project and Editor CLI output."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re
from typing import Any


HERE = pathlib.Path(__file__).resolve().parent
CONTRACT = json.loads((HERE / "contract.json").read_text())
MD5 = re.compile(r"^[0-9a-fA-F]{32}$")


def read_json(path: pathlib.Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain one JSON object")
    return value


def digest_sources(paths: list[pathlib.Path], root: pathlib.Path | None = None) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.as_posix()):
        label = path.relative_to(root) if root is not None else path
        relative = label.as_posix().encode()
        payload = path.read_bytes()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def project_observation(project: pathlib.Path) -> tuple[dict[str, Any], list[pathlib.Path]]:
    metadata_path = project / "project.json"
    program_path = project / "pous/programs/main.fbd"
    configuration_path = project / "devices/configuration.json"
    paths = [metadata_path, program_path, configuration_path]
    if not all(path.is_file() for path in paths):
        raise ValueError("saved OpenPLC project is incomplete")
    metadata = read_json(metadata_path)
    configuration = read_json(configuration_path)
    program = program_path.read_text()
    task = metadata["data"]["configuration"]["resource"]["tasks"][0]
    revision = re.search(r"\bProjectRevision\b[^\n]*:=\s*(\d+)\s*;", program)
    declared_program = re.search(r"^PROGRAM\s+(\w+)\s*$", program, re.MULTILINE)
    if revision is None or declared_program is None:
        raise ValueError("saved project lacks its declared program identity")
    return {
        "name": project.name,
        "participant_path": CONTRACT["project"]["participant_path"],
        "main_program": declared_program.group(1),
        "language": "FBD",
        "project_revision": int(revision.group(1)),
        "task_interval": task["interval"],
        "device_target": configuration["deviceBoard"],
        "runtime_host": configuration["runtimeIpAddress"],
        "project_sha256": digest_sources(paths, project),
    }, paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=pathlib.Path, required=True)
    parser.add_argument("--debug-status", type=pathlib.Path, required=True)
    parser.add_argument("--debug-read", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path)
    args = parser.parse_args()

    project, project_paths = project_observation(args.project.resolve())
    status_document = read_json(args.debug_status)
    read_document = read_json(args.debug_read)
    status = status_document.get("status")
    values = read_document.get("values")
    if status_document.get("kind") != "status" or not isinstance(status, dict):
        raise ValueError("debug status is not native OpenPLC CLI status output")
    if read_document.get("kind") != "read" or not isinstance(values, list):
        raise ValueError("debug read is not native OpenPLC CLI variable output")
    revisions = [item for item in values if isinstance(item, dict) and str(item.get("name", "")).split(".")[-1] == "ProjectRevision"]
    if len(revisions) != 1 or isinstance(revisions[0].get("value"), bool) or not isinstance(revisions[0].get("value"), (int, float)):
        raise ValueError("debug read lacks one typed ProjectRevision value")
    program_md5 = status.get("programMd5")
    if not isinstance(program_md5, str) or not MD5.fullmatch(program_md5):
        raise ValueError("debug status lacks a valid program MD5")
    captured_at = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    raw_paths = [*project_paths, args.debug_status.resolve(), args.debug_read.resolve()]
    snapshot = {
        "schema": CONTRACT["product_snapshot"]["schema"],
        "asset": CONTRACT["asset"],
        "captured_at": captured_at,
        "source_digest": digest_sources(raw_paths),
        "saved_project": project,
        "runtime": {
            "observed_at": captured_at,
            "target": status.get("target"),
            "host": project["runtime_host"],
            "program_md5": program_md5.lower(),
            "program_matches_saved_project": status.get("md5Matches"),
            "state": status.get("plcState"),
            "connected": status.get("connected"),
            "forced_variables": status.get("forced"),
            "live_project_revision": int(revisions[0]["value"]),
        },
    }
    rendered = json.dumps(snapshot, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered)
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
