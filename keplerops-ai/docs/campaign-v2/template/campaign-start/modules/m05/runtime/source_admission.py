from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

import yaml


API = os.getenv("FORGEJO_API_URL", "http://10.61.40.20:3000/api/v1").rstrip("/")
USER = os.getenv("FORGEJO_ADMISSION_USER", "svc-orion-release-admission")
PASSWORD = os.getenv("FORGEJO_ADMISSION_PASSWORD", "")
STATE = pathlib.Path(os.getenv("SOURCE_ADMISSION_STATE", "/state/admission.json"))
POLL_SECONDS = int(os.getenv("SOURCE_ADMISSION_POLL_SECONDS", "5"))
COMMIT_RE = re.compile(r"^[0-9a-f]{40,64}$")

POLICIES: dict[str, tuple[re.Pattern[str], ...]] = {
    "orion-release-tools": (re.compile(r"^tool/release-source\.json$"),),
    "orion-agent-config": (re.compile(r"^agent\.yaml$"),),
    "orion-staging": (
        re.compile(r"^Dockerfile$"),
        re.compile(r"^app\.py$"),
        re.compile(r"^model/[A-Za-z0-9._/-]+$"),
    ),
}


def api(
    method: str,
    path: str,
    body: object | None = None,
    accepted: tuple[int, ...] = (200, 201, 202, 204),
) -> tuple[int, bytes]:
    token = base64.b64encode(f"{USER}:{PASSWORD}".encode()).decode()
    request = urllib.request.Request(
        f"{API}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Authorization": f"Basic {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status, payload = response.status, response.read()
    except urllib.error.HTTPError as exc:
        status, payload = exc.code, exc.read()
    if status not in accepted:
        raise RuntimeError(f"{method} {path} returned {status}: {payload[:300]!r}")
    return status, payload


def json_api(method: str, path: str, body: object | None = None) -> Any:
    _, payload = api(method, path, body)
    return json.loads(payload) if payload else None


def raw(repository: str, path: str, commit: str) -> bytes:
    encoded = "/".join(urllib.parse.quote(part, safe="") for part in path.split("/"))
    _, payload = api(
        "GET",
        f"/repos/keplerops/{repository}/raw/{encoded}?ref={urllib.parse.quote(commit)}",
    )
    return payload


def validate_tool(body: bytes) -> None:
    value = json.loads(body)
    allowed = value.get("allowed_references")
    if (
        value.get("name") != "release-source"
        or value.get("input_schema", {}).get("required") != ["reference"]
        or value.get("input_schema", {}).get("additionalProperties") is not False
        or not isinstance(allowed, list)
        or len(allowed) != len(set(allowed))
        or "ORION-RELEASE-POLICY-2026" not in allowed
        or not set(allowed).issubset({"ORION-RELEASE-POLICY-2026", "ORION-TOOL-AUDIT-2026"})
        or value.get("host_bridge_policy") not in {"required", "unattended"}
    ):
        raise ValueError("release-source change exceeds the reviewed tool contract")


def validate_agent(body: bytes) -> None:
    value = yaml.safe_load(body)
    spec = value.get("spec", {}) if isinstance(value, dict) else {}
    sources = spec.get("knowledgeSources")
    provider = spec.get("provider", {})
    if (
        value.get("kind") != "AgentRuntime"
        or value.get("metadata", {}).get("name") != "orion-release-assistant"
        or spec.get("tools") != ["release-source", "forgejo-ci-status"]
        or not isinstance(sources, list)
        or not set(sources).issubset(
            {"ORION-RELEASE-POLICY-2026", "ORION-CONFIGURATION-REVISION-2026"}
        )
        or provider.get("baseURL")
        not in {"http://litellm.orion-platform.svc:4000", "https://orion-relay.cinder.lab"}
    ):
        raise ValueError("agent change exceeds the reviewed runtime contract")


def validate_staging(files: dict[str, bytes]) -> None:
    required = {"Dockerfile", "app.py", "model/orion-model.pkl"}
    if not required.issubset(files):
        raise ValueError("staging change must carry a callable model and fixed inference source")
    dockerfile = files["Dockerfile"].decode(errors="replace")
    if "USER " not in dockerfile or "COPY model/orion-model.pkl" not in dockerfile:
        raise ValueError("staging image must retain its unprivileged callable-model contract")


def validate(repository: str, commit: str, paths: list[str]) -> str:
    if not COMMIT_RE.fullmatch(commit):
        raise ValueError("immutable pull-request head is required")
    patterns = POLICIES[repository]
    if not paths or any(not any(pattern.fullmatch(path) for pattern in patterns) for path in paths):
        raise ValueError("pull request changes a protected workflow or runtime path")
    files = {path: raw(repository, path, commit) for path in paths}
    if repository == "orion-release-tools":
        validate_tool(files["tool/release-source.json"])
    elif repository == "orion-agent-config":
        validate_agent(files["agent.yaml"])
    else:
        # Admission evaluates the complete release source at the immutable PR
        # head. A contributor may legitimately update only the model, but the
        # accepted image must still be bound to the reviewed Dockerfile and app.
        for required_path in ("Dockerfile", "app.py", "model/orion-model.pkl"):
            files.setdefault(required_path, raw(repository, required_path, commit))
        validate_staging(files)
    digest = hashlib.sha256()
    for path in sorted(files):
        digest.update(path.encode() + b"\0" + files[path])
    return digest.hexdigest()


def review(repository: str, pull: dict[str, Any]) -> None:
    number = int(pull["number"])
    commit = str(pull["head"]["sha"])
    files = json_api("GET", f"/repos/keplerops/{repository}/pulls/{number}/files")
    paths = [str(item["filename"]) for item in files]
    digest = validate(repository, commit, paths)
    body = f"Release admission accepted immutable source {commit}; admitted-content SHA-256 {digest}."
    api(
        "POST",
        f"/repos/keplerops/{repository}/pulls/{number}/reviews",
        {"event": "APPROVE", "body": body, "commit_id": commit},
    )
    api(
        "POST",
        f"/repos/keplerops/{repository}/pulls/{number}/merge",
        {"Do": "merge", "merge_when_checks_succeed": False, "delete_branch_after_merge": False},
    )
    record(
        f"{repository}:{number}",
        {
            "repository": repository,
            "pull_number": number,
            "commit": commit,
            "parent_commit": str(pull["base"]["sha"]),
            "paths": paths,
            "decision": "accepted",
            "at": int(time.time()),
        },
    )


def record(key: str, value: dict[str, object]) -> None:
    current: dict[str, object] = {}
    if STATE.is_file():
        current = json.loads(STATE.read_text(encoding="utf-8"))
    current[key] = value
    STATE.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATE.with_suffix(".tmp")
    temporary.write_text(json.dumps(current, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(STATE)


def processed(key: str, commit: str) -> bool:
    if not STATE.is_file():
        return False
    value = json.loads(STATE.read_text(encoding="utf-8")).get(key, {})
    return value.get("commit") == commit


def run_once() -> None:
    for repository in POLICIES:
        pulls = json_api("GET", f"/repos/keplerops/{repository}/pulls?state=open&limit=50")
        for pull in pulls:
            key = f"{repository}:{pull['number']}"
            commit = str(pull["head"]["sha"])
            if processed(key, commit):
                continue
            try:
                review(repository, pull)
                # review() records the immutable source, parent, and changed paths.
            except Exception as exc:
                message = f"Release admission rejected immutable source {commit}: {exc}"
                try:
                    api(
                        "POST",
                        f"/repos/keplerops/{repository}/issues/{pull['number']}/comments",
                        {"body": message},
                    )
                finally:
                    record(
                        key,
                        {"commit": commit, "decision": "rejected", "reason": str(exc), "at": int(time.time())},
                    )


def reset_attempt(repository: str, commit: str) -> dict[str, object]:
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.is_file() else {}
    matches = [
        value for value in state.values()
        if value.get("decision") == "accepted"
        and value.get("repository") == repository
        and value.get("commit") == commit
    ]
    if len(matches) != 1:
        raise ValueError("source attempt is not uniquely recorded by admission")
    record_value = matches[0]
    paths = list(record_value.get("paths") or [])
    if len(paths) != 1:
        raise ValueError("bounded source reset requires one admitted source path")
    path = str(paths[0])
    current = raw(repository, path, "main")
    admitted = raw(repository, path, commit)
    if not secrets_compare(current, admitted):
        raise ValueError("source moved after this attempt; refusing to overwrite unrelated work")
    parent = raw(repository, path, str(record_value["parent_commit"]))
    encoded = "/".join(urllib.parse.quote(part, safe="") for part in path.split("/"))
    current_metadata = json_api("GET", f"/repos/keplerops/{repository}/contents/{encoded}?ref=main")
    response = json_api(
        "PUT",
        f"/repos/keplerops/{repository}/contents/{encoded}",
        {
            "branch": "main",
            "content": base64.b64encode(parent).decode(),
            "message": f"Restore {path} after aborted release change",
            "sha": current_metadata["sha"],
        },
    )
    reset_commit = str(response.get("commit", {}).get("sha") or "")
    record_value["reset_commit"] = reset_commit
    record_value["reset_at"] = int(time.time())
    record(f"reset:{repository}:{commit}", record_value)
    return {"repository": repository, "attempt_id": commit, "reset_commit": reset_commit}


def secrets_compare(left: bytes, right: bytes) -> bool:
    return hashlib.sha256(left).digest() == hashlib.sha256(right).digest() and left == right


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", nargs="?", default="serve", choices=("serve", "reset-attempt"))
    parser.add_argument("repository", nargs="?")
    parser.add_argument("commit", nargs="?")
    args = parser.parse_args()
    if args.action == "reset-attempt":
        if not args.repository or not args.commit:
            parser.error("reset-attempt requires repository and commit")
        print(json.dumps(reset_attempt(args.repository, args.commit)))
        return
    if not PASSWORD:
        raise SystemExit("FORGEJO_ADMISSION_PASSWORD is required")
    while True:
        try:
            run_once()
        except Exception as exc:
            print(f"source admission cycle failed: {exc}", flush=True)
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
