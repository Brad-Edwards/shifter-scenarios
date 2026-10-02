#!/usr/bin/env python3
"""Alterra's bounded FieldLink package and diagnostic consumer."""

from __future__ import annotations

import base64
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import secrets
import ssl
import subprocess
import tarfile
import tempfile
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
import uuid

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding


FIELDLINK = Path("/var/lib/fieldlink-connector")
CUSTOMER = Path("/var/lib/arwc-connector")
CONSUMER = FIELDLINK / "consumer"
CANDIDATES = CONSUMER / "candidates"
RECEIPTS = FIELDLINK / "receipts"
AUDIT = CUSTOMER / "audit" / "fieldlink-consumer.jsonl"
TOKEN = FIELDLINK / "handover" / "corporate-session"
TRANSITION = FIELDLINK / "handover" / "customer-transition.json"
TOKEN_HASH = CUSTOMER / "auth" / "corporate-session.sha256"
LOCK = threading.RLock()
PACKAGE_PRINCIPAL = "svc-keplerops-registry-delivery"
DIAGNOSTIC_PRINCIPAL = "svc-keplerops-support-delivery"
VERSION = re.compile(r"7\.4\.3-cinder\.[a-z0-9][a-z0-9-]{0,23}")
JOB = re.compile(r"DIAG-ARWC-[A-Z0-9]{8,24}")

