#!/usr/bin/env python3
"""Reset one rejected M02 attempt and only resources owned by that attempt."""

from __future__ import annotations

import base64
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import httpx


STATE_ROOT = Path(os.getenv("STATE_ROOT", "/state"))
NEXTCLOUD_URL = os.getenv("NEXTCLOUD_URL", "http://10.61.30.23").rstrip("/")
NEXTCLOUD_HOST = os.getenv("NEXTCLOUD_HOST", "files.keplerops.lab")
NEXTCLOUD_USER = os.getenv("NEXTCLOUD_OWNER_USER", "reviewer")
NEXTCLOUD_AUTH = (NEXTCLOUD_USER, os.getenv("NEXTCLOUD_OWNER_PASSWORD", "KeplerV2-Training-Reviewer"))
ROOM = "/Partner Rooms/Cinder Labs"
RELAY_URL = os.getenv("CINDER_RELAY_URL", "http://192.168.78.30:31080").rstrip("/")
RELAY_HOST = os.getenv("CINDER_RELAY_HOST", "relay.cinder.cinder.lab")
FORGEJO_URL = os.getenv("FORGEJO_URL", "http://10.61.40.20:3000").rstrip("/")
FORGEJO_AUTH = (os.getenv("FORGEJO_USER", "range-admin"), os.getenv("FORGEJO_PASSWORD", "KeplerV2-Training-Forgejo-Admin"))

RESULT_FOLDERS = {
    "kep-m02-a": "Release Briefs", "kep-m02-b": "Citation Cards", "kep-m02-c": "Policy Answers",
    "kep-m02-d": "Source Cards", "kep-m02-e": "Model Intake Results", "kep-m02-f": "Model Intake Results",
    "kep-m02-l": "Package Review Results", "kep-m02-m": "Integration Rejections",
}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"non-object attempt record: {path}")
    return value


def attempt_record(operation: str, attempt_id: str) -> tuple[Path, dict[str, Any]]:
    for directory in ("records", "active"):
        path = STATE_ROOT / directory / f"{operation}-{attempt_id}.json"
        if not path.exists():
            continue
        value = load(path)
        observed_id = str(value.get("attempt_id") or value.get("native_attempt_id", ""))
        if observed_id != attempt_id:
            raise ValueError("attempt filename and server-issued identity disagree")
        return path, value
    raise ValueError("the exact server-issued attempt does not exist")


def dav_delete(path: str) -> None:
    allowed = tuple(f"{ROOM}/{folder}/" for folder in {*RESULT_FOLDERS.values(), "Control Results"})
    if not path.startswith(allowed):
        raise ValueError(f"refusing to delete non-worker-owned WebDAV path: {path}")
    url = f"{NEXTCLOUD_URL}/remote.php/dav/files/{quote(NEXTCLOUD_USER)}{quote(path, safe='/')}"
    response = httpx.delete(url, headers={"Host": NEXTCLOUD_HOST}, auth=NEXTCLOUD_AUTH, timeout=30)
    if response.status_code not in (204, 404):
        response.raise_for_status()


def relay_delete(name: str, token: str) -> None:
    response = httpx.delete(f"{RELAY_URL}/api/baskets/{name}", headers={"Host": RELAY_HOST, "Authorization": token}, timeout=30)
    if response.status_code not in (200, 202, 204, 404):
        response.raise_for_status()


def terminate_mcp_session(endpoint: str, session_id: str) -> None:
    parsed = urlparse(endpoint)
    if parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith(".cinder.lab"):
        raise ValueError("refusing to terminate a session outside the Cinder integration boundary")
    response = httpx.delete(endpoint, headers={"Mcp-Session-Id": session_id}, timeout=30)
    if response.status_code not in (200, 202, 204, 404, 405):
        response.raise_for_status()


