#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import hmac
import grp
import json
import os
import pathlib
import re
import secrets
import ssl
import subprocess
import tempfile
import unicodedata
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit


ROOT = pathlib.Path("/var/lib/arwc-archive")
AUDIT = ROOT / "audit" / "events.jsonl"
TOKEN_HASH = ROOT / "auth" / "corporate-session.sha256"
STATE = ROOT / "state" / "archive.json"
RESULT = ROOT / "results" / "HND-PLANNER-06.json"
HANDOVER_EVIDENCE = ROOT / "results" / "W06-access.json"
ARCHIVE_CA = "/tmp/archive-ca.crt"
ARCHIVE_CA_KEY = "/tmp/archive-ca.key"

WORKFLOW = {
    "record_id": "AWF-CRR-229-R4",
    "revision": 4,
    "attachment": "ARC-229-A",
    "protected_record": "AR-CRR-229",
    "enrollment_profile": {
        "name": "ArchiveSubmitter",
        "common_name": "corporate-reader-principal",
        "extended_key_usage": "clientAuth",
        "organizational_unit": "caller supplied",
        "use": "one time",
    },
}

CALLER_RECORD = {
    "record_id": "AR-MAINT-017",
    "revision": 2,
    "organizational_unit": "MaintenanceArchive",
    "classification": "maintenance archive",
}

PROTECTED_RECORD = {
    "record_id": "AR-CRR-229",
    "revision": 4,
    "workflow": "AWF-CRR-229-R4",
    "attachment": "ARC-229-A",
    "classification": "retained corporate archive",
}

HANDOVER = {
    "record_id": "HND-PLANNER-06",
    "revision": 6,
    "service_identity": "svc-archive-helper",
    "source_record": "AR-CRR-229",
    "destination": "caller result directory",
    "archive_helper": "7-Zip 23.01",
}


def atomic_json(path: pathlib.Path, value: object) -> None:
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def new_enrollment() -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    return token, hashlib.sha256(token.encode()).hexdigest()


def initialize() -> None:
    if not STATE.exists():
        token, digest = new_enrollment()
        atomic_json(STATE, {
            "enrollment_token": token,
            "enrollment_token_sha256": digest,
            "enrollment_consumed": False,
            "issued_certificates": [],
            "protected_record_observed": False,
            "helper_handover_copied": False,
            "planner_handover_token": None,
        })
    AUDIT.touch(mode=0o600, exist_ok=True)
    os.chmod(AUDIT, 0o600)


def load_state() -> dict[str, object]:
    return json.loads(STATE.read_text(encoding="utf-8"))


def save_state(state: dict[str, object]) -> None:
    atomic_json(STATE, state)


