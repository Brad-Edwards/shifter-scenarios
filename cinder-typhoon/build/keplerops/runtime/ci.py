"""FieldLink report review, isolated diagnostics, and connector rehearsal."""

from __future__ import annotations

import base64
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import socket
import threading
import subprocess
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
import uuid
import zipfile

from http_support import (
    KeplerHandler, append_audit, canonical_bytes, serve_tls,
    sha256_bytes, utc_now, issue_worker_token, validate_worker_token,
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
_RUNNER_CONFIG = json.loads((STATE / "config/runner-foundation.json").read_text())
_DIAGNOSTIC_REFERENCE = Path("/srv/fieldlink-ci/diagnostic-request-reference.md")
_RUNNER_NOTE = Path("/srv/fieldlink-ci/runner/runner-operations.md")
_WORKER_HMAC_KEY = Path("/tmp/worker-hmac.key")
_WORKSPACE_ROOT = STATE / "workspaces" / "rowan"
# Base URLs for the worker's service connections
_BUILD_RECORDS_URL = "https://review.keplerops.test"
_SOURCE_URL = "https://source.keplerops.test"
_PACKAGES_URL = "https://packages.keplerops.test"
REVIEW_JOBS = RESULTS / "review-jobs"


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
        # K09.4: build-records routes use worker bearer tokens, not developer auth.
        if path in ("/api/build-records/worker-status", "/api/build-records"):
            self._build_records_handler(path)
            return
        if not self._authorized():
            self.send_json(401, {"error": "authentication_required"})
            return
        if path.startswith("/api/jobs/"):
            job_id = path.removeprefix("/api/jobs/")
            if not job_id.startswith("JOB-") or not (RESULTS / f"{job_id}.json").is_file():
                self.send_json(404, {"error": "job_not_found"})
                return
            self.send_json(200, json.loads((RESULTS / f"{job_id}.json").read_text()))
        elif path.startswith("/api/review-jobs/"):
            # K09.3: retrieve a submitted review job result.
            import re as _re
            run_id = path.removeprefix("/api/review-jobs/")
            job_path = REVIEW_JOBS / f"{run_id}.json"
            if not _re.fullmatch(r"RJ-[0-9A-F]{8}", run_id) or not job_path.is_file():
                self.send_json(404, {"error": "review_job_not_found"})
                return
            self.send_json(200, json.loads(job_path.read_text()))
        elif path.startswith("/api/runs/"):
            # K09.2: CI runner run metadata and retained artifacts.
            # The run metadata lists retained_artifacts that are not on the Jenkins
            # results page; the participant must access this service to find them.
            remainder = path.removeprefix("/api/runs/")
            import re as _re
            if "/" not in remainder:
                run_id = remainder
                run_path = STATE / "runs" / f"{run_id}.json"
                if not _re.fullmatch(r"BLD-\d+", run_id) or not run_path.is_file():
                    self.send_json(404, {"error": "run_not_found"})
                    return
                self.send_json(200, json.loads(run_path.read_text()))
            elif remainder.endswith("/log"):
                run_id = remainder.removesuffix("/log")
                log_path = STATE / "runs" / f"{run_id}.log"
                if not _re.fullmatch(r"BLD-\d+", run_id) or not log_path.is_file():
                    self.send_json(404, {"error": "run_not_found"})
                    return
                log_data = log_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(log_data)))
                self.end_headers()
                self.wfile.write(log_data)
            elif "/artifacts/" in remainder:
                run_id, artifact_name = remainder.split("/artifacts/", 1)
                art_path = STATE / "artifacts" / run_id / artifact_name
                if not _re.fullmatch(r"BLD-\d+", run_id) or "/" in artifact_name or not art_path.is_file():
                    self.send_json(404, {"error": "artifact_not_found"})
                    return
                append_audit(AUDIT, "artifact-reads", {
                    "request_id": self.request_id, "principal": USERNAME,
                    "run_id": run_id, "artifact": artifact_name, "status": 200,
                })
                self.send_json(200, json.loads(art_path.read_text()))
            else:
                self.send_json(404, {"error": "not_found"})
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
        if path == "/api/review-jobs":
            self._review_job_submit()
        elif path == "/api/jobs":
            self._job_submit()
        elif path == "/api/rehearsals/connector":
            self._connector_rehearsal()
        else:
            self.send_json(404, {"error": "not_found"})

    def _build_records_handler(self, path: str) -> None:
        """K09.4: build-records status endpoint authenticated by per-run worker token."""
        if path == "/api/build-records":
            self.send_json(200, {"routes": [{"method": "GET", "path": "/api/build-records/worker-status"}]})
            return
        authorization = self.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            self.send_json(401, {"error": "worker_authentication_required"})
            return
        try:
            secret = _WORKER_HMAC_KEY.read_bytes()
            peer = self.client_address[0]
            claims = validate_worker_token(
                authorization, secret, "fieldkest-build-records", peer,
                origin_network="0.0.0.0/0",
            )
        except (OSError, Exception):
            claims = None
        if not claims:
            self.send_json(403, {"error": "worker_identity_denied"})
            return
        status = {
            "principal": claims.get("principal", "svc-fieldlink-ci"),
            "availability": "available",
            "run_id": claims.get("run_id", ""),
            "request_id": self.request_id,
        }
        append_audit(AUDIT, "build-records", {
            "request_id": self.request_id,
            "principal": status["principal"],
            "run_id": status["run_id"],
            "lease_id": claims.get("lease_id", ""),
            "peer_address": self.client_address[0],
            "status": 200,
        })
        self.send_json(200, status)

    def _review_job_submit(self) -> None:
        """K09.3: submit a support-input review job.

        When the submitted support_input has diagnostic_eligible=true and the
        profile is render-review, the job resolves the linked_support_ref to the
        diagnostic-request-reference document and returns its content in
        review.maintained_reference.  The returned support_input is the
        integration reference, which is used in K09.4 runner-command dispatch.
        """
        try:
            request = self.read_json(131_072)
        except (ValueError, OverflowError, UnicodeDecodeError, json.JSONDecodeError):
            self.send_json(422, {"error": "invalid_review_job"})
            return
        support_input = request.get("support_input")
        diagnostic = request.get("diagnostic", {})
        profile = str(diagnostic.get("profile", ""))
        if support_input is None:
            self.send_json(422, {"error": "support_input_required"})
            return
        REVIEW_JOBS.mkdir(parents=True, exist_ok=True)
        run_id = "RJ-" + uuid.uuid4().hex[:8].upper()
        # For runner-command, the support_input must be the integration reference
        # returned by K09.3 (not an ordinary artifact or unresolved link).
        is_integration_ref = (
            isinstance(support_input, str)
            and support_input == _RUNNER_CONFIG.get("integration_reference")
        )
        eligible_artifact = (
            isinstance(support_input, dict)
            and support_input.get("diagnostic_eligible", False)
            and support_input.get("artifact_id") == _RUNNER_CONFIG.get("integration_artifact")
        )
        if profile == "runner-command":
            if not is_integration_ref:
                self.send_json(403, {"error": "build_operations_entitlement_required"})
                return
            argv = diagnostic.get("argv", [])
            if not argv or not isinstance(argv, list) or not all(isinstance(a, str) for a in argv):
                self.send_json(422, {"error": "invalid_argv"})
                return
            result = self._run_command(run_id, argv)
        elif eligible_artifact:
            # Integration artifact with render-review: resolve linked_support_ref.
            maintained = _DIAGNOSTIC_REFERENCE.read_text() if _DIAGNOSTIC_REFERENCE.is_file() else ""
            result = {
                "run_id": run_id,
                "state": "success",
                "profile": profile,
                "workspace_generation": _RUNNER_CONFIG["workspace"]["generation"],
                "support_input": _RUNNER_CONFIG.get("integration_reference", ""),
                "review": {"maintained_reference": maintained},
            }
        elif isinstance(support_input, str):
            # Unresolved string reference — not permitted as a submission directly.
            self.send_json(403, {"error": "retained_input_denied"})
            return
        else:
            # Ordinary (non-diagnostic) artifact: produce a retained reference.
            retained_ref = support_input.get("linked_support_ref", "")
            result = {
                "run_id": run_id,
                "state": "success",
                "profile": profile,
                "workspace_generation": _RUNNER_CONFIG["workspace"]["generation"],
                "support_input": retained_ref,
                "review": {"maintained_reference": ""},
            }
        artifact_id = support_input.get("artifact_id", "") if isinstance(support_input, dict) else ""
        eligible = eligible_artifact or is_integration_ref
        (REVIEW_JOBS / f"{run_id}.json").write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
        append_audit(AUDIT, "review-jobs", {
            "request_id": self.request_id, "principal": USERNAME,
            "run_id": run_id, "artifact_id": artifact_id,
            "profile": profile, "eligible": eligible, "status": 202,
        })
        self.send_json(202, {"run_id": run_id, "result": f"/api/review-jobs/{run_id}"})

    def _run_command(self, run_id: str, argv: list[str]) -> dict:
        """Execute a runner-command subprocess with per-run worker credentials."""
        import os
        import tempfile
        lease_id = uuid.uuid4().hex
        # Issue per-run worker token
        worker_token = ""
        try:
            hmac_secret = _WORKER_HMAC_KEY.read_bytes()
            worker_token = issue_worker_token(
                hmac_secret, "fieldkest-build-records",
                run_id, lease_id, lifetime_seconds=_RUNNER_CONFIG.get("lease_seconds", 180),
            )
        except (OSError, Exception):
            pass
        # Create per-run credential directory
        run_dir = Path(tempfile.mkdtemp(prefix=f"fk-run-{run_id}-"))
        try:
            ci_dir = run_dir / "fieldlink-ci"
            ci_dir.mkdir(mode=0o700)
            ca = Path("/tmp/fieldkest-ca.crt")
            # connections.env
            (ci_dir / "connections.env").write_text(
                f'FIELDLINK_BUILD_RECORDS_URL={_BUILD_RECORDS_URL}\n'
                f'FIELDLINK_SOURCE_URL={_SOURCE_URL}\n'
                f'FIELDLINK_PACKAGES_URL={_PACKAGES_URL}\n'
            )
            # build-records.curl (curl config with worker token; connects to localhost)
            curl_config = (
                f'resolve = "review.keplerops.test:443:127.0.0.1"\n'
                f'cacert = {str(ca)}\n'
                f'insecure\n'
                f'header = "Authorization: Bearer {worker_token}"\n'
            ) if worker_token else (
                f'resolve = "review.keplerops.test:443:127.0.0.1"\n'
                f'cacert = {str(ca)}\n'
                f'insecure\n'
            )
            (ci_dir / "build-records.curl").write_text(curl_config)
            (ci_dir / "build-records.curl").chmod(0o600)
            # Workspace
            workspace = _WORKSPACE_ROOT
            workspace.mkdir(parents=True, exist_ok=True)
            env = os.environ.copy()
            env["HOME"] = str(workspace)
            # Execute command
            proc = subprocess.run(
                argv,
                cwd=str(workspace),
                capture_output=True,
                timeout=_RUNNER_CONFIG.get("execution_timeout_seconds", 20),
                env=env | {"FIELDLINK_RUN_DIR": str(ci_dir)},
                check=False,
            )
            stdout = proc.stdout.decode(errors="replace")
            stderr = proc.stderr.decode(errors="replace")
            state = "success" if proc.returncode == 0 else "failure"
            return {
                "run_id": run_id,
                "state": state,
                "profile": "runner-command",
                "argv": argv,
                "exit_code": proc.returncode,
                "stdout": stdout,
                "stderr": stderr,
                "lease_id": lease_id,
                "workspace_generation": _RUNNER_CONFIG["workspace"]["generation"],
                "opened_paths": argv,
                "saved_files": [],
            }
        except subprocess.TimeoutExpired:
            return {"run_id": run_id, "state": "timeout", "profile": "runner-command", "argv": argv, "exit_code": -1, "stdout": "", "stderr": "execution_timeout", "lease_id": lease_id, "workspace_generation": _RUNNER_CONFIG["workspace"]["generation"]}
        except Exception as exc:
            return {"run_id": run_id, "state": "failure", "profile": "runner-command", "argv": argv, "exit_code": -1, "stdout": "", "stderr": str(exc), "lease_id": lease_id, "workspace_generation": _RUNNER_CONFIG["workspace"]["generation"]}
        finally:
            import shutil
            shutil.rmtree(run_dir, ignore_errors=True)

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
