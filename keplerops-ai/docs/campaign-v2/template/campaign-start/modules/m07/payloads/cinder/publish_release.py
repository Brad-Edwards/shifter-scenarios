#!/usr/bin/env python3
"""Publish exact accepted artifact bytes as an immutable Cinder release."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import requests


OWNER = "cinder-operator"
REPOSITORY = "orion-model-artifacts"


def checked(response: requests.Response) -> requests.Response:
    response.raise_for_status()
    return response


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", required=True, type=Path)
    parser.add_argument("--card", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--locator", required=True, type=Path)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--repository-commit", required=True)
    parser.add_argument("--attempt-state-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if len(args.source_commit) != 40 or any(ch not in "0123456789abcdef" for ch in args.source_commit):
        raise SystemExit("source commit must be a full lowercase digest")
    if not re.fullmatch(r"[0-9a-f]{40}", args.repository_commit):
        raise SystemExit("repository commit must be a full lowercase digest")
    assets = {
        "orion-model.pkl": args.artifact.read_bytes(),
        "MODEL_CARD.md": args.card.read_bytes(),
        "signed-artifact-report.json": args.report.read_bytes(),
        "signed-artifact-locator.json": args.locator.read_bytes(),
    }
    report = json.loads(assets["signed-artifact-report.json"])
    locator = json.loads(assets["signed-artifact-locator.json"])
    report_digest = hashlib.sha256(assets["signed-artifact-report.json"]).hexdigest()
    artifact_digest = hashlib.sha256(assets["orion-model.pkl"]).hexdigest()
    card_digest = hashlib.sha256(assets["MODEL_CARD.md"]).hexdigest()
    attempt_id = str(report.get("attempt_id") or "")
    if (report.get("schema") != "keplerops.cinder.artifact-execution/v2"
            or report.get("source_commit") != args.source_commit
            or report.get("artifact_sha256") != artifact_digest
            or report.get("release_card_sha256") != card_digest
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{7,95}", attempt_id)
            or locator.get("system") != "cinder-minio"
            or locator.get("bucket") != "operations"
            or locator.get("sha256") != f"sha256:{report_digest}"
            or locator.get("key") != f"release-risk/integrity-handoffs/serialized-model/{report_digest}.json"
            or locator.get("object_lock_mode") != "GOVERNANCE"
            or not locator.get("retain_until")):
        raise SystemExit("release assets do not bind one immutable execution handoff")
    attempt_path = args.attempt_state_root / "attempts" / "kep-m07-i" / f"{attempt_id}.json"
    if not attempt_path.is_file():
        raise SystemExit("execution report does not bind a reserved attempt")
    attempt = json.loads(attempt_path.read_text())
    if (attempt.get("operation") != "kep-m07-i" or attempt.get("attempt_id") != attempt_id
            or attempt.get("status") != "running"):
        raise SystemExit("attempt state does not match the execution report")
    succeeded = [
        path for path in attempt_path.parent.glob("*.json")
        if path != attempt_path and json.loads(path.read_text()).get("status") == "succeeded"
    ]
    if succeeded:
        raise SystemExit("an immutable accepted m07-i execution checkpoint already exists")
    api = os.environ["CINDER_FORGEJO_API"].rstrip("/")
    auth = (os.environ["ARTIFACT_RELEASE_USER"], os.environ["ARTIFACT_RELEASE_PASSWORD"])
    attempt_scope = hashlib.sha256(attempt_id.encode()).hexdigest()[:16]
    tag = f"orion-release-risk-artifact-{args.source_commit[:12]}-{attempt_scope}"
    endpoint = f"{api}/repos/{OWNER}/{REPOSITORY}/releases/tags/{tag}"
    response = requests.get(endpoint, auth=auth, timeout=30)
    if response.status_code == 404:
        release = checked(requests.post(
            f"{api}/repos/{OWNER}/{REPOSITORY}/releases",
            auth=auth,
            json={
                "tag_name": tag,
                "target_commitish": args.repository_commit,
                "name": "Accepted Orion release-risk artifact",
                "body": "Protected isolated execution, schema, fidelity, and bounded-effect review.",
                "draft": False,
                "prerelease": False,
            },
            timeout=30,
        )).json()
    else:
        release = checked(response).json()
    if str(release.get("target_commitish") or "") != args.repository_commit:
        raise SystemExit("immutable release tag points at a different verifier commit")
    current = {item["name"]: item for item in release.get("assets", [])}
    if not set(current) <= set(assets):
        raise SystemExit("immutable release contains an unexpected asset")
    for name, body in assets.items():
        if name in current:
            existing = checked(requests.get(
                f"{api}/repos/{OWNER}/{REPOSITORY}/releases/assets/{current[name]['id']}",
                auth=auth, headers={"Accept": "application/octet-stream"}, timeout=60,
            )).content
            if existing != body:
                raise SystemExit(f"immutable release asset differs: {name}")
            continue
        checked(requests.post(
            f"{api}/repos/{OWNER}/{REPOSITORY}/releases/{release['id']}/assets",
            params={"name": name}, auth=auth,
            files={"attachment": (name, body, "application/octet-stream")}, timeout=120,
        ))
    release_locator = {
        "system": "cinder-forgejo",
        "owner": OWNER,
        "repository": REPOSITORY,
        "release_tag": tag,
        "release_id": release["id"],
        "artifact_sha256": report["artifact_sha256"],
        "embedded_model_sha256": report["model_sha256"],
        "report_sha256": report_digest,
        "handoff": locator,
    }
    args.output.write_text(json.dumps(release_locator, sort_keys=True, separators=(",", ":")))
    attempt.update({
        "status": "succeeded",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "resources": [release_locator, locator],
    })
    temporary = attempt_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(attempt, sort_keys=True, separators=(",", ":")))
    temporary.replace(attempt_path)


if __name__ == "__main__":
    main()
