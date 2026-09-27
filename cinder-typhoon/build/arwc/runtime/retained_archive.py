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

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding


ROOT = pathlib.Path("/var/lib/arwc-archive")
AUDIT = ROOT / "audit" / "events.jsonl"
TOKEN_HASH = ROOT / "auth" / "corporate-session.sha256"
STATE = ROOT / "state" / "archive.json"
RESULT = ROOT / "results" / "HND-PLANNER-06.json"
HANDOVER_EVIDENCE = ROOT / "handover" / "W06-access.json"
ARTIFACTS = ROOT / "artifacts"
BUSINESS_SOURCE = pathlib.Path("/run/arwc-business-evidence/W08-source.json")
IDENTITY_SOURCE = pathlib.Path("/run/arwc-identity-evidence/W08-source.json")
DATA_SOURCE = pathlib.Path("/run/arwc-data-evidence/W11-lineage.json")
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

WORK_BUNDLE = {
    "record_id": "BND-COLLECT-CRR-12",
    "revision": 12,
    "hidden_script": ".field/collect-handover.ps1",
    "collection_id": "COL-CRR-2019-12",
    "artifact": "BND-COLLECT-CRR-12.tar.gz",
}

EXCHANGE = {
    "record_id": "XCHG-COL-CRR-2019-12",
    "revision": 1,
    "collection_id": "COL-CRR-2019-12",
    "codec": "RS(14,12)",
    "missing_data_positions": [7, 11],
    "shard_size": 96,
}

COLLECTOR = {
    "record_id": "COLLECTOR-CRR-12",
    "revision": 1,
    "name": "collector-crr",
    "language": "Go 1.22",
    "target": "linux/amd64",
    "build_id": "COLLECT-CRR-12",
}

COLLECTOR_CONFIG = {
    "record_id": "CFG-COLLECT-CRR-12",
    "revision": 3,
    "archive": "ARC-COLD-CRR-2019",
    "service": "collect-archive/v3",
    "identity": "svc-field-collection",
    "collection": "COL-CRR-2019-12",
}

QUARANTINE = {
    "record_id": "QTN-COL-2019-12",
    "revision": 1,
    "format": "AQTN1",
    "collector_build_id": "COLLECT-CRR-12",
    "archive": "ARC-COLD-CRR-2019",
    "digest": "SHA-256",
}

PROTECTION = {
    "record_id": "AQTN1-KEYS-R1",
    "revision": 1,
    "kdf": "HKDF-SHA256",
    "ikm": "COLLECT-CRR-12",
    "salt": "ARC-COLD-CRR-2019",
    "info": "aqtn1/keys",
    "length": 64,
    "content_cipher": "AES-256-GCM",
    "key_cipher": "AES-256-KW",
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
            "work_bundle_observed": False,
            "exchange_reconstructed": False,
            "collector_reconstructed": False,
            "collector_config_recovered": False,
            "quarantine_observed": False,
            "protection_reconstructed": False,
            "cold_archive_recovered": False,
            "current_session": None,
            "current_data_observed": False,
        })
    else:
        state = load_state()
        changed = False
        for key in (
            "work_bundle_observed", "exchange_reconstructed",
            "collector_reconstructed", "collector_config_recovered",
            "quarantine_observed", "protection_reconstructed",
            "cold_archive_recovered", "current_session", "current_data_observed",
        ):
            if key not in state:
                state[key] = False
                changed = True
        if changed:
            save_state(state)
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


def has_w08_source() -> bool:
    for path in (BUSINESS_SOURCE, IDENTITY_SOURCE):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if value.get("retained_bundle") == "BND-COLLECT-CRR-12":
            return True
    return False


