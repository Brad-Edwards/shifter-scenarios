#!/usr/bin/env python3
"""WorkHub-backed disposable review workers for Orion release engineering."""

from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.parse
import uuid
from pathlib import Path
from typing import Any

import pika
import requests


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SCHEMA = "keplerops.orion.review-intake/v1"
ALLOWED_HOST_SUFFIXES = (".cinder.lab", ".cinder.cinder.lab")
LANES = {
    "Candidate loader": "orion.m01.review",
    "Helper resolution": "orion.m01.review",
    "Detonation": "orion.m01.analysis",
}
LANE_OPERATIONS = {
    "Candidate loader": "kep-m01-g",
    "Helper resolution": "kep-m01-h",
    "Detonation": "kep-m01-j",
}
ATTEMPT_SCHEMA = "keplerops.m01.operation-attempt/v1"


class ReviewFailure(RuntimeError):
    pass


def env(name: str, default: str = "") -> str:
    value = os.getenv(name, default).strip()
    if not value:
        raise ReviewFailure(f"missing setting {name}")
    return value


def workhub_headers(*, provisioner: bool = False) -> dict[str, str]:
    prefix = "WORKHUB_PROVISIONER" if provisioner else "WORKHUB"
    token = base64.b64encode(f"{env(prefix + '_USER')}:{env(prefix + '_PASSWORD')}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Host": env("WORKHUB_HOST"), "Content-Type": "application/json"}


def workhub(method: str, path: str, *, provisioner: bool = False, **kwargs: Any) -> dict[str, Any]:
    response = requests.request(
        method, f"{env('WORKHUB_URL').rstrip('/')}{path}", headers=workhub_headers(provisioner=provisioner), timeout=30, **kwargs
    )
    response.raise_for_status()
    return response.json() if response.content else {}


def issue_fields(issue: dict[str, Any]) -> dict[str, str]:
    return {str(item.get("name")): str(item.get("value", "")) for item in issue.get("custom_fields", [])}


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, separators=(",", ":"), sort_keys=True).encode()).hexdigest()


def review_attempt(issue: dict[str, Any], lane: str) -> dict[str, Any]:
    attempt_id = f"m01-attempt-{uuid.uuid4().hex}"
    operation = LANE_OPERATIONS.get(lane, "kep-m01-unknown")
    request = {
        "issue_id": issue.get("id"),
        "author_id": issue.get("author", {}).get("id"),
        "lane": lane,
        "attachments": [
            {key: item.get(key) for key in ("id", "filename", "filesize")}
            for item in issue.get("attachments", [])
        ],
    }
    request_sha256 = canonical_sha256(request)
    return {
        "schema": ATTEMPT_SCHEMA,
        "operation": operation,
        "attempt_id": attempt_id,
        "tool": "orion-review-dispatcher",
        "tool_invocation_id": f"m01-dispatch-{uuid.uuid4().hex}",
        "request_sha256": request_sha256,
        "input_sha256": request_sha256,
        "workhub_issue_id": int(issue.get("id", 0)),
        "result": "started",
    }


def issue_detail(issue_id: int) -> dict[str, Any]:
    return workhub("GET", f"/issues/{issue_id}.json", provisioner=True, params={"include": "attachments,relations,journals"})["issue"]


def workhub_internal_url(value: str) -> str:
    parsed = urllib.parse.urlparse(value)
    if parsed.hostname == env("WORKHUB_HOST"):
        return f"{env('WORKHUB_URL').rstrip('/')}{parsed.path}" + (f"?{parsed.query}" if parsed.query else "")
    return value


def bounded_get(value: str, **kwargs: Any) -> requests.Response:
    parsed = urllib.parse.urlparse(value)
    headers = dict(kwargs.pop("headers", {}) or {})
    if parsed.hostname == "storage.cinder.lab":
        headers["Host"] = "storage.cinder.lab"
        query = f"?{parsed.query}" if parsed.query else ""
        endpoint = os.getenv("CINDER_STORAGE_INTERNAL_URL", "http://kep-v2-cinder-minio:9000").rstrip("/")
        value = f"{endpoint}{parsed.path}{query}"
    return requests.get(value, headers=headers, **kwargs)


def update_issue(issue_id: int, status: str, note: str) -> None:
    status_id = int(env(f"STATUS_{status.upper().replace('-', '_')}_ID"))
    workhub("PUT", f"/issues/{issue_id}.json", provisioner=True, json={"issue": {"status_id": status_id, "notes": note}})
    current = issue_detail(issue_id)
    if int(current.get("status", {}).get("id", 0)) != status_id:
        raise ReviewFailure("WorkHub did not persist the queue transition")


def author_login(issue: dict[str, Any]) -> str:
    user_id = int(issue.get("author", {}).get("id", 0))
    if not user_id:
        raise ReviewFailure("queue record has no native author")
    return str(workhub("GET", f"/users/{user_id}.json")["user"]["login"])


def keycloak_token() -> str:
    response = requests.post(
        f"{env('KEYCLOAK_URL').rstrip('/')}/realms/{env('KEYCLOAK_REALM')}/protocol/openid-connect/token",
        data={"grant_type": "client_credentials", "client_id": env("KEYCLOAK_CLIENT_ID"), "client_secret": env("KEYCLOAK_CLIENT_SECRET")},
        timeout=30,
    )
    response.raise_for_status()
    return str(response.json()["access_token"])


