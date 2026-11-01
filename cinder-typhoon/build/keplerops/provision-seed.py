#!/usr/bin/env python3
"""Create the operator-only, per-range KeplerOps credential material."""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys


ROOT = Path(__file__).resolve().parents[3]
COOKIE_TEMPLATE = (
    ROOT
    / "cinder-typhoon"
    / "assets"
    / "keplerops"
    / "opening"
    / "k-dev"
    / "chromium-Cookies"
)
SCHEMA = "fieldkest.runtime-credentials/v1"

# Every accepted, replayable bearer, session, and service credential is
# generated here. Dynamic one-time values (worker leases, assertions,
# receipts, channel approvals, and completion leases) remain service-issued.
PURPOSES = {
    "assistant_tool_session": "assistant-tool",
    "cert_enrollment_worker": "cert-enrollment",
    "ci_maintenance_worker": "ci-maintenance",
    "ci_registry_reader": "ci-registry-reader",
    "cloud_history_recovery_session": "history-recovery",
    "cloud_maintenance_runtime": "maintenance-runtime",
    "cloud_support_export_role": "support-export",
    "cloud_workload_fixture_token": "workload-fixture",
    "cloud_workload_session": "workload-session",
    "connector_package_internal": "connector-package",
    "developer_token": "developer",
    "indexer_worker_lease": "indexer-worker",
    "registry_publisher_token": "registry-publisher",
    "registry_release_admin_token": "registry-release-admin",
    "release_reader_token": "release-reader",
    "staff_preview_service": "staff-preview",
    "support_delivery_token": "support-delivery",
    "support_reviewer_session": "support-reviewer",
    "support_rowan_session": "support-rowan",
}


def derive(seed: bytes, name: str) -> str:
    """Return a range-bound credential with at least 192 bits of entropy."""
    digest = hmac.new(seed, f"keplerops:{name}:v1".encode(), hashlib.sha256).digest()
    encoded = base64.urlsafe_b64encode(digest[:24]).decode().rstrip("=")
    return f"fk_{PURPOSES[name].replace('-', '_')}_{encoded}"


def write_private(path: Path, data: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as output:
        output.write(data)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seed-file", type=Path, required=True,
        help="0600 file containing the range seed",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cookie-template", type=Path, default=COOKIE_TEMPLATE)
    args = parser.parse_args()

    try:
        seed_bytes = args.seed_file.read_bytes()
    except OSError as error:
        print(f"error: cannot read seed: {error}", file=sys.stderr)
        return 2
    if len(seed_bytes) < 32:
        print("error: seed must contain at least 32 bytes", file=sys.stderr)
        return 2
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        print("error: output directory must be new or empty", file=sys.stderr)
        return 2
    args.output_dir.mkdir(parents=True, mode=0o700, exist_ok=True)
    os.chmod(args.output_dir, 0o700)

    credentials = {name: derive(seed_bytes, name) for name in sorted(PURPOSES)}
    runtime = {"schema": SCHEMA, "credentials": credentials}
    write_private(
        args.output_dir / "runtime-credentials.json",
        (json.dumps(runtime, sort_keys=True, separators=(",", ":")) + "\n").encode(),
    )

    participant = args.output_dir / "participant"
    participant.mkdir(mode=0o700)
    git_credential = (
        f"https://rowan.ito:{credentials['developer_token']}@source.keplerops.test\n"
    )
    write_private(participant / "git-credentials", git_credential.encode())
    cookie_path = participant / "chromium-Cookies"
    shutil.copyfile(args.cookie_template, cookie_path)
    os.chmod(cookie_path, 0o600)
    with sqlite3.connect(cookie_path) as connection:
        updated = connection.execute(
            "UPDATE cookies SET value = ?, encrypted_value = X'' "
            "WHERE host_key = ? AND name = ?",
            (
                credentials["support_rowan_session"],
                "support.keplerops.test",
                "fieldkest_support",
            ),
        ).rowcount
        if updated != 1:
            print("error: cookie template does not contain the expected session", file=sys.stderr)
            return 2

    generation_id = hmac.new(
        seed_bytes, b"keplerops:generation-id:v1", hashlib.sha256
    ).hexdigest()
    metadata = {
        "schema": "fieldkest.range-credential-metadata/v1",
        "generation_id": generation_id,
        "credential_classes": sorted(credentials),
        "participant_artifacts": ["chromium-Cookies", "git-credentials"],
    }
    write_private(
        args.output_dir / "metadata.json",
        (json.dumps(metadata, indent=2, sort_keys=True) + "\n").encode(),
    )
    print("Generated per-range KeplerOps credential material (values withheld).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