NODE_WRAPPER = r"""
const vm = require('node:vm');
let raw = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => raw += chunk);
process.stdin.on('end', () => {
  try {
    const request = JSON.parse(raw);
    const sandbox = {exports: {}};
    vm.createContext(sandbox, {codeGeneration: {strings: false, wasm: false}});
    new vm.Script(request.source, {filename: 'fieldlink/package/index.js'}).runInContext(sandbox, {timeout: 1000});
    const operation = sandbox.exports.diagnostic_summary;
    if (typeof operation !== 'function') throw new Error('diagnostic_summary export required');
    const output = operation(request.input);
    if (!output || Array.isArray(output) || typeof output !== 'object') throw new Error('object output required');
    process.stdout.write(JSON.stringify({ok: true, output}) + '\n');
  } catch (error) {
    process.stdout.write(JSON.stringify({ok: false, error: 'bounded_execution_failed'}) + '\n');
  }
});
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def atomic_json(path: Path, value: object, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(canonical(value) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def append_audit(event: dict[str, object]) -> str:
    correlation = str(uuid.uuid4())
    record = {"audit_id": correlation, "observed_at": now(), **event}
    with LOCK, AUDIT.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return correlation


def execute(source: str, request: dict[str, object]) -> dict[str, object]:
    try:
        completed = subprocess.run(
            [
                "/usr/bin/prlimit", "--cpu=2:2", "--as=1073741824:1073741824",
                "--nofile=32:32", "--nproc=16:16", "--", "/usr/bin/node",
                "--max-old-space-size=64", "--disallow-code-generation-from-strings",
                "-e", NODE_WRAPPER,
            ],
            input=canonical({"source": source, "input": request}),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=4,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise ValueError("bounded_execution_failed") from error
    if completed.returncode or len(completed.stdout) > 131_072:
        raise ValueError("bounded_execution_failed")
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise ValueError("bounded_execution_failed") from error
    if result.get("ok") is not True or not isinstance(result.get("output"), dict):
        raise ValueError("bounded_execution_failed")
    return result["output"]


def unpack_package(payload: bytes, version: str) -> tuple[dict[str, object], str]:
    if len(payload) > 1_000_000:
        raise ValueError("package_too_large")
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(payload)) as zipped:
            tar_bytes = zipped.read(1_100_000)
        with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:") as archive:
            members = {item.name: item for item in archive.getmembers() if item.isfile()}
            if set(members) != {"package/package.json", "package/index.js"}:
                raise ValueError
            metadata_file = archive.extractfile(members["package/package.json"])
            source_file = archive.extractfile(members["package/index.js"])
            if metadata_file is None or source_file is None:
                raise ValueError
            metadata = json.loads(metadata_file.read(65_536))
            source = source_file.read(131_073).decode()
    except (OSError, EOFError, UnicodeDecodeError, ValueError, tarfile.TarError, json.JSONDecodeError) as error:
        raise ValueError("invalid_package") from error
    if len(source.encode()) > 131_072:
        raise ValueError("package_source_too_large")
    if metadata.get("name") != "@keplerops/fieldlink-connector" or metadata.get("version") != version:
        raise ValueError("package_identity_mismatch")
    if metadata.get("fieldkest", {}).get("interface") != "fieldkest.connector/v3":
        raise ValueError("package_interface_mismatch")
    return metadata, source


def earn_corporate(route: str, receipt_id: str, version: str) -> None:
    with LOCK:
        if TOKEN.exists():
            return
        token = secrets.token_hex(32)
        TOKEN.write_text(token + "\n", encoding="ascii")
        os.chown(TOKEN, -1, FIELDLINK.stat().st_gid)
        os.chmod(TOKEN, 0o440)
        TOKEN_HASH.write_text(hashlib.sha256(token.encode()).hexdigest() + "\n", encoding="ascii")
        os.chmod(TOKEN_HASH, 0o400)
        transition = {
            "account": "Alterra Regional Water Company",
            "tenant": "TEN-ARWC-047",
            "active_connector": "FLK-7.4.2",
            "delivery_route": route,
            "delivery_receipt": receipt_id,
            "delivered_version": version,
            "maintenance_case": "MTN-CRR-204",
            "customer_receipt": "RCP-742-047",
            "customer_handover": "https://customer-handover.arwc.test:8443",
            "business_workplace": "https://business-workplace.arwc.test",
            "planning_data": "https://planning-data.arwc.test",
            "retained_archive": "https://retained-archive.arwc.test",
            "corporate_identity": "https://corporate-identity.arwc.test",
            "contractor_portal": "https://contractor-portal.arwc.test",
            "field_gateway": "https://field-gateway.arwc.test",
            "maintenance_review": "https://maintenance-review.arwc.test",
            "session_file": "/var/lib/fieldlink-connector/handover/corporate-session",
            "request_header": "Authorization: Bearer <session>",
        }
        atomic_json(TRANSITION, transition, 0o440)
        os.chown(TRANSITION, -1, FIELDLINK.stat().st_gid)


class Handler(BaseHTTPRequestHandler):
    server_version = "FieldLink-Customer-Consumer/3.2"
    sys_version = ""

    def log_message(self, message: str, *args: object) -> None:
        print(f"{self.client_address[0]} {message % args}", flush=True)

    def send_json(self, status: int, value: object) -> None:
        payload = canonical(value) + b"\n"
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    def body(self) -> tuple[bytes, dict[str, object]]:
        length = self.headers.get("Content-Length", "")
        if not length.isdigit() or int(length) > 1_500_000:
            raise ValueError("invalid_request")
        raw = self.rfile.read(int(length))
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError("invalid_request")
        return raw, value

    def principal(self) -> str | None:
        certificate = self.connection.getpeercert()
        for relative_name in certificate.get("subject", ()):
            for key, value in relative_name:
                if key == "commonName":
                    return value
        return None

    def verify_request(self, raw: bytes, allowed: str) -> bool:
        principal = self.principal()
        if principal != allowed:
            self.send_json(403, {"error": "supplier_identity_denied"})
            return False
        try:
            signature = base64.b64decode(self.headers.get("X-FieldLink-Signature", ""), validate=True)
            certificate = x509.load_der_x509_certificate(self.connection.getpeercert(binary_form=True))
            signed = self.command.encode() + b"\n" + urlsplit(self.path).path.encode() + b"\n" + hashlib.sha256(raw).hexdigest().encode()
            certificate.public_key().verify(signature, signed, padding.PKCS1v15(), hashes.SHA256())
        except (ValueError, InvalidSignature):
            self.send_json(403, {"error": "supplier_signature_denied"})
            return False
        return True

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        try:
            raw, request = self.body()
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            return self.send_json(422, {"error": "invalid_request"})
        package_match = re.fullmatch(r"/api/fieldlink/packages/(7\.4\.3-cinder\.[a-z0-9][a-z0-9-]{0,23})/activate", path)
        if path == "/api/fieldlink/packages/poll":
            if not self.verify_request(raw, PACKAGE_PRINCIPAL):
                return
            return self.poll(request)
        if package_match:
            if not self.verify_request(raw, PACKAGE_PRINCIPAL):
                return
            return self.activate(package_match.group(1), request)
        if path == "/api/fieldlink/rehearsals/rollback":
            if not self.verify_request(raw, PACKAGE_PRINCIPAL):
                return
            return self.rollback(request)
        if path == "/api/fieldlink/diagnostics":
            if not self.verify_request(raw, DIAGNOSTIC_PRINCIPAL):
                return
            return self.diagnostic(request)
        self.send_json(404, {"error": "route_not_found"})

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        package_match = re.fullmatch(r"/api/fieldlink/packages/([^/]+)/receipt", path)
        diagnostic_match = re.fullmatch(r"/api/fieldlink/diagnostics/(DIAG-ARWC-[A-Z0-9]{8,24})/receipt", path)
        allowed = PACKAGE_PRINCIPAL if package_match else DIAGNOSTIC_PRINCIPAL if diagnostic_match else ""
        if not allowed or not self.verify_request(b"", allowed):
            if not allowed:
                self.send_json(404, {"error": "route_not_found"})
            return
        key = package_match.group(1) if package_match else diagnostic_match.group(1)
        receipt = RECEIPTS / f"{key}.json"
        if not receipt.is_file():
            return self.send_json(404, {"error": "receipt_not_found"})
        self.send_json(200, json.loads(receipt.read_text()))

    def poll(self, request: dict[str, object]) -> None:
        if request.get("tenant") != "TEN-ARWC-047" or request.get("channel") != "arwc-stable":
            return self.send_json(409, {"error": "customer_channel_denied"})
        record = request.get("record")
        encoded = request.get("tarball_base64")
        if not isinstance(record, dict) or not isinstance(encoded, str):
            return self.send_json(422, {"error": "package_candidate_required"})
        version = record.get("version")
        try:
            archive = base64.b64decode(encoded, validate=True)
        except ValueError:
            return self.send_json(422, {"error": "package_encoding_invalid"})
        approval = record.get("approval", {})
        if (not isinstance(version, str) or not VERSION.fullmatch(version)
                or record.get("name") != "@keplerops/fieldlink-connector"
                or record.get("channel") != "arwc-stable"
                or hashlib.sha256(archive).hexdigest() != record.get("sha256")
                or not isinstance(approval, dict) or approval.get("approved") is not True
                or approval.get("signed") is not True
                or "fieldkest.connector/v3" not in approval.get("interfaces", [])):
            return self.send_json(422, {"error": "package_candidate_denied"})
        try:
            metadata, source = unpack_package(archive, version)
        except ValueError as error:
            return self.send_json(422, {"error": str(error)})
        candidate = {
            "schema": "fieldlink.customer-candidate/v1",
            "tenant": "TEN-ARWC-047",
            "channel": "arwc-stable",
            "version": version,
            "sha256": record["sha256"],
            "key_id": approval.get("key_id"),
            "metadata": metadata,
            "source": source,
            "polled_at": now(),
        }
        path = CANDIDATES / f"{version}.json"
        with LOCK:
            if path.exists() and json.loads(path.read_text()).get("sha256") != candidate["sha256"]:
                return self.send_json(409, {"error": "immutable_candidate_conflict"})
            atomic_json(path, candidate)
        correlation = append_audit({"action": "package-poll", "principal": PACKAGE_PRINCIPAL, "tenant": candidate["tenant"], "version": version, "sha256": candidate["sha256"]})
        self.send_json(200, {key: candidate[key] for key in ("tenant", "channel", "version", "sha256")} | {"interface": "fieldkest.connector/v3", "audit_id": correlation})

    def activate(self, version: str, request: dict[str, object]) -> None:
        if request != {"tenant": "TEN-ARWC-047", "channel": "arwc-stable"}:
            return self.send_json(422, {"error": "activation_binding_denied"})
        candidate_path = CANDIDATES / f"{version}.json"
        if not candidate_path.is_file():
            return self.send_json(409, {"error": "package_not_polled"})
        candidate = json.loads(candidate_path.read_text())
        invocation = {"schema": "fieldkest.connector/v3", "tenant_id": "TEN-ARWC-047", "asset_id": "CRR-OG2", "operation": "diagnostic_summary"}
        try:
            output = execute(candidate["source"], invocation)
        except ValueError as error:
            return self.send_json(422, {"error": str(error)})
        receipt_id = "ACT-" + uuid.uuid4().hex[:12].upper()
        receipt = {
            "schema": "fieldlink.customer-activation/v1", "receipt_id": receipt_id,
            "tenant": "TEN-ARWC-047", "account": "Alterra Regional Water Company",
            "maintenance_case": "MTN-CRR-204", "version": version,
            "package_sha256": candidate["sha256"], "interface": "fieldkest.connector/v3",
            "operation": "diagnostic_summary", "runtime_identity": "svc-arwc-fieldlink",
            "output": output, "state": "complete", "completed_at": now(),
        }
        correlation = append_audit({"action": "package-activation", "principal": PACKAGE_PRINCIPAL, **receipt})
        receipt["audit_id"] = correlation
        atomic_json(RECEIPTS / f"{version}.json", receipt)
        earn_corporate("package-activation", receipt_id, version)
        self.send_json(201, receipt)

    def rollback(self, request: dict[str, object]) -> None:
        if request != {"tenant": "TEN-ARWC-047", "version": "7.4.2", "slot": "future-state"}:
            return self.send_json(422, {"error": "rollback_binding_denied"})
        output = {"schema": "fieldkest.rehearsal-result/v1", "tenant_id": "TEN-ARWC-047", "asset_id": "CRR-OG2", "assessment": "baseline-retained"}
        receipt_id = "RBK-" + uuid.uuid4().hex[:12].upper()
        receipt = {"receipt_id": receipt_id, "tenant": "TEN-ARWC-047", "selected_version": "7.4.2", "slot": "future-state", "current_activation": "unchanged", "operation": "diagnostic_summary", "output": output, "state": "complete", "completed_at": now()}
        receipt["audit_id"] = append_audit({"action": "rollback-rehearsal", "principal": PACKAGE_PRINCIPAL, **receipt})
        atomic_json(RECEIPTS / f"rollback-{receipt_id}.json", receipt)
        self.send_json(201, receipt)

    def diagnostic(self, request: dict[str, object]) -> None:
        job_id = request.get("job_id")
        source = request.get("source")
        expected_digest = request.get("package_sha256")
        signed_package = {key: request.get(key) for key in ("interface", "source", "expected_output")}
        if (not isinstance(job_id, str) or not JOB.fullmatch(job_id)
                or request.get("tenant") != "TEN-ARWC-047"
                or request.get("connector_revision") != "FLK-7.4.2"
                or request.get("interface") != "fieldkest.connector/v3"
                or not isinstance(source, str) or len(source.encode()) > 131_072
                or not isinstance(request.get("expected_output"), dict)
                or hashlib.sha256(canonical(signed_package)).hexdigest() != expected_digest):
            return self.send_json(403, {"error": "diagnostic_binding_denied"})
        receipt_path = RECEIPTS / f"{job_id}.json"
        if receipt_path.exists():
            return self.send_json(409, {"error": "diagnostic_already_executed"})
        invocation = {"schema": "fieldkest.connector/v3", "tenant_id": "TEN-ARWC-047", "asset_id": "CRR-OG2", "operation": "diagnostic_summary", "job_id": job_id}
        try:
            output = execute(source, invocation)
        except ValueError as error:
            return self.send_json(422, {"error": str(error)})
        if output != request["expected_output"]:
            return self.send_json(422, {"error": "diagnostic_output_mismatch"})
        receipt_id = "DIAG-RCPT-" + uuid.uuid4().hex[:12].upper()
        receipt = {"schema": "fieldlink.diagnostic-receipt/v1", "receipt_id": receipt_id, "job_id": job_id, "tenant": "TEN-ARWC-047", "account": "Alterra Regional Water Company", "maintenance_case": "MTN-CRR-204", "connector_revision": "FLK-7.4.2", "package_sha256": expected_digest, "operation": "diagnostic_summary", "runtime_identity": "svc-arwc-fieldlink", "output": output, "state": "complete", "completed_at": now()}
        receipt["audit_id"] = append_audit({"action": "diagnostic-execution", "principal": DIAGNOSTIC_PRINCIPAL, **receipt})
        atomic_json(receipt_path, receipt)
        earn_corporate("diagnostic-execution", receipt_id, "FLK-7.4.2")
        self.send_json(202, receipt)


def main() -> None:
    for directory in (CONSUMER, CANDIDATES, RECEIPTS, AUDIT.parent):
        directory.mkdir(parents=True, exist_ok=True)
    AUDIT.touch(mode=0o600, exist_ok=True)
    server = ThreadingHTTPServer(("0.0.0.0", 443), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain("/tmp/arwc-server.crt", "/tmp/arwc-server.key")
    context.load_verify_locations(cafile="/tmp/keplerops-ca.crt")
    context.verify_mode = ssl.CERT_REQUIRED
    server.socket = context.wrap_socket(server.socket, server_side=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
