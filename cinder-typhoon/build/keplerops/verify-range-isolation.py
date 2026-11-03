#!/usr/bin/env python3
"""Operator-side cross-range replay and credential leakage verifier."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


DEFAULT_CURRENT = Path(".operator/range-seed/runtime-credentials.json")
CONTAINER = "cinder-keplerops-k-dev"
CA = "/home/rowan/.local/share/keplerops/ca.crt"


def load(path: Path) -> dict[str, str]:
    document = json.loads(path.read_text())
    if document.get("schema") != "fieldkest.runtime-credentials/v1":
        raise ValueError(f"invalid credential schema: {path}")
    credentials = document.get("credentials")
    if not isinstance(credentials, dict) or not credentials:
        raise ValueError(f"missing credentials: {path}")
    return credentials


def status(
    host: str,
    path: str,
    *,
    token: str | None = None,
    cookie: str | None = None,
    method: str = "GET",
    body: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
) -> int:
    command = [
        "docker", "exec", "--user", "rowan", CONTAINER,
        "curl", "-sS", "--cacert", CA, "-o", "/tmp/range-isolation-response",
        "-w", "%{http_code}", "-X", method,
    ]
    if token is not None:
        command += ["-H", f"Authorization: Bearer {token}"]
    if cookie is not None:
        command += ["-H", f"Cookie: fieldkest_support={cookie}"]
    for name, value in (headers or {}).items():
        command += ["-H", f"{name}: {value}"]
    if body is not None:
        command += [
            "-H", "Content-Type: application/json",
            "--data-binary", json.dumps(body, sort_keys=True, separators=(",", ":")),
        ]
    command.append(f"https://{host}{path}")
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode or not completed.stdout.isdigit():
        raise RuntimeError(f"request failed without an HTTP status: {host}{path}")
    return int(completed.stdout)


def json_request(
    host: str,
    path: str,
    *,
    token: str | None = None,
    method: str = "GET",
    body: dict[str, object] | None = None,
) -> tuple[int, dict[str, object]]:
    command = [
        "docker", "exec", "--user", "rowan", CONTAINER,
        "curl", "-sS", "--cacert", CA, "-w", "\n%{http_code}", "-X", method,
    ]
    if token is not None:
        command += ["-H", f"Authorization: Bearer {token}"]
    if body is not None:
        command += [
            "-H", "Content-Type: application/json",
            "--data-binary", json.dumps(body, sort_keys=True, separators=(",", ":")),
        ]
    command.append(f"https://{host}{path}")
    completed = subprocess.run(command, capture_output=True, text=True, check=True)
    raw, separator, raw_status = completed.stdout.rpartition("\n")
    if not separator or not raw_status.isdigit():
        raise RuntimeError(f"request failed without an HTTP status: {host}{path}")
    value = json.loads(raw) if raw else {}
    if not isinstance(value, dict):
        raise RuntimeError(f"request returned a non-object: {host}{path}")
    return int(raw_status), value


def expect_replay_denied(
    name: str,
    current: str,
    foreign: str,
    request,
    accepted: set[int],
    denied: set[int],
) -> None:
    foreign_status = request(foreign)
    if foreign_status not in denied:
        raise AssertionError(f"{name}: foreign credential returned HTTP {foreign_status}")
    current_status = request(current)
    if current_status not in accepted:
        raise AssertionError(f"{name}: current credential returned HTTP {current_status}")
    if current_status == foreign_status:
        raise AssertionError(f"{name}: current and foreign credentials were indistinguishable")


def verify_replay(current: dict[str, str], foreign: dict[str, str]) -> None:
    if set(current) != set(foreign):
        raise AssertionError("credential class inventory differs across ranges")
    for name in sorted(current):
        if current[name] == foreign[name]:
            raise AssertionError(f"{name}: value did not vary across ranges")

    checks = {
        "developer_token": (
            lambda value: status("source.keplerops.test", "/api/fieldkest/handovers/current", token=value),
            {200}, {401},
        ),
        "support_rowan_session": (
            lambda value: status("support.keplerops.test", "/api/session", cookie=value),
            {200}, {403},
        ),
        "support_reviewer_session": (
            lambda value: status("support.keplerops.test", "/api/session", cookie=value),
            {200}, {403},
        ),
        "registry_publisher_token": (
            lambda value: status(
                "packages.keplerops.test", "/@keplerops%2ffieldlink-connector",
                token=value, method="PUT", body={},
            ),
            {422}, {403},
        ),
        "ci_registry_reader": (
            lambda value: status(
                "packages.keplerops.test",
                "/@keplerops%2ffieldlink-connector/-/fieldlink-connector-7.4.3-cinder.isolation.tgz",
                token=value,
            ),
            {404}, {403},
        ),
        "registry_release_admin_token": (
            lambda value: status("packages.keplerops.test", "/api/release-administration/session", token=value),
            {200}, {403},
        ),
        "release_reader_token": (
            lambda value: status("ci.keplerops.test", "/api/runs/BLD-REL-742/artifacts/release-dossier.json", token=value),
            {200}, {403},
        ),
        "cloud_workload_fixture_token": (
            lambda value: status(
                "cloud-api.keplerops.test", "/api/token-exchange/support-export-editor",
                token=value, method="POST", body={},
            ),
            {201}, {403},
        ),
        "cloud_workload_session": (
            lambda value: status("cloud-api.keplerops.test", "/api/build-records/BLD-1842", token=value),
            {200}, {403},
        ),
        "cloud_support_export_role": (
            lambda value: status("cloud-api.keplerops.test", "/api/roles/support-export-editor", token=value),
            {200}, {403},
        ),
        "cloud_history_recovery_session": (
            lambda value: status("data.keplerops.test", "/api/backups/BAK-2026-021", token=value),
            {200}, {403},
        ),
        "ci_maintenance_worker": (
            lambda value: status("cloud-api.keplerops.test", "/api/policies/fieldlink-maintenance", token=value),
            {200}, {403},
        ),
        "cloud_maintenance_runtime": (
            lambda value: status(
                "data.keplerops.test", "/api/field-archive/FIELD-CRR-2026-09",
                token=value,
                headers={"X-Workload-Class": "maintenance", "X-Scheduler-Attestation": "isolation-check"},
            ),
            {200}, {403},
        ),
        "staff_preview_service": (
            lambda value: status("identity.keplerops.test", "/api/registrations/OIDC-FIELDKEST-SUPPORT", token=value),
            {200}, {401},
        ),
        "cert_enrollment_worker": (
            lambda value: status(
                "cert.keplerops.test", "/api/enrollment/StaffArchiveUser/requests",
                token=value, method="POST", body={"upn": "evan.calderoux@KEPLEROPS.TEST"},
            ),
            {201}, {403},
        ),
        "assistant_tool_session": (
            lambda value: status(
                "support.keplerops.test", "/api/reviews/DREV-2841-2/duplicate-disposition",
                token=value, method="PATCH", body={"recommendation_id": "assistant-obsolete-bundle"},
            ),
            {200}, {403},
        ),
    }
    for name, (request, accepted, denied) in checks.items():
        expect_replay_denied(name, current[name], foreign[name], request, accepted, denied)

    # A current diagnostic identity must traverse the relay, mTLS connection,
    # and paired carrier.  The intentionally incomplete request is rejected by
    # ARWC's binding validation, which distinguishes end-to-end transit from a
    # local relay authentication failure.
    transit_status, transit_response = json_request(
        "connector.arwc.test", "/api/fieldlink/diagnostics",
        token=current["support_delivery_token"], method="POST", body={},
    )
    if transit_status != 403 or transit_response.get("error") != "diagnostic_binding_denied":
        raise AssertionError(
            f"paired carrier transit failed with HTTP {transit_status} "
            f"and error {transit_response.get('error')!r}"
        )

    # These internal credentials require an earned service state before a
    # positive request. Their distinct values are checked above; a foreign
    # value must still fail at the public boundary without changing state.
    negative_only = {
        "indexer_worker_lease": lambda value: status(
            "indexer.keplerops.test", "/api/internal/release-exceptions/state",
            token=value, method="POST", body={"state": "queue-ready", "integrity": "invalid"},
        ),
        "support_delivery_token": lambda value: status(
            "connector.arwc.test", "/api/fieldlink/diagnostics",
            token=value, method="POST", body={},
        ),
        "connector_package_internal": lambda value: status(
            "connector.arwc.test", "/api/fieldlink/packages/poll",
            token=value, method="POST", body={},
        ),
    }
    for name, request in negative_only.items():
        foreign_status = request(foreign[name])
        if foreign_status != 403:
            raise AssertionError(f"{name}: foreign credential returned HTTP {foreign_status}")


def verify_mounts() -> None:
    completed = subprocess.run(
        ["docker", "inspect", CONTAINER], capture_output=True, text=True, check=True
    )
    document = json.loads(completed.stdout)[0]
    forbidden = ("runtime-credentials", "metadata.json", "seed-manifest", "/range-seed/")
    for mount in document.get("Mounts", []):
        description = json.dumps(mount, sort_keys=True)
        if any(value in description for value in forbidden):
            raise AssertionError("participant container mounts operator credential material")


def verify_logs(credentials: dict[str, str]) -> None:
    containers = subprocess.run(
        ["docker", "ps", "-a", "--format", "{{.Names}}"],
        capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    for container in containers:
        output = subprocess.run(
            ["docker", "logs", container], capture_output=True, check=False
        )
        combined = output.stdout + output.stderr
        for name, value in credentials.items():
            if value.encode() in combined:
                raise AssertionError(f"{name}: credential present in container logs")


def verify_image_metadata(credentials: dict[str, str]) -> None:
    images = subprocess.run(
        ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"],
        capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    for image in (value for value in images if value.startswith("cinder-keplerops/")):
        metadata = subprocess.run(
            ["docker", "image", "inspect", image], capture_output=True, check=True
        ).stdout
        history = subprocess.run(
            ["docker", "history", "--no-trunc", image], capture_output=True, check=True
        ).stdout
        combined = metadata + history
        for name, value in credentials.items():
            if value.encode() in combined:
                raise AssertionError(f"{name}: credential present in image metadata")
        if b"seed-manifest.json" in combined or b"runtime-credentials.json" in combined:
            raise AssertionError(f"operator credential path present in image metadata: {image}")


def verify_assertion_replay(current: dict[str, str], foreign_path: Path) -> None:
    foreign = json.loads(foreign_path.read_text())
    assertion = foreign.get("assertion") if isinstance(foreign, dict) else None
    if not isinstance(assertion, str) or not assertion:
        raise ValueError("foreign assertion is missing")
    enabled = status(
        "identity.keplerops.test", "/api/registrations/OIDC-FIELDKEST-SUPPORT",
        token=current["staff_preview_service"], method="POST",
        body={"add_provider": "OIDC-FIELDKEST-RETAINED-SUPPORT", "preserve_existing": True},
    )
    if enabled != 200:
        raise AssertionError(f"target retained-support provider enablement returned HTTP {enabled}")
    foreign_status = status(
        "identity.keplerops.test", "/api/federation/login", method="POST",
        body={"assertion": assertion},
    )
    if foreign_status != 403:
        raise AssertionError(f"foreign assertion returned HTTP {foreign_status}")
    issued_status, issued = json_request(
        "support.keplerops.test", "/federation/retained-support/assertions", method="POST",
        body={
            "audience": "fieldkest-support",
            "subject": "urn:fieldkest:pairwise:7c0e4f2a-2e62-4d80-a279-1fdb4f02b6c7",
            "tenant": "TEN-ARWC-047",
        },
    )
    if issued_status != 201 or not isinstance(issued.get("assertion"), str):
        raise AssertionError("target assertion issuer did not issue an assertion")
    local_status = status(
        "identity.keplerops.test", "/api/federation/login", method="POST",
        body={"assertion": issued["assertion"]},
    )
    if local_status != 201:
        raise AssertionError(f"target assertion returned HTTP {local_status}")


def verify_channel_replay(foreign_path: Path) -> None:
    foreign = json.loads(foreign_path.read_text())
    foreign_grants = foreign.get("grants") if isinstance(foreign, dict) else None
    foreign_poll = foreign_grants.get("poll") if isinstance(foreign_grants, dict) else None
    foreign_token = foreign_poll.get("token") if isinstance(foreign_poll, dict) else None
    version = foreign.get("approved_version") if isinstance(foreign, dict) else None
    if not isinstance(foreign_token, str) or not isinstance(version, str):
        raise ValueError("foreign channel credential is invalid")
    current_raw = subprocess.run(
        [
            "docker", "exec", "--user", "fieldkest-registry", "cinder-keplerops-registry",
            "cat", "/var/lib/fieldkest-registry/published/delivery/channel-credential.json",
        ],
        capture_output=True, text=True, check=True,
    ).stdout
    current = json.loads(current_raw)
    current_token = current["grants"]["poll"]["token"]
    if current_token == foreign_token:
        raise AssertionError("channel token did not vary across ranges")
    if current.get("range_binding") == foreign.get("range_binding"):
        raise AssertionError("channel credential range binding did not vary across ranges")
    body = {"tenant": "TEN-ARWC-047", "channel": "arwc-stable", "version": version}
    foreign_status = status(
        "connector.arwc.test", "/api/fieldlink/packages/poll",
        token=foreign_token, method="POST", body=body,
    )
    if foreign_status != 403:
        raise AssertionError(f"foreign channel token returned HTTP {foreign_status}")
    local_status = status(
        "connector.arwc.test", "/api/fieldlink/packages/poll",
        token=current_token, method="POST", body=body,
    )
    if local_status != 200:
        raise AssertionError(f"target channel token returned HTTP {local_status}")


def verify_receipt_replay(current: dict[str, str], foreign_path: Path) -> None:
    foreign = json.loads(foreign_path.read_text())
    job_id = foreign.get("job_id") if isinstance(foreign, dict) else None
    if not isinstance(job_id, str) or not job_id:
        raise ValueError("foreign diagnostic receipt is invalid")
    result = status(
        "connector.arwc.test", f"/api/fieldlink/diagnostics/{job_id}/receipt",
        token=current["support_delivery_token"],
    )
    if result != 404:
        raise AssertionError(f"foreign receipt identifier returned HTTP {result}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("foreign_credentials", type=Path)
    parser.add_argument("--current", type=Path, default=DEFAULT_CURRENT)
    parser.add_argument("--foreign-assertion", type=Path)
    parser.add_argument("--foreign-channel", type=Path)
    parser.add_argument("--foreign-receipt", type=Path)
    args = parser.parse_args()
    current = load(args.current)
    foreign = load(args.foreign_credentials)
    verify_replay(current, foreign)
    verify_mounts()
    verify_logs(current)
    verify_image_metadata(current)
    if args.foreign_assertion:
        verify_assertion_replay(current, args.foreign_assertion)
    if args.foreign_channel:
        verify_channel_replay(args.foreign_channel)
    if args.foreign_receipt:
        verify_receipt_replay(current, args.foreign_receipt)
    print(f"PASS: {len(current)} credential classes vary; cross-range replay denied; logs and participant mounts clean")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