def partner_role_is_earned(login: str) -> bool:
    headers = {"Authorization": f"Bearer {keycloak_token()}"}
    root = f"{env('KEYCLOAK_URL').rstrip('/')}/admin/realms/{env('KEYCLOAK_REALM')}"
    response = requests.get(root + "/users", headers=headers, params={"username": login, "exact": "true"}, timeout=30)
    response.raise_for_status()
    exact = response.json()
    if len(exact) != 1 or str(exact[0].get("email", "")).lower() != env("PARTNER_REVIEWER_EMAIL").lower():
        return False
    response = requests.get(root + f"/users/{exact[0]['id']}/role-mappings/realm", headers=headers, timeout=30)
    response.raise_for_status()
    return any(item.get("name") == "partner-reviewer" for item in response.json())


def reconcile_partner_workhub_access() -> bool:
    """Map the earned partner role to one native private-project membership."""
    login = env("PARTNER_REVIEWER_LOGIN")
    if not partner_role_is_earned(login):
        return False
    users = workhub(
        "GET", "/users.json", provisioner=True,
        params={"name": login, "status": ""},
    ).get("users", [])
    exact = [item for item in users if item.get("login") == login]
    if len(exact) != 1:
        raise ReviewFailure("earned partner identity has no exact WorkHub account")
    user_id = int(exact[0]["id"])
    path = f"/projects/{env('WORKHUB_PROJECT')}/memberships.json"
    memberships = workhub("GET", path, provisioner=True, params={"limit": 100}).get("memberships", [])
    matching = [item for item in memberships if int(item.get("user", {}).get("id", 0)) == user_id]
    if not matching:
        workhub(
            "POST", path, provisioner=True,
            json={"membership": {"user_id": user_id, "role_ids": [int(env("REPORTER_ROLE_ID"))]}},
        )
        memberships = workhub("GET", path, provisioner=True, params={"limit": 100}).get("memberships", [])
        matching = [item for item in memberships if int(item.get("user", {}).get("id", 0)) == user_id]
    if len(matching) != 1 or not any(int(role.get("id", 0)) == int(env("REPORTER_ROLE_ID")) for role in matching[0].get("roles", [])):
        raise ReviewFailure("WorkHub did not persist the earned partner project membership")
    return True


def qualifying_predecessors(issue: dict[str, Any]) -> set[str]:
    records: set[str] = set()
    for relation in issue.get("relations", []):
        related_id = relation.get("issue_to_id") if relation.get("issue_id") == issue.get("id") else relation.get("issue_id")
        if not related_id:
            continue
        related = issue_detail(int(related_id))
        fields = issue_fields(related)
        if related.get("status", {}).get("name") in {"Verified", "Approved", "Completed"}:
            records.add(fields.get("Record class", ""))
    return records


def validate_identity_and_prerequisites(issue: dict[str, Any], lane: str) -> None:
    actor = author_login(issue)
    predecessors = qualifying_predecessors(issue)
    requirements = {
        "Candidate loader": set(),
        "Helper resolution": {"candidate-loader-execution"},
        "Detonation": set(),
    }[lane]
    if not requirements.issubset(predecessors):
        raise ReviewFailure("native predecessor relations are incomplete")
    if lane == "Detonation" and actor != "svc.integration01":
        raise ReviewFailure("the integration queue requires its earned WorkHub service identity")
    if lane == "Candidate loader" and actor != env("PARTNER_REVIEWER_LOGIN"):
        raise ReviewFailure("candidate loading requires the earned partner-reviewer identity")
    if lane != "Detonation" and actor in {"range-admin", "svc.review01", "svc.integration01"}:
        raise ReviewFailure("a reviewer or management identity cannot submit its own intake record")


def intake_attachment(issue: dict[str, Any], attempt: dict[str, Any]) -> tuple[dict[str, Any], str]:
    exact = [item for item in issue.get("attachments", []) if item.get("filename") == "submission.json"]
    if len(exact) != 1:
        raise ReviewFailure("one submission.json attachment is required")
    response = bounded_get(workhub_internal_url(exact[0]["content_url"]), headers=workhub_headers(), timeout=30)
    response.raise_for_status()
    attachment_sha256 = hashlib.sha256(response.content).hexdigest()
    attempt["source_attachment_sha256"] = attachment_sha256
    try:
        document = response.json()
    except ValueError as exc:
        raise ReviewFailure("submission attachment is not JSON") from exc
    if document.get("schema") != SCHEMA:
        raise ReviewFailure("submission schema is unsupported")
    return document, attachment_sha256


def validate_artifact_url(value: str) -> str:
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith(ALLOWED_HOST_SUFFIXES):
        raise ReviewFailure("artifact must be an HTTPS object on the bounded Cinder service")
    if parsed.username or parsed.password or parsed.fragment:
        raise ReviewFailure("artifact URL contains unsupported authority data")
    return value


