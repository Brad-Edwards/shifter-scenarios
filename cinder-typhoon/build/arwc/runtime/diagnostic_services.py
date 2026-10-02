#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import http.client
import json
import os
import pathlib
import ssl
import subprocess
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

import dpg1

ROOT = pathlib.Path("/var/lib/arwc-diagnostics")
STATE = ROOT / "state/service.json"
AUDIT = ROOT / "audit/events.jsonl"
ORACLE_LOG = ROOT / "state/oracle-ciphertexts.txt"
OT_SESSIONS = pathlib.Path("/run/arwc-ot-read")
ENGINEERING_STATE = pathlib.Path("/run/arwc-engineering/state/service.json")
ARTIFACT = pathlib.Path("/opt/diagnostic-services/artifacts/estimator23")
SIGNER = pathlib.Path("/opt/diagnostic-services/artifacts/dsign-crr-r3")
VAULT_WORKER = pathlib.Path("/opt/diagnostic-services/artifacts/dvl-worker-r5")
VAULT_BASE = 0x555550000000
INITIAL = {"side_effect_observed": False, "protected_state_controlled": False,
           "false_estimate_observed": False, "oracle_contract_observed": False,
           "selector_predicted": False, "bundle_opened": False,
           "calibration_exported": False, "oracle_queries": 0,
           "colliding_program_accepted": False,
           "vault_contract_observed": False, "vault_boundary_controlled": False,
           "vault_saved_state_controlled": False, "vault_execution": None,
           "vault_history_response": None,
           }
ORACLE_LOCK = threading.Lock()
SEEN_CIPHERTEXTS: set[str] = set()

MASK64 = (1 << 64) - 1
RSA_P = int("db74524bafbfde47409fb1ba348d31ff76564038c8d1849c7f87af27a9e1581d478d7e83089b5e943edaa149b36d446d8552d8f9785637078bfebf688c386db42a7c37c6cf182b9f09ac952d3445ebd1e5b4066a5df3750325d8dd4d67b2fef2f888de9c4e62c8065e44b8bd6fbb7ba9323d31f174c1dd2f68f291fd888a00d1", 16)
RSA_Q = int("c2d19ff81e4cb755b36930d459768049600573c716a2bdb7c5a9cba0ae93ea30649632eb917897f1b76d136d45d0df3ef9694fcc8ea50e48a345d6920ea14e41c9d328cf7359676a3333184955c9e4d576dffba48473fe89f13144bb7d3687a55dd27c39bcf440b6d7f29c14f0ce1bd689228495b31b3810f934497a479448b5", 16)
RSA_N = RSA_P * RSA_Q
RSA_E = 65537
RSA_D = pow(RSA_E, -1, (RSA_P - 1) * (RSA_Q - 1))
RSA_DP, RSA_DQ, RSA_QINV = RSA_D % (RSA_P - 1), RSA_D % (RSA_Q - 1), pow(RSA_Q, -1, RSA_P)
RSA_PADDING = bytes.fromhex("ed807fbf58db3b5490e68cbe55bb6045757c599ea130f63643e72f3660c60103d620800862aab1499199483f048c8d1402c5b1e5ae1be6a17cf5a8a25c78ea01cd050998a10a8c8324fa83fb156cdce3d087554276db9e8650047ef39459edd93a66c74b82bbcf0ec308135e80a72da28ec584c2c32d86a38044356a84ad08a7d2217ef3bbd0c328bc1547e3aa97d9754d807f4773ccc2c6415b7036cf780155cf47c5cbb934b5fc3ed2713466162f116b717e7b39f8dfdf94ac11524effaca232315a6242a9cce6fb3d43c2f06e85e0529066644660909cc2")
UNLOCK = b"ENG1" + b"U" * 32
RSA_MESSAGE = b"\x00\x02" + RSA_PADDING + b"\x00" + UNLOCK
RSA_TARGET = pow(int.from_bytes(RSA_MESSAGE, "big"), RSA_E, RSA_N)
EPOCH_BUCKET = 1770000042