def delete_catalog(attempt_id: str) -> None:
    path = f"integrations/{attempt_id}.json"
    url = f"{FORGEJO_URL}/api/v1/repos/keplerops/orion-mcp-catalog/contents/{path}"
    existing = httpx.get(url, auth=FORGEJO_AUTH, timeout=30)
    if existing.status_code == 404:
        return
    existing.raise_for_status()
    carrier = existing.json()
    try:
        content = json.loads(base64.b64decode("".join(str(carrier["content"]).split()), validate=True))
    except (KeyError, ValueError, json.JSONDecodeError) as error:
        raise ValueError("catalog record is not readable attempt-owned JSON") from error
    identities = {str(content.get(key, "")) for key in ("request_id", "external_request_id", "native_attempt_id")}
    if attempt_id not in identities:
        raise ValueError("refusing to delete a catalog record not owned by this attempt")
    response = httpx.delete(url, auth=FORGEJO_AUTH, json={"sha": carrier["sha"], "message": "Remove incomplete Orion integration review"}, timeout=30)
    response.raise_for_status()


def unlink_owned_control(path_value: str) -> None:
    path = Path(path_value)
    controls = (STATE_ROOT / "controls").resolve()
    try:
        resolved = path.resolve()
    except OSError:
        return
    if resolved.parent != controls:
        raise ValueError("refusing to remove a control outside the worker-owned control directory")
    resolved.unlink(missing_ok=True)


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: reset_runtime.py <operation-id> <attempt-id>")
    operation, attempt_id = sys.argv[1:]
    if not operation.startswith("kep-m02-") or not attempt_id or "/" in attempt_id:
        raise SystemExit("invalid operation or attempt identity")
    path, value = attempt_record(operation, attempt_id)
    if value.get("status") == "completed":
        raise SystemExit("accepted attempts are immutable and cannot be reset")
    reset = value.get("_reset", {}) if isinstance(value.get("_reset"), dict) else {}
    for basket in reset.get("baskets", []):
        if isinstance(basket, dict) and basket.get("name") and basket.get("token"):
            relay_delete(str(basket["name"]), str(basket["token"]))
    if operation == "kep-m02-k" and value.get("callback_basket") and value.get("callback_read_token"):
        relay_delete(str(value["callback_basket"]), str(value["callback_read_token"]))
    for session in reset.get("sessions", []):
        if isinstance(session, dict) and session.get("endpoint") and session.get("mcp_session_id"):
            terminate_mcp_session(str(session["endpoint"]), str(session["mcp_session_id"]))
    carrier = str(value.get("native_carrier", ""))
    if carrier:
        dav_delete(carrier)
    controls = value.get("negative_controls") or value.get("negative_control") or {}
    if isinstance(controls, dict):
        for control in controls.values() if all(isinstance(item, dict) for item in controls.values()) else (controls,):
            if not isinstance(control, dict):
                continue
            if control.get("record_path"):
                unlink_owned_control(str(control["record_path"]))
            if control.get("native_result_path"):
                dav_delete(str(control["native_result_path"]))
    if operation == "kep-m02-m":
        delete_catalog(attempt_id)
    shutil.rmtree(STATE_ROOT / "model-jobs" / attempt_id, ignore_errors=True)
    for root in (STATE_ROOT / "attempts",):
        for owned in root.glob(f"*/{attempt_id}"):
            shutil.rmtree(owned, ignore_errors=True)
        for owned in root.glob(f"*/{attempt_id}.json"):
            owned.unlink(missing_ok=True)
    for folder in ("repository-queue", "repository-results"):
        (STATE_ROOT / folder / f"{attempt_id}.json").unlink(missing_ok=True)
    (STATE_ROOT / "active" / f"{operation}-{attempt_id}.json").unlink(missing_ok=True)
    path.unlink(missing_ok=True)
    print(json.dumps({"operation": operation, "attempt_id": attempt_id, "status": "reset"}, sort_keys=True))


if __name__ == "__main__":
    main()