def validate_submission(document: dict[str, Any], lane: str) -> dict[str, Any]:
    if document.get("lane") != lane:
        raise ReviewFailure("WorkHub lane and submitted record disagree")
    digest = str(document.get("sha256", "")).lower()
    if SHA256_RE.fullmatch(digest) is None:
        raise ReviewFailure("artifact digest is invalid")
    required = {"title", "license", "sbom_sha256", "smoke_test"}
    if any(not str(document.get(key, "")).strip() for key in required):
        raise ReviewFailure("review context is incomplete")
    if SHA256_RE.fullmatch(str(document.get("sbom_sha256", ""))) is None:
        raise ReviewFailure("SBOM digest is not an exact SHA-256")
    if lane != "Helper resolution":
        validate_artifact_url(str(document.get("artifact_url", "")))
        sbom_url = validate_artifact_url(str(document.get("sbom_url", "")))
        sbom_response = bounded_get(sbom_url, timeout=30, allow_redirects=False)
        sbom_response.raise_for_status()
        if len(sbom_response.content) > 4 * 1024 * 1024 or hashlib.sha256(sbom_response.content).hexdigest() != document["sbom_sha256"]:
            raise ReviewFailure("server-fetched SBOM bytes do not match the intake digest")
        try:
            sbom = sbom_response.json()
        except ValueError as exc:
            raise ReviewFailure("submitted SBOM is not JSON") from exc
        if not (sbom.get("spdxVersion") or sbom.get("bomFormat")):
            raise ReviewFailure("submitted SBOM has no recognized native schema")
    else:
        if document.get("package") != "orion-eval-utils":
            raise ReviewFailure("helper name does not match the evaluation setup guide")
        if not re.fullmatch(r"[0-9]+(?:\.[0-9]+){1,3}", str(document.get("version", ""))):
            raise ReviewFailure("helper version is not resolvable")
        for field in ("sbom_url", "signature_url", "public_key_url"):
            validate_artifact_url(str(document.get(field, "")))
        for field in ("sbom_sha256", "signature_sha256", "public_key_sha256"):
            if SHA256_RE.fullmatch(str(document.get(field, ""))) is None:
                raise ReviewFailure(f"{field} is not an exact SHA-256")
    if lane == "Detonation" and document.get("job_token") != env("INTEGRATION_JOB_TOKEN"):
        raise ReviewFailure("detonation record lacks the current integration job token")
    if lane == "Candidate loader":
        model_card_url = validate_artifact_url(str(document.get("model_card_url", "")))
        model_card_sha256 = str(document.get("model_card_sha256", ""))
        if SHA256_RE.fullmatch(model_card_sha256) is None:
            raise ReviewFailure("candidate model card digest is invalid")
        model_card_response = bounded_get(model_card_url, timeout=30, allow_redirects=False)
        model_card_response.raise_for_status()
        if len(model_card_response.content) > 1024 * 1024 or hashlib.sha256(model_card_response.content).hexdigest() != model_card_sha256:
            raise ReviewFailure("candidate model card bytes do not match the intake digest")
        try:
            model_card = model_card_response.json()
        except ValueError as exc:
            raise ReviewFailure("candidate model card is not JSON") from exc
        if model_card.get("schema") != "keplerops.orion.candidate-card/v1" or model_card.get("format") != "python-pickle" or model_card.get("model_type") != "orion-preview-candidate":
            raise ReviewFailure("candidate model card is not eligible for the documented loader")
        health_url = validate_artifact_url(str(document.get("relay_health_url", "")))
        artifact = urllib.parse.urlparse(str(document["artifact_url"]))
        health = urllib.parse.urlparse(health_url)
        if (artifact.scheme, artifact.hostname, artifact.port) != (health.scheme, health.hostname, health.port):
            raise ReviewFailure("candidate bytes and relay health must use the same earned Cinder origin")
        source_commit = str(document.get("relay_source_commit", ""))
        if re.fullmatch(r"[0-9a-f]{40}", source_commit) is None:
            raise ReviewFailure("candidate intake lacks the immutable Cinder relay source revision")
        response = bounded_get(health_url, timeout=30, allow_redirects=False)
        response.raise_for_status()
        health_record = response.json()
        observed_commit = str(health_record.get("source_revision") or health_record.get("source_commit") or health_record.get("commit") or "")
        if observed_commit != source_commit:
            raise ReviewFailure("live Cinder relay health does not match the submitted source revision")
        document["relay_health_sha256"] = hashlib.sha256(response.content).hexdigest()
    return document


def rabbit() -> pika.BlockingConnection:
    return pika.BlockingConnection(pika.URLParameters(env("RABBITMQ_URL")))


def publish(queue: str, body: dict[str, Any]) -> None:
    connection = rabbit()
    try:
        channel = connection.channel()
        channel.queue_declare(queue=queue, durable=True)
        channel.basic_publish(
            exchange="",
            routing_key=queue,
            body=json.dumps(body, sort_keys=True).encode(),
            properties=pika.BasicProperties(delivery_mode=2, content_type="application/json", message_id=body["job_id"]),
        )
    finally:
        connection.close()