def append_audit(action: str, result: dict[str, object], principal: str) -> str:
    correlation = str(uuid.uuid4())
    event = {
        "audit_id": correlation,
        "time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "tenant": "arwc",
        "principal": principal,
        "action": action,
        "object": result.get("record_id"),
        "revision": result.get("revision"),
        "result_digest": hashlib.sha256(
            json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }
    with AUDIT.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return correlation


def issue_certificate(organizational_unit: str) -> tuple[str, str, str]:
    if not (1 <= len(organizational_unit) <= 160):
        raise ValueError("organizational unit has an invalid length")
    if any(character in organizational_unit for character in "\r\n\x00/"):
        raise ValueError("organizational unit contains an invalid character")
    with tempfile.TemporaryDirectory() as directory:
        work = pathlib.Path(directory)
        key = work / "client.key"
        request = work / "client.csr"
        certificate = work / "client.crt"
        extensions = work / "client.ext"
        extensions.write_text(
            "basicConstraints=critical,CA:FALSE\n"
            "keyUsage=critical,digitalSignature\n"
            "extendedKeyUsage=clientAuth\n",
            encoding="utf-8",
        )
        subprocess.run(
            ["openssl", "req", "-new", "-newkey", "rsa:2048", "-nodes",
             "-subj", "/CN=corporate-reader-principal/O=Alterra Regional Water Company/"
             f"OU={organizational_unit}",
             "-keyout", str(key), "-out", str(request)],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        serial = "0x" + secrets.token_hex(16)
        subprocess.run(
            ["openssl", "x509", "-req", "-days", "30", "-sha256",
             "-in", str(request), "-CA", ARCHIVE_CA, "-CAkey", ARCHIVE_CA_KEY,
             "-set_serial", serial, "-extfile", str(extensions), "-out", str(certificate)],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return (
            certificate.read_text(encoding="utf-8"),
            key.read_text(encoding="utf-8"),
            serial,
        )


def peer_organizational_unit(socket: ssl.SSLSocket) -> str | None:
    der = socket.getpeercert(binary_form=True)
    if not der:
        return None
    pem = ssl.DER_cert_to_PEM_cert(der)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".crt", encoding="utf-8") as handle:
        handle.write(pem)
        handle.flush()
        completed = subprocess.run(
            ["openssl", "x509", "-in", handle.name, "-noout", "-subject", "-nameopt", "multiline"],
            check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
    for line in completed.stdout.splitlines():
        match = re.match(r"\s*organizationalUnitName\s*=\s*(.*)$", line)
        if match:
            return match.group(1)
    return None


def archive_member(data: bytes) -> str:
    if len(data) > 1_048_576:
        raise ValueError("archive exceeds the accepted size")
    with tempfile.NamedTemporaryFile(suffix=".7z") as handle:
        handle.write(data)
        handle.flush()
        tested = subprocess.run(
            ["7zz", "t", handle.name], text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False, timeout=10,
        )
        if tested.returncode:
            raise ValueError("archive integrity check failed")
        listed = subprocess.run(
            ["7zz", "l", "-slt", "-ba", handle.name], text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False, timeout=10,
        )
        if listed.returncode:
            raise ValueError("archive directory could not be read")
    members = [line[7:] for line in listed.stdout.splitlines() if line.startswith("Path = ")]
    if len(members) != 1:
        raise ValueError("archive must contain exactly one member")
    return members[0]


class Handler(BaseHTTPRequestHandler):
    server_version = "ARWC-Retained-Archive/4.0"
    sys_version = ""

    def log_message(self, message: str, *args: object) -> None:
        print(f"{self.client_address[0]} {message % args}", flush=True)

    def send_json(self, status: int, body: dict[str, object]) -> None:
        encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(encoded)

    def authorized(self) -> bool:
        if self.headers.get("X-ARWC-Tenant", "arwc") != "arwc":
            self.send_json(403, {"error": "session is not valid for this tenant"})
            return False
        supplied = self.headers.get("Authorization", "")
        if not supplied.startswith("Bearer "):
            self.send_json(403, {"error": "archive session required"})
            return False
        digest = hashlib.sha256(supplied[7:].encode()).hexdigest()
        if not hmac.compare_digest(digest, TOKEN_HASH.read_text().strip()):
            self.send_json(403, {"error": "archive session required"})
            return False
        return True

    def body(self) -> dict[str, object] | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 2 or length > 1_500_000:
                raise ValueError
            value = json.loads(self.rfile.read(length))
            if not isinstance(value, dict):
                raise ValueError
            return value
        except (ValueError, json.JSONDecodeError):
            self.send_json(409, {"error": "invalid request"})
            return None

    def accepted(self, action: str, result: dict[str, object], principal: str,
                 status: int = 201, extra: dict[str, object] | None = None) -> None:
        response: dict[str, object] = {
            "audit_id": append_audit(action, result, principal),
            "record": result,
        }
        if extra:
            response.update(extra)
        self.send_json(status, response)

    def do_GET(self) -> None:
        if not self.authorized():
            return
        if urlsplit(self.path).path != "/api/the-archive-s-missing-contract":
            self.send_json(404, {"error": "record not found"})
            return
        state = load_state()
        if state["enrollment_consumed"]:
            token, digest = new_enrollment()
            state["enrollment_token"] = token
            state["enrollment_token_sha256"] = digest
            state["enrollment_consumed"] = False
            save_state(state)
        result = dict(WORKFLOW)
        result["enrollment_token"] = state["enrollment_token"]
        self.accepted("the-archive-s-missing-contract", result, "corporate-reader-principal", 200)

    def do_POST(self) -> None:
        if not self.authorized():
            return
        path = urlsplit(self.path).path
        request = self.body()
        if request is None:
            return
        if path == "/api/the-query-behind-the-identity":
            self.query(request)
        elif path == "/api/the-archive-helper-acts":
            self.helper(request)
        else:
            self.send_json(404, {"error": "record not found"})

    def query(self, request: dict[str, object]) -> None:
        operation = request.get("operation")
        if operation == "enroll":
            state = load_state()
            supplied = request.get("enrollment_token")
            if not isinstance(supplied, str) or state["enrollment_consumed"]:
                self.send_json(409, {"error": "enrollment is not current"})
                return
            if not hmac.compare_digest(hashlib.sha256(supplied.encode()).hexdigest(),
                                       str(state["enrollment_token_sha256"])):
                self.send_json(409, {"error": "enrollment is not current"})
                return
            organizational_unit = request.get("organizational_unit")
            if not isinstance(organizational_unit, str):
                self.send_json(409, {"error": "organizational unit is required"})
                return
            try:
                certificate, private_key, serial = issue_certificate(organizational_unit)
            except (ValueError, subprocess.SubprocessError):
                self.send_json(409, {"error": "organizational unit is not accepted"})
                return
            state["enrollment_consumed"] = True
            issued = state["issued_certificates"]
            assert isinstance(issued, list)
            issued.append({"serial": serial, "organizational_unit": organizational_unit})
            save_state(state)
            result = {
                "record_id": f"ArchiveSubmitter-{serial[2:]}",
                "revision": 1,
                "profile": "ArchiveSubmitter",
                "common_name": "corporate-reader-principal",
                "organizational_unit": organizational_unit,
                "extended_key_usage": "clientAuth",
            }
            self.accepted(
                "the-query-behind-the-identity/enroll", result,
                "corporate-reader-principal", extra={"certificate": certificate, "private_key": private_key},
            )
            return
        if operation != "query":
            self.send_json(409, {"error": "unknown archive operation"})
            return
        organizational_unit = peer_organizational_unit(self.connection)
        if not organizational_unit:
            self.send_json(403, {"error": "ArchiveSubmitter client identity required"})
            return
        query = (
            "MATCH (i:Identity {ou:'" + organizational_unit +
            "'})-[:CAN_READ]->(r:ArchiveRecord) RETURN r"
        )
        if re.search(r"\b(CREATE|DELETE|SET|MERGE|REMOVE|DROP)\b", query, re.IGNORECASE):
            self.send_json(409, {"error": "archive backend is read only"})
            return
        if organizational_unit == "MaintenanceArchive":
            self.accepted("the-query-behind-the-identity/query", CALLER_RECORD,
                          "corporate-reader-principal", extra={"backend_query": query})
            return
        protected = re.search(
            r"\bOR\s+r\.id\s*=\s*['\"]AR-CRR-229['\"]", organizational_unit, re.IGNORECASE,
        )
        other_record = re.search(r"\b(?:r\.id|record_id)\s*=\s*['\"]([^'\"]+)", organizational_unit,
                                 re.IGNORECASE)
        if not protected or (other_record and other_record.group(1) != "AR-CRR-229"):
            self.send_json(403, {"error": "identity has no matching archive record"})
            return
        state = load_state()
        state["protected_record_observed"] = True
        save_state(state)
        self.accepted("the-query-behind-the-identity/query", PROTECTED_RECORD,
                      "corporate-reader-principal", extra={"backend_query": query})

    def helper(self, request: dict[str, object]) -> None:
        state = load_state()
        if not state["protected_record_observed"]:
            self.send_json(403, {"error": "protected archive record has not been observed"})
            return
        supplied = request.get("archive")
        if not isinstance(supplied, str):
            self.send_json(409, {"error": "archive is required"})
            return
        try:
            data = base64.b64decode(supplied, validate=True)
            member = archive_member(data)
        except (ValueError, subprocess.SubprocessError, TimeoutError):
            self.send_json(409, {"error": "archive is not accepted"})
            return
        if ".." in member or "/" in member:
            self.send_json(409, {"error": "archive member is outside the result directory"})
            return
        normalized = unicodedata.normalize("NFKC", member)
        if normalized != "../copy_handover(HND-PLANNER-06)":
            self.send_json(409, {"error": "archive member does not select an available action"})
            return
        atomic_json(RESULT, HANDOVER)
        token = state.get("planner_handover_token")
        if not isinstance(token, str):
            token = secrets.token_urlsafe(32)
            state["planner_handover_token"] = token
        atomic_json(HANDOVER_EVIDENCE, {
            "record_id": "HND-PLANNER-06",
            "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
        })
        os.chown(HANDOVER_EVIDENCE, -1, grp.getgrnam("arwc-handover").gr_gid)
        os.chmod(HANDOVER_EVIDENCE, 0o640)
        state["helper_handover_copied"] = True
        save_state(state)
        self.accepted(
            "the-archive-helper-acts", HANDOVER, "svc-archive-helper",
            extra={"planner_handover": token},
        )


def main() -> None:
    initialize()
    server = ThreadingHTTPServer(("0.0.0.0", 443), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain("/tmp/server.crt", "/tmp/server.key")
    context.load_verify_locations(ARCHIVE_CA)
    context.verify_mode = ssl.CERT_OPTIONAL
    server.socket = context.wrap_socket(server.socket, server_side=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
