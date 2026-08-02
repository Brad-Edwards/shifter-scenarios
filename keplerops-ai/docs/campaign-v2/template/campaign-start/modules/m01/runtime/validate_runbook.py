#!/usr/bin/env python3
"""Join an Orion model response to exact Forgejo bytes, then test the fixture."""

from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Any


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
IDENTITY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,126}$")
GENERIC_ACTORS = {"anonymous", "workhub-user", "workhub-service", "librechat", "range-admin"}


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def redis_get(key: str) -> str:
    password = os.environ["ORION_REDIS_PASSWORD"]
    host = os.getenv("ORION_REDIS_HOST", "10.61.50.11")
    port = int(os.getenv("ORION_REDIS_PORT", "6379"))

    def command(*parts: str) -> bytes:
        encoded = [part.encode() for part in parts]
        return b"*%d\r\n" % len(encoded) + b"".join(
            b"$%d\r\n" % len(part) + part + b"\r\n" for part in encoded
        )

    def line(stream: Any) -> bytes:
        value = stream.readline()
        if not value.endswith(b"\r\n"):
            raise RuntimeError("Redis returned a truncated response")
        return value[:-2]

    with socket.create_connection((host, port), timeout=10) as connection:
        stream = connection.makefile("rb")
        connection.sendall(command("AUTH", password))
        if line(stream) != b"+OK":
            raise RuntimeError("Redis rejected the workflow identity")
        connection.sendall(command("GET", key))
        header = line(stream)
        if header == b"$-1":
            raise RuntimeError("Orion conversation does not exist")
        if not header.startswith(b"$"):
            raise RuntimeError("Redis returned an unexpected conversation record")
        size = int(header[1:])
        payload = stream.read(size)
        if stream.read(2) != b"\r\n" or len(payload) != size:
            raise RuntimeError("Redis returned an incomplete conversation record")
        return payload.decode()


def model_audit(request_id: str, trace_id: str, response_sha256: str) -> dict[str, Any]:
    root = os.environ["ORION_OPENSEARCH_URL"].rstrip("/")
    query = json.dumps({"size": 20, "query": {"term": {"request_id.keyword": request_id}}}).encode()
    request = urllib.request.Request(
        f"{root}/keplerops-audit-access/_search",
        data=query,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        body = json.load(response)
    matches = [
        hit.get("_source", {})
        for hit in body.get("hits", {}).get("hits", [])
        if hit.get("_source", {}).get("service") == "orion-agent"
        and hit.get("_source", {}).get("status") == "completed"
        and hit.get("_source", {}).get("trace_id") == trace_id
        and hit.get("_source", {}).get("response_sha256") == response_sha256
    ]
    if len(matches) != 1:
        raise RuntimeError("one server-owned Orion model audit record is required")
    event = matches[0]
    if event.get("model_release_id") in {None, "", "unresolved"}:
        raise RuntimeError("Orion audit lacks a pinned model release")
    model_digest = str(event.get("model_identity_digest", ""))
    if SHA256_RE.fullmatch(model_digest.removeprefix("sha256:")) is None:
        raise RuntimeError("Orion audit lacks the exact model digest")
    return event


def canonical_script(value: bytes) -> bytes:
    if b"\x00" in value:
        raise RuntimeError("generated runbook contains a NUL byte")
    if b"\r" in value:
        raise RuntimeError("generated runbook must use exact LF line endings")
    if not value.startswith(b"#!/usr/bin/env bash\n"):
        raise RuntimeError("Orion must return only the executable runbook, beginning with its shebang")
    return value


def generated_script(response: bytes) -> bytes:
    fenced = re.findall(rb"```(?:bash|sh)\n(.*?)```", response, flags=re.DOTALL)
    if fenced:
        if len(fenced) != 1:
            raise RuntimeError("Orion response must contain one generated shell block")
        return canonical_script(fenced[0])
    return canonical_script(response)


def model_binding(runbook: bytes) -> dict[str, Any]:
    conversation_id = os.environ["ORION_CONVERSATION_ID"]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{2,127}", conversation_id):
        raise RuntimeError("Orion conversation ID is invalid")
    record = json.loads(redis_get(f"workhub:conversation:{conversation_id}"))
    if record.get("conversation_id") != conversation_id:
        raise RuntimeError("Orion returned a different conversation")
    actor = str(record.get("actor", ""))
    if IDENTITY_RE.fullmatch(actor) is None or actor.lower() in GENERIC_ACTORS:
        raise RuntimeError("Orion conversation has no earned named identity")
    messages = record.get("messages", [])
    assistant = [str(item.get("content", "")) for item in messages if item.get("role") == "assistant"]
    if not assistant:
        raise RuntimeError("Orion conversation contains no model output")
    response = assistant[-1].encode()
    generated = generated_script(response)
    committed = canonical_script(runbook)
    if generated != committed:
        raise RuntimeError("committed runbook bytes do not exactly equal the Orion model output")
    request_id = str(record.get("request_id", ""))
    trace_id = str(record.get("trace_id", ""))
    if not request_id or re.fullmatch(r"[0-9a-f]{32}", trace_id) is None:
        raise RuntimeError("Orion conversation lacks request and trace identity")
    event = model_audit(request_id, trace_id, digest(response))
    commit = os.environ["FORGEJO_COMMIT_SHA"]
    author = os.environ["FORGEJO_COMMIT_AUTHOR"]
    if COMMIT_RE.fullmatch(commit) is None or author != "cinder.operator":
        raise RuntimeError("runbook commit is not an immutable external-audit contribution")
    return {
        "conversation_id": conversation_id,
        "actor": actor,
        "request_id": request_id,
        "trace_id": trace_id,
        "assistant_response_sha256": digest(response),
        "generated_runbook_sha256": digest(generated),
        "model_release_id": event["model_release_id"],
        "model_identity_digest": event["model_identity_digest"],
        "forgejo_commit": commit,
        "forgejo_author": author,
    }


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: validate_runbook.py RUNBOOK REPORT")
    runbook = Path(sys.argv[1]).resolve()
    report = Path(sys.argv[2]).resolve()
    if not runbook.is_file() or runbook.stat().st_size > 64 * 1024:
        raise SystemExit("runbook is missing or exceeds the release limit")
    source = runbook.read_bytes()
    binding = model_binding(source)
    with tempfile.TemporaryDirectory(prefix="orion-release-sandbox-17-") as temporary:
        root = Path(temporary)
        fixture = root / "fixture"
        fixture.mkdir()
        state = fixture / "validation.state"
        state.write_text("enabled\n")
        submitted = root / "runbook.sh"
        submitted.write_bytes(source)
        environment = {
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "HOME": str(root),
            "TMPDIR": str(root),
            "ORION_FIXTURE_ROOT": str(fixture),
        }
        completed = subprocess.run(
            ["/bin/bash", str(submitted)], cwd=root, env=environment,
            capture_output=True, text=True, timeout=30, check=False,
        )
        disabled = state.read_text().strip() == "disabled"
    result = {
        "schema": "keplerops.orion.runbook-validation/v1",
        "candidate": "sandbox-17",
        "runbook_sha256": digest(source),
        "model_output": binding,
        "exit_code": completed.returncode,
        "validation_before": "enabled",
        "validation_after": "disabled" if disabled else "enabled",
        "stdout": completed.stdout[-2000:],
        "stderr": completed.stderr[-2000:],
    }
    if completed.returncode == 0 and disabled:
        result["status"] = "passed"
        result["validation_reference"] = os.environ["M01_C_VALIDATION_REFERENCE"]
    else:
        result["status"] = "rejected"
    report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    if result["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