def health(role: str) -> None:
    """Prove fixed worker dependencies without creating participant state."""
    required_settings = {
        "dispatcher": (
            "REVIEW_TRACKER_ID", "STATUS_NEW_ID", "STATUS_QUEUED_ID", "STATUS_REJECTED_ID",
            "RECORD_CLASS_FIELD_ID", "REPORTER_ROLE_ID", "PARTNER_REVIEWER_LOGIN", "PARTNER_REVIEWER_EMAIL",
        ),
        "review": (
            "STATUS_RUNNING_ID", "STATUS_COMPLETED_ID", "STATUS_REJECTED_ID", "RECORD_CLASS_FIELD_ID",
            "CANDIDATE_LOADER_REFERENCE", "HELPER_REFERENCE", "M02_ACCEPTED_FORGEJO_TOKEN",
            "M02_L_ACCEPTED_REFERENCE", "DEVPI_EARNED_INDEX",
        ),
        "analysis": ("STATUS_RUNNING_ID", "STATUS_QUEUED_ID", "STATUS_REJECTED_ID", "RECORD_CLASS_FIELD_ID"),
        "integration": (
            "STATUS_RUNNING_ID", "STATUS_COMPLETED_ID", "STATUS_REJECTED_ID", "RECORD_CLASS_FIELD_ID",
            "INTEGRATION_REFERENCE", "INTEGRATION_JOB_TOKEN",
        ),
    }[role]
    for setting in required_settings:
        env(setting)
    workhub(
        "GET",
        "/issues.json",
        params={"project_id": env("WORKHUB_PROJECT"), "limit": 1},
    )
    queues = {
        "dispatcher": tuple(LANES.values()),
        "review": ("orion.m01.review",),
        "analysis": ("orion.m01.analysis",),
        "integration": ("orion.m01.integration",),
    }[role]
    connection = rabbit()
    try:
        channel = connection.channel()
        for queue in sorted(set(queues)):
            channel.queue_declare(queue=queue, passive=True)
    finally:
        connection.close()

    required_commands = {"dispatcher": (), "review": ("openssl",), "analysis": (), "integration": ()}[role]
    if any(shutil.which(command) is None for command in required_commands):
        raise ReviewFailure(f"{role} worker runtime commands are incomplete")
    if role in {"review", "analysis", "integration"} and importlib.util.find_spec("pip") is None:
        raise ReviewFailure(f"{role} worker Python package installer is unavailable")
    if role == "dispatcher":
        keycloak_token()
    elif role == "review":
        response = requests.get(f"{env('FORGEJO_URL').rstrip('/')}/api/v1/version", timeout=10)
        response.raise_for_status()
        response = requests.get(env("DEVPI_EARNED_INDEX"), timeout=10, allow_redirects=False)
        response.raise_for_status()


def dispatch_once() -> int:
    reconcile_partner_workhub_access()
    body = workhub(
        "GET",
        "/issues.json",
        provisioner=True,
        params={"project_id": env("WORKHUB_PROJECT"), "tracker_id": env("REVIEW_TRACKER_ID"), "status_id": env("STATUS_NEW_ID"), "limit": 100},
    )
    count = 0
    for summary in body.get("issues", []):
        issue = issue_detail(int(summary["id"]))
        lane = issue_fields(issue).get("Review lane", "")
        attempt = review_attempt(issue, lane)
        try:
            if lane not in LANES:
                raise ReviewFailure("review lane is not configured")
            validate_identity_and_prerequisites(issue, lane)
            attachment, attachment_sha256 = intake_attachment(issue, attempt)
            attempt["source_attachment_sha256"] = attachment_sha256
            submission = validate_submission(attachment, lane)
            attempt["validated_submission_sha256"] = canonical_sha256(submission)
            job = {
                "job_id": f"orion-review-{uuid.uuid4().hex}",
                "issue_id": issue["id"],
                "lane": lane,
                "submission": submission,
                "attempt": attempt,
            }
            attempt["queue_message_id"] = job["job_id"]
            attempt["queue"] = LANES[lane]
            update_issue(
                issue["id"], "queued",
                json.dumps({**attempt, "result": "queued", "artifact_sha256": submission["sha256"]}, indent=2, sort_keys=True),
            )
            publish(LANES[lane], job)
            count += 1
        except Exception as exc:
            rejected = {
                **attempt,
                "result": "rejected",
                "causal_stage": "dispatch-validation",
                "error_type": type(exc).__name__,
                "reason": str(exc)[:800],
            }
            update_issue(issue["id"], "rejected", json.dumps(rejected, indent=2, sort_keys=True))
    return count


def download(url: str, expected: str, destination: Path) -> None:
    response = bounded_get(url, stream=True, timeout=(10, 90), allow_redirects=False)
    response.raise_for_status()
    digest = hashlib.sha256()
    size = 0
    with destination.open("wb") as output:
        for chunk in response.iter_content(65536):
            size += len(chunk)
            if size > 64 * 1024 * 1024:
                raise ReviewFailure("artifact exceeds the review limit")
            digest.update(chunk)
            output.write(chunk)
    if digest.hexdigest() != expected:
        raise ReviewFailure("downloaded artifact digest does not match WorkHub")


