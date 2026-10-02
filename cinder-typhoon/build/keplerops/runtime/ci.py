"""FieldKest CI history, importer and isolated report consumer."""

from __future__ import annotations

import base64
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import socket
import ssl
import tarfile
import threading
import time
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlsplit
import uuid
import zipfile

from http_support import (
    KeplerHandler, append_audit, canonical_bytes, issue_worker_token, serve_tls,
    sha256_bytes, utc_now,
)


STATE = Path("/var/lib/fieldkest-ci")
AUDIT = STATE / "audit"
RESULTS = STATE / "results"
HANDOVER = Path("/var/lib/fieldkest-handover/current.json")
RUNNER_SOCKET = Path("/run/fieldkest-runner/runner.sock")
CONFIG = json.loads((STATE / "config/opening.json").read_text())
TOKEN = "kpl_rowan_7X4mQ9vN2cL6"
USERNAME = "rowan.ito"
LOCK = threading.RLock()
REGISTRY_READER_TOKEN = "fkci_registry_reader_8Hd3Lp6Ws1"
K09_CONFIG = json.loads((STATE / "config/k09.json").read_text())
K29_CONFIG = json.loads((STATE / "config/k29.json").read_text())
WORKSPACE = STATE / "workspaces/rowan"
REFERENCE = Path("/srv/fieldlink-ci/reviews/diagnostic-request-reference.md")
WORKER_SECRET = Path("/tmp/worker-hmac.key").read_bytes()
WORKER_AUDIENCES = ("source", "packages", "staff", "cloud-policy", "build-records", "maintenance")
ACTIVE_REVIEW_JOBS: set[str] = set()


def run_worker(source: str, fixture: dict[str, object]) -> dict[str, object]:
    request = canonical_bytes({"source": source, "fixture": fixture}) + b"\n"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(14)
        client.connect(str(RUNNER_SOCKET))
        client.sendall(request)
        response = b""
        while not response.endswith(b"\n"):
            chunk = client.recv(65536)
            if not chunk or len(response) + len(chunk) > 1_100_000:
                raise RuntimeError("invalid_runner_response")
            response += chunk
    return json.loads(response)


def run_node_consumer(source: str, input_value: dict[str, object]) -> dict[str, object]:
    request = canonical_bytes({"kind": "node-package", "source": source, "input": input_value}) + b"\n"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(14)
        client.connect(str(RUNNER_SOCKET))
        client.sendall(request)
        response = b""
        while not response.endswith(b"\n"):
            chunk = client.recv(65536)
            if not chunk or len(response) + len(chunk) > 1_100_000:
                raise RuntimeError("invalid_runner_response")
            response += chunk
    return json.loads(response)


def runner_request(value: dict[str, object], *, timeout: int = 35) -> dict[str, object]:
    payload = canonical_bytes(value) + b"\n"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(timeout)
        client.connect(str(RUNNER_SOCKET))
        client.sendall(payload)
        response = b""
        while not response.endswith(b"\n"):
            chunk = client.recv(65536)
            if not chunk or len(response) + len(chunk) > 1_100_000:
                raise RuntimeError("invalid_runner_response")
            response += chunk
    return json.loads(response)


