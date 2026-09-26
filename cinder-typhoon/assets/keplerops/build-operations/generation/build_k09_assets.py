#!/usr/bin/env python3
"""Build deterministic K09 CI and build-record service archives."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import tarfile


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source"
GENERATED_AT = "2026-09-18T15:24:00Z"


def encoded(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode() + b"\n"


def write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def build_sources() -> None:
    revision = "c37effd7cc86ae4d44f18e95f899b7557d65e0a9"
    integration = {
        "schema": "fieldkest.review-input/v3",
        "artifact_id": "ART-BLD-1842-INTEGRATION-REVIEW",
        "run_id": "BLD-1842",
        "object_version": 3,
        "build_revision": revision,
        "collection": "build-results/BLD-1842",
        "linked_support_ref": "buildops://reviews/diagnostic-request-reference@3",
        "classification": "integration-diagnostic",
        "diagnostic_eligible": True,
    }
    ordinary = {
        "schema": "fieldkest.review-input/v3",
        "artifact_id": "ART-BLD-1842-ORDINARY-SUPPORT",
        "run_id": "BLD-1842",
        "object_version": 1,
        "build_revision": revision,
        "collection": "build-results/BLD-1842",
        "linked_support_ref": "support://reviews/ordinary-summary@1",
        "classification": "support-review",
        "diagnostic_eligible": False,
    }
    integration_payload = encoded(integration)
    ordinary_payload = encoded(ordinary)
    run = {
        "schema": "fieldkest.ci-run/v1",
        "run_id": "BLD-1842",
        "repository": "fieldkest/fieldlink-connector",
        "revision": revision,
        "test": "tests/test_crr_og2_report.py",
        "expected_fixture": "fixtures/report-crr-og2.json",
        "fixture_revision": "fk-test-6d1e9f7",
        "state": "failed",
        "summary": "Fixture unavailable at the selected revision.",
        "log_url": "/api/runs/BLD-1842/log",
        "result_page": {"artifacts": ["junit.xml"]},
        "retained_artifacts": [{
            "artifact_id": integration["artifact_id"],
            "name": "integration-review-input-v3.json",
            "object_version": integration["object_version"],
            "build_revision": revision,
            "sha256": hashlib.sha256(integration_payload).hexdigest(),
            "url": "/api/runs/BLD-1842/artifacts/integration-review-input-v3.json",
            "listed_on_results_page": False,
        }],
        "started_at": "2026-09-18T15:17:04Z",
        "finished_at": "2026-09-18T15:17:19Z",
    }
    log = """2026-09-18T15:17:04Z checkout fieldkest/fieldlink-connector@c37effd7cc86ae4d44f18e95f899b7557d65e0a9
2026-09-18T15:17:10Z run tests/test_crr_og2_report.py
2026-09-18T15:17:11Z fixture reference: fixtures/report-crr-og2.json
2026-09-18T15:17:11Z fixture provenance: fk-test-6d1e9f7
2026-09-18T15:17:11Z release dossier: BLD-REL-742
2026-09-18T15:17:11Z recovery build record: BLD-REC-021
2026-09-18T15:17:12Z retained artifact: integration-review-input-v3.json
2026-09-18T15:17:12Z artifact record: ART-BLD-1842-INTEGRATION-REVIEW version 3
2026-09-18T15:17:12Z ERROR fixture not present at current revision
2026-09-18T15:17:19Z result failed
""".encode()
    k09 = {
        "schema": "fieldkest.review-job-config/v1",
        "developer": {"principal": "rowan.ito"},
        "workspace": {"owner": "rowan.ito", "generation": "WS-ROWAN-2026-09-G1"},
        "integration_artifact": integration["artifact_id"],
        "ordinary_artifact": ordinary["artifact_id"],
        "integration_reference": integration["linked_support_ref"],
        "runner_note": "/srv/fieldlink-ci/runner/runner-operations.md",
        "worker_principal": "svc-fieldlink-ci",
        "worker_origin": "10.77.53.0/24",
        "lease_seconds": 180,
        "execution_timeout_seconds": 20,
        "workspace_volume": "cinder-keplerops-ci-rowan-workspace",
    }
    cloud = {
        "schema": "fieldkest.build-record-service/v1",
        "worker_status": {
            "principal": "svc-fieldlink-ci",
            "availability": "available",
            "accepted_audience": "build-records",
            "accepted_origin": "10.77.53.0/24",
        },
        "records": {
            "BLD-REL-742": {"classification": "release-dossier", "status": "retained"},
            "BLD-REC-021": {"classification": "recovery", "status": "retained"},
        },
    }
    write(SOURCE / "k-ci/config/k09.json", encoded(k09))
    write(SOURCE / "k-ci/runs/BLD-1842.json", encoded(run))
    write(SOURCE / "k-ci/runs/BLD-1842.log", log)
    write(SOURCE / "k-ci/artifacts/BLD-1842/integration-review-input-v3.json", integration_payload)
    write(SOURCE / "k-ci/artifacts/BLD-1842/ordinary-support-input-v1.json", ordinary_payload)
    write(SOURCE / "k-cloud-api/config/k09.json", encoded(cloud))


def archive(name: str, source: Path) -> dict[str, object]:
    files = sorted(path for path in source.rglob("*") if path.is_file())
    output = io.BytesIO()
    inventory = []
    with tarfile.open(fileobj=output, mode="w", format=tarfile.USTAR_FORMAT) as bundle:
        for path in files:
            relative = path.relative_to(source).as_posix()
            payload = path.read_bytes()
            mode = 0o600 if relative.startswith("config/") else 0o640
            info = tarfile.TarInfo(relative)
            info.size = len(payload)
            info.mode = mode
            info.uid = info.gid = 0
            info.uname = info.gname = "root"
            info.mtime = 0
            bundle.addfile(info, io.BytesIO(payload))
            inventory.append({
                "path": relative,
                "mode": f"{mode:04o}",
                "size": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            })
    payload = output.getvalue()
    write(ROOT / name, payload)
    return {"archive": name, "size": len(payload), "sha256": hashlib.sha256(payload).hexdigest(), "files": inventory}


def main() -> None:
    build_sources()
    manifest = {
        "schema": "fieldkest.k09-foundation-artifacts/v1",
        "generated_at": GENERATED_AT,
        "archives": [
            archive("k-ci-k09-state.tar", SOURCE / "k-ci"),
            archive("k-cloud-api-k09-state.tar", SOURCE / "k-cloud-api"),
        ],
    }
    write(ROOT / "artifact-manifest.json", encoded(manifest))


if __name__ == "__main__":
    main()