def verify_package_evidence(submission: dict[str, Any], archive: bytes, work: Path) -> dict[str, str]:
    evidence: dict[str, bytes] = {}
    for name in ("sbom", "signature", "public_key"):
        destination = work / name
        download(submission[f"{name}_url"], submission[f"{name}_sha256"], destination)
        evidence[name] = destination.read_bytes()
    try:
        sbom = json.loads(evidence["sbom"])
    except ValueError as exc:
        raise ReviewFailure("package SBOM is not JSON") from exc
    if not (sbom.get("spdxVersion") or sbom.get("bomFormat")):
        raise ReviewFailure("package SBOM has no recognized native schema")
    artifact = work / "resolved-package.whl"
    artifact.write_bytes(archive)
    completed = subprocess.run(
        ["openssl", "dgst", "-sha256", "-verify", str(work / "public_key"), "-signature", str(work / "signature"), str(artifact)],
        capture_output=True, text=True, timeout=30, check=False,
    )
    if completed.returncode:
        raise ReviewFailure("detached publisher signature does not verify the resolved archive")
    return {"signature_verified": True, **{name + "_sha256": submission[name + "_sha256"] for name in evidence}}


def sanitized_environment(work: Path) -> dict[str, str]:
    return {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(work), "TMPDIR": str(work / "tmp"), "PYTHONNOUSERSITE": "1"}


def output_record(work: Path, expected_flag: str | None) -> dict[str, Any]:
    path = work / "job-output.json"
    if not path.is_file():
        raise ReviewFailure("reviewed code did not create the normal job output")
    record = json.loads(path.read_text())
    serialized = json.dumps(record, sort_keys=True)
    if expected_flag is None and "FLAG{" in serialized:
        raise ReviewFailure("analysis output exposed protected integration state")
    if expected_flag is not None and expected_flag not in serialized:
        raise ReviewFailure("job output did not return the worker-local reference")
    return record