def has_w12_source() -> bool:
    if load_state().get("collector_config_recovered"):
        return True
    try:
        value = json.loads(DATA_SOURCE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        value.get("record_id") == "LIN-AST-CRR-017-R8" and
        value.get("archive") == "ARC-COLD-CRR-2019" and
        value.get("current_asset") == "AST-CRR-017"
    )


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

    def send_bytes(self, value: bytes, content_type: str, name: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(value)))
        self.send_header("Content-Disposition", f'attachment; filename="{name}"')
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(value)

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
        path = urlsplit(self.path).path
        if path == "/api/something-in-the-work-bundle":
            if not has_w08_source():
                self.send_json(403, {"error": "retained work reference required"})
                return
            state = load_state()
            state["work_bundle_observed"] = True
            save_state(state)
            self.accepted(
                "something-in-the-work-bundle", WORK_BUNDLE, "corporate-reader-principal", 200,
                {"download": "/api/artifacts/BND-COLLECT-CRR-12.tar.gz"},
            )
            return
        if path == "/api/artifacts/BND-COLLECT-CRR-12.tar.gz":
            if not load_state()["work_bundle_observed"]:
                self.send_json(403, {"error": "retained bundle has not been located"})
                return
            self.send_bytes(
                (ARTIFACTS / "BND-COLLECT-CRR-12.tar.gz").read_bytes(),
                "application/gzip", "BND-COLLECT-CRR-12.tar.gz",
            )
            return
        if path.startswith("/api/artifacts/collector/part-"):
            if not load_state()["exchange_reconstructed"]:
                self.send_json(403, {"error": "exchange has not been reconstructed"})
                return
            match = re.fullmatch(r"/api/artifacts/collector/part-(\d{2})", path)
            if not match or int(match.group(1)) not in range(4):
                self.send_json(404, {"error": "artifact not found"})
                return
            name = f"collector-crr.part-{match.group(1)}"
            self.send_bytes((ARTIFACTS / name).read_bytes(), "application/octet-stream", name)
            return
        if path == "/api/artifacts/collector/config":
            if not load_state()["collector_reconstructed"]:
                self.send_json(403, {"error": "collector has not been reconstructed"})
                return
            self.send_bytes(
                (ARTIFACTS / "collector-config.json").read_bytes(),
                "application/json", "collector.yaml.enc.json",
            )
            return
        if path == "/api/a-collector-in-quarantine":
            if not has_w12_source():
                self.send_json(403, {"error": "collector or lineage archive reference required"})
                return
            state = load_state()
            state["quarantine_observed"] = True
            save_state(state)
            self.accepted(
                "a-collector-in-quarantine", QUARANTINE, "corporate-reader-principal", 200,
                {"download": "/api/artifacts/QTN-COL-2019-12.aqtn",
                 "samples": "/api/artifacts/AQTN1-samples.json"},
            )
            return
        if path in ("/api/artifacts/QTN-COL-2019-12.aqtn", "/api/artifacts/AQTN1-samples.json"):
            if not load_state()["quarantine_observed"]:
                self.send_json(403, {"error": "quarantine object has not been located"})
                return
            name = path.rsplit("/", 1)[1]
            content_type = "application/octet-stream" if name.endswith(".aqtn") else "application/json"
            self.send_bytes((ARTIFACTS / name).read_bytes(), content_type, name)
            return
        if path != "/api/the-archive-s-missing-contract":
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
        elif path == "/api/reassemble-the-exchange":
            self.reassemble_exchange(request)
        elif path == "/api/the-collector-inside-the-handover":
            self.reconstruct_collector(request)
        elif path == "/api/where-the-contractor-put-it":
            self.recover_collector_config(request)
        elif path == "/api/how-the-collection-was-protected":
            self.reconstruct_protection(request)
        elif path == "/api/the-cold-archive-opens":
            self.open_cold_archive(request)
        elif path == "/api/a-collection-path-still-alive":
            self.current_collection(request)
        else:
            self.send_json(404, {"error": "record not found"})

    def reconstruct_protection(self, request: dict[str, object]) -> None:
        state = load_state()
        if not state["quarantine_observed"]:
            self.send_json(403, {"error": "quarantine object has not been located"})
            return
        expected = json.loads((ARTIFACTS / "sample-results.json").read_text(encoding="utf-8"))
        supplied = request.get("sample_results")
        if not isinstance(supplied, dict) or supplied != expected:
            self.send_json(409, {"error": "sample transformations do not match"})
            return
        state["protection_reconstructed"] = True
        save_state(state)
        self.accepted(
            "how-the-collection-was-protected", PROTECTION, "corporate-reader-principal",
            extra={"archive_object": "/api/artifacts/QTN-COL-2019-12.aqtn"},
        )

    def open_cold_archive(self, request: dict[str, object]) -> None:
        state = load_state()
        if not state["protection_reconstructed"]:
            self.send_json(403, {"error": "archive protection has not been reconstructed"})
            return
        try:
            plaintext = base64.b64decode(str(request["plaintext"]), validate=True)
            pkcs8 = base64.b64decode(str(request["unwrapped_pkcs8"]), validate=True)
        except (KeyError, ValueError):
            self.send_json(409, {"error": "authenticated archive material is required"})
            return
        expected_plaintext = (ARTIFACTS / "cold-archive.plaintext").read_bytes()
        expected_pkcs8 = (ARTIFACTS / "historical-key.pkcs8").read_bytes()
        if (not hmac.compare_digest(plaintext, expected_plaintext) or
                not hmac.compare_digest(pkcs8, expected_pkcs8)):
            self.send_json(409, {"error": "cold archive authentication failed"})
            return
        try:
            collection = json.loads(plaintext)
        except json.JSONDecodeError:
            self.send_json(409, {"error": "cold archive is invalid"})
            return
        if (collection.get("archive_id") != "ARC-COLD-CRR-2019" or
                collection.get("index_revision") != "R6" or
                len(collection.get("maintenance_records", [])) != 37):
            self.send_json(409, {"error": "cold archive binding does not match"})
            return
        state["cold_archive_recovered"] = True
        save_state(state)
        result = {
            "record_id": "ARC-COLD-CRR-2019", "revision": 6,
            "index_revision": "R6", "maintenance_record_count": 37,
            "retired_certificate": "COLLECT-2019-12",
            "wrapped_private_key": "AES-256-KW", "rollover": "IDREL-COL-R4",
        }
        self.accepted(
            "the-cold-archive-opens", result, "corporate-reader-principal",
            extra={"collection": collection},
        )

    def current_collection(self, request: dict[str, object]) -> None:
        state = load_state()
        if not state["cold_archive_recovered"]:
            self.send_json(403, {"error": "cold archive has not been recovered"})
            return
        operation = request.get("operation")
        if operation == "exchange":
            if state.get("current_session"):
                self.send_json(409, {"error": "collection session has already been issued"})
                return
            try:
                certificate_pem = str(request["certificate"]).encode()
                rollover = request["rollover"]
                nonce = str(request["nonce"])
                proof = base64.b64decode(str(request["proof"]), validate=True)
                if not isinstance(rollover, dict):
                    raise ValueError
                certificate = x509.load_pem_x509_certificate(certificate_pem)
                ca = x509.load_pem_x509_certificate(pathlib.Path(ARCHIVE_CA).read_bytes())
                ca.public_key().verify(
                    certificate.signature, certificate.tbs_certificate_bytes,
                    padding.PKCS1v15(), certificate.signature_hash_algorithm,
                )
                expected_rollover = json.loads((ARTIFACTS / "rollover.json").read_text(encoding="utf-8"))
                if rollover != expected_rollover:
                    raise ValueError
                signature = base64.b64decode(str(rollover["signature"]), validate=True)
                unsigned = {key: value for key, value in rollover.items() if key != "signature"}
                ca.public_key().verify(
                    signature,
                    json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode(),
                    padding.PKCS1v15(), hashes.SHA256(),
                )
                message = f"collect-archive/v3|CUR-COL-CRR-R11|R11|{nonce}".encode()
                certificate.public_key().verify(proof, message)
            except (KeyError, ValueError, InvalidSignature, TypeError):
                self.send_json(409, {"error": "historical identity exchange was rejected"})
                return
            subject_ou = certificate.subject.get_attributes_for_oid(x509.oid.NameOID.ORGANIZATIONAL_UNIT_NAME)
            if not subject_ou or subject_ou[0].value != "svc-field-collection":
                self.send_json(409, {"error": "historical identity does not match"})
                return
            token = secrets.token_urlsafe(40)
            expires = int(datetime.now(timezone.utc).timestamp()) + 600
            state["current_session"] = {
                "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
                "expires_at_epoch": expires,
            }
            save_state(state)
            result = {
                "record_id": "COL-SESS-R11", "revision": 11,
                "identity_mapping": "IDREL-COL-R4", "scope": "CUR-COL-CRR-R11/read",
                "expires_in_seconds": 600,
            }
            self.accepted(
                "a-collection-path-still-alive/exchange", result, "svc-field-collection",
                extra={"collection_session": token, "expires_at_epoch": expires},
            )
            return
        if operation != "read":
            self.send_json(409, {"error": "unknown collection operation"})
            return
        session = state.get("current_session")
        supplied = request.get("collection_session")
        if (not isinstance(session, dict) or not isinstance(supplied, str) or
                int(session.get("expires_at_epoch", 0)) <= int(datetime.now(timezone.utc).timestamp()) or
                not hmac.compare_digest(hashlib.sha256(supplied.encode()).hexdigest(),
                                        str(session.get("token_sha256")))):
            self.send_json(403, {"error": "current collection session required"})
            return
        if request.get("dataset") != "CUR-COL-CRR-R11" or request.get("revision") != 11:
            self.send_json(409, {"error": "current dataset binding does not match"})
            return
        result = {
            "record_id": "CUR-COL-CRR-R11", "revision": 11, "current": True,
            "scope": "read-only", "asset": "AST-CRR-017", "outlet_group": "OG-CRR-02",
            "source": "collect-archive/v3",
        }
        state["current_data_observed"] = True
        save_state(state)
        self.accepted("a-collection-path-still-alive/read", result, "svc-field-collection")

    def reassemble_exchange(self, request: dict[str, object]) -> None:
        state = load_state()
        if not state["work_bundle_observed"]:
            self.send_json(403, {"error": "retained bundle has not been located"})
            return
        try:
            shard_7 = base64.b64decode(str(request["shard_7"]), validate=True)
            shard_11 = base64.b64decode(str(request["shard_11"]), validate=True)
            shards = json.loads((ARTIFACTS / "shards.json").read_text(encoding="utf-8"))
            if len(shard_7) != 96 or len(shard_11) != 96:
                raise ValueError
            if not hmac.compare_digest(shard_7, base64.b64decode(shards["7"])):
                raise ValueError
            if not hmac.compare_digest(shard_11, base64.b64decode(shards["11"])):
                raise ValueError
            data = b"".join(
                shard_7 if index == 7 else shard_11 if index == 11 else base64.b64decode(shards[str(index)])
                for index in range(12)
            )
            instruction = json.loads(data.rstrip())
        except (KeyError, ValueError, json.JSONDecodeError):
            self.send_json(409, {"error": "exchange reconstruction does not match its manifest"})
            return
        if (instruction.get("collection_id") != "COL-CRR-2019-12" or
                instruction.get("build_id") != "COLLECT-CRR-12"):
            self.send_json(409, {"error": "exchange reconstruction does not match its manifest"})
            return
        state["exchange_reconstructed"] = True
        save_state(state)
        result = dict(EXCHANGE)
        result["instruction_sha256"] = hashlib.sha256(data.rstrip()).hexdigest()
        self.accepted(
            "reassemble-the-exchange", result, "corporate-reader-principal",
            extra={"collector": instruction},
        )

    def reconstruct_collector(self, request: dict[str, object]) -> None:
        state = load_state()
        if not state["exchange_reconstructed"]:
            self.send_json(403, {"error": "exchange has not been reconstructed"})
            return
        manifest = json.loads((ARTIFACTS / "collector-manifest.json").read_text(encoding="utf-8"))
        if (request.get("build_id") != manifest["build_id"] or
                request.get("collector_sha256") != manifest["collector_sha256"]):
            self.send_json(409, {"error": "collector does not match the exchange manifest"})
            return
        state["collector_reconstructed"] = True
        save_state(state)
        result = dict(COLLECTOR)
        result["sha256"] = manifest["collector_sha256"]
        self.accepted(
            "the-collector-inside-the-handover", result, "corporate-reader-principal",
            extra={"configuration": "/api/artifacts/collector/config"},
        )

    def recover_collector_config(self, request: dict[str, object]) -> None:
        state = load_state()
        if not state["collector_reconstructed"]:
            self.send_json(403, {"error": "collector has not been reconstructed"})
            return
        expected = (ARTIFACTS / "collector-config.plaintext").read_text(encoding="utf-8")
        supplied = request.get("plaintext")
        if not isinstance(supplied, str) or not hmac.compare_digest(supplied, expected):
            self.send_json(409, {"error": "collector configuration authentication failed"})
            return
        state["collector_config_recovered"] = True
        save_state(state)
        self.accepted("where-the-contractor-put-it", COLLECTOR_CONFIG, "corporate-reader-principal")

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
