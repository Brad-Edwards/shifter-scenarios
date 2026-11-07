#!/usr/bin/env python3
"""Prepare an isolated participant-proxy workspace for one agent operation."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import shlex


ROOT = Path(__file__).resolve().parents[2]
PROXY_SOURCE = Path(__file__).with_name("proxy.py")
CATALOG_MODULE_PATH = ROOT / "challenges/catalog.py"
SPEC = importlib.util.spec_from_file_location("cinder_agentic_qa_prepare_catalog", CATALOG_MODULE_PATH)
assert SPEC and SPEC.loader
catalog_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(catalog_module)
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:+/\-\[\]]{0,159}$")


def digest_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_private(path: Path, content: str, mode: int = 0o600) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), mode)
    os.fchmod(descriptor, mode)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        output.write(content)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("training", "keplerops", "arwc"), required=True)
    parser.add_argument("--operation", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--reset-identity", required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--zone", default="us-central1-a")
    parser.add_argument("--account", required=True)
    parser.add_argument("--agent-product", required=True)
    parser.add_argument("--agent-model", required=True)
    parser.add_argument("--agent-version", required=True)
    parser.add_argument("--agent-configuration", default="restricted-participant-proxy-v1")
    parser.add_argument("--start-label", choices=("pristine", "retained", "transition-earned"), required=True)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    arguments = parser.parse_args()

    workspace = arguments.workspace.resolve()
    if workspace == ROOT or ROOT in workspace.parents or workspace.exists():
        parser.error("--workspace must be a new directory outside the repository")
    if (
        arguments.project != "prod-mgau4w"
        or arguments.zone != "us-central1-a"
        or arguments.account != "bedwards@paloaltonetworks.com"
    ):
        parser.error("the approved Cinder golden project, zone, and account are required")
    agent_identity = {
        "product": arguments.agent_product,
        "model": arguments.agent_model,
        "version": arguments.agent_version,
        "configuration": arguments.agent_configuration,
    }
    for field, value in agent_identity.items():
        if SAFE_ID.fullmatch(value) is None:
            parser.error(f"--agent-{field} must be a report-safe identifier")
    gcloud_path = shutil.which("gcloud")
    if gcloud_path is None:
        parser.error("gcloud is required on the supervisor host")

    catalog = catalog_module.load_catalog()
    operations = {
        operation["id"]: operation
        for operation in catalog["phases"][arguments.phase]["operations"]
    }
    if arguments.operation not in operations:
        parser.error("operation does not belong to the selected phase")
    candidate_path = ROOT / "build/participant-runner/candidate.json"
    release_path = ROOT / "build/release/manifest.json"
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    release = json.loads(release_path.read_text(encoding="utf-8"))
    if candidate.get("immutable") is not True:
        parser.error("the candidate must be immutable")
    candidate_identity = {
        "candidate_id": candidate["candidate_id"],
        "source_commit": candidate["source_commit"],
        "candidate_manifest_sha256": digest_file(candidate_path),
        "release_manifest_sha256": digest_file(release_path),
    }
    release_candidate = release.get("candidate")
    if not isinstance(release_candidate, dict) or (
        release.get("release_id") != candidate_identity["candidate_id"]
        or release.get("source_commit") != candidate_identity["source_commit"]
        or release_candidate.get("candidate_id") != candidate_identity["candidate_id"]
        or release_candidate.get("path") != "build/participant-runner/candidate.json"
        or release_candidate.get("sha256") != candidate_identity["candidate_manifest_sha256"]
    ):
        parser.error("release manifest does not bind the candidate")

    workspace.mkdir(mode=0o700, parents=False)
    proxy_path = workspace / "proxy.py"
    shutil.copyfile(PROXY_SOURCE, proxy_path)
    proxy_path.chmod(0o700)
    config_path = workspace / "config.json"
    state_path = workspace / "state.json"
    raw_log_path = workspace / "raw.jsonl"
    export_path = workspace / "operation.json"
    operation = operations[arguments.operation]
    config = {
        "schema_version": 1,
        "candidate": candidate_identity,
        "phase": arguments.phase,
        "operation_id": arguments.operation,
        "session_id": arguments.session_id,
        "reset_identity": arguments.reset_identity,
        "project": arguments.project,
        "zone": arguments.zone,
        "account": arguments.account,
        "gcloud_path": gcloud_path,
        "agent": {
            **agent_identity,
            "tools": ["cinder-participant"],
        },
        "cards": [
            {key: card[key] for key in ("id", "title", "description", "points", "hints")}
            for card in operation["cards"]
        ],
        "paths": {
            "state": str(state_path),
            "raw_log": str(raw_log_path),
            "export": str(export_path),
        },
        "started_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "start_label": arguments.start_label,
        "timeout_seconds": arguments.timeout_seconds,
    }
    write_private(config_path, json.dumps(config, indent=2, sort_keys=True) + "\n")
    launcher_path = workspace / "cinder-participant"
    launcher = (
        "#!/bin/sh\n"
        f"exec python3 {shlex.quote(str(proxy_path))} --config {shlex.quote(str(config_path))} \"$@\"\n"
    )
    write_private(launcher_path, launcher, 0o700)
    print(json.dumps({
        "workspace": str(workspace),
        "launcher": str(launcher_path),
        "operation_id": arguments.operation,
        "card_count": len(operation["cards"]),
        "candidate_id": candidate_identity["candidate_id"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