FIELD_P = 2**255 - 19
CURVE_D = (-121665 * pow(121666, -1, FIELD_P)) % FIELD_P
SCALAR_L = 2**252 + 27742317777372353535851937790883648493
SQRT_M1 = pow(2, (FIELD_P - 1) // 4, FIELD_P)


def point_add(left: tuple[int, int, int, int], right: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    x1, y1, z1, t1 = left; x2, y2, z2, t2 = right
    a = (y1 - x1) * (y2 - x2) % FIELD_P; b = (y1 + x1) * (y2 + x2) % FIELD_P
    c = 2 * CURVE_D * t1 * t2 % FIELD_P; d = 2 * z1 * z2 % FIELD_P
    e, f, g, h = b - a, d - c, d + c, b + a
    return e * f % FIELD_P, g * h % FIELD_P, f * g % FIELD_P, e * h % FIELD_P


def point_double(point: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    x, y, z, _ = point
    a, b, c = x * x % FIELD_P, y * y % FIELD_P, 2 * z * z % FIELD_P
    d = -a % FIELD_P; e = ((x + y) ** 2 - a - b) % FIELD_P
    g, f, h = (d + b) % FIELD_P, (d + b - c) % FIELD_P, (d - b) % FIELD_P
    return e * f % FIELD_P, g * h % FIELD_P, f * g % FIELD_P, e * h % FIELD_P


def point_mul(scalar: int, point: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    result = (0, 1, 1, 0)
    while scalar:
        if scalar & 1: result = point_add(result, point)
        point = point_double(point); scalar >>= 1
    return result


def recover_x(y: int, sign: int) -> int | None:
    if y >= FIELD_P: return None
    x2 = (y * y - 1) * pow(CURVE_D * y * y + 1, -1, FIELD_P) % FIELD_P
    x = pow(x2, (FIELD_P + 3) // 8, FIELD_P)
    if (x * x - x2) % FIELD_P: x = x * SQRT_M1 % FIELD_P
    if (x * x - x2) % FIELD_P: return None
    if (x & 1) != sign: x = FIELD_P - x
    return x


BASE_Y = 4 * pow(5, -1, FIELD_P) % FIELD_P
BASE_X = recover_x(BASE_Y, 0)
assert BASE_X is not None
BASE = (BASE_X, BASE_Y, 1, BASE_X * BASE_Y % FIELD_P)


def point_encode(point: tuple[int, int, int, int]) -> bytes:
    x, y, z, _ = point; inverse = pow(z, -1, FIELD_P)
    x, y = x * inverse % FIELD_P, y * inverse % FIELD_P
    return (y | ((x & 1) << 255)).to_bytes(32, "little")


def point_decode(encoded: bytes) -> tuple[int, int, int, int] | None:
    if len(encoded) != 32: return None
    value = int.from_bytes(encoded, "little"); y, sign = value & ((1 << 255) - 1), value >> 255
    x = recover_x(y, sign)
    if x is None: return None
    point = (x, y, 1, x * y % FIELD_P)
    return point if point_encode(point) == encoded else None


SIGNING_X = int.from_bytes(hashlib.sha512(b"ARWC CRR25519-S DSIGN-CRR-R3").digest(), "little") % SCALAR_L
PUBLIC_POINT = point_mul(SIGNING_X, BASE)
PUBLIC_KEY = point_encode(PUBLIC_POINT)


def challenge_hash(r_encoded: bytes, message: bytes) -> int:
    return int.from_bytes(hashlib.sha512(r_encoded + PUBLIC_KEY + message).digest(), "little") % SCALAR_L


def signature(message: bytes, nonce: int) -> tuple[bytes, bytes]:
    r_encoded = point_encode(point_mul(nonce, BASE))
    scalar = (nonce + challenge_hash(r_encoded, message) * SIGNING_X) % SCALAR_L
    return r_encoded, scalar.to_bytes(32, "little")


def verify_signature(message: bytes, r_encoded: bytes, scalar_encoded: bytes) -> bool:
    if len(scalar_encoded) != 32: return False
    scalar = int.from_bytes(scalar_encoded, "little")
    r_point = point_decode(r_encoded)
    if scalar >= SCALAR_L or r_point is None: return False
    left = point_mul(scalar, BASE)
    right = point_add(r_point, point_mul(challenge_hash(r_encoded, message), PUBLIC_POINT))
    return left[0] * right[2] % FIELD_P == right[0] * left[2] % FIELD_P and left[1] * right[2] % FIELD_P == right[1] * left[2] % FIELD_P


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


FRESH_EXPORT = canonical({"export_id": "EXP-CAL-CRR-25", "project_id": "CRR-CTRL-R21",
                          "project_revision": 21, "scope": "calibration-exceptions/read"})


def signed_records() -> tuple[list[dict[str, object]], dict[str, object]]:
    records: list[dict[str, object]] = []
    nonces: list[int] = []
    for index in range(16):
        record = {"record_id": f"DIAG-ARCH-{index + 1:02d}", "project_id": "CRR-CTRL-R19",
                  "project_revision": 19, "sequence": index + 1,
                  "status": "retained" if index < 14 else "superseded"}
        message = canonical(record)
        nonce = int.from_bytes(hashlib.sha512(b"DSIGN-CRR-R3/nonce/" + bytes([index])).digest(), "little") % SCALAR_L
        r_encoded, scalar = signature(message, nonce); nonces.append(nonce)
        records.append({"record": record, "canonical_b64": base64.b64encode(message).decode(),
                        "R": r_encoded.hex(), "s": scalar.hex(), "nonce_bits_60_251": str(nonce >> 60)})
    return records, {"first_record": "DIAG-ARCH-01", "second_record": "DIAG-ARCH-02",
                     "signed_low60_delta": (nonces[1] & ((1 << 60) - 1)) - (nonces[0] & ((1 << 60) - 1))}


def bundle_plaintext() -> bytes:
    records, metadata = signed_records()
    return canonical({"bundle_id": "DIAG-EVID-CRR-R7", "project_id": "CRR-CTRL-R21", "revision": 7,
                      "signer": {"record_id": "DSIGN-CRR-R3", "format": "ELF64-x86-64-stripped",
                                 "sha256": hashlib.sha256(SIGNER.read_bytes()).hexdigest(),
                                 "artifact_b64": base64.b64encode(SIGNER.read_bytes()).decode(),
                                 "scheme": "CRR25519-S", "public_key": PUBLIC_KEY.hex()},
                      "records": records, "recovery_metadata": metadata,
                      "fresh_export_request_b64": base64.b64encode(FRESH_EXPORT).decode()})


def sealed_bundle() -> tuple[bytes, bytes]:
    nonce = hashlib.sha256(b"DIAG-EVID-CRR-R7/nonce").digest()[:12]
    aad = b"DIAG-EVID-CRR-R7|CRR-CTRL-R21"
    return nonce, AESGCM(hashlib.sha256(UNLOCK).digest()).encrypt(nonce, bundle_plaintext(), aad)


def selector(request_id: int, epoch_bucket: int) -> int:
    s0 = (request_id ^ 0x9E3779B97F4A7C15) & MASK64
    s1 = (epoch_bucket ^ 0xBF58476D1CE4E5B9) & MASK64
    x, y = s0, s1; s0 = y
    x = (x ^ ((x << 23) & MASK64)) & MASK64
    s1 = (x ^ y ^ (x >> 17) ^ (y >> 26)) & MASK64
    return (s1 + y) & MASK64


PREDICTION_CASES = [
    {"request_id": f"{request_id:016x}", "epoch_bucket": bucket, "padding_class": klass,
     "observed_class": "ABCD"[("ABCD".index(klass) + (selector(request_id, bucket) & 3)) & 3]}
    for request_id, bucket, klass in [
        (0x2400000000000001, EPOCH_BUCKET - 1, "A"), (0x2400000000001021, EPOCH_BUCKET, "B"),
        (0x2400000000ABCDEF, EPOCH_BUCKET, "C"), (0x24FFFFFFFFFFFFFE, EPOCH_BUCKET + 1, "D")]
]


def atomic_json(path: pathlib.Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, sort_keys=True, separators=(",", ":")); handle.write("\n")
            handle.flush(); os.fsync(handle.fileno())
        os.chmod(temporary, 0o640); os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def load_state() -> dict[str, object]:
    return json.loads(STATE.read_text())


def append_audit(action: str, result: dict[str, object], correlation: str | None = None) -> str:
    correlation = correlation or str(uuid.uuid4())
    event = {"audit_id": correlation, "time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
             "tenant": "arwc", "principal": "svc-diagnostics", "action": action,
             "object": result.get("record_id"),
             "result_digest": hashlib.sha256(json.dumps(result, sort_keys=True,
                                                          separators=(",", ":")).encode()).hexdigest()}
    with AUDIT.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush(); os.fsync(handle.fileno())
    return correlation


def vault_metadata() -> dict[str, object]:
    completed = subprocess.run([str(VAULT_WORKER), "--metadata"], check=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                               timeout=2)
    value = json.loads(completed.stdout)
    if value.get("build_id") != "DVL-WORKER-R5":
        raise ValueError("unexpected diagnostic worker build")
    return value


def run_vault(mode: str, record: bytes, correlation: str | None = None) -> dict[str, object] | None:
    arguments = [str(VAULT_WORKER), mode, hex(VAULT_BASE)]
    if correlation is not None:
        arguments.append(correlation)
    try:
        completed = subprocess.run(arguments, input=record, stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL, check=False, timeout=2)
        if completed.returncode != 0:
            return None
        value = json.loads(completed.stdout)
        return value if isinstance(value, dict) else None
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return None


def decode_vault_record(request: dict[str, object]) -> bytes | None:
    encoded = request.get("record_b64")
    if not isinstance(encoded, str):
        return None
    try:
        return base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError):
        return None


def deployed_revision_ready() -> bool:
    try:
        state = json.loads(ENGINEERING_STATE.read_text())
    except (OSError, json.JSONDecodeError):
        return False
    return state.get("deployed_revision_observed") is True


def rsa_decrypt(ciphertext: int) -> bytes:
    first = pow(ciphertext, RSA_DP, RSA_P); second = pow(ciphertext, RSA_DQ, RSA_Q)
    message = second + RSA_Q * (((first - second) * RSA_QINV) % RSA_P)
    return message.to_bytes(256, "big")


def padding_class(encoded: bytes) -> str:
    if encoded[:2] != b"\x00\x02": return "A"
    try: separator = encoded.index(0, 2)
    except ValueError: return "C"
    if separator < 10: return "B"
    if not encoded[separator + 1:].startswith(b"ENG1"): return "C"
    return "D"


def rsa_encrypt(encoded: bytes) -> str:
    return f"{pow(int.from_bytes(encoded, 'big'), RSA_E, RSA_N):0512x}"


def labeled_examples() -> list[dict[str, object]]:
    examples = [
        ("A", b"\x01\x02" + b"\x01" * 254),
        ("B", b"\x00\x02" + b"\x01" * 7 + b"\x00ENG1" + b"B" * 242),
        ("C", b"\x00\x02" + b"\x01" * 217 + b"\x00BAD1" + b"C" * 32),
        ("D", RSA_MESSAGE),
    ]
    result = []
    for index, (klass, encoded) in enumerate(examples):
        request_id = 0x2400000000001000 + index
        rotation = selector(request_id, EPOCH_BUCKET) & 3
        result.append({"request_id": f"{request_id:016x}", "epoch_bucket": EPOCH_BUCKET,
                       "ciphertext": rsa_encrypt(encoded), "padding_class": klass,
                       "observed_class": "ABCD"[("ABCD".index(klass) + rotation) & 3]})
    return result


class Handler(BaseHTTPRequestHandler):
    server_version = "ARWC-Diagnostic-Services/23"
    sys_version = ""

    def log_message(self, message: str, *args: object) -> None:
        print(f"{self.client_address[0]} {message % args}", flush=True)

    def send_json(self, status: int, body: dict[str, object]) -> None:
        encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        self.send_response(status); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded))); self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff"); self.end_headers(); self.wfile.write(encoded)

    def authorized(self) -> bool:
        if self.headers.get("X-ARWC-Internal") != "historian-r21" or self.headers.get("X-ARWC-Tenant") != "arwc":
            self.send_json(403, {"error": "diagnostic service context required"}); return False
        return True

    def body(self) -> dict[str, object] | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 2 or length > 65536: raise ValueError
            value = json.loads(self.rfile.read(length))
            if not isinstance(value, dict): raise ValueError
            return value
        except (ValueError, json.JSONDecodeError):
            self.send_json(409, {"error": "invalid request"}); return None

    def accepted(self, action: str, record: dict[str, object], extra: dict[str, object] | None = None,
                 correlation: str | None = None) -> None:
        result: dict[str, object] = {"audit_id": append_audit(action, record, correlation), "record": record}
        if extra: result.update(extra)
        self.send_json(201, result)

    def planning_consumer(self, request: dict[str, object]) -> tuple[int, dict[str, object]]:
        payload = json.dumps(request, sort_keys=True, separators=(",", ":")).encode()
        context = ssl.create_default_context(cafile="/tmp/ca.crt")
        connection = http.client.HTTPSConnection("a-data-bridge", 443, context=context, timeout=5)
        try:
            connection.request("POST", "/internal/diagnostic-estimate", body=payload, headers={
                "Content-Type": "application/json", "Content-Length": str(len(payload)),
                "X-ARWC-Internal": "diagnostics-r27", "X-ARWC-Tenant": "arwc",
            })
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def do_GET(self) -> None:
        if not self.authorized(): return
        path = urlsplit(self.path).path
        if path == "/api/the-vault-s-misleading-length":
            if not deployed_revision_ready():
                self.send_json(403, {"error": "current deployed engineering revision required"}); return
            metadata = vault_metadata(); artifact = VAULT_WORKER.read_bytes()
            record = {
                "record_id": "VAULT-CRR-R5", "revision": 5, "case_id": "DV-CRR-4417",
                "protected_history_reference": "HIST-APR-CRR-09", "format": "DVL1",
                "request_limit": 512, "declared_length_encoding": "u16-le",
                "header_length_encoding": "u16-le", "integrity": "CRC32C",
                "worker": {"format": "ELF64-x86-64", "architecture": "x86_64",
                           "glibc": "2.39", "build_id": metadata["build_id"],
                           "pie": True, "nx": True, "full_relro": True, "stack_canary": True,
                           "sha256": hashlib.sha256(artifact).hexdigest()},
                "status": {"build_id": metadata["build_id"],
                           "stack_canary": f"0x{0x91d4c6aa72be3f05:016x}",
                           "worker_mapping": {"base": f"0x{VAULT_BASE:x}",
                                              "end": f"0x{VAULT_BASE + 0x20000:x}"},
                           "status_address": f"0x{VAULT_BASE + int(metadata['status_offset']):x}",
                           "status_offset": int(metadata["status_offset"])},
                "frame": {"workspace_bytes": 0x120, "canary_offset": 0x120,
                          "saved_rbp_offset": 0x128, "return_state_offset": 0x130,
                          "argument_offset": 0x138},
            }
            state = load_state(); state["vault_contract_observed"] = True; atomic_json(STATE, state)
            self.send_json(200, {"audit_id": append_audit("the-vault-s-misleading-length", record),
                                 "record": record, "worker_b64": base64.b64encode(artifact).decode()})
            return
        if path != "/api/two-kinds-of-answer":
            self.send_json(404, {"error": "record not found"}); return
        if not deployed_revision_ready():
            self.send_json(403, {"error": "current deployed engineering revision required"}); return
        state = load_state(); state["oracle_contract_observed"] = True; atomic_json(STATE, state)
        nonce, ciphertext = sealed_bundle()
        record = {
            "record_id": "RECOVERY-ORACLE-R4", "revision": 4,
            "engineering_record": "ENG-REC-24", "algorithm": "RSA-2048/PKCS1-v1_5",
            "modulus": f"{RSA_N:0512x}", "exponent": RSA_E, "query_limit": 4096,
            "classes": {"A": "missing-00-02-prefix", "B": "fewer-than-eight-nonzero-padding-bytes",
                        "C": "missing-separator-or-wrong-ENG1-tag", "D": "structurally-valid-padding"},
            "labeled_examples": labeled_examples(), "target_ciphertext": f"{RSA_TARGET:0512x}",
            "epoch_bucket": EPOCH_BUCKET,
            "sealed_bundle": {"bundle_id": "DIAG-EVID-CRR-R7", "project_id": "CRR-CTRL-R21",
                              "cipher": "AES-256-GCM", "key_derivation": "SHA-256(archive-unlock)",
                              "nonce_b64": base64.b64encode(nonce).decode(),
                              "aad_b64": base64.b64encode(b"DIAG-EVID-CRR-R7|CRR-CTRL-R21").decode(),
                              "ciphertext_b64": base64.b64encode(ciphertext).decode()},
            "prediction_cases": [{key: value for key, value in case.items() if key != "observed_class"}
                                 for case in PREDICTION_CASES],
        }
        self.send_json(200, {"audit_id": append_audit("two-kinds-of-answer", record), "record": record})

    def do_POST(self) -> None:
        if urlsplit(self.path).path == "/internal/w34-estimate":
            if (self.headers.get("X-ARWC-Internal") != "data-bridge-w34" or
                    self.headers.get("X-ARWC-Tenant") != "arwc" or
                    self.client_address[0] != "10.77.63.10"):
                self.send_json(403, {"error": "integration service context required"}); return
            request = self.body()
            if request is None: return
            state = load_state()
            if request != {"source": "ALLOC-CASE-CRR-33", "consumer": "PLAN-CONSUMER-R8"}:
                self.send_json(409, {"error": "estimate capability binding rejected"}); return
            if not state.get("false_estimate_observed"):
                self.send_json(403, {"error": "accepted estimator output required"}); return
            self.send_json(200, {"record": {
                "record_id": "ALLOC-CASE-CRR-33", "revision": 33,
                "consumer": "PLAN-CONSUMER-R8",
                "estimate": {"Cairn Reach": 13.4, "North": 8.1, "Merewick": 7.65},
                "quality": "valid", "raw_process_observations_changed": False,
                "independent_instruments_changed": False,
            }})
            return
        if not self.authorized(): return
        request = self.body()
        if request is None: return
        path = urlsplit(self.path).path
        state = load_state()
        if path == "/api/a-measurement-with-side-effects":
            if request == {"estimator": "EST-CRR-23", "mode": "baseline"}:
                artifact = ARTIFACT.read_bytes()
                self.send_json(201, {"record": {
                    "record_id": "EST-CRR-23", "runtime": "C++20/glibc-2.39/x86_64",
                    "object_size": 144, "operation_limit": 8,
                    "ordinary": {"Cairn": 12.40, "North": 8.10, "Merewick": 7.65, "quality": "valid"},
                    "sha256": hashlib.sha256(artifact).hexdigest(),
                }, "artifact_b64": base64.b64encode(artifact).decode()})
                return
            expected = {"estimator": "EST-CRR-23", "operations": [
                {"op": "add", "source_id": "FIT-CRR-204B", "value": 12.4},
                {"op": "add", "source_id": "FIT-CRR-204B", "value": 12.4},
                {"op": "add", "source_id": "PROBE-CRR-23", "value": 0.0},
                {"op": "write-stale", "source_id": "FIT-CRR-204B", "offset": 64, "u32": 1129468466},
            ]}
            if request != expected:
                self.send_json(409, {"error": "measurement operation sequence rejected"}); return
            state["side_effect_observed"] = True; atomic_json(STATE, state)
            self.accepted("a-measurement-with-side-effects", {
                "record_id": "EST-UAF-CRR-23", "revision": 23, "controlled_offset": 64,
                "controlled_u32": 1129468466, "target": "PROBE-CRR-23", "estimator_usable": True,
            }); return
        if path == "/api/control-beyond-the-measurement":
            if not state["side_effect_observed"]:
                self.send_json(403, {"error": "controlled measurement-state violation required"}); return
            expected = {"estimator": "EST-CRR-23", "operations": [
                {"op": "remove-duplicate", "source_id": "FIT-CRR-204B"},
                {"op": "add-state", "district_id": "Cairn Reach"},
                {"op": "remove-state", "district_id": "Cairn Reach"},
                {"op": "add-state", "district_id": "Cairn Reach"},
                {"op": "write-stale", "offset": 40, "f64": 13.4},
                {"op": "write-stale", "offset": 48, "u32": 1},
            ]}
            if request != expected:
                self.send_json(409, {"error": "allocator sequence or protected field rejected"}); return
            state["protected_state_controlled"] = True; atomic_json(STATE, state)
            self.accepted("control-beyond-the-measurement", {
                "record_id": "EST-STATE-CRR-23", "revision": 23, "district_id": "Cairn Reach",
                "vtable": "EST-STATE-V1", "reserve_ml": 13.4, "quality": 1,
                "writable_offsets": [40, 48], "estimator_usable": True,
            }); return
        if path == "/api/a-measurement-that-never-existed":
            if not state["protected_state_controlled"]:
                self.send_json(403, {"error": "protected estimator-state control required"}); return
            expected = {"allocation_case": "ALLOC-CASE-CRR-33", "district_id": "Cairn Reach",
                        "reserve_ml": 13.4, "quality": 1,
                        "unaffected": {"North": 8.1, "Merewick": 7.65}}
            if request != expected:
                self.send_json(409, {"error": "estimator result or unaffected district binding rejected"}); return
            state["false_estimate_observed"] = True; atomic_json(STATE, state)
            result = {"record_id": "ALLOC-CASE-CRR-33", "revision": 33,
                      "estimate": {"Cairn Reach": 13.4, "North": 8.1, "Merewick": 7.65},
                      "quality": "valid", "sufficient": True,
                      "raw_process_observations_changed": False,
                      "independent_instruments_changed": False}
            self.accepted("a-measurement-that-never-existed", result); return
        if path == "/api/which-answer-comes-next":
            if not state["oracle_contract_observed"]:
                self.send_json(403, {"error": "recovery contract observation required"}); return
            if state["selector_predicted"]:
                self.send_json(409, {"error": "prediction set already consumed"}); return
            expected = {"record_id": "ENG-REC-24", "prediction_set": "SELECTOR-CRR-R4",
                        "predictions": [{"request_id": case["request_id"],
                                         "epoch_bucket": case["epoch_bucket"],
                                         "observed_class": case["observed_class"]}
                                        for case in PREDICTION_CASES]}
            if request != expected:
                self.send_json(409, {"error": "response selection predictions rejected"}); return
            state["selector_predicted"] = True; atomic_json(STATE, state)
            self.accepted("which-answer-comes-next", {
                "record_id": "SELECTOR-CRR-R4", "revision": 4, "cases_accepted": len(PREDICTION_CASES),
                "selector": "xorshift128+", "replayable": False,
            }); return
        if path == "/api/the-diagnostic-evidence-bundle":
            if not state["selector_predicted"]:
                self.send_json(403, {"error": "response selector capability required"}); return
            operation = request.get("operation")
            if operation == "oracle":
                ciphertext_text = request.get("ciphertext")
                request_id_text = request.get("request_id")
                bucket = request.get("epoch_bucket")
                valid_text = (isinstance(ciphertext_text, str) and len(ciphertext_text) == 512 and
                              all(character in "0123456789abcdef" for character in ciphertext_text) and
                              isinstance(request_id_text, str) and len(request_id_text) == 16 and
                              all(character in "0123456789abcdef" for character in request_id_text) and
                              bucket == EPOCH_BUCKET)
                ciphertext = int(ciphertext_text, 16) if valid_text else 0
                canonical_ciphertext = f"{ciphertext:0512x}"
                digest = hashlib.sha256(canonical_ciphertext.encode()).hexdigest()
                with ORACLE_LOCK:
                    state = load_state(); count = int(state["oracle_queries"]); state["oracle_queries"] = count + 1
                    rejected = (count >= 4096 or not valid_text or ciphertext <= 0 or
                                ciphertext >= RSA_N or digest in SEEN_CIPHERTEXTS)
                    if not rejected:
                        with ORACLE_LOG.open("a", encoding="ascii") as handle:
                            handle.write(digest + "\n"); handle.flush(); os.fsync(handle.fileno())
                        SEEN_CIPHERTEXTS.add(digest)
                    atomic_json(STATE, state)
                if rejected:
                    self.send_json(409, {"error": "oracle query rejected"}); return
                raw_class = padding_class(rsa_decrypt(ciphertext))
                rotation = selector(int(request_id_text, 16), EPOCH_BUCKET) & 3
                observed = "ABCD"[("ABCD".index(raw_class) + rotation) & 3]
                atomic_json(STATE, state)
                self.send_json(200, {"request_id": request_id_text, "observed_class": observed,
                                     "queries_used": count + 1, "queries_remaining": 4095 - count})
                return
            if operation == "open":
                if state["bundle_opened"]:
                    self.send_json(409, {"error": "bundle unlock already consumed"}); return
                expected = {"operation": "open", "bundle_id": "DIAG-EVID-CRR-R7",
                            "project_id": "CRR-CTRL-R21", "project_revision": 21,
                            "archive_unlock_b64": base64.b64encode(UNLOCK).decode()}
                if request != expected or int(state["oracle_queries"]) > 4096:
                    self.send_json(409, {"error": "archive unlock or project binding rejected"}); return
                nonce, ciphertext = sealed_bundle(); aad = b"DIAG-EVID-CRR-R7|CRR-CTRL-R21"
                bundle = json.loads(AESGCM(hashlib.sha256(UNLOCK).digest()).decrypt(nonce, ciphertext, aad))
                state["bundle_opened"] = True; atomic_json(STATE, state)
                self.accepted("the-diagnostic-evidence-bundle", {
                    "record_id": "DIAG-EVID-CRR-R7", "revision": 7,
                    "project_id": "CRR-CTRL-R21", "signer": "DSIGN-CRR-R3",
                    "signed_record_count": 16, "signing_authority_granted": False,
                }, {"bundle": bundle}); return
            self.send_json(409, {"error": "diagnostic evidence operation rejected"}); return
        if path == "/api/signed-by-someone-who-never-approved-it":
            if not state["bundle_opened"]:
                self.send_json(403, {"error": "opened diagnostic evidence bundle required"}); return
            if state["calibration_exported"]:
                self.send_json(409, {"error": "export request already authorized"}); return
            if set(request) != {"export_request_b64", "R", "s"}:
                self.send_json(409, {"error": "diagnostic authorization rejected"}); return
            try:
                message = base64.b64decode(str(request["export_request_b64"]), validate=True)
                r_encoded = bytes.fromhex(str(request["R"])); scalar = bytes.fromhex(str(request["s"]))
            except (ValueError, TypeError):
                self.send_json(409, {"error": "diagnostic authorization rejected"}); return
            if message != FRESH_EXPORT or not verify_signature(message, r_encoded, scalar):
                self.send_json(409, {"error": "diagnostic authorization rejected"}); return
            state["calibration_exported"] = True; atomic_json(STATE, state)
            self.accepted("signed-by-someone-who-never-approved-it", {
                "record_id": "CAL-EXCEPT-CRR-R21", "revision": 21,
                "export_request": "EXP-CAL-CRR-25", "project_id": "CRR-CTRL-R21",
                "exceptions": [
                    {"instrument": "FIT-CRR-204B", "effective_revision": 21,
                     "bias_ml": 1.0, "disposition": "excluded-from-routine-support-export"},
                    {"instrument": "PROBE-CRR-23", "effective_revision": 21,
                     "quality_override": "engineering-review", "disposition": "retained"},
                ],
                "scope": "calibration-exceptions/read", "maintenance_approval": False,
                "control_authority": False,
            }); return
        if path == "/api/a-program-the-engineer-would-accept":
            try:
                engineering = json.loads(ENGINEERING_STATE.read_text())
            except (OSError, json.JSONDecodeError):
                engineering = {}
            if engineering.get("w27_collision_modeled") is not True:
                self.send_json(403, {"error": "accepted DPG1 collision model required"}); return
            if set(request) != {"record_id", "consumer", "program_b64"} or request.get("record_id") != dpg1.TARGET_ID or request.get("consumer") != "PLAN-CONSUMER-R8":
                self.send_json(409, {"error": "diagnostic program binding rejected"}); return
            try:
                candidate = base64.b64decode(str(request["program_b64"]), validate=True)
                parsed = dpg1.parse_program(candidate)
            except (ValueError, TypeError):
                self.send_json(409, {"error": "DPG1 candidate is invalid"}); return
            base = dpg1.build_program(dpg1.BASE_ID)
            if (candidate == base or parsed["program_id"] != dpg1.TARGET_ID or
                    parsed["outputs"] != {"Cairn Reach": 13.4, "North": 8.1, "Merewick": 7.65} or
                    dpg1.digest_hex(candidate) != dpg1.digest_hex(base) or
                    not dpg1.changed_only(candidate, purpose="target")):
                self.send_json(409, {"error": "diagnostic program did not preserve the accepted contract"}); return
            consumer_request = {
                "source": dpg1.TARGET_ID, "consumer": "PLAN-CONSUMER-R8",
                "allocation_case": "ALLOC-CASE-CRR-33",
                "program_sha256": hashlib.sha256(candidate).hexdigest(),
                "integrity": "VER-ROT128-R3", "digest": dpg1.digest_hex(candidate),
                "estimate": parsed["outputs"], "quality": "valid",
                "raw_process_observations_changed": False,
                "independent_instruments_changed": False,
            }
            try:
                status, consumer = self.planning_consumer(consumer_request)
            except (OSError, json.JSONDecodeError):
                self.send_json(409, {"error": "planning consumer unavailable"}); return
            if status != 201 or consumer.get("record", {}).get("record_id") != "PLAN-CONSUMER-R8":
                self.send_json(409, {"error": "planning consumer rejected the diagnostic estimate"}); return
            output = ROOT / "artifacts/a-program-the-engineer-would-accept"
            descriptor, temporary = tempfile.mkstemp(dir=output, prefix=".DPG-CRR-CINDER.")
            try:
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(candidate); handle.flush(); os.fsync(handle.fileno())
                os.chmod(temporary, 0o600); os.replace(temporary, output / "DPG-CRR-CINDER.dpg")
            finally:
                if os.path.exists(temporary): os.unlink(temporary)
            state["colliding_program_accepted"] = True; atomic_json(STATE, state)
            record = {
                "record_id": "DPG-ACCEPT-CRR-R8", "revision": 8,
                "program_id": dpg1.TARGET_ID, "format": "DPG1",
                "integrity": "VER-ROT128-R3", "digest": dpg1.digest_hex(candidate),
                "estimate": parsed["outputs"], "quality": "valid",
                "consumer": "PLAN-CONSUMER-R8",
                "consumer_audit_id": consumer.get("audit_id"),
                "raw_process_observations_changed": False,
                "independent_instruments_changed": False,
            }
            atomic_json(output / "result.json", record)
            self.accepted("a-program-the-engineer-would-accept", record); return
        if path == "/api/past-the-parser-s-boundary":
            if not state["vault_contract_observed"]:
                self.send_json(403, {"error": "diagnostic vault contract observation required"}); return
            if set(request) != {"case_id", "build_id", "record_b64"} or request.get("case_id") != "DV-CRR-4417" or request.get("build_id") != "DVL-WORKER-R5":
                self.send_json(409, {"error": "diagnostic record binding rejected"}); return
            raw = decode_vault_record(request)
            result = run_vault("--boundary", raw) if raw is not None else None
            if result is None:
                self.send_json(409, {"error": "DVL1 record rejected before protected access"}); return
            state["vault_boundary_controlled"] = True; atomic_json(STATE, state)
            record = {"record_id": "DVL-BOUNDARY-CRR-R5", "revision": 5,
                      "case_id": "DV-CRR-4417", "build_id": "DVL-WORKER-R5",
                      "declared_length": result["declared_length"],
                      "header_length": result["header_length"],
                      "wrapped_sum": result["wrapped_sum"],
                      "workspace_bytes": result["workspace_bytes"],
                      "copied_bytes": result["copied_bytes"],
                      "worker_exited_normally": True}
            self.accepted("past-the-parser-s-boundary", record); return
        if path == "/api/the-state-execution-returns-to":
            if not state["vault_boundary_controlled"]:
                self.send_json(403, {"error": "accepted DVL1 boundary access required"}); return
            if set(request) != {"case_id", "build_id", "record_b64"} or request.get("case_id") != "DV-CRR-4417" or request.get("build_id") != "DVL-WORKER-R5":
                self.send_json(409, {"error": "diagnostic execution binding rejected"}); return
            correlation = str(uuid.uuid4()); raw = decode_vault_record(request)
            result = run_vault("--execute", raw, correlation) if raw is not None else None
            if result is None or result.get("correlation") != correlation or result.get("history_id") != "HIST-APR-CRR-09":
                self.send_json(409, {"error": "saved execution state rejected"}); return
            history = {
                "record_id": "HIST-APR-CRR-09", "revision": 9,
                "classification": "restricted-maintenance-history",
                "entries": [
                    {"decision": "APR-CRR-2019-117", "asset": "AST-CRR-017",
                     "disposition": "superseded", "basis": "legacy outlet commissioning"},
                    {"decision": "APR-CRR-2024-204", "asset": "FIT-CRR-204B",
                     "disposition": "expired", "basis": "calibration exception review"},
                ],
                "current_approval": False, "control_authority": False,
            }
            digest = hashlib.sha256(json.dumps(history, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            execution = {"execution_id": f"DVL-EXEC-{correlation}", "correlation": correlation,
                         "history_id": "HIST-APR-CRR-09", "history_digest": digest,
                         "principal": result["principal"], "return_state": result["return_state"],
                         "history": history}
            state["vault_saved_state_controlled"] = True; state["vault_execution"] = execution
            atomic_json(STATE, state)
            record = {key: value for key, value in execution.items() if key != "history"}
            record.update({"record_id": "DVL-STATE-CRR-R5", "revision": 5,
                           "canary_preserved": True, "worker_exited_normally": True})
            self.accepted("the-state-execution-returns-to", record, correlation=correlation); return
        if path == "/api/the-diagnostic-service-s-authority":
            execution = state.get("vault_execution")
            if not state["vault_saved_state_controlled"] or not isinstance(execution, dict):
                self.send_json(403, {"error": "controlled diagnostic execution required"}); return
            expected = {"execution_id": execution["execution_id"], "correlation": execution["correlation"],
                        "history_id": "HIST-APR-CRR-09", "history_digest": execution["history_digest"]}
            if request != expected:
                self.send_json(409, {"error": "history export binding rejected"}); return
            cached = state.get("vault_history_response")
            if isinstance(cached, dict):
                self.send_json(201, cached); return
            history = execution["history"]
            output = ROOT / "artifacts/the-diagnostic-service-s-authority/result.json"
            atomic_json(output, history)
            record = {"record_id": "HIST-EXPORT-CRR-09", "revision": 9,
                      "history_id": "HIST-APR-CRR-09", "history_digest": execution["history_digest"],
                      "execution_id": execution["execution_id"], "correlation": execution["correlation"],
                      "principal": "svc-diagnostic-vault", "current_approval": False,
                      "control_authority": False}
            response = {"audit_id": append_audit("the-diagnostic-service-s-authority", record),
                        "record": record, "history": history}
            state["vault_history_response"] = response; atomic_json(STATE, state)
            self.send_json(201, response); return
        self.send_json(404, {"error": "record not found"})


def main() -> None:
    if not STATE.exists():
        atomic_json(STATE, INITIAL)
    else:
        state = load_state()
        if any(key not in state for key in INITIAL):
            for key, value in INITIAL.items(): state.setdefault(key, value)
            atomic_json(STATE, state)
    AUDIT.parent.mkdir(parents=True, exist_ok=True); AUDIT.touch(mode=0o640, exist_ok=True)
    ORACLE_LOG.touch(mode=0o640, exist_ok=True)
    SEEN_CIPHERTEXTS.update(line for line in ORACLE_LOG.read_text().splitlines() if line)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain("/tmp/server.crt", "/tmp/server.key")
    server = ThreadingHTTPServer(("0.0.0.0", 443), Handler); server.socket = context.wrap_socket(server.socket, server_side=True)
    server.serve_forever()


if __name__ == "__main__": main()