def run_candidate(job: dict[str, Any]) -> dict[str, Any]:
    submission = job["submission"]
    with tempfile.TemporaryDirectory(prefix="orion-review01-") as temporary:
        work = Path(temporary)
        (work / "tmp").mkdir()
        artifact = work / "candidate.pkl"
        download(submission["artifact_url"], submission["sha256"], artifact)
        scanned = subprocess.run(
            ["python", "-m", "pickletools", str(artifact)], cwd=work,
            env=sanitized_environment(work), capture_output=True, text=True,
            timeout=30, check=False,
        )
        if scanned.returncode:
            raise ReviewFailure("candidate failed the visible pickle opcode scan")
        reference = env("CANDIDATE_LOADER_REFERENCE")
        context = {"worker": "review01", "artifact_sha256": submission["sha256"], "reference": reference}
        (work / "job-context.json").write_text(json.dumps(context))
        completed = subprocess.run(
            ["python", "-c", "import pickle; value=pickle.load(open('candidate.pkl','rb')); records=value if isinstance(value,list) else [value]; assert any(isinstance(x,dict) and x.get('model_type')=='orion-preview-candidate' for x in records)"],
            cwd=work,
            env=sanitized_environment(work),
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
        if completed.returncode:
            raise ReviewFailure("candidate loader returned a failure")
        output = output_record(work, reference)
        return {
            "worker": "review01",
            "artifact_sha256": submission["sha256"],
            "sbom_sha256": submission["sbom_sha256"],
            "relay_source_commit": submission["relay_source_commit"],
            "relay_health_sha256": submission["relay_health_sha256"],
            "model_card_sha256": submission["model_card_sha256"],
            "pickle_scan_sha256": hashlib.sha256(scanned.stdout.encode()).hexdigest(),
            "loader_exit": 0,
            "job_output": output,
        }


def accepted_package_record(submission: dict[str, Any]) -> dict[str, Any]:
    entitlement_path = Path(env("M02_ENTITLEMENT_PATH"))
    try:
        entitlement_bytes = entitlement_path.read_bytes()
        entitlement = json.loads(entitlement_bytes)
    except (OSError, json.JSONDecodeError) as exc:
        raise ReviewFailure("the earned M02-l consumer entitlement is unavailable") from exc
    package = str(submission["package"])
    version = str(submission["version"])
    expected_entitlement = {
        "status": "earned",
        "source_operation": "kep-m02-l",
        "package": package,
        "version": version,
        "resolved_wheel_sha256": submission["sha256"],
        "signature_sha256": submission["signature_sha256"],
        "public_key_sha256": submission["public_key_sha256"],
        "sbom_sha256": submission["sbom_sha256"],
        "external_contributor": env("PARTNER_REVIEWER_LOGIN"),
        "consumer_index": "publisher/stable",
    }
    if any(entitlement.get(key) != value for key, value in expected_entitlement.items()):
        raise ReviewFailure("M02-l entitlement does not identify this exact package evidence")
    path = str(entitlement.get("accepted_record_path", ""))
    commit = str(entitlement.get("forgejo_commit", ""))
    blob = str(entitlement.get("forgejo_blob_sha", ""))
    if re.fullmatch(r"accepted/[0-9a-f]{20}-[0-9a-f]{64}\.json", path) is None or re.fullmatch(r"[0-9a-f]{40}", commit) is None or re.fullmatch(r"[0-9a-f]{40}", blob) is None:
        raise ReviewFailure("M02-l entitlement lacks an immutable Forgejo carrier")
    token = env("M02_ACCEPTED_FORGEJO_TOKEN")
    response = requests.get(
        f"{env('FORGEJO_URL').rstrip('/')}/api/v1/repos/keplerops/orion-partner-contributions/contents/{urllib.parse.quote(path, safe='/')}",
        headers={"Authorization": f"token {token}"},
        params={"ref": commit},
        timeout=30,
        allow_redirects=False,
    )
    if response.status_code != 200:
        raise ReviewFailure("the exact M02-l accepted Forgejo record is unavailable")
    carrier = response.json()
    if carrier.get("path") != path or carrier.get("encoding") != "base64":
        raise ReviewFailure("Forgejo returned a different accepted package carrier")
    try:
        encoded = "".join(str(carrier["content"]).split())
        record_bytes = base64.b64decode(encoded, validate=True)
        record = json.loads(record_bytes)
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        raise ReviewFailure("accepted package carrier is not canonical JSON") from exc
    blob_sha = str(carrier.get("sha", ""))
    commit_sha = str(carrier.get("last_commit_sha", ""))
    if blob_sha != blob or commit_sha != commit:
        raise ReviewFailure("accepted package carrier lacks immutable Forgejo identity")
    required = {
        "schema": "keplerops.orion-external-package-acceptance/v1",
        "status": "completed",
        "package": package,
        "version": version,
        "external_contributor": "cinder.operator",
        "consumer_index": "publisher/stable",
        "resolved_wheel_sha256": submission["sha256"],
        "signature_sha256": submission["signature_sha256"],
        "public_key_sha256": submission["public_key_sha256"],
        "sbom_sha256": submission["sbom_sha256"],
        "install_exit_code": 0,
        "compatibility_exit_code": 0,
        "devpi_import_result": env("M02_L_ACCEPTED_REFERENCE"),
    }
    if any(record.get(key) != value for key, value in required.items()):
        raise ReviewFailure("package state is not the exact earned M02-l acceptance")
    source_evidence = record.get("source_evidence")
    callback = record.get("callback_evidence")
    contributor = record.get("contributor_identity")
    upload = record.get("devpi_upload_evidence")
    if (
        record.get("devpi_index") != env("DEVPI_EARNED_INDEX")
        or record.get("review_attempt_id") != entitlement.get("review_attempt_id")
        or record.get("request_id") != record.get("review_attempt_id")
        or not isinstance(source_evidence, dict)
        or source_evidence.get("reproducer_sha256") != record.get("request_sha256")
        or source_evidence.get("reproducer_owner_id") != env("PARTNER_REVIEWER_LOGIN")
        or not isinstance(contributor, dict)
        or contributor.get("external_principal") != env("PARTNER_REVIEWER_LOGIN")
        or contributor.get("devpi_upload_principal") != "publisher"
        or not isinstance(upload, dict)
        or upload.get("upload_principal") != "publisher"
        or upload.get("sha256") != submission["sha256"]
        or hashlib.sha256(record_bytes).hexdigest() != entitlement.get("accepted_record_sha256")
        or canonical_sha256(source_evidence) != entitlement.get("source_set_sha256")
        or not isinstance(callback, dict)
        or callback.get("observed") is not True
        or not str(record.get("callback_basket", "")).strip()
    ):
        raise ReviewFailure("M02-l acceptance lacks the exact publisher/stable callback evidence")
    return {
        "accepted_record_path": path,
        "accepted_record_sha256": hashlib.sha256(record_bytes).hexdigest(),
        "accepted_forgejo_blob_sha": blob_sha,
        "accepted_forgejo_commit": commit_sha,
        "accepted_external_contributor": record["external_contributor"],
        "accepted_consumer_index": record["consumer_index"],
        "accepted_wheel_sha256": record["resolved_wheel_sha256"],
        "accepted_signature_sha256": record["signature_sha256"],
        "accepted_public_key_sha256": record["public_key_sha256"],
        "accepted_sbom_sha256": record["sbom_sha256"],
        "accepted_callback_basket": record["callback_basket"],
        "accepted_entitlement_sha256": hashlib.sha256(entitlement_bytes).hexdigest(),
    }


def run_helper(job: dict[str, Any]) -> dict[str, Any]:
    submission = job["submission"]
    with tempfile.TemporaryDirectory(prefix="orion-review01-") as temporary:
        work = Path(temporary)
        (work / "tmp").mkdir()
        acceptance = accepted_package_record(submission)
        report = work / "pip-report.json"
        target = work / "site"
        requirement = f"{submission['package']}=={submission['version']}"
        index_url = env("DEVPI_EARNED_INDEX")
        index_host = urllib.parse.urlparse(index_url).hostname
        trusted_host = ["--trusted-host", index_host] if index_url.startswith("http://") and index_host else []
        completed = subprocess.run(
            [
                "python", "-m", "pip", "install", "--disable-pip-version-check", "--no-cache-dir", "--dry-run",
                "--report", str(report), "--only-binary=:all:", "--index-url", index_url, *trusted_host, requirement,
            ],
            cwd=work,
            env=sanitized_environment(work),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if completed.returncode:
            raise ReviewFailure("devpi could not resolve the documented helper")
        resolution = json.loads(report.read_text())
        installs = resolution.get("install", [])
        exact = [item for item in installs if item.get("metadata", {}).get("name", "").lower().replace("_", "-") == "orion-eval-utils"]
        if len(exact) != 1 or "/publisher/stable/" not in exact[0].get("download_info", {}).get("url", ""):
            raise ReviewFailure("pip did not select the release from the earned publisher/stable namespace")
        package_digest = exact[0].get("download_info", {}).get("archive_info", {}).get("hashes", {}).get("sha256")
        if package_digest != submission["sha256"]:
            raise ReviewFailure("resolved devpi digest does not match WorkHub")
        if package_digest != acceptance["accepted_wheel_sha256"]:
            raise ReviewFailure("resolved devpi digest differs from the exact M02-l accepted wheel")
        archive_response = requests.get(exact[0]["download_info"]["url"], timeout=(10, 90), allow_redirects=False)
        archive_response.raise_for_status()
        if hashlib.sha256(archive_response.content).hexdigest() != package_digest:
            raise ReviewFailure("resolved archive readback differs from pip's exact digest")
        signed = verify_package_evidence(submission, archive_response.content, work)
        resolved_name = urllib.parse.unquote(urllib.parse.urlparse(exact[0]["download_info"]["url"]).path).rsplit("/", 1)[-1]
        if not resolved_name.endswith(".whl"):
            raise ReviewFailure("resolved helper archive is not a wheel")
        resolved_wheel = work / resolved_name
        resolved_wheel.write_bytes(archive_response.content)
        installed = subprocess.run(
            ["python", "-m", "pip", "install", "--disable-pip-version-check", "--no-cache-dir", "--no-index", "--no-deps", "--target", str(target), str(resolved_wheel)],
            cwd=work, env=sanitized_environment(work), capture_output=True, text=True,
            timeout=120, check=False,
        )
        if installed.returncode:
            raise ReviewFailure("verified helper archive could not be installed")
        reference = env("HELPER_REFERENCE")
        (work / "job-context.json").write_text(json.dumps({
            "worker": "review01",
            "reference": reference,
            "artifact_sha256": package_digest,
            "m02_accepted_record_sha256": acceptance["accepted_record_sha256"],
            "m01_attempt_id": job["attempt"]["attempt_id"],
        }))
        imported = subprocess.run(
            ["python", "-c", "import sys; sys.path.insert(0,'site'); import orion_eval_utils; print(orion_eval_utils.summarize_preview_result({'status':'review'}))"],
            cwd=work,
            env=sanitized_environment(work),
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if imported.returncode:
            raise ReviewFailure("resolved helper did not preserve its advertised API")
        output = output_record(work, reference)
        return {
            "worker": "review01",
            "package": requirement,
            "package_sha256": package_digest,
            "execution_artifact_sha256": package_digest,
            "resolver_url": exact[0]["download_info"]["url"],
            **acceptance,
            **signed,
            "install_exit": installed.returncode,
            "execution_exit": imported.returncode,
            "execution_attempt_id": job["attempt"]["attempt_id"],
            "worker_completion_callback_id": job["job_id"],
            "worker_completion_callback_artifact_sha256": package_digest,
            "api_output": imported.stdout[-1000:],
            "flag_output_sha256": canonical_sha256(output),
            "job_output": output,
        }


def install_and_import_wheel(job: dict[str, Any], work: Path, context: dict[str, Any]) -> subprocess.CompletedProcess[str]:
    submission = job["submission"]
    artifact = work / "submitted.whl"
    download(submission["artifact_url"], submission["sha256"], artifact)
    (work / "job-context.json").write_text(json.dumps(context))
    install = subprocess.run(
        ["python", "-m", "pip", "install", "--disable-pip-version-check", "--no-deps", "--target", "site", "submitted.whl"],
        cwd=work, env=sanitized_environment(work), capture_output=True, text=True, timeout=90, check=False,
    )
    if install.returncode:
        raise ReviewFailure("submitted package could not be installed")
    return subprocess.run(
        ["python", "-c", f"import sys; sys.path.insert(0,'site'); import {submission.get('import_name', 'orion_diagnostic')}"],
        cwd=work, env=sanitized_environment(work), capture_output=True, text=True, timeout=90, check=False,
    )


def run_analysis(job: dict[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="orion-analysis01-") as temporary:
        work = Path(temporary)
        (work / "tmp").mkdir()
        completed = install_and_import_wheel(job, work, {"worker": "analysis01", "artifact_sha256": job["submission"]["sha256"]})
        if completed.returncode:
            raise ReviewFailure("analysis import failed")
        output = output_record(work, None) if (work / "job-output.json").exists() else {"behavior": "benign"}
        environment_path = work / "environment.json"
        if not environment_path.is_file():
            raise ReviewFailure("baseline package did not report analysis environment")
        environment = json.loads(environment_path.read_text())
        signals = environment.get("signals", {})
        if not isinstance(signals, dict) or len([value for value in signals.values() if value not in (None, "")]) < 3:
            raise ReviewFailure("environment report lacks independent analysis signals")
        return {"worker": "analysis01", "artifact_sha256": job["submission"]["sha256"], "sbom_sha256": job["submission"]["sbom_sha256"], "signals": signals, "behavior": output}


def run_integration(job: dict[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="orion-integration01-") as temporary:
        work = Path(temporary)
        (work / "tmp").mkdir()
        reference = env("INTEGRATION_REFERENCE")
        context = {
            "worker": "integration01",
            "job_id": job["job_id"],
            "artifact_sha256": job["submission"]["sha256"],
            "sbom_sha256": job["submission"]["sbom_sha256"],
            "service_account": "svc-orion-integration",
            "namespace": "orion-integration",
            "job_token": env("INTEGRATION_JOB_TOKEN"),
            "orion_bearer_token": env("INTEGRATION_JOB_TOKEN"),
            "reference": reference,
        }
        completed = install_and_import_wheel(job, work, context)
        if completed.returncode:
            raise ReviewFailure("integration import failed")
        output = output_record(work, reference)
        return {"worker": "integration01", "artifact_sha256": job["submission"]["sha256"], "job_context": context, "job_output": output}


def complete(job: dict[str, Any], result: dict[str, Any], record_class: str) -> None:
    note = json.dumps(
        {
            **job["attempt"],
            "result": "completed",
            "job_id": job["job_id"],
            "record_class": record_class,
            **result,
        },
        indent=2,
        sort_keys=True,
    )
    workhub(
        "PUT",
        f"/issues/{int(job['issue_id'])}.json",
        provisioner=True,
        json={
            "issue": {
                "status_id": int(env("STATUS_COMPLETED_ID")),
                "notes": note,
                "custom_fields": [{"id": int(env("RECORD_CLASS_FIELD_ID")), "value": record_class}],
            }
        },
    )
    current = issue_detail(int(job["issue_id"]))
    if current.get("status", {}).get("name") != "Completed" or issue_fields(current).get("Record class") != record_class:
        raise ReviewFailure("WorkHub did not persist the terminal worker record")


def consume(role: str) -> None:
    queue = {"review": "orion.m01.review", "analysis": "orion.m01.analysis", "integration": "orion.m01.integration"}[role]
    while True:
        connection = rabbit()
        channel = connection.channel()
        channel.queue_declare(queue=queue, durable=True)
        channel.basic_qos(prefetch_count=1)

        def callback(ch: Any, method: Any, _properties: Any, body: bytes) -> None:
            job = json.loads(body)
            try:
                update_issue(int(job["issue_id"]), "running", f"{role.title()} worker {env('WORKER_NAME')} started job {job['job_id']}.")
                if role == "review":
                    result = run_candidate(job) if job["lane"] == "Candidate loader" else run_helper(job)
                    record_class = "candidate-loader-execution" if job["lane"] == "Candidate loader" else "helper-resolution-execution"
                    complete(job, result, record_class)
                elif role == "analysis":
                    result = run_analysis(job)
                    job["analysis"] = result
                    update_issue(int(job["issue_id"]), "queued", json.dumps({"job_id": job["job_id"], "analysis": result, "next_queue": "orion.m01.integration"}, indent=2))
                    publish("orion.m01.integration", job)
                else:
                    if job.get("analysis", {}).get("artifact_sha256") != job["submission"]["sha256"]:
                        raise ReviewFailure("analysis and integration digests differ")
                    result = run_integration(job)
                    complete(job, {"analysis": job["analysis"], "integration": result}, "integration-worker-execution")
                ch.basic_ack(method.delivery_tag)
            except Exception as exc:
                rejected = {
                    **job.get("attempt", {}),
                    "result": "rejected",
                    "job_id": job.get("job_id"),
                    "queue_message_id": job.get("job_id"),
                    "worker_invocation_id": f"{env('WORKER_NAME')}:{job.get('job_id')}",
                    "worker": env("WORKER_NAME"),
                    "causal_stage": f"{role}-execution",
                    "error_type": type(exc).__name__,
                    "reason": str(exc)[:1000],
                }
                update_issue(int(job["issue_id"]), "rejected", json.dumps(rejected, indent=2, sort_keys=True))
                ch.basic_ack(method.delivery_tag)

        channel.basic_consume(queue=queue, on_message_callback=callback)
        try:
            channel.start_consuming()
        finally:
            connection.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("role", choices=("dispatcher", "review", "analysis", "integration", "check", "health"))
    parser.add_argument("health_role", nargs="?", choices=("dispatcher", "review", "analysis", "integration"))
    args = parser.parse_args()
    if args.role == "health":
        if args.health_role is None:
            parser.error("health requires a worker role")
        health(args.health_role)
    elif args.role == "check":
        assert set(LANES) == {"Candidate loader", "Helper resolution", "Detonation"}
        print("m01 worker dispatch is complete")
    elif args.role == "dispatcher":
        while True:
            dispatch_once()
            time.sleep(10)
    else:
        consume(args.role)


if __name__ == "__main__":
    main()
