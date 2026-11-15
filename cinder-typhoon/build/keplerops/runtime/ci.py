"""FieldLink report review, isolated diagnostics, and connector rehearsal."""

from __future__ import annotations

import base64
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import posixpath
import socket
import threading
import subprocess
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlsplit
import uuid
import zipfile

from http_support import (
    KeplerHandler, append_audit, canonical_bytes, serve_tls,
    sha256_bytes, utc_now,
)
from credentials import credential
from package_delivery import pack_connector, consume_package


STATE = Path("/var/lib/fieldkest-ci")
AUDIT = STATE / "audit"
RESULTS = STATE / "results"
HANDOVER = Path("/var/lib/fieldkest-handover/current.json")
RUNNER_SOCKET = Path("/run/fieldkest-runner/runner.sock")
CONFIG = json.loads((STATE / "config/opening.json").read_text())
TOKEN = credential("developer_token")
USERNAME = "rowan.ito"
LOCK = threading.RLock()
RELEASE_READER_TOKEN = credential("release_reader_token")
K29_CONFIG = json.loads((STATE / "config/release-lineage.json").read_text())


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


class CIHandler(KeplerHandler):
    def _authorized(self) -> bool:
        return self.basic_or_bearer(USERNAME, TOKEN)

    def do_GET(self) -> None:
        if self.send_client_document():
            return
        path = urlsplit(self.path).path
        if not self._authorized():
            self.send_json(401, {"error": "authentication_required"})
            return
        if path.startswith("/api/jobs/"):
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
            if self.headers.get("Authorization") != f"Bearer {RELEASE_READER_TOKEN}":
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
        else:
            self.send_json(404, {"error": "not_found"})


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
            self.send_json(422, {
                "error": "fixture_binding_mismatch",
                "binding": "sha256_file_bytes",
                "message": (
                    "fixture.json must preserve the exact file bytes from the "
                    "baseline path and revision"
                ),
            })
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
            metadata, archive = pack_connector(version)
            worker = consume_package(archive, input_value)
        except (OSError, ValueError, RuntimeError, json.JSONDecodeError, HTTPError, URLError, subprocess.SubprocessError):
            self.send_json(422, {"error": "package_resolution_or_execution_failed"})
            return
        output = worker.get("output")
        if not worker.get("ok") or not isinstance(output, dict) or output.get("schema") != "fieldkest.rehearsal-result/v1" or output.get("tenant_id") != input_value["tenant_id"] or output.get("asset_id") != input_value["asset_id"] or not isinstance(output.get("assessment"), str) or output.get("assessment") in {"", "baseline-support-review"}:
            self.send_json(422, {"error": "rehearsal_result_failed", "details": worker.get("details")})
            return
        rehearsal_id = "REH-" + uuid.uuid4().hex[:12].upper()
        result = {
            "schema": "fieldkest.connector-rehearsal-result/v1",
            "rehearsal_id": rehearsal_id,
            "state": "success",
            "consumer": consumer,
            "package": "@keplerops/fieldlink-connector",
            "version": metadata["version"],
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