def write_json_atomic(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name("." + path.name + ".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")
    temporary.replace(path)


def workspace_parts(raw: str) -> tuple[str, ...]:
    decoded = unquote(raw)
    path = PurePosixPath(decoded)
    if decoded.startswith("/") or not path.parts or len(path.parts) > 16 or ".." in path.parts:
        raise ValueError("invalid_workspace_path")
    if any(not part or len(part.encode()) > 255 for part in path.parts):
        raise ValueError("invalid_workspace_path")
    return path.parts


def workspace_open(parts: tuple[str, ...], flags: int, mode: int = 0o600, *, create_parents: bool = False) -> int:
    directory = os.open(WORKSPACE, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts[:-1]:
            if create_parents:
                try:
                    os.mkdir(part, 0o700, dir_fd=directory)
                except FileExistsError:
                    pass
            next_directory = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = next_directory
        return os.open(parts[-1], flags | os.O_NOFOLLOW, mode, dir_fd=directory)
    finally:
        os.close(directory)


def execute_review_command(run_id: str, lease_id: str, argv: list[str]) -> None:
    tokens = {
        audience: issue_worker_token(
            WORKER_SECRET, audience, run_id, lease_id,
            lifetime_seconds=K09_CONFIG["lease_seconds"],
        )
        for audience in WORKER_AUDIENCES
    }
    try:
        response = runner_request({
            "kind": "command", "run_id": run_id, "lease_id": lease_id,
            "argv": argv, "tokens": tokens,
        })
        if response.get("ok") and isinstance(response.get("result"), dict):
            proof = response["result"]
            state = "success" if proof.get("exit_status") == 0 and not proof.get("timed_out") else "failed"
            result = {"schema": "fieldkest.review-command-result/v1", "state": state, **proof}
        else:
            error = str(response.get("error", "worker_failed"))
            state = "cancelled" if error == "worker_cancelled" else "failed"
            result = {
                "schema": "fieldkest.review-command-result/v1", "run_id": run_id,
                "lease_id": lease_id, "state": state, "error": error,
            }
    except (OSError, RuntimeError, json.JSONDecodeError):
        result = {
            "schema": "fieldkest.review-command-result/v1", "run_id": run_id,
            "lease_id": lease_id, "state": "failed", "error": "worker_unavailable",
        }
    with LOCK:
        write_json_atomic(RESULTS / "review-jobs" / f"{run_id}.json", result)
        ACTIVE_REVIEW_JOBS.discard(run_id)
    append_audit(AUDIT, "review-jobs", {
        "request_id": str(uuid.uuid4()), "principal": USERNAME, "run_id": run_id,
        "lease_id": lease_id, "profile": "runner-command", "state": result["state"],
        "exit_status": result.get("exit_status"), "opened_paths": result.get("opened_paths", []),
        "status": 200,
    })


def fetch_connector_package(version: str) -> bytes:
    url = f"https://packages.keplerops.test/@keplerops%2ffieldlink-connector/-/fieldlink-connector-{version}.tgz"
    request = urllib_request.Request(url, headers={"Authorization": f"Bearer {REGISTRY_READER_TOKEN}"})
    context = ssl.create_default_context(cafile="/tmp/fieldkest-ca.crt")
    with urllib_request.urlopen(request, context=context, timeout=5) as response:
        payload = response.read(1_000_001)
    if len(payload) > 1_000_000:
        raise ValueError("package_too_large")
    return payload


def package_source(archive_bytes: bytes, version: str) -> str:
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(archive_bytes)) as zipped:
            tar_bytes = zipped.read(1_100_000)
        with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:") as archive:
            metadata_file = archive.extractfile("package/package.json")
            source_file = archive.extractfile("package/index.js")
            if metadata_file is None or source_file is None:
                raise ValueError
            metadata = json.loads(metadata_file.read(65_536))
            source = source_file.read(524_289).decode("utf-8")
    except (OSError, EOFError, ValueError, UnicodeDecodeError, json.JSONDecodeError, tarfile.TarError, KeyError):
        raise ValueError("invalid_package")
    if len(source.encode()) > 524_288 or metadata.get("name") != "@keplerops/fieldlink-connector" or metadata.get("version") != version or metadata.get("fieldkest", {}).get("interface") != "fieldkest.connector/v3":
        raise ValueError("package_contract_failed")
    return source


class CIHandler(KeplerHandler):
    def _authorized(self) -> bool:
        return self.basic_or_bearer(USERNAME, TOKEN)

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/api/runs/BLD-REL-742/artifacts/release-dossier.json":
            if self.headers.get("Authorization") != "Bearer release-reader-handle":
                return self.send_json(403, {"error": "release_reader_required"})
            value = json.loads((STATE / "records/release-dossier.json").read_text())
            append_audit(AUDIT, "release-dossier", {"request_id": self.request_id, "principal": "release-reader", "build_id": "BLD-REL-742", "digest": sha256_bytes(canonical_bytes(value)), "status": 200})
            return self.send_json(200, value)
        if not self._authorized():
            self.send_json(401, {"error": "authentication_required"})
            return
        if path == "/api/runs/BLD-1842":
            value = json.loads((STATE / "runs/BLD-1842.json").read_text())
            append_audit(AUDIT, "runs", {"request_id": self.request_id, "principal": USERNAME, "run_id": "BLD-1842", "status": 200})
            self.send_json(200, value)
        elif path == "/api/runs/BLD-1842/log":
            payload = (STATE / "runs/BLD-1842.log").read_bytes()
            append_audit(AUDIT, "runs", {"request_id": self.request_id, "principal": USERNAME, "run_id": "BLD-1842", "object": "log", "status": 200})
            self.send_bytes(200, payload, "text/plain; charset=utf-8")
        elif path.startswith("/api/runs/BLD-1842/artifacts/"):
            self._historical_artifact(path.removeprefix("/api/runs/BLD-1842/artifacts/"))
        elif path.startswith("/api/review-jobs/"):
            self._review_job_result(path.removeprefix("/api/review-jobs/"))
        elif path.startswith("/api/review-workspace/files/"):
            self._workspace_get(path.removeprefix("/api/review-workspace/files/"))
        elif path.startswith("/api/jobs/"):
            job_id = path.removeprefix("/api/jobs/")
            if not job_id.startswith("JOB-") or not (RESULTS / f"{job_id}.json").is_file():
                self.send_json(404, {"error": "job_not_found"})
                return
            self.send_json(200, json.loads((RESULTS / f"{job_id}.json").read_text()))
        else:
            self.send_json(404, {"error": "not_found"})

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if path == "/api/rehearsals/lineage-rollover":
            if self.headers.get("Authorization") != "Bearer release-reader-handle":
                return self.send_json(403, {"error": "release_reader_required"})
            try: request = self.read_json(131_072)
            except (ValueError, OverflowError, UnicodeDecodeError, json.JSONDecodeError): return self.send_json(422, {"error": "invalid_rollover_rehearsal"})
            if request.get("old_key_id") != K29_CONFIG["old_key_id"] or request.get("next_key_id") != K29_CONFIG["next_key_id"] or request.get("cutoff") != K29_CONFIG["cutoff"]:
                return self.send_json(422, {"error": "rollover_binding_denied"})
            if request.get("expired_proof_credential") is not True:
                return self.send_json(422, {"error": "lineage_proof_required"})
            value = {"rehearsal_id": "ROL-" + uuid.uuid4().hex[:10].upper(), "cutoff": K29_CONFIG["cutoff"], "old_key": {"key_id": K29_CONFIG["old_key_id"], "accepted": False}, "next_key": {"key_id": K29_CONFIG["next_key_id"], "accepted": True}, "reference_behavior": "unchanged", "unwrapped_next_seed_base64": base64.b64encode(hashlib.sha256(b"FieldKest release next key 2026").digest()).decode()}
            append_audit(AUDIT, "rollover-rehearsal", {"request_id": self.request_id, "principal": "release-reader", **value, "status": 200}); return self.send_json(200, value)
        if not self._authorized():
            self.send_json(401, {"error": "authentication_required"})
            return
        if path == "/api/reviews/import":
            self._review_import()
        elif path == "/api/jobs":
            self._job_submit()
        elif path == "/api/rehearsals/connector":
            self._connector_rehearsal()
        elif path == "/api/review-jobs":
            self._review_job_submit()
        elif path.startswith("/api/review-jobs/") and path.endswith("/cancel"):
            run_id = path.removeprefix("/api/review-jobs/").removesuffix("/cancel")
            self._review_job_cancel(run_id)
        else:
            self.send_json(404, {"error": "not_found"})

    def do_PUT(self) -> None:
        if not self._authorized():
            self.send_json(401, {"error": "authentication_required"})
            return
        path = urlsplit(self.path).path
        if path.startswith("/api/review-workspace/files/"):
            self._workspace_put(path.removeprefix("/api/review-workspace/files/"))
        else:
            self.send_json(404, {"error": "not_found"})

    def _historical_artifact(self, name: str) -> None:
        if name != "integration-review-input-v3.json":
            self.send_json(404, {"error": "artifact_not_found"})
            return
        path = STATE / "artifacts/BLD-1842" / name
        payload = path.read_bytes()
        append_audit(AUDIT, "artifacts", {
            "request_id": self.request_id, "principal": USERNAME, "run_id": "BLD-1842",
            "artifact": name, "object_version": 3,
            "build_revision": "c37effd7cc86ae4d44f18e95f899b7557d65e0a9",
            "sha256": sha256_bytes(payload), "status": 200,
        })
        self.send_bytes(200, payload, "application/json")

    def _review_job_submit(self) -> None:
        try:
            value = self.read_json(131_072)
            support_input = value["support_input"]
            diagnostic = value["diagnostic"]
        except (ValueError, KeyError, TypeError, OverflowError, UnicodeDecodeError, json.JSONDecodeError):
            self.send_json(422, {"error": "invalid_review_job"})
            return
        if not isinstance(diagnostic, dict) or not isinstance(diagnostic.get("profile"), str):
            self.send_json(422, {"error": "invalid_diagnostic"})
            return
        profile = diagnostic["profile"]
        if profile == "render-review":
            if not isinstance(support_input, dict):
                self.send_json(422, {"error": "retained_artifact_required"})
                return
            artifacts = {
                "ART-BLD-1842-INTEGRATION-REVIEW": "integration-review-input-v3.json",
                "ART-BLD-1842-ORDINARY-SUPPORT": "ordinary-support-input-v1.json",
            }
            artifact_id = support_input.get("artifact_id")
            filename = artifacts.get(artifact_id)
            if filename is None:
                self.send_json(422, {"error": "artifact_binding_denied"})
                return
            artifact = json.loads((STATE / "artifacts/BLD-1842" / filename).read_text())
            if support_input != artifact:
                self.send_json(422, {"error": "artifact_binding_denied"})
                return
            run_id = "REVJOB-" + uuid.uuid4().hex[:12].upper()
            retained = "SIR-" + uuid.uuid4().hex[:16].upper()
            retained_record = {
                "schema": "fieldkest.retained-support-input/v1",
                "support_input": retained,
                "submitting_account": USERNAME,
                "workspace_generation": K09_CONFIG["workspace"]["generation"],
                "artifact_id": artifact["artifact_id"],
                "object_version": artifact["object_version"],
                "build_revision": artifact["build_revision"],
                "resolved_support_ref": artifact["linked_support_ref"],
                "diagnostic_eligible": artifact["diagnostic_eligible"],
            }
            if artifact["diagnostic_eligible"]:
                review = {
                    "schema": "fieldkest.integration-review/v1",
                    "resolved_support_ref": artifact["linked_support_ref"],
                    "maintained_reference": REFERENCE.read_text(),
                }
            else:
                review = {
                    "schema": "fieldkest.support-review/v1",
                    "resolved_support_ref": artifact["linked_support_ref"],
                    "summary": "Ordinary support review completed.",
                }
            result = {
                "schema": "fieldkest.review-job-result/v1", "run_id": run_id,
                "state": "success", "profile": profile, "support_input": retained,
                "workspace_generation": retained_record["workspace_generation"], "review": review,
            }
            with LOCK:
                write_json_atomic(RESULTS / "retained-inputs" / f"{retained}.json", retained_record)
                write_json_atomic(RESULTS / "review-jobs" / f"{run_id}.json", result)
            append_audit(AUDIT, "review-jobs", {
                "request_id": self.request_id, "principal": USERNAME, "run_id": run_id,
                "profile": profile, "artifact_id": artifact_id,
                "resolved_support_ref": artifact["linked_support_ref"],
                "workspace_generation": retained_record["workspace_generation"], "state": "success", "status": 202,
            })
            self.send_json(202, {"run_id": run_id, "state": "success", "result": f"/api/review-jobs/{run_id}"})
            return
        if profile != "runner-command" or not isinstance(support_input, str):
            self.send_json(422, {"error": "unsupported_diagnostic_profile"})
            return
        retained_path = RESULTS / "retained-inputs" / f"{support_input}.json"
        if not retained_path.is_file():
            self.send_json(403, {"error": "retained_input_denied"})
            return
        retained = json.loads(retained_path.read_text())
        if (retained.get("submitting_account") != USERNAME or
                retained.get("workspace_generation") != K09_CONFIG["workspace"]["generation"] or
                not retained.get("diagnostic_eligible")):
            self.send_json(403, {"error": "build_operations_entitlement_required"})
            return
        argv = diagnostic.get("argv")
        if (not isinstance(argv, list) or not argv or len(argv) > 64 or
                not all(isinstance(item, str) and item and len(item.encode()) <= 16_384 for item in argv)):
            self.send_json(422, {"error": "invalid_command_argv"})
            return
        run_id = "CMDRUN-" + uuid.uuid4().hex[:12].upper()
        lease_id = "LEASE-" + uuid.uuid4().hex[:16].upper()
        queued = {
            "schema": "fieldkest.review-command-result/v1", "run_id": run_id,
            "lease_id": lease_id, "state": "queued", "profile": profile,
            "support_input": support_input, "workspace_generation": retained["workspace_generation"],
            "argv": argv,
        }
        with LOCK:
            if ACTIVE_REVIEW_JOBS:
                self.send_json(409, {"error": "workspace_busy"})
                return
            ACTIVE_REVIEW_JOBS.add(run_id)
            write_json_atomic(RESULTS / "review-jobs" / f"{run_id}.json", queued)
        threading.Thread(target=execute_review_command, args=(run_id, lease_id, argv), daemon=True).start()
        append_audit(AUDIT, "review-jobs", {
            "request_id": self.request_id, "principal": USERNAME, "run_id": run_id,
            "lease_id": lease_id, "profile": profile, "support_input": support_input,
            "workspace_generation": retained["workspace_generation"], "state": "queued", "status": 202,
        })
        self.send_json(202, {"run_id": run_id, "state": "queued", "result": f"/api/review-jobs/{run_id}"})

    def _review_job_result(self, run_id: str) -> None:
        if "/" in run_id or not run_id:
            self.send_json(404, {"error": "review_job_not_found"})
            return
        path = RESULTS / "review-jobs" / f"{run_id}.json"
        if not path.is_file():
            self.send_json(404, {"error": "review_job_not_found"})
            return
        result = json.loads(path.read_text())
        append_audit(AUDIT, "review-job-reads", {
            "request_id": self.request_id, "principal": USERNAME, "run_id": run_id,
            "state": result["state"], "status": 200,
        })
        self.send_json(200, result)

    def _review_job_cancel(self, run_id: str) -> None:
        with LOCK:
            active = run_id in ACTIVE_REVIEW_JOBS
        if not active:
            self.send_json(409, {"error": "review_job_not_active"})
            return
        try:
            response = runner_request({"kind": "command-cancel", "run_id": run_id}, timeout=8)
        except (OSError, RuntimeError, json.JSONDecodeError):
            self.send_json(503, {"error": "worker_unavailable"})
            return
        if not response.get("ok"):
            self.send_json(409, {"error": response.get("error", "cancel_failed")})
            return
        append_audit(AUDIT, "review-jobs", {
            "request_id": self.request_id, "principal": USERNAME, "run_id": run_id,
            "operation": "cancel", "state": "cancelled", "status": 202,
        })
        self.send_json(202, {"run_id": run_id, "state": "cancelled"})

    def _workspace_get(self, raw_path: str) -> None:
        try:
            parts = workspace_parts(raw_path)
            descriptor = workspace_open(parts, os.O_RDONLY)
            with os.fdopen(descriptor, "rb") as handle:
                payload = handle.read(1_048_577)
            if len(payload) > 1_048_576:
                raise OverflowError
        except (ValueError, FileNotFoundError, NotADirectoryError, OSError, OverflowError):
            self.send_json(404, {"error": "workspace_file_not_found"})
            return
        append_audit(AUDIT, "workspace-files", {
            "request_id": self.request_id, "principal": USERNAME,
            "path": "/".join(parts), "operation": "read", "sha256": sha256_bytes(payload), "status": 200,
        })
        self.send_bytes(200, payload, "application/octet-stream")

    def _workspace_put(self, raw_path: str) -> None:
        try:
            parts = workspace_parts(raw_path)
            payload = self.read_body(1_048_576)
            with LOCK:
                descriptor = workspace_open(
                    parts, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600, create_parents=True
                )
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(payload)
        except (ValueError, NotADirectoryError, OSError, OverflowError):
            self.send_json(422, {"error": "invalid_workspace_file"})
            return
        append_audit(AUDIT, "workspace-files", {
            "request_id": self.request_id, "principal": USERNAME,
            "path": "/".join(parts), "operation": "write", "sha256": sha256_bytes(payload), "status": 201,
        })
        self.send_json(201, {"path": "/".join(parts), "size": len(payload), "sha256": sha256_bytes(payload)})

    def _review_import(self) -> None:
        try:
            request = self.read_json(65_536)
        except (ValueError, OverflowError, UnicodeDecodeError, json.JSONDecodeError):
            self.send_json(422, {"error": "invalid_import"})
            return
        raw_object = request.get("object") if isinstance(request, dict) else None
        if not isinstance(request, dict) or request.get("schema") != "fieldkest.review-import/v1" or request.get("run_id") != "BLD-1842" or not isinstance(raw_object, str) or not raw_object.startswith("inputs/"):
            self.send_json(422, {"error": "input_contract_denied"})
            return
        decoded = unquote(raw_object)
        normalized = posixpath.normpath(decoded)
        candidate = PurePosixPath(normalized)
        if normalized.startswith("/") or ".." in candidate.parts:
            self.send_json(422, {"error": "object_outside_repository"})
            return
        path = STATE / "import-objects" / candidate
        if not path.is_file():
            self.send_json(422, {"error": "object_not_found"})
            return
        value = json.loads(path.read_text())
        append_audit(AUDIT, "imports", {"request_id": self.request_id, "principal": USERNAME, "run_id": "BLD-1842", "raw_object": raw_object, "resolved_object": normalized, "object_sha256": sha256_bytes(path.read_bytes()), "status": 201})
        self.send_json(201, {"schema": "fieldkest.review-import-receipt/v1", "run_id": "BLD-1842", "raw_object": raw_object, "resolved_object": normalized, "object": value, "job_mutated": False})

    def _job_submit(self) -> None:
        try:
            request = self.read_json(700_000)
            encoded = request["input"]["archive_base64"]
            archive_bytes = base64.b64decode(encoded, validate=True)
        except (ValueError, KeyError, TypeError, OverflowError, UnicodeDecodeError, json.JSONDecodeError):
            self.send_json(422, {"error": "invalid_job"})
            return
        if request.get("template") != "report-consumer-v2" or len(archive_bytes) > 524_288:
            self.send_json(422, {"error": "invalid_job"})
            return
        try:
            with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
                names = archive.namelist()
                if set(names) != {"provider.py", "fixture.json"} or any(name.startswith("/") or ".." in PurePosixPath(name).parts for name in names):
                    raise ValueError
                if sum(item.file_size for item in archive.infolist()) > 524_288:
                    raise ValueError
                source = archive.read("provider.py").decode("utf-8")
                fixture_raw = archive.read("fixture.json")
                fixture = json.loads(fixture_raw)
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError, zipfile.BadZipFile, KeyError):
            self.send_json(422, {"error": "invalid_job_archive"})
            return
        contract = CONFIG["report_consumer"]
        if sha256_bytes(fixture_raw) != contract["baseline_sha256"]:
            self.send_json(422, {"error": "fixture_binding_mismatch"})
            return
        try:
            worker = run_worker(source, fixture)
        except (OSError, RuntimeError, json.JSONDecodeError):
            self.send_json(503, {"error": "worker_unavailable"})
            return
        if not worker.get("ok") or not isinstance(worker.get("output"), dict):
            self.send_json(422, {"error": "provider_failed"})
            return
        output = worker["output"]
        immutable = contract["immutable_fields"]
        valid = output.get("schema") == contract["required_schema"] and all(output.get(field) == fixture.get(field) for field in immutable)
        assessment = output.get("assessment")
        valid = valid and isinstance(assessment, dict) and set(assessment) == {"rating", "summary"} and all(isinstance(value, str) and value.strip() for value in assessment.values())
        valid = valid and set(output) == set(fixture) and canonical_bytes(output) != canonical_bytes(fixture)
        if not valid:
            self.send_json(422, {"error": "report_contract_failed"})
            return
        job_id = "JOB-" + uuid.uuid4().hex[:12].upper()
        report_sha = sha256_bytes(canonical_bytes(output))
        result = {
            "schema": "fieldkest.ci-job-result/v1",
            "job_id": job_id,
            "template": "report-consumer-v2",
            "state": "success",
            "completed_at": utc_now(),
            "input_archive_sha256": sha256_bytes(archive_bytes),
            "report_sha256": report_sha,
            "report": output,
        }
        handover = {
            "schema": "fieldkest.support-handover/v1",
            "job_id": job_id,
            "state": "success",
            "report_sha256": report_sha,
            "asset_id": output["asset_id"],
            "connector_revision": output["connector_revision"],
            "report": output,
        }
        with LOCK:
            RESULTS.mkdir(parents=True, exist_ok=True)
            HANDOVER.parent.mkdir(parents=True, exist_ok=True)
            (RESULTS / f".{job_id}.tmp").write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
            (RESULTS / f".{job_id}.tmp").replace(RESULTS / f"{job_id}.json")
            HANDOVER.with_suffix(".tmp").write_text(json.dumps(handover, sort_keys=True, separators=(",", ":")) + "\n")
            HANDOVER.with_suffix(".tmp").replace(HANDOVER)
        append_audit(AUDIT, "jobs", {"request_id": self.request_id, "principal": USERNAME, "job_id": job_id, "template": "report-consumer-v2", "report_sha256": report_sha, "state": "success", "status": 202})
        self.send_json(202, {"job_id": job_id, "state": "success", "result": f"/api/jobs/{job_id}"})

    def _connector_rehearsal(self) -> None:
        try:
            request = self.read_json(131_072)
            version = request["version"]
            consumer = request["consumer"]
            input_value = request["input"]
        except (ValueError, KeyError, TypeError, OverflowError, UnicodeDecodeError, json.JSONDecodeError):
            self.send_json(422, {"error": "invalid_rehearsal"})
            return
        accepted_inputs = {
            "support-rehearsal-v3": {"schema": "fieldkest.connector/v3", "tenant_id": "TEN-SYNTH-REHEARSAL-01", "asset_id": "SYNTH-PUMP-07", "operation": "support_review"},
            "arwc-release-v3": {"schema": "fieldkest.connector/v3", "tenant_id": "TEN-ARWC-047", "asset_id": "CRR-OG2", "operation": "diagnostic_summary"},
            "rillhaven-reference-v2": {"schema": "fieldkest.connector/v2", "tenant_id": "TEN-RILL-022", "asset_id": "RILL-PUMP-442", "operation": "diagnostic_summary"},
        }
        if not isinstance(version, str) or consumer not in accepted_inputs or not isinstance(input_value, dict) or input_value != accepted_inputs[consumer]:
            self.send_json(422, {"error": "rehearsal_contract_failed"})
            return
        try:
            archive = fetch_connector_package(version)
            source = package_source(archive, version)
            worker = run_node_consumer(source, input_value)
        except (OSError, ValueError, RuntimeError, json.JSONDecodeError, HTTPError, URLError):
            self.send_json(422, {"error": "package_resolution_or_execution_failed"})
            return
        output = worker.get("output")
        if not worker.get("ok") or not isinstance(output, dict) or output.get("schema") != "fieldkest.rehearsal-result/v1" or output.get("tenant_id") != input_value["tenant_id"] or output.get("asset_id") != input_value["asset_id"] or not isinstance(output.get("assessment"), str) or output.get("assessment") in {"", "baseline-support-review"}:
            self.send_json(422, {"error": "rehearsal_result_failed"})
            return
        rehearsal_id = "REH-" + uuid.uuid4().hex[:12].upper()
        result = {
            "schema": "fieldkest.connector-rehearsal-result/v1",
            "rehearsal_id": rehearsal_id,
            "state": "success",
            "consumer": consumer,
            "package": "@keplerops/fieldlink-connector",
            "version": version,
            "package_sha256": sha256_bytes(archive),
            "completed_at": utc_now(),
            "input": input_value,
            "output": output,
        }
        with LOCK:
            RESULTS.mkdir(parents=True, exist_ok=True)
            (RESULTS / f"{rehearsal_id}.json").write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
        append_audit(AUDIT, "rehearsals", {"request_id": self.request_id, "principal": USERNAME, "rehearsal_id": rehearsal_id, "consumer": consumer, "package": result["package"], "version": version, "package_sha256": result["package_sha256"], "output_sha256": sha256_bytes(canonical_bytes(output)), "state": "success", "status": 202})
        self.send_json(202, result)


def main() -> None:
    AUDIT.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    serve_tls(CIHandler)


if __name__ == "__main__":
    main()
