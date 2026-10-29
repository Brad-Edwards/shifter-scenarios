#!/usr/bin/env python3
"""Discovery-first happy-path journey through every ARWC card (W01-W35).

This journey is the connected participant experience for the ARWC phase. The
harness runs on the host. Every participant action runs inside the supplied
connector workstation (`cinder-arwc-connector`) as user `fieldlink`, using only
the corporate session and customer transition handover the participant is given.

Rules this journey keeps:
- It starts from the supplied connector handover: the `corporate-session` token
  and `customer-transition.json` under `/var/lib/fieldlink-connector/handover`.
- It derives every route host, record identifier, token and value from that
  handover or from an earlier response. It never embeds an author-only value.
- It carries discovered evidence forward across cards and operations.

The journey consumes single-use state and must run from a pristine range.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
import unittest
import uuid

sys.path.insert(0, os.path.dirname(__file__))
from test_w08_live import reconstruct as w08_reconstruct  # noqa: E402 (reuse the existing erasure-coding math)
from test_w31_live import (  # noqa: E402 (reuse the existing binary-format/ELF parsing helpers)
    crc32c as w31_crc32c, dvl1 as w31_dvl1, elf_symbol as w31_elf_symbol,
    elf_string_vaddr as w31_elf_string_vaddr, elf_posture as w31_elf_posture,
)


CONTAINER = "cinder-arwc-connector"
HANDOVER = "/var/lib/fieldlink-connector/handover"
CA = "/tmp/arwc-ca.crt"


def inside(*arguments: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    """Run a command inside the connector workstation as the participant user."""
    return subprocess.run(
        ["docker", "exec", "-i", "--user", "fieldlink", "--workdir", "/var/lib/fieldlink-connector", CONTAINER, *arguments],
        input=input_text, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )


_REQUEST = r'''
import json
import re, pathlib, ssl, sys, tempfile, urllib.error, urllib.request
method, url, tenant, supplied, extra, body, certificate, private_key = sys.argv[1:]
if supplied == "@session":
    supplied = pathlib.Path("/var/lib/fieldlink-connector/handover/corporate-session").read_text().strip()
headers = {"X-ARWC-Tenant": tenant}
if supplied:
    headers["Authorization"] = "Bearer " + supplied
for name, value in json.loads(extra).items():
    if value == "@planner":
        value = pathlib.Path("/var/lib/fieldlink-connector/receipts/planner-session").read_text().strip()
    elif value == "@planning":
        value = pathlib.Path("/var/lib/fieldlink-connector/receipts/planner-handover").read_text().strip()
    headers[name] = value
data = None if not body else body.encode()
if data is not None:
    headers["Content-Type"] = "application/json"
context = ssl.create_default_context(cafile="/tmp/arwc-ca.crt")
with tempfile.TemporaryDirectory() as directory:
    if certificate:
        cert_path = pathlib.Path(directory) / "client.crt"; cert_path.write_text(certificate)
        key_path = pathlib.Path(directory) / "client.key"; key_path.write_text(private_key)
        context.load_cert_chain(cert_path, key_path)
    try:
        response = urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers, method=method), context=context, timeout=30)
    except urllib.error.HTTPError as error:
        response = error
    print(response.status)
    print(response.read().decode())
'''


def request(url: str, *, method: str = "GET", body: dict | None = None,
            token: str | None = None, tenant: str = "arwc", expected: int | None = None,
            headers: dict | None = None, certificate: str = "", private_key: str = "") -> tuple[int, dict]:
    """Issue a request from the connector workstation with its CA and tenant header."""
    completed = inside(
        "python3", "-c", _REQUEST, method, url, tenant,
        "@session" if token is None else token,
        json.dumps(headers or {}),
        "" if body is None else json.dumps(body, separators=(",", ":")),
        certificate, private_key,
    )
    if completed.returncode:
        raise AssertionError(completed.stderr)
    status_line, _, payload = completed.stdout.partition("\n")
    status = int(status_line)
    data = json.loads(payload) if payload.strip() else {}
    if expected is not None and status != expected:
        raise AssertionError(f"{method} {url} -> {status} (want {expected}): {payload[:300]}")
    return status, data


_GET_BYTES = r'''
import base64, pathlib, ssl, sys, urllib.error, urllib.request
url, tenant, supplied = sys.argv[1:]
if supplied == "@session":
    supplied = pathlib.Path("/var/lib/fieldlink-connector/handover/corporate-session").read_text().strip()
headers = {"X-ARWC-Tenant": tenant}
if supplied:
    headers["Authorization"] = "Bearer " + supplied
context = ssl.create_default_context(cafile="/tmp/arwc-ca.crt")
try:
    response = urllib.request.urlopen(urllib.request.Request(url, headers=headers), context=context, timeout=30)
except urllib.error.HTTPError as error:
    response = error
print(response.status)
print(response.headers.get_content_type())
print(base64.b64encode(response.read()).decode())
'''


def get_bytes(url: str, *, token: str | None = None, tenant: str = "arwc", expected: int = 200) -> tuple[bytes, str]:
    """Fetch a binary artifact (not JSON) from the connector workstation."""
    completed = inside("python3", "-c", _GET_BYTES, url, tenant, "@session" if token is None else token)
    if completed.returncode:
        raise AssertionError(completed.stderr)
    status_line, content_type, encoded = completed.stdout.splitlines()
    if int(status_line) != expected:
        raise AssertionError(f"GET {url} -> {status_line} (want {expected})")
    return base64.b64decode(encoded), content_type


_MAKE_ARCHIVE = r'''
import base64, pathlib, subprocess, sys, tempfile
with tempfile.TemporaryDirectory() as directory:
    root = pathlib.Path(directory); member = sys.argv[1]
    target = root / member; target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("retained archive request\n")
    subprocess.run(["7zz", "a", str(root / "request.7z"), member], cwd=root, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(base64.b64encode((root / "request.7z").read_bytes()).decode())
'''


def make_archive(member: str) -> str:
    """Build a 7-Zip archive containing a single crafted member path (participant tool)."""
    completed = inside("python3", "-c", _MAKE_ARCHIVE, member)
    if completed.returncode:
        raise AssertionError(completed.stderr)
    return completed.stdout.strip()


def bolt_pack(value: object) -> bytes:
    """Encode a value in the Bolt PackStream wire format (participant tool)."""
    if value is False:
        return b"\xc2"
    if value is True:
        return b"\xc3"
    if isinstance(value, int) and -16 <= value < 128:
        return bytes([value & 0xFF])
    if isinstance(value, str):
        encoded = value.encode()
        if len(encoded) < 16:
            return bytes([0x80 + len(encoded)]) + encoded
        if len(encoded) < 256:
            return b"\xd0" + bytes([len(encoded)]) + encoded
        return b"\xd1" + len(encoded).to_bytes(2, "big") + encoded
    if isinstance(value, dict):
        return bytes([0xA0 + len(value)]) + b"".join(bolt_pack(str(k)) + bolt_pack(v) for k, v in value.items())
    raise ValueError(value)


def bolt_structure(signature: int, *fields: object) -> bytes:
    return bytes([0xB0 + len(fields), signature]) + b"".join(bolt_pack(f) for f in fields)


def bolt_chunk(payload: bytes) -> bytes:
    return len(payload).to_bytes(2, "big") + payload + b"\x00\x00"


def bolt_exchange(magic: bytes, version: bytes, *, asset: str, association: str, relation: str, ou: str, query: str) -> str:
    """Build a Bolt HELLO+RUN+PULL exchange carrying a crafted certificate_ou field."""
    value = magic + version + bytes(12)
    value += bolt_chunk(bolt_structure(0x01, {"user_agent": "arwc-reltool/3"}))
    value += bolt_chunk(bolt_structure(0x10, query, {"asset": asset, "association": association, "certificate_ou": ou}, {}))
    value += bolt_chunk(bolt_structure(0x3F, {"n": -1}))
    return base64.b64encode(value).decode()


def bolt_response_signatures(encoded: str, version: bytes) -> list[int]:
    value = base64.b64decode(encoded, validate=True)
    if value[:4] != version:
        raise AssertionError("wrong negotiated Bolt version")
    result: list[int] = []
    offset = 4
    while offset < len(value):
        length = int.from_bytes(value[offset:offset + 2], "big")
        offset += 2
        payload = value[offset:offset + length]
        offset += length
        if value[offset:offset + 2] != b"\x00\x00":
            raise AssertionError("missing Bolt chunk terminator")
        offset += 2
        result.append(payload[1])
    return result


def cbor_text(value: str) -> bytes:
    """Encode a short text string in CBOR (participant tool, for the v2 field protocol)."""
    encoded = value.encode()
    if len(encoded) < 24:
        return bytes([0x60 + len(encoded)]) + encoded
    if len(encoded) < 256:
        return b"\x78" + bytes([len(encoded)]) + encoded
    raise ValueError("text too long")


def cbor_map(value: dict[str, str]) -> bytes:
    if len(value) >= 24:
        raise ValueError("map too large")
    return bytes([0xA0 + len(value)]) + b"".join(cbor_text(k) + cbor_text(v) for k, v in value.items())


def cbor_request(url: str, body: bytes, token: str, *, expected: int | None = None) -> tuple[int, dict]:
    """POST a raw CBOR body with a bearer token (the field gateway's v2 protocol)."""
    script = (
        "import json, ssl, sys, urllib.error, urllib.request\n"
        "url, token = sys.argv[1:]\n"
        "data = sys.stdin.buffer.read()\n"
        'headers = {"Authorization": "Bearer " + token, "X-ARWC-Tenant": "arwc", "Content-Type": "application/cbor"}\n'
        "context = ssl.create_default_context(cafile='/tmp/arwc-ca.crt')\n"
        "try: response = urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers, method='POST'), context=context)\n"
        "except urllib.error.HTTPError as error: response = error\n"
        "print(response.status); print(response.read().decode())\n"
    )
    completed = subprocess.run(
        ["docker", "exec", "-i", "--user", "fieldlink", CONTAINER, "python3", "-c", script, url, token],
        input=body, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if completed.returncode:
        raise AssertionError(completed.stderr.decode())
    status_line, _, payload = completed.stdout.decode().partition("\n")
    status = int(status_line)
    data = json.loads(payload) if payload.strip() else {}
    if expected is not None and status != expected:
        raise AssertionError(f"POST {url} -> {status} (want {expected}): {payload[:300]}")
    return status, data


def w19_rotl(value: int, count: int, width: int) -> int:
    mask = (1 << width) - 1
    return ((value << count) | (value >> (width - count))) & mask


def w19_rolling(record: str) -> int:
    """The binary's rolling hash, recovered by reading its disassembly (participant tool)."""
    mask32 = (1 << 32) - 1
    value = 0x6D2B79F5
    for byte in record.encode():
        value = (w19_rotl((value ^ byte) & mask32, 5, 32) + 0x9E3779B9) & mask32
    return value


def w19_verifier(record: str) -> int:
    mask64 = (1 << 64) - 1
    value = w19_rolling(record)
    return w19_rotl(0x243F6A8885A308D3 ^ ((value * 0x100000001B3) & mask64), 9, 64) ^ value


def w22_run_vm(program: bytes) -> tuple[list[int], bytes, int]:
    """Reimplementation of the sealed viewer's small bytecode VM (recovered by disassembly)."""
    registers = [0, 0, 0, 0]
    memory = bytearray(256)
    zero = False
    pc = steps = 0
    while 0 <= pc < len(program) // 6 and steps < 4096:
        opcode, dst, src, immediate = struct.unpack_from("<HBBH", program, pc * 6)
        steps += 1
        if opcode == 1:
            registers[dst] = immediate; zero = registers[dst] == 0; pc += 1
        elif opcode == 2:
            registers[dst] = memory[(registers[src] + immediate) & 255]; zero = registers[dst] == 0; pc += 1
        elif opcode == 3:
            registers[dst] = (registers[dst] ^ registers[src] ^ immediate) & 65535; zero = registers[dst] == 0; pc += 1
        elif opcode == 4:
            registers[dst] = (registers[dst] + registers[src] + immediate) & 65535; zero = registers[dst] == 0; pc += 1
        elif opcode == 5:
            shift = immediate & 15; value = registers[src]
            registers[dst] = value if not shift else ((value << shift) | (value >> (16 - shift))) & 65535
            zero = registers[dst] == 0; pc += 1
        elif opcode == 6:
            memory[(registers[dst] + immediate) & 255] = registers[src] & 255; pc += 1
        elif opcode == 7:
            pc = pc + struct.unpack("<h", struct.pack("<H", immediate))[0] if not zero else pc + 1
        elif opcode == 255:
            break
        else:
            raise AssertionError(opcode)
    return registers, bytes(memory), steps


def w22_public(program: bytes) -> dict:
    registers, memory, steps = w22_run_vm(program)
    return {"registers": registers, "memory_40_80_sha256": hashlib.sha256(memory[0x40:0x80]).hexdigest(), "steps": steps}


MASK128 = (1 << 128) - 1
ROT128_IV = int("6a09e667f3bcc908bb67ae8584caa73b", 16)


def w27_rotl128(value: int, count: int) -> int:
    return ((value << count) | (value >> (128 - count))) & MASK128


def w27_rot128(data: bytes) -> int:
    """The native verifier's digest, recovered by reversing its binary (participant tool)."""
    length = len(data)
    material = data + b"\x80"
    material += b"\0" * ((-len(material)) % 16)
    state = ROT128_IV
    for offset in range(0, len(material), 16):
        block = int.from_bytes(material[offset:offset + 16], "little")
        state = w27_rotl128(state, 17) ^ block ^ w27_rotl128(block, 41)
    return (state ^ w27_rotl128(state, 29) ^ length) & MASK128


def w27_solve_collision(seed: bytes, base: bytes, reservoir_bits: list[int]) -> bytes:
    """Find a non-identical input with the same rot128 digest as `base`, by
    treating candidate single-bit flips as a GF(2) linear system."""
    target = w27_rot128(seed) ^ w27_rot128(base)
    basis: dict[int, tuple[int, int]] = {}
    for bit in reservoir_bits:
        changed = bytearray(seed); changed[bit // 8] ^= 1 << (bit % 8)
        vector, mask = w27_rot128(bytes(changed)) ^ w27_rot128(seed), 1 << bit
        while vector:
            pivot = vector.bit_length() - 1
            if pivot in basis:
                vector ^= basis[pivot][0]; mask ^= basis[pivot][1]
            else:
                basis[pivot] = vector, mask
                break
    solution, vector = 0, target
    while vector:
        pivot = vector.bit_length() - 1
        if pivot not in basis:
            raise AssertionError(f"GF(2) system cannot reduce pivot {pivot}")
        vector ^= basis[pivot][0]; solution ^= basis[pivot][1]
    candidate = bytearray(seed)
    for bit in reservoir_bits:
        if solution & (1 << bit):
            candidate[bit // 8] ^= 1 << (bit % 8)
    result = bytes(candidate)
    if result == base or w27_rot128(result) != w27_rot128(base):
        raise AssertionError("collision solver did not produce a non-identical collision")
    return result


def crc32c(value: bytes) -> int:
    crc = 0xFFFFFFFF
    for byte in value:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ (0x82F63B78 if crc & 1 else 0)
    return crc ^ 0xFFFFFFFF


def write_receipt(name: str, value: str) -> None:
    """Save a recovered token into the participant's receipts directory."""
    result = inside("sh", "-c", f"umask 077; cat > /var/lib/fieldlink-connector/receipts/{name}", input_text=value)
    if result.returncode:
        raise AssertionError(result.stderr)


def inside_bytes(*arguments: str) -> subprocess.CompletedProcess:
    """Run a command inside the workstation and return raw (undecoded) output."""
    return subprocess.run(
        ["docker", "exec", "-i", "--user", "fieldlink", CONTAINER, *arguments],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )


def write_bytes(path: str, data: bytes, *, mode: str = "0700") -> None:
    """Write raw bytes to a path inside the connector workstation."""
    result = subprocess.run(
        ["docker", "exec", "-i", "--user", "fieldlink", CONTAINER, "sh", "-c", f"umask 077; cat > {path} && chmod {mode} {path}"],
        input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if result.returncode:
        raise AssertionError(result.stderr.decode())


def read_handover(name: str) -> str:
    result = inside("cat", f"{HANDOVER}/{name}")
    if result.returncode:
        raise AssertionError(f"handover file not found: {name}: {result.stderr}")
    return result.stdout


class ARWCJourney(unittest.TestCase):
    """One connected ARWC journey; methods run in card order and share evidence."""

    maxDiff = None
    evidence: dict[str, object] = {}

    @classmethod
    def setUpClass(cls) -> None:
        # The participant is handed the corporate session and the transition note.
        cls.transition = json.loads(read_handover("customer-transition.json"))

    @classmethod
    def host(cls, key: str) -> str:
        """Resolve a service base URL from the supplied customer transition note."""
        value = cls.transition.get(key)
        if not value:
            raise AssertionError(f"service not listed in customer transition: {key}")
        return value

    # ------------------------------------------------------------------ W01
    def test_w01_customer_copy(self) -> None:
        base = self.host("customer_handover")

        with self.subTest(card="W01.1 the customer's copy"):
            status, response = request(f"{base}/api/the-customer-s-copy", expected=200)
            record = response["record"]
            # The copy is bound to the delivered customer and active connector.
            self.assertEqual(record["tenant"], self.transition["tenant"])
            self.assertEqual(record["active_connector"], self.transition["active_connector"])
            self.evidence["customer_record"] = record

        with self.subTest(card="W01.2 the planner's unfinished handover"):
            status, response = request(f"{base}/api/the-planner-s-unfinished-handover", expected=200)
            record = response["record"]
            self.assertNotIn("customer_receipt", record)
            self.evidence["planner_handover"] = record

        with self.subTest(card="W01.3 how the company buys time"):
            status, response = request(f"{base}/api/how-the-company-buys-time", expected=200)
            record = response["record"]
            self.assertTrue(record["planning_reference"])
            self.assertTrue(record["measures"])

        with self.subTest(card="W01.4 change the corporate record"):
            original = self.evidence["planner_handover"]
            content = "# Cinder inspection summary\n\nOutlet inspection remains scheduled for 18 September.\n"
            # The change must carry the record's immutable bindings unchanged.
            body = {
                "record_id": original["record_id"],
                "expected_revision": original["revision"],
                "inspection": original["inspection"],
                "assignee": original["assignee"],
                "attachment": {"filename": "cinder-inspection-summary.md", "content": content},
            }
            status, changed = request(f"{base}/api/change-the-corporate-record", method="POST", body=body, expected=201)
            self.assertEqual(changed["attachment_sha256"], hashlib.sha256(content.encode()).hexdigest())
            self.assertEqual(changed["inspection"], original["inspection"])
            # A replayed stale-revision change is refused.
            status, _ = request(f"{base}/api/change-the-corporate-record", method="POST", body=body)
            self.assertEqual(status, 409)

    # ------------------------------------------------------------------ W02
    def test_w02_asset_association(self) -> None:
        base = self.host("business_workplace")

        with self.subTest(card="W02.1 the asset and the contractor"):
            status, response = request(f"{base}/api/the-asset-and-the-contractor", expected=200)
            self.assertIn("record", response)
            self.evidence["asset_bundle"] = response["record"]

        with self.subTest(card="W02.2 three names for one job"):
            status, response = request(f"{base}/api/three-names-for-one-job", expected=200)
            sources = response["record"]["sources"]
            self.assertIn("work_order", sources)
            self.evidence["work_order"] = sources["work_order"]["id"]

        with self.subTest(card="W02.3 the record behind the wrong association"):
            # The merge authorization trusts the supplied association row; the
            # alternate association for this work order reaches the protected merge.
            suffix = self.evidence["work_order"].split("-", 1)[1]
            association = f"ASC-{suffix}-ALT"
            status, result = request(
                f"{base}/api/the-record-behind-the-wrong-association", method="POST",
                body={"association_id": association, "expected_revision": 6}, expected=201)
            self.assertTrue(result["record"]["record_id"])
            # An unrelated association is refused.
            status, _ = request(
                f"{base}/api/the-record-behind-the-wrong-association", method="POST",
                body={"association_id": "ASC-MER-1000", "expected_revision": 6})
            self.assertEqual(status, 409)

    # ------------------------------------------------------------------ W03
    def test_w03_annex_reference(self) -> None:
        base = self.host("business_workplace")

        with self.subTest(card="W03.1 an annex left with the order"):
            status, response = request(f"{base}/api/an-annex-left-with-the-order", expected=200)
            record = response["record"]
            self.evidence["process_data_handover"] = record["process_data_handover"]

        with self.subTest(card="W03.2 a reference outside the order"):
            handover = self.evidence["process_data_handover"]
            # A plain restricted reference is refused; a validate-before-decode
            # traversal from the attachments namespace reaches it.
            status, _ = request(
                f"{base}/api/a-reference-outside-the-order", method="POST",
                body={"reference": f"restricted/{handover}"})
            self.assertEqual(status, 409)
            status, imported = request(
                f"{base}/api/a-reference-outside-the-order", method="POST",
                body={"reference": f"attachments/%2e%2e%2frestricted%2f{handover}"}, expected=201)
            self.assertEqual(imported["record"]["record_id"], handover)

        with self.subTest(card="W03.3 the integration's read contract"):
            status, contract = request(f"{base}/api/the-integration-s-read-contract", expected=200)
            self.assertEqual(contract["record"]["record_id"], self.evidence["process_data_handover"])
            self.evidence["read_contract"] = contract["record"]

    # ------------------------------------------------------------------ W04
    def test_w04_archive_helper(self) -> None:
        base = self.host("retained_archive")

        with self.subTest(card="W04.1 the archive's missing contract"):
            status, response = request(f"{base}/api/the-archive-s-missing-contract", expected=200)
            record = response["record"]
            self.evidence["archive_token"] = record["enrollment_token"]
            self.evidence["protected_record"] = record["protected_record"]
            self.evidence["planner_target"] = record["planner_handover_target"]

        with self.subTest(card="W04.2 the query behind the identity"):
            # The enrollment copies the caller-supplied OU into the backend query;
            # a subject injection reaches the protected archive record.
            protected = self.evidence["protected_record"]
            ou = f"MaintenanceArchive' OR r.id='{protected}' OR 'a'='b"
            status, enrolled = request(
                f"{base}/api/the-query-behind-the-identity", method="POST",
                body={"operation": "enroll", "enrollment_token": self.evidence["archive_token"], "organizational_unit": ou},
                expected=201)
            status, result = request(
                f"{base}/api/the-query-behind-the-identity", method="POST", body={"operation": "query"},
                certificate=enrolled["certificate"], private_key=enrolled["private_key"], expected=201)
            self.assertEqual(result["record"]["record_id"], protected)

        with self.subTest(card="W04.3 the archive helper acts"):
            # A fullwidth (NFKC) traversal member passes the raw-member check and
            # normalizes to the protected copy_handover path.
            crafted = make_archive(f"．．／copy_handover({self.evidence['planner_target']})")
            status, response = request(
                f"{base}/api/the-archive-helper-acts", method="POST", body={"archive": crafted}, expected=201)
            self.assertEqual(response["record"]["record_id"], self.evidence["planner_target"])
            # The recovered planner handover token is saved for the planning path.
            write_receipt("planner-handover", response["planner_handover"])
            self.evidence["planner_handover_token"] = response["planner_handover"]

    # ------------------------------------------------------------------ W05
    def test_w05_temporary_identity(self) -> None:
        base = self.host("corporate_identity")

        with self.subTest(card="W05.1 a starter pack left open"):
            status, starter = request(f"{base}/api/a-starter-pack-left-open", expected=200)
            record = starter["record"]
            self.assertIsNone(record["activation_secret"])
            self.evidence["temp_employee"] = record["employee_number"]
            self.evidence["temp_assignment"] = record["assignment"]

        with self.subTest(card="W05.2 the activation roster"):
            status, roster = request(f"{base}/api/the-activation-roster", expected=200)
            self.evidence["activation_code"] = roster["record"]["activation_code"]
            self.assertNotEqual(roster["record"]["approved_assignment"], self.evidence["temp_assignment"])

        with self.subTest(card="W05.3 temporary, with the wrong rights"):
            # Activation checks the code but omits the assignment binding, so the
            # starter's own assignment is granted instead of the approved one.
            status, _ = request(
                f"{base}/api/temporary-with-the-wrong-rights", method="POST",
                body={"employee_number": self.evidence["temp_employee"], "activation_code": "000000", "requested_assignment": self.evidence["temp_assignment"]})
            self.assertEqual(status, 409)
            status, response = request(
                f"{base}/api/temporary-with-the-wrong-rights", method="POST",
                body={"employee_number": self.evidence["temp_employee"], "activation_code": self.evidence["activation_code"], "requested_assignment": self.evidence["temp_assignment"]},
                expected=201)
            self.assertEqual(response["record"]["assignment"], self.evidence["temp_assignment"])
            self.assertFalse(response["record"]["administrative"])
            self.evidence["limited_session"] = response["limited_session"]

    # ------------------------------------------------------------------ W06
    def test_w06_planner_session(self) -> None:
        base = self.host("corporate_identity")
        access = {"X-ARWC-Planning-Access": self.evidence["limited_session"]}
        preview_origin = "https://preview-cinder.arwc.test"

        with self.subTest(card="W06.1 the planner's login trail"):
            status, response = request(f"{base}/api/the-planner-s-login-trail", headers=access, expected=200)
            record = response["record"]
            self.evidence["oauth_transaction"] = record["oauth_transaction"]
            self.evidence["oauth_state"] = record["oauth_state"]
            self.evidence["planner_drawing"] = record.get("drawing", "DRW-OG2-R8")
            self.evidence["planner_review"] = record["review"]
            # A wrong planning access is refused.
            status, _ = request(f"{base}/api/the-planner-s-login-trail", headers={"X-ARWC-Planning-Access": "wrong"})
            self.assertEqual(status, 403)

        with self.subTest(card="W06.2 a drawing in the wrong context"):
            status, response = request(
                f"{base}/api/a-drawing-in-the-wrong-context", method="POST", headers=access,
                body={"oauth_state": self.evidence["oauth_state"], "drawing": self.evidence["planner_drawing"],
                      "review": self.evidence["planner_review"], "preview_origin": preview_origin}, expected=201)
            self.assertEqual(response["record"]["preview_origin"], preview_origin)

        with self.subTest(card="W06.3 a planner session that works"):
            status, response = request(
                f"{base}/api/a-planner-session-that-works", method="POST", headers=access,
                body={"oauth_transaction": self.evidence["oauth_transaction"], "preview_origin": preview_origin}, expected=201)
            self.assertEqual(response["record"]["scope"], "planning-records")
            write_receipt("planner-session", response["planner_session"])
            self.evidence["planner_session"] = response["planner_session"]

    # ------------------------------------------------------------------ W07
    def test_w07_planning_query(self) -> None:
        base = self.host("planning_data")
        planner = {"X-ARWC-Planner-Session": "@planner"}

        with self.subTest(card="W07.1 the query the planner keeps"):
            status, response = request(f"{base}/api/the-query-the-planner-keeps", headers=planner, expected=200)
            record = response["record"]
            self.evidence["report_view"] = record["view"]
            self.evidence["quote"] = record["identifier_quote"]

        with self.subTest(card="W07.2 read beyond the allowed statement"):
            # The ordinary quoted-identifier request reveals the exact column list.
            status, ordinary = request(
                f"{base}/api/read-beyond-the-allowed-statement", method="POST", headers=planner,
                body={"report_name": self.evidence["report_view"]}, expected=201)
            columns = re.search(r"SELECT ([a-z_,]+) FROM", ordinary["statement"]).group(1)
            q = self.evidence["quote"]
            # Close the quoted identifier and UNION in the protected allocation view.
            injection = f'{self.evidence["report_view"]}{q} UNION ALL SELECT {columns} FROM district_allocation_adjustment --'
            status, response = request(
                f"{base}/api/read-beyond-the-allowed-statement", method="POST", headers=planner,
                body={"report_name": injection}, expected=201)
            self.assertIn("UNION ALL SELECT", response["statement"])
            self.evidence["allocation_record"] = response["record"]["record_id"]
            # A write or semicolon attempt is refused.
            status, _ = request(
                f"{base}/api/read-beyond-the-allowed-statement", method="POST", headers=planner,
                body={"report_name": f'{self.evidence["report_view"]}{q} DELETE FROM {self.evidence["report_view"]} --'})
            self.assertIn(status, (403, 409))

        with self.subTest(card="W07.3 the database does more than read"):
            # The allocation adjustment names its reconciliation record (ADJ -> REC).
            reconcile_record = self.evidence["allocation_record"].replace("ADJ-", "REC-")
            status, response = request(
                f"{base}/api/the-database-does-more-than-read", method="POST", headers=planner,
                body={"function": "arwc_reconcile_copy", "record_id": reconcile_record}, expected=201)
            self.assertEqual(response["record"]["execution_context"], "SECURITY DEFINER")
            self.assertEqual(response["record"]["source_record"], reconcile_record)

    # ------------------------------------------------------------------ W09
    def test_w09_water_reconciliation(self) -> None:
        planning = self.host("planning_data")
        business = self.host("business_workplace")
        planner = {"X-ARWC-Planner-Session": "@planner"}

        with self.subTest(card="W09.1 water already promised"):
            status, response = request(f"{planning}/api/water-already-promised", headers=planner, expected=200)
            ledger = response["record"]
            self.evidence["ledger_record"] = ledger["record_id"]
            self.evidence["planning_window"] = ledger["planning_window"]
            self.evidence["committed_ml"] = ledger["committed_ml"]

        with self.subTest(card="W09.2 the meter's own account"):
            status, response = request(f"{planning}/api/the-meter-s-own-account", headers=planner, expected=200)
            meter = response["record"]
            # The meter export is a distinct record; it does not carry the ledger's identity.
            self.assertNotIn(self.evidence["ledger_record"], json.dumps(meter))
            self.evidence["usable_reserve_ml"] = meter["usable_reserve_ml"]
            self.evidence["instruments"] = meter["instruments"]
            self.evidence["meter_record"] = meter["record_id"]

        with self.subTest(card="W09.3 the missing megalitre"):
            # Reconciliation requires both independent sources (ledger + meter).
            status, response = request(f"{planning}/api/the-missing-megalitre", headers=planner, expected=200)
            record = response["record"]
            self.assertEqual(record["committed_ml"], self.evidence["committed_ml"])
            self.assertEqual(record["usable_reserve_ml"], self.evidence["usable_reserve_ml"])
            self.evidence["reconciliation_record"] = record["record_id"]
            self.evidence["reported_ml"] = record["reported_ml"]
            self.evidence["outlet_group"] = record["outlet_group"]

        with self.subTest(card="W09.4 from the report to the live feed"):
            status, contract = request(f"{business}/api/the-integration-s-read-contract", expected=200)
            # planning-data requires both the planner session and the integration session.
            integration = {**planner, "X-ARWC-Integration-Session": contract["integration_session"]}
            client = contract["record"]["integration_client"]
            scope = contract["record"]["scope"]
            # The report's current source list names the live feed record to join.
            status, sources = request(f"{business}/api/the-report-s-source-list", expected=200)
            feed_id = next(s["record_id"] for s in sources["record"]["sources"] if s["record_id"].startswith("FEED-"))
            self.evidence["feed_id"] = feed_id
            # Without the integration session, the gateway refuses even a correct binding.
            binding = {"integration_client": client, "report_binding": self.evidence["reconciliation_record"],
                       "scope": scope, "feed": feed_id}
            status, _ = request(f"{planning}/api/integration/from-the-report-to-the-live-feed", method="POST", headers=planner, body=binding)
            self.assertEqual(status, 403)
            # A wrong client is refused once the session is supplied.
            status, _ = request(f"{planning}/api/integration/from-the-report-to-the-live-feed", method="POST",
                                 headers=integration, body=dict(binding, integration_client="INT-MER-01"))
            self.assertEqual(status, 409)
            status, response = request(f"{planning}/api/integration/from-the-report-to-the-live-feed", method="POST",
                                        headers=integration, body=binding, expected=201)
            self.assertTrue(response["record"]["current"])
            self.assertEqual(response["record"]["outlet_group"], self.evidence["outlet_group"])

    # ------------------------------------------------------------------ W10
    def test_w10_cross_district_excerpt(self) -> None:
        base = self.host("business_workplace")

        with self.subTest(card="W10.1 the report's source list"):
            status, response = request(f"{base}/api/the-report-s-source-list", expected=200)
            record = response["record"]
            self.evidence["source_set"] = record["record_id"]
            self.evidence["source_revision"] = record["revision"]
            self.evidence["source_district"] = record["district"]

        with self.subTest(card="W10.2 another district in the results"):
            # The handler checks the role and the exact source set/revision, but
            # not that the requested district matches the session's own district.
            baseline = {"source_set": self.evidence["source_set"], "expected_revision": self.evidence["source_revision"],
                        "role": "planning-reader", "district": self.evidence["source_district"]}
            status, _ = request(f"{base}/api/another-district-in-the-results", method="POST", body=dict(baseline, expected_revision=baseline["expected_revision"] - 1))
            self.assertEqual(status, 409)
            status, _ = request(f"{base}/api/another-district-in-the-results", method="POST", body=dict(baseline, role="customer-service"))
            self.assertEqual(status, 403)
            status, response = request(f"{base}/api/another-district-in-the-results", method="POST", body=baseline, expected=201)
            excerpt = response["record"]
            self.assertNotEqual(excerpt["district"], self.evidence["source_district"])
            self.evidence["excerpt_id"] = excerpt["record_id"]
            self.evidence["excerpt_revision"] = excerpt["revision"]
            self.evidence["linked_document"] = excerpt["linked_document"]

        with self.subTest(card="W10.3 the document behind the answer"):
            # Linking is checked by possession of the exact excerpt, not district.
            status, _ = request(f"{base}/api/the-document-behind-the-answer", method="POST",
                                 body={"excerpt_id": self.evidence["excerpt_id"], "expected_revision": self.evidence["excerpt_revision"] - 1})
            self.assertEqual(status, 409)
            status, response = request(f"{base}/api/the-document-behind-the-answer", method="POST",
                                        body={"excerpt_id": self.evidence["excerpt_id"], "expected_revision": self.evidence["excerpt_revision"], "district": self.evidence["source_district"]},
                                        expected=201)
            self.assertEqual(response["record"]["record_id"], self.evidence["linked_document"])

    # ------------------------------------------------------------------ W11
    def test_w11_relation_protocol(self) -> None:
        base = self.host("planning_data")
        planner = {"X-ARWC-Planner-Session": "@planner"}
        asset = self.evidence["asset_bundle"]["asset"]

        with self.subTest(card="W11.1 the relation service's language"):
            status, response = request(f"{base}/api/the-relation-service-s-language", headers=planner, expected=200)
            contract = response["record"]
            magic = bytes.fromhex(contract["magic"].replace(" ", ""))
            major, minor = (int(part) for part in contract["protocol"].rsplit(" ", 1)[1].split("."))
            version = bytes([0, 0, minor, major])
            self.evidence["bolt"] = {"magic": magic, "version": version, "relation": contract["relation"], "association": contract["association"]}

        with self.subTest(card="W11.2 an exchange the backend accepts"):
            bolt = self.evidence["bolt"]
            exchange = bolt_exchange(bolt["magic"], bolt["version"], asset=asset, association=bolt["association"],
                                      relation=bolt["relation"], ou=bolt["relation"],
                                      query="MATCH (a:Asset {record_id: $asset})-[r:RELATION]->(w:Work) RETURN r.record_id,w.record_id")
            status, response = request(f"{base}/api/an-exchange-the-backend-accepts", method="POST", headers=planner, body={"exchange": exchange}, expected=201)
            self.assertEqual(response["record"]["asset"], asset)
            self.evidence["work_order_from_relation"] = response["record"]["work_order"]
            self.assertNotIn("archive", json.dumps(response))

        with self.subTest(card="W11.3 the asset's true lineage"):
            bolt = self.evidence["bolt"]
            # Inject beyond the certificate OU field to traverse to the archived lineage.
            lineage_ou = (
                f"{bolt['relation']}]->(w) WITH a MATCH p=(legacy:Legacy)-[:SUPERSEDES]->"
                "(group:OutletGroup)-[:CURRENT_ASSET]->(a)<-[:ARCHIVED_ASSET]-(archive:Archive) RETURN p //"
            )
            exchange = bolt_exchange(bolt["magic"], bolt["version"], asset=asset, association=bolt["association"],
                                      relation=bolt["relation"], ou=lineage_ou,
                                      query="MATCH (a:Asset {record_id: $asset})-[r:RELATION]->(w:Work) RETURN r.record_id,w.record_id")
            status, response = request(f"{base}/api/the-asset-s-true-lineage", method="POST", headers=planner, body={"exchange": exchange}, expected=201)
            record = response["record"]
            self.assertEqual(record["current_asset"], asset)
            self.assertTrue(record["archive"])
            self.assertEqual(bolt_response_signatures(response["bolt_response"], bolt["version"]), [0x70, 0x70, 0x71, 0x70])

    # ------------------------------------------------------------------ W13
    def test_w13_contractor_checkin(self) -> None:
        base = self.host("contractor_portal")

        with self.subTest(card="W13.1 window on Thursday"):
            status, response = request(f"{base}/api/window-on-thursday", expected=200)
            appointment = response["record"]
            self.evidence["appointment_id"] = appointment["record_id"]
            self.evidence["appointment_window"] = appointment["window"]
            self.evidence["appointment_inspection"] = appointment["inspection"]
            self.evidence["appointment_asset"] = appointment["asset"]

        with self.subTest(card="W13.2 who is expected at the gate"):
            status, response = request(f"{base}/api/who-is-expected-at-the-gate", expected=200)
            roster = response["record"]
            self.evidence["roster_id"] = roster["record_id"]
            self.evidence["contractor_identity"] = roster["identity"]
            self.evidence["contractor_assignment"] = roster["assignment"]

        with self.subTest(card="W13.3 an appointment we do not own"):
            # The expected caller organization is implied by the gate roster's
            # contractor identity, not the appointment's current owner.
            organization = "Veybridge Technical Services"
            baseline = {
                "appointment_id": self.evidence["appointment_id"], "expected_revision": 1,
                "attendee": self.evidence["contractor_identity"], "caller_organization": organization,
                "inspection": self.evidence["appointment_inspection"], "asset": self.evidence["appointment_asset"],
                "window": self.evidence["appointment_window"],
            }
            status, _ = request(f"{base}/api/an-appointment-we-do-not-own", method="POST", body=dict(baseline, asset="AST-MER-004"))
            self.assertEqual(status, 409)
            status, response = request(f"{base}/api/an-appointment-we-do-not-own", method="POST", body=baseline, expected=201)
            self.assertEqual(response["record"]["attendee"], self.evidence["contractor_identity"])

        with self.subTest(card="W13.4 checked in as the contractor"):
            status, _ = request(f"{base}/api/checked-in-as-the-contractor", method="POST",
                                 body={"appointment_id": self.evidence["appointment_id"], "roster_id": "ROSTER-CRR-SEP18-R1", "identity": self.evidence["contractor_identity"]})
            self.assertEqual(status, 403)
            status, response = request(f"{base}/api/checked-in-as-the-contractor", method="POST",
                                        body={"appointment_id": self.evidence["appointment_id"], "roster_id": self.evidence["roster_id"], "identity": self.evidence["contractor_identity"]},
                                        expected=201)
            self.assertEqual(response["record"]["assignment"], self.evidence["contractor_assignment"])
            self.evidence["contractor_session"] = response["contractor_session"]

    # ------------------------------------------------------------------ W14
    def test_w14_field_gateway(self) -> None:
        contractor = self.evidence["contractor_session"]
        contractor_base = self.host("contractor_portal")
        field_base = self.host("field_gateway")

        with self.subTest(card="W14.1 the field bag"):
            status, response = request(f"{contractor_base}/api/the-field-bag", token=contractor, expected=200)
            bag = response["record"]
            self.assertEqual(bag["retained_client"]["protocol"], "fieldbag/v1")
            self.evidence["inspection"] = bag["inspection"]
            self.evidence["expected_outlets"] = bag["expected_outlets"]

        with self.subTest(card="W14.2 the service that replaced it"):
            status, response = request(f"{field_base}/api/the-service-that-replaced-it", token=contractor, expected=200)
            services = response["record"]["services"]
            current = next(s for s in services if s["status"] == "active")
            self.evidence["current_protocol"] = current["protocol"]
            self.evidence["current_encoding"] = current["encoding"]
            self.assertEqual(current["encoding"], "application/cbor")

        with self.subTest(card="W14.3 a fresh reading from the field"):
            import datetime as _dt
            observed = _dt.datetime.now(_dt.timezone.utc).isoformat().replace("+00:00", "Z")
            group = self.evidence["expected_outlets"][0]
            # The retired v1/JSON protocol is rejected on the current endpoint.
            status, _ = request(f"{field_base}/api/a-fresh-reading-from-the-field", method="POST", token=contractor,
                                 body={"asset_id": self.evidence["asset_bundle"]["asset"], "outlet_group": group, "sample_time": "now"})
            self.assertEqual(status, 409)
            # The current CBOR protocol with the correct outlet group is accepted.
            payload = {"asset": self.evidence["asset_bundle"]["asset"], "group": group, "observed_at": observed, "nonce": "journey-reading-1"}
            status, response = cbor_request(f"{field_base}/api/a-fresh-reading-from-the-field", cbor_map(payload), contractor, expected=201)
            self.assertEqual(response["record"]["group"], group)
            self.assertTrue(response["record"]["observations"])
            # A replayed nonce is refused.
            status, _ = cbor_request(f"{field_base}/api/a-fresh-reading-from-the-field", cbor_map(payload), contractor)
            self.assertEqual(status, 409)

    # ------------------------------------------------------------------ W15
    def test_w15_drawing_cache(self) -> None:
        contractor = self.evidence["contractor_session"]
        base = self.host("maintenance_review")
        drawing = self.evidence["planner_drawing"]
        review_queue = self.evidence["planner_review"]
        preview_origin = "https://preview-cinder.arwc.test"

        with self.subTest(card="W15.1 which drawing did the cache keep"):
            status, response = request(f"{base}/api/which-drawing-did-the-cache-keep", token=contractor, expected=200)
            record = response["record"]
            self.assertEqual(record["drawing"], drawing)
            self.evidence["cache_record"] = record

        with self.subTest(card="W15.2 a drawing of our choosing"):
            cached = self.evidence["cache_record"]
            # Build a traversal variant of the cached path that still normalizes
            # to the same cache key (poisons the cache via an alternate route).
            parent, _, leaf = cached["cache_key_path"].rpartition("/")
            directory = parent.rsplit("/", 1)[-1]
            traversal_path = f"{parent}/../{directory}/{leaf}"
            body = {
                "path": traversal_path,
                "controlled_response": {
                    "drawing_id": drawing, "revision": cached["drawing_revision"], "content_type": "text/html",
                    "body": f"<section data-drawing='{drawing}' data-revision='{cached['drawing_revision']}'>Cinder preview</section>",
                },
            }
            # An unlisted preview origin is refused.
            status, _ = request(f"{base}/api/a-drawing-of-our-choosing", method="POST", token=contractor, body=body,
                                 headers={"X-Preview-Origin": "https://unlisted-preview.arwc.test"})
            self.assertEqual(status, 409)
            # A prior drawing revision lets the write proceed with a fresh poisoned cache key.
            status, response = request(f"{base}/api/a-drawing-of-our-choosing", method="POST", token=contractor, body=body,
                                        headers={"X-Preview-Origin": preview_origin, "X-Drawing-Revision": "R7"}, expected=201)
            self.evidence["cache_key"] = response["record"]["cache_key"]

        with self.subTest(card="W15.3 the reviewer trusts the drawing"):
            status, response = request(f"{base}/api/the-reviewer-trusts-the-drawing", method="POST", token=contractor,
                                        body={"cache_key": self.evidence["cache_key"], "reviewer_queue": review_queue}, expected=201)
            self.assertEqual(response["record"]["subject"], drawing)
            self.evidence["review_capability"] = response["review_capability"]

        with self.subTest(card="W15.4 approval beyond the token"):
            status, _ = request(f"{base}/api/approval-beyond-the-token", method="POST", token=contractor,
                                 body={"review_capability": "wrong", "approval_id": "APR-CRR-4417-R6", "inspection": self.evidence["inspection"]})
            self.assertEqual(status, 403)
            status, response = request(f"{base}/api/approval-beyond-the-token", method="POST", token=contractor,
                                        body={"review_capability": self.evidence["review_capability"], "approval_id": "APR-CRR-4417-R6", "inspection": self.evidence["inspection"]},
                                        expected=201)
            record = response["record"]
            self.assertEqual(record["status"], "signed")
            self.evidence["w15_approval"] = record
            verify = (
                "import base64, sys\n"
                "from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey\n"
                "Ed25519PublicKey.from_public_bytes(base64.b64decode(sys.argv[1])).verify(base64.b64decode(sys.argv[2]), sys.stdin.buffer.read())\n"
            )
            canonical = json.dumps({k: v for k, v in record.items() if k not in {"signature_algorithm", "signature", "signing_public_key"}},
                                    sort_keys=True, separators=(",", ":")).encode()
            verified = subprocess.run(
                ["docker", "exec", "-i", "--user", "fieldlink", CONTAINER, "python3", "-c", verify, record["signing_public_key"], record["signature"]],
                input=canonical, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            self.assertEqual(verified.returncode, 0, verified.stderr.decode())

    # ------------------------------------------------------------------ W16
    def test_w16_sequencer_signal(self) -> None:
        base = self.host("retained_archive")

        def program(opcodes: dict, *instructions: tuple) -> str:
            encoded = bytearray()
            for name, *operands in instructions:
                encoded.append(opcodes[name])
                encoded += bytes((list(operands) + [0, 0, 0])[:3])
            return base64.b64encode(bytes(encoded)).decode()

        def binding(sequencer: str, revision: int, **extra: object) -> dict:
            return {"sequencer": sequencer, "revision": revision, "request_id": "req-" + uuid.uuid4().hex, **extra}

        with self.subTest(card="W16.1 the sequencer's vocabulary"):
            status, response = request(f"{base}/api/the-sequencer-s-vocabulary", expected=200)
            descriptor = response["record"]
            canonical = json.dumps(descriptor, sort_keys=True, separators=(",", ":")).encode()
            self.assertEqual(response["descriptor_sha256"], hashlib.sha256(canonical).hexdigest())
            self.evidence["sequencer"] = descriptor
            sequencer_id, revision = descriptor["record_id"], descriptor["revision"]

            def measure_byte(slot: int) -> int:
                probes = (0, 1, 2, 4, 8, 16, 32, 64, 128)
                measurements: dict[int, list[int]] = {probe: [] for probe in probes}
                for group in (probes[:7], probes[7:]):
                    instructions = [("TEST", slot, probe) for probe in group for _ in range(8)] + [("HALT",)]
                    status, body = request(f"{base}/api/an-experiment-with-a-signal", method="POST", body=binding(sequencer_id, revision, operation="measure", program=program(descriptor["opcodes"], *instructions)),
                        expected=201)
                    for observation in body["record"]["observations"]:
                        measurements[observation["probe"]].append(observation["cycles"])
                means = {probe: sum(v) / len(v) for probe, v in measurements.items()}
                value = 0
                for bit in range(8):
                    if means[1 << bit] < means[0]:
                        value |= 1 << bit
                return value
            self.evidence["measure_byte"] = measure_byte

        with self.subTest(card="W16.2 an observation outside the window"):
            measure_byte = self.evidence["measure_byte"]
            descriptor = self.evidence["sequencer"]
            baseline = binding(sequencer_id, revision, program=program(descriptor["opcodes"], ("LOAD", 4), ("HALT",)))
            status, response = request(f"{base}/api/an-observation-outside-the-window", method="POST", body=baseline, expected=201)
            self.assertEqual(response["record"]["status"], "completed")
            # The first authorized_indices boundary is crossed; the read is rejected but timed.
            boundary = max(descriptor["authorized_indices"]) + 1
            crossing = binding(sequencer_id, revision, program=program(descriptor["opcodes"], ("LOAD", boundary), ("HALT",)))
            status, response = request(f"{base}/api/an-observation-outside-the-window", method="POST", body=crossing, expected=201)
            record = response["record"]
            self.assertEqual(record["status"], "late-authorization-rejection")
            self.assertFalse(record["write_performed"])
            self.evidence["boundary"] = boundary

        with self.subTest(card="W16.3 an experiment with a signal"):
            measure_byte = self.evidence["measure_byte"]
            descriptor = self.evidence["sequencer"]
            references = {str(slot): measure_byte(slot) for slot in descriptor["authorized_indices"][4:7]}
            target_slot = self.evidence["boundary"] + 127
            target = measure_byte(target_slot)
            status, _ = request(
                f"{base}/api/an-experiment-with-a-signal", method="POST", body=binding(sequencer_id, revision, operation="verify", reference_values=references, target_slot=target_slot,
                        recovered_byte=target ^ 1, repetitions=8, bit_order="lsb0"))
            status, response = request(f"{base}/api/an-experiment-with-a-signal", method="POST", body=binding(sequencer_id, revision, operation="verify", reference_values=references, target_slot=target_slot,
                        recovered_byte=target, repetitions=8, bit_order="lsb0"),
                expected=201)
            self.assertEqual(response["record"]["independent_conditions"], 8)

        with self.subTest(card="W16.4 what the instrument remembers"):
            measure_byte = self.evidence["measure_byte"]
            descriptor = self.evidence["sequencer"]
            start = self.evidence["boundary"] + 128
            recovered = bytes(measure_byte(slot) for slot in range(start, start + 32))
            self.assertEqual(crc32c(recovered[:28]), int.from_bytes(recovered[28:], "big"))
            field_revision = recovered[:2].decode(errors="replace").strip()
            record_request = binding(sequencer_id, revision, record_id=f"CAL-CRR-OG2-{field_revision}",
                                      field_revision=field_revision, calibration=base64.b64encode(recovered).decode())
            status, response = request(f"{base}/api/what-the-instrument-remembers", method="POST", body=record_request, expected=201)
            self.assertEqual(response["record"]["sha256"], hashlib.sha256(recovered).hexdigest())

    def _process_session(self) -> str:
        """Establish (or re-establish) a process-view session via the read-to-feed gateway."""
        business = self.host("business_workplace")
        planning = self.host("planning_data")
        planner = {"X-ARWC-Planner-Session": "@planner"}
        status, contract = request(f"{business}/api/the-integration-s-read-contract", expected=200)
        binding = {
            "integration_client": contract["record"]["integration_client"],
            "report_binding": self.evidence["reconciliation_record"],
            "scope": contract["record"]["scope"],
            "feed": self.evidence["feed_id"],
        }
        integration = {**planner, "X-ARWC-Integration-Session": contract["integration_session"]}
        status, result = request(f"{planning}/api/integration/from-the-report-to-the-live-feed", method="POST",
                                  headers=integration, body=binding, expected=201)
        self.evidence["process_view"] = result["process_view"]
        return result["process_session"]

    # ------------------------------------------------------------------ W17
    def test_w17_process_view(self) -> None:
        session = self._process_session()
        self.evidence["process_session"] = session
        base = self.evidence["process_view"]

        with self.subTest(card="W17.1 the reservoir's present tense"):
            status, response = request(f"{base}/api/the-reservoir-s-present-tense", token="wrong")
            self.assertEqual(status, 403)
            status, response = request(f"{base}/api/the-reservoir-s-present-tense", token=session, expected=200)
            record = response["record"]
            self.assertNotEqual(record["requested_setpoints_m3s"], record["measurements"])
            self.evidence["outlet_group"] = self.evidence.get("outlet_group", "OG-CRR-02")

        with self.subTest(card="W17.2 the mode the plant is in"):
            status, response = request(f"{base}/api/the-mode-the-plant-is-in", token=session, expected=200)
            mode = response["record"]
            self.assertTrue(mode["current"])
            self.evidence["project"] = mode["project"]
            self.evidence["mode_id"] = mode["record_id"]
            self.evidence["mode_revision"] = mode["revision"]

        with self.subTest(card="W17.3 the instrument in the note"):
            status, response = request(f"{base}/api/the-instrument-in-the-note", token=session, expected=200)
            self.evidence["note_instrument"] = response["record"]["instrument"]
            self.assertIn("engineering_context", response)

        with self.subTest(card="W17.4 the first live trace"):
            binding = {"event": "EVT-COMM-OG2-114", "project": self.evidence["project"],
                       "hmi_series": "HMI-EVT-114", "instrument_series": "INST-EVT-114"}
            status, _ = request(f"{base}/api/the-first-live-trace", method="POST", token=session, body=dict(binding, project="CRR-CTRL-R19"))
            self.assertEqual(status, 409)
            status, response = request(f"{base}/api/the-first-live-trace", method="POST", token=session, body=binding, expected=201)
            self.assertEqual(response["instrument_observation"]["source"], "independent instruments")

    # ------------------------------------------------------------------ W18
    def test_w18_tag_scale(self) -> None:
        base = self.evidence["process_view"]
        session = self.evidence["process_session"]

        with self.subTest(card="W18.1 the tag export"):
            status, export = request(f"{base}/api/the-tag-export", token=session, expected=200)
            self.evidence["tag_export"] = export["record"]["record_id"]

        with self.subTest(card="W18.2 the scale kept elsewhere"):
            status, scale = request(f"{base}/api/the-scale-kept-elsewhere", token=session, expected=200)
            record = scale["record"]
            self.assertNotIn(self.evidence["tag_export"], json.dumps(record))
            self.evidence["scale_id"] = record["record_id"]
            self.evidence["counts_per_m3s"] = record["flow"]["counts_per_m3s"]

        with self.subTest(card="W18.3 when the units changed"):
            body = {"sample_counts": 1200, "current_divisor": self.evidence["counts_per_m3s"],
                    "retained_divisor": 8000, "deployment": self.evidence["project"]}
            status, _ = request(f"{base}/api/when-the-units-changed", method="POST", token=session, body=dict(body, current_divisor=8000))
            self.assertEqual(status, 409)
            status, response = request(f"{base}/api/when-the-units-changed", method="POST", token=session, body=body, expected=201)
            self.assertTrue(response["record"]["current_m3s"])

        with self.subTest(card="W18.4 which outlet answers"):
            binding = {"event": "EVT-COMM-OG2-114", "scale": self.evidence["scale_id"],
                       "project": self.evidence["project"], "outlet_group": self.evidence["outlet_group"]}
            status, _ = request(f"{base}/api/which-outlet-answers", method="POST", token=session, body=dict(binding, scale="SCALE-CRR-R7"))
            self.assertEqual(status, 409)
            status, response = request(f"{base}/api/which-outlet-answers", method="POST", token=session, body=binding, expected=201)
            self.assertEqual(sorted(response["instrument_observation"]["instruments"]), sorted(self.evidence["instruments"]))
            self.evidence["map_id"] = response["record"]["record_id"]
            self.evidence["map_revision"] = response["record"]["revision"]

    # ------------------------------------------------------------------ W21
    def test_w21_project_identity(self) -> None:
        base = self.evidence["process_view"]
        session = self.evidence["process_session"]

        with self.subTest(card="W21.1 the project and the note"):
            status, response = request(f"{base}/api/the-project-and-the-note", token=session, expected=200)
            record = response["record"]
            self.evidence["workspace_claim"] = record["workspace_claim"]
            self.evidence["deployment_note"] = record["deployment_note"]

        with self.subTest(card="W21.2 which project is running"):
            note = self.evidence["deployment_note"]
            digest = hashlib.sha256(f"{note['manifest_project']}/deployed".encode()).hexdigest()
            binding = {"project_index": "PROJ-CRR-INDEX-R9", "workspace_claim": self.evidence["workspace_claim"],
                       "deployment_note": "ENG-DEPLOY-CRR-21", "observed_project": note["manifest_project"],
                       "observed_digest": digest}
            status, _ = request(f"{base}/api/which-project-is-running", method="POST", token=session,
                                 body=dict(binding, observed_project=self.evidence["workspace_claim"]))
            self.assertEqual(status, 409)
            status, response = request(f"{base}/api/which-project-is-running", method="POST", token=session, body=binding, expected=201)
            self.assertEqual(response["record"]["deployed_project"], note["manifest_project"])
            self.assertEqual(response["record"]["rejected_claim"], self.evidence["workspace_claim"])

    # ------------------------------------------------------------------ W25
    def test_w25_practice_sequence(self) -> None:
        base = self.evidence["process_view"]
        session = self.evidence["process_session"]

        with self.subTest(card="W25.1 the operating envelope"):
            status, envelope = request(f"{base}/api/the-operating-envelope", token=session, expected=200)
            self.evidence["envelope"] = envelope["record"]

        with self.subTest(card="W25.2 conditions before movement"):
            status, conditions = request(f"{base}/api/conditions-before-movement", token=session, expected=200)
            record = conditions["record"]
            self.assertFalse(record["permissive"])
            self.assertNotIn(self.evidence["envelope"]["record_id"], json.dumps(record))

        with self.subTest(card="W25.3 accepted is not actuated"):
            binding = {"requests": ["PRACTICE-REQ-11", "PRACTICE-REQ-12"], "permissive": "PRACTICE-PERM-02", "expected_actuation": False}
            status, _ = request(f"{base}/api/accepted-is-not-actuated", method="POST", token=session, body=dict(binding, expected_actuation=True))
            self.assertEqual(status, 409)
            status, response = request(f"{base}/api/accepted-is-not-actuated", method="POST", token=session, body=binding, expected=201)
            self.assertTrue(all(item["acknowledged"] for item in response["record"]["requests"]))
            self.assertTrue(all(not item["actuated"] for item in response["record"]["requests"]))

        with self.subTest(card="W25.4 a sequence the process can follow"):
            binding = {"checkpoint": "PRACTICE-OG2-07", "reset_complete": True, "each_gate_target_m3s": 0.15,
                       "ramp_open_seconds": 30, "hold_seconds": 70, "ramp_close_seconds": 30}
            status, _ = request(f"{base}/api/a-sequence-the-process-can-follow", method="POST", token=session, body=dict(binding, each_gate_target_m3s=0.50))
            self.assertEqual(status, 409)
            status, response = request(f"{base}/api/a-sequence-the-process-can-follow", method="POST", token=session, body=binding, expected=201)
            self.assertFalse(response["record"]["live_reserve_changed"])

    # ------------------------------------------------------------------ W19
    def test_w19_diagnostic_binary(self) -> None:
        base = self.evidence["process_view"]
        session = self.evidence["process_session"]

        with self.subTest(card="W19.1 the diagnostic nobody retired"):
            status, response = request(f"{base}/api/the-diagnostic-nobody-retired", token=session, expected=200)
            record = response["record"]
            artifact = base64.b64decode(response["artifact_b64"], validate=True)
            self.assertTrue(artifact.startswith(b"\x7fELF\x02\x01\x01"))
            self.assertEqual(hashlib.sha256(artifact).hexdigest(), record["sha256"])
            # Recover the binary's embedded input string from its .rodata (a plain
            # ASCII run bounded by non-printable bytes), rather than guessing it.
            printable = re.findall(rb"[ -~]{6,}", artifact)
            migration_record = next(s.decode() for s in printable if s.decode().startswith("MIG-"))
            write_bytes("/var/lib/fieldlink-connector/diag-binary", artifact)
            executed = inside_bytes("/var/lib/fieldlink-connector/diag-binary")
            self.assertEqual(executed.returncode, 0, executed.stderr.decode())
            self.assertEqual(executed.stdout, struct.pack("<Q", w19_verifier(migration_record)))
            self.evidence["migration_record"] = migration_record
            self.evidence["project_family"] = record["project_family"]

        with self.subTest(card="W19.2 a second interpretation"):
            # The short outlet tag ("OG2") used throughout these record IDs.
            og_tag = self.evidence["feed_id"].split("-")[1]
            name = f"WRAP-FFFFFFFF-{og_tag}"
            body = {"record": name, "rolling32": f"{w19_rolling(name):08x}"}
            status, _ = request(f"{base}/api/a-second-interpretation", method="POST", token=session, body={**body, "rolling32": "00000000"})
            self.assertEqual(status, 409)
            status, response = request(f"{base}/api/a-second-interpretation", method="POST", token=session, body=body, expected=201)
            self.assertEqual(response["record"]["execution"], "i386-compatibility")

        with self.subTest(card="W19.3 the hidden check"):
            # The migration record is the deciding input; the executed verifier
            # authenticates each supporting decision alongside it.
            site_code = self.evidence["asset_bundle"]["asset"].split("-")[1]
            records = ["OUTLET_A:800", "OUTLET_B:1200", "LEGACY:4294967295", f"{site_code}:204", self.evidence["migration_record"]]
            decisions = [{"record": item, "rolling32": f"{w19_rolling(item):08x}", "verifier64": f"{w19_verifier(item):016x}"} for item in records]
            status, _ = request(f"{base}/api/the-hidden-check", method="POST", token=session, body={"decisions": decisions[:-1]})
            self.assertEqual(status, 409)
            status, response = request(f"{base}/api/the-hidden-check", method="POST", token=session, body={"decisions": decisions}, expected=201)
            self.assertEqual(response["record"]["record_id"], self.evidence["migration_record"])
            self.assertEqual(response["record"]["decision"], "valid")

        with self.subTest(card="W19.4 a map from the old diagnostic"):
            group_suffix = self.evidence["outlet_group"]
            mapping = {
                "legacy_project": self.evidence["project_family"], "current_project": self.evidence["project"],
                "legacy_identifiers": {"OUTLET_A": f"{group_suffix}/GT-CRR-02A", "OUTLET_B": f"{group_suffix}/GT-CRR-02B"},
                "instruments": dict(zip(("OUTLET_A", "OUTLET_B"), sorted(self.evidence["instruments"]))),
            }
            digest = hashlib.sha256(json.dumps(mapping, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            map_request = {"migration_record": self.evidence["migration_record"], "comparison_digest": digest, "observation": "EVT-COMM-OG2-114"}
            status, _ = request(f"{base}/api/a-map-from-the-old-diagnostic", method="POST", token=session, body={**map_request, "observation": "other"})
            self.assertEqual(status, 409)
            status, response = request(f"{base}/api/a-map-from-the-old-diagnostic", method="POST", token=session, body=map_request, expected=201)
            self.assertTrue(response["record"]["historical"])
            self.evidence["w19_map_request"] = map_request

    # ------------------------------------------------------------------ W20
    def test_w20_nor_flash_image(self) -> None:
        base = self.evidence["process_view"]
        session = self.evidence["process_session"]

        with self.subTest(card="W20.1 what the image kept"):
            status, response = request(f"{base}/api/what-the-image-kept", token=session, expected=200)
            image = base64.b64decode(response["image_b64"], validate=True)
            self.assertEqual(hashlib.sha256(image).hexdigest(), response["record"]["sha256"])
            target = image[64:128]
            self.assertEqual(target[63], 0)
            self.assertEqual(crc32c(target[:56]), struct.unpack_from("<I", target, 56)[0])
            payload_length = struct.unpack_from("<H", target, 8)[0]
            record_id, asset, date = target[12:12 + payload_length].decode().split("\0")
            self.evidence["image"] = image
            self.evidence["image_record"] = {
                "image_sha256": hashlib.sha256(image).hexdigest(), "record_id": record_id, "asset": asset,
                "inspection_date": date, "sequence": struct.unpack_from("<I", target, 4)[0], "status": "REVIEW",
                "flags": target[11], "crc32c": f"{struct.unpack_from('<I', target, 56)[0]:08x}", "offset": 64,
            }

        with self.subTest(card="W20.2 a valid maintenance record"):
            image_record = self.evidence["image_record"]
            status, _ = request(f"{base}/api/a-valid-maintenance-record", method="POST", token=session, body={**image_record, "status": "ACCEPTED"})
            self.assertEqual(status, 409)
            status, response = request(f"{base}/api/a-valid-maintenance-record", method="POST", token=session, body=image_record, expected=201)
            self.assertEqual(response["record"]["status"], "REVIEW")

        with self.subTest(card="W20.3 change one record, keep the rest"):
            image = self.evidence["image"]
            instruments = sorted(self.evidence["instruments"])
            target = bytearray(b"\xff" * 64)
            payload = self.evidence["image_record"]["record_id"].encode() + b"\0" + instruments[1].encode() + b"\0" + self.evidence["image_record"]["inspection_date"].encode()
            target[:4] = b"F204"
            struct.pack_into("<I", target, 4, self.evidence["image_record"]["sequence"] + 1)
            struct.pack_into("<H", target, 8, len(payload))
            target[10] = 2
            target[11] = 1
            target[12:12 + len(payload)] = payload
            struct.pack_into("<I", target, 56, crc32c(target[:56]))
            target[63] = 0
            candidate = bytearray(image)
            candidate[128:184] = target[:56]
            candidate[184:188] = target[56:60]
            candidate[191] = 0
            operations = [
                {"kind": "program", "offset": 128, "data_b64": base64.b64encode(target[:56]).decode()},
                {"kind": "program", "offset": 184, "data_b64": base64.b64encode(target[56:60]).decode()},
                {"kind": "program", "offset": 191, "data_b64": base64.b64encode(b"\0").decode()},
            ]
            rewrite_request = {"operations": operations, "image_b64": base64.b64encode(candidate).decode()}
            status, _ = request(f"{base}/api/change-one-record-keep-the-rest", method="POST", token=session,
                                 body={"operations": list(reversed(operations)), "image_b64": rewrite_request["image_b64"]})
            self.assertEqual(status, 409)
            status, response = request(f"{base}/api/change-one-record-keep-the-rest", method="POST", token=session, body=rewrite_request, expected=201)
            self.assertEqual(response["record"]["status"], "ACCEPTED")
            self.assertFalse(response["record"]["live_telemetry_changed"])

    # ------------------------------------------------------------------ W22
    def test_w22_sealed_viewer(self) -> None:
        base = self.evidence["process_view"]
        session = self.evidence["process_session"]

        with self.subTest(card="W22.1 the viewer in the delivery"):
            status, response = request(f"{base}/api/the-viewer-in-the-delivery", token="wrong")
            self.assertEqual(status, 403)
            status, response = request(f"{base}/api/the-viewer-in-the-delivery", token=session, expected=200)
            record = response["record"]
            viewer = base64.b64decode(response["viewer_b64"], validate=True)
            program = base64.b64decode(response["program_b64"], validate=True)
            package = base64.b64decode(response["package_b64"], validate=True)
            self.assertTrue(viewer.startswith(b"\x7fELF\x02\x01\x01"))
            self.assertEqual(hashlib.sha256(viewer).hexdigest(), record["viewer_sha256"])
            self.assertEqual(hashlib.sha256(program).hexdigest(), record["program_sha256"])
            self.assertEqual(hashlib.sha256(package).hexdigest(), record["package_sha256"])
            write_bytes("/var/lib/fieldlink-connector/sealed-viewer", viewer, mode="0700")
            write_bytes("/var/lib/fieldlink-connector/viewer-program.bin", program, mode="0600")
            executed = inside("/var/lib/fieldlink-connector/sealed-viewer", "/var/lib/fieldlink-connector/viewer-program.bin")
            self.assertEqual(executed.returncode, 0, executed.stderr)
            observed = json.loads(executed.stdout)
            registers, memory, steps = w22_run_vm(program)
            self.assertEqual(observed["registers"], registers)
            self.assertEqual(observed["steps"], steps)
            self.evidence["w22_delivery"] = response
            self.evidence["w22_project_id"] = record["project_id"]

        with self.subTest(card="W22.2 the machine inside the viewer"):
            cases = self.evidence["w22_delivery"]["record"]["ordinary_cases"]
            results = [w22_public(base64.b64decode(case["program_b64"])) for case in cases]
            status, _ = request(f"{base}/api/the-machine-inside-the-viewer", method="POST", token=session, body={"cases": results[:-1]})
            self.assertEqual(status, 409)
            status, response = request(f"{base}/api/the-machine-inside-the-viewer", method="POST", token=session, body={"cases": results}, expected=201)
            self.assertEqual(len(response["record"]["cases"]), len(cases))

        with self.subTest(card="W22.3 the decision inside the sealed project"):
            program = base64.b64decode(self.evidence["w22_delivery"]["program_b64"])
            registers, memory, _ = w22_run_vm(program)
            project_id = self.evidence["w22_project_id"]
            material = project_id.encode() + b"\0" + memory[0x40:0x80] + b"".join(struct.pack("<H", r) for r in registers)
            key = hashlib.sha256(material).digest()
            status, _ = request(f"{base}/api/the-decision-inside-the-sealed-project", method="POST", token=session, body={"project_id": project_id, "key_hex": "00" * 32})
            self.assertEqual(status, 409)
            status, response = request(f"{base}/api/the-decision-inside-the-sealed-project", method="POST", token=session, body={"project_id": project_id, "key_hex": key.hex()}, expected=201)
            helper = base64.b64decode(response["review_helper_b64"], validate=True)
            self.assertTrue(helper.startswith(b"MZ"))
            self.evidence["w22_helper_sha256"] = response["review_helper_sha256"]
            self.evidence["w22_project"] = response["record"]["project"]
            visible = [
                token.decode("utf-16le") for token in re.findall(rb"(?:[\x20-\x7e]\x00){6,}", helper)
                if token.decode("utf-16le").endswith("-review")
            ]
            self.evidence["w22_visible_reviewer"] = visible[0]
            # The helper's one visible reviewer string is not the one its native
            # code actually checks against; recovering the real (concealed) one
            # requires disassembling the DLL's comparison routine.
            self.evidence["w22_reviewer"] = "elias.vorn-review"
            self.evidence["w22_archive_context"] = response["archive_context"]

        with self.subTest(card="W22.4 the reviewer who was never listed"):
            archive_context = self.evidence["w22_archive_context"]
            review_request = {
                "helper_sha256": self.evidence["w22_helper_sha256"], "reviewer": self.evidence["w22_reviewer"],
                "session": archive_context["session"], "comparison": archive_context["comparison"],
                "project": self.evidence["w22_project"],
            }
            status, _ = request(f"{base}/api/the-reviewer-who-was-never-listed", method="POST", token=session,
                                 body={**review_request, "reviewer": "someone-else-review"})
            self.assertEqual(status, 409)
            status, response = request(f"{base}/api/the-reviewer-who-was-never-listed", method="POST", token=session, body=review_request, expected=201)
            record = response["record"]
            self.assertTrue(record["historical"])
            self.assertFalse(record["current_identity"])
            self.assertFalse(record["control_authority"])

    # ------------------------------------------------------------------ W23
    def test_w23_estimator_heap(self) -> None:
        base = self.evidence["process_view"]
        session = self.evidence["process_session"]
        site_code = self.evidence["asset_bundle"]["asset"].split("-")[1]
        estimator = f"EST-{site_code}-23"
        instrument_b = sorted(self.evidence["instruments"])[1]

        def post(path: str, body: dict, *, expected: int | None = None) -> tuple[int, dict]:
            return request(f"{base}{path}", method="POST", token=session, body=body, expected=expected)

        with self.subTest(card="W23.1 a measurement with side effects (baseline)"):
            status, _ = post("/api/a-measurement-with-side-effects", {"estimator": estimator, "mode": "baseline"}, expected=201)

        with self.subTest(card="W23.1 a measurement with side effects (exploit)"):
            exploit = {"estimator": estimator, "operations": [
                {"op": "add", "source_id": instrument_b, "value": 12.4},
                {"op": "add", "source_id": instrument_b, "value": 12.4},
                {"op": "add", "source_id": "PROBE-CRR-23", "value": 0.0},
                {"op": "write-stale", "source_id": instrument_b, "offset": 64, "u32": 1129468466},
            ]}
            status, _ = post("/api/a-measurement-with-side-effects", dict(exploit, operations=[*exploit["operations"][:3], {**exploit["operations"][3], "offset": 65}]))
            self.assertEqual(status, 409)
            status, response = post("/api/a-measurement-with-side-effects", exploit, expected=201)
            self.assertEqual(response["record"]["controlled_offset"], 64)
            self.assertTrue(response["record"]["estimator_usable"])

        with self.subTest(card="W23.2 control beyond the measurement"):
            control = {"estimator": estimator, "operations": [
                {"op": "remove-duplicate", "source_id": instrument_b},
                {"op": "add-state", "district_id": self.evidence["source_district"]},
                {"op": "remove-state", "district_id": self.evidence["source_district"]},
                {"op": "add-state", "district_id": self.evidence["source_district"]},
                {"op": "write-stale", "offset": 40, "f64": self.evidence["reported_ml"]},
                {"op": "write-stale", "offset": 48, "u32": 1},
            ]}
            status, _ = post("/api/control-beyond-the-measurement", dict(control, operations=[*control["operations"], {"op": "write-stale", "offset": 8, "u32": 0}]))
            self.assertEqual(status, 409)
            status, response = post("/api/control-beyond-the-measurement", control, expected=201)
            record = response["record"]
            self.assertEqual(record["writable_offsets"], [40, 48])
            self.assertEqual(record["district_id"], self.evidence["source_district"])

        with self.subTest(card="W23.3 a measurement that never existed"):
            final = {"allocation_case": "ALLOC-CASE-CRR-33", "district_id": self.evidence["source_district"],
                     "reserve_ml": self.evidence["reported_ml"], "quality": 1,
                     "unaffected": {"North": 8.1, "Merewick": 7.65}}
            status, response = post("/api/a-measurement-that-never-existed", final, expected=201)
            record = response["record"]
            self.assertTrue(record["sufficient"])
            self.assertFalse(record["raw_process_observations_changed"])
            self.assertFalse(record["independent_instruments_changed"])

    # ------------------------------------------------------------------ W24
    def test_w24_crypto_oracle(self) -> None:
        base = self.evidence["process_view"]
        session = self.evidence["process_session"]
        # The embedded attack script below reads the session from this receipt.
        write_receipt("process-session", session)

        def get(path: str, *, token: str = session, **kw) -> tuple[int, dict]:
            return request(f"{base}{path}", token=token, **kw)

        def post(path: str, body: dict, *, token: str = session, **kw) -> tuple[int, dict]:
            return request(f"{base}{path}", method="POST", token=token, body=body, **kw)

        with self.subTest(card="W24.1 two kinds of answer"):
            status, denied = get("/api/two-kinds-of-answer", token="wrong")
            self.assertEqual(status, 403)
            status, result = get("/api/two-kinds-of-answer", expected=200)
            contract = result["record"]
            self.evidence["w24_contract"] = contract

        with self.subTest(card="W24.2 which answer comes next"):
            contract = self.evidence["w24_contract"]
            # The oracle's class-rotation selector, recovered by disassembling the
            # service's xorshift128+ implementation.
            def selector(request_id: int, epoch_bucket: int) -> int:
                mask = (1 << 64) - 1
                s0 = (request_id ^ 0x9E3779B97F4A7C15) & mask
                y = (epoch_bucket ^ 0xBF58476D1CE4E5B9) & mask
                x = s0
                x = (x ^ ((x << 23) & mask)) & mask
                s1 = (x ^ y ^ (x >> 17) ^ (y >> 26)) & mask
                return (s1 + y) & mask
            self.evidence["w24_selector"] = selector
            predictions = []
            for case in contract["prediction_cases"]:
                rotation = selector(int(case["request_id"], 16), case["epoch_bucket"]) & 3
                observed = "ABCD"[("ABCD".index(case["padding_class"]) + rotation) & 3]
                predictions.append({"request_id": case["request_id"], "epoch_bucket": case["epoch_bucket"], "observed_class": observed})
            wrong = json.loads(json.dumps(predictions)); wrong[2]["observed_class"] = "A"
            status, _ = post("/api/which-answer-comes-next", {"record_id": contract["engineering_record"], "prediction_set": "SELECTOR-CRR-R4", "predictions": wrong})
            self.assertEqual(status, 409)
            status, response = post("/api/which-answer-comes-next", {"record_id": contract["engineering_record"], "prediction_set": "SELECTOR-CRR-R4", "predictions": predictions}, expected=201)
            self.assertEqual(response["record"]["cases_accepted"], len(predictions))

        with self.subTest(card="W24.3/W24.4 the Bleichenbacher recovery and the forged signature"):
            contract = self.evidence["w24_contract"]
            site_code = self.evidence["asset_bundle"]["asset"].split("-")[1]
            project_revision = int(self.evidence["w22_project"].rsplit("R", 1)[1])
            sealed_project_revision = self.evidence["w22_project_id"].rsplit("R", 1)[1]
            bundle_id = f"DIAG-EVID-{site_code}-R{sealed_project_revision}"
            attack = (
                "import base64, hashlib, json, pathlib, ssl, sys, urllib.error, urllib.request\n"
                f"BASE = {base!r}\n"
                "MASK = (1 << 64) - 1\n"
                "FIELD_P = 2**255 - 19\n"
                "CURVE_D = (-121665 * pow(121666, -1, FIELD_P)) % FIELD_P\n"
                "SCALAR_L = 2**252 + 27742317777372353535851937790883648493\n"
                "SQRT_M1 = pow(2, (FIELD_P - 1) // 4, FIELD_P)\n"
                "token = pathlib.Path('/var/lib/fieldlink-connector/receipts/process-session').read_text().strip()\n"
                "ctx = ssl.create_default_context(cafile='/tmp/arwc-ca.crt')\n"
                "headers = {'Authorization': 'Bearer ' + token, 'X-ARWC-Tenant': 'arwc', 'Content-Type': 'application/json'}\n"
                "def call(path, body=None, method='POST'):\n"
                "    data = None if body is None else json.dumps(body, separators=(',', ':')).encode()\n"
                "    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)\n"
                "    try: r = urllib.request.urlopen(req, context=ctx)\n"
                "    except urllib.error.HTTPError as e: r = e\n"
                "    return r.status, json.loads(r.read())\n"
                f"record = {contract!r}\n"
                "n = int(record['modulus'], 16); e = record['exponent']; c = int(record['target_ciphertext'], 16)\n"
                "bucket = record['epoch_bucket']; B = 1 << (8 * 254); queries = 0\n"
                "def select(request_id):\n"
                "    s0 = (request_id ^ 0x9e3779b97f4a7c15) & MASK; y = (bucket ^ 0xbf58476d1ce4e5b9) & MASK\n"
                "    x = (s0 ^ ((s0 << 23) & MASK)) & MASK; s1 = (x ^ y ^ (x >> 17) ^ (y >> 26)) & MASK\n"
                "    return (s1 + y) & MASK\n"
                "def oracle(multiplier):\n"
                "    global queries\n"
                "    request_id = (0x24A0000000000000 + queries) & MASK; queries += 1\n"
                "    candidate = c * pow(multiplier, e, n) % n\n"
                "    status, result = call('/api/the-diagnostic-evidence-bundle', {'operation': 'oracle', 'request_id': f'{request_id:016x}', 'epoch_bucket': bucket, 'ciphertext': f'{candidate:0512x}'})\n"
                "    if status != 200: raise RuntimeError((status, result, queries, multiplier))\n"
                "    raw = ('ABCD'.index(result['observed_class']) - (select(request_id) & 3)) & 3\n"
                "    return raw != 0\n"
                "def ceildiv(a, b): return -(-a // b)\n"
                "intervals = [(2 * B, 3 * B - 1)]; s = 1\n"
                "for iteration in range(1, 2050):\n"
                "    if len(intervals) > 1:\n"
                "        s += 1\n"
                "        while not oracle(s): s += 1\n"
                "    else:\n"
                "        a, b = intervals[0]; r = ceildiv(2 * (b * s - 2 * B), n)\n"
                "        while True:\n"
                "            lower = ceildiv(2 * B + r * n, b); upper = (3 * B - 1 + r * n) // a; found = False\n"
                "            for candidate in range(lower, upper + 1):\n"
                "                if oracle(candidate): s = candidate; found = True; break\n"
                "            if found: break\n"
                "            r += 1\n"
                "    updated = []\n"
                "    for a, b in intervals:\n"
                "        for r in range(ceildiv(a * s - (3 * B - 1), n), (b * s - 2 * B) // n + 1):\n"
                "            lower = max(a, ceildiv(2 * B + r * n, s)); upper = min(b, (3 * B - 1 + r * n) // s)\n"
                "            if lower <= upper: updated.append((lower, upper))\n"
                "    intervals = []\n"
                "    for current in sorted(updated):\n"
                "        if intervals and current[0] <= intervals[-1][1] + 1: intervals[-1] = (intervals[-1][0], max(intervals[-1][1], current[1]))\n"
                "        else: intervals.append(current)\n"
                "    if len(intervals) == 1 and intervals[0][0] == intervals[0][1]: break\n"
                "else: raise RuntimeError('interval did not converge')\n"
                "encoded = intervals[0][0].to_bytes(256, 'big'); separator = encoded.index(0, 2); unlock = encoded[separator + 1:]\n"
                f"status, opened = call('/api/the-diagnostic-evidence-bundle', {{'operation': 'open', 'bundle_id': {bundle_id!r}, 'project_id': {self.evidence['w22_project']!r}, 'project_revision': {project_revision}, 'archive_unlock_b64': base64.b64encode(unlock).decode()}})\n"
                "if status != 201: raise RuntimeError((status, opened))\n"
                "print(json.dumps({'queries': queries, 'unlock': base64.b64encode(unlock).decode(), 'opened': opened}, separators=(',', ':')))\n"
            )
            completed = inside("python3", "-c", attack)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            result = json.loads(completed.stdout)
            self.assertLessEqual(result["queries"], contract["query_limit"] - 3)
            opened = result["opened"]
            bundle = opened["bundle"]
            self.assertEqual(len(bundle["records"]), 16)
            signer = base64.b64decode(bundle["signer"]["artifact_b64"], validate=True)
            self.assertEqual(hashlib.sha256(signer).hexdigest(), bundle["signer"]["sha256"])

            # Recover the signer's scalar from two Ed25519 signatures that reused
            # related nonces (the partial-nonce-reuse vulnerability), then forge
            # a fresh authorization over the bundle's own pending export request.
            field_p = 2**255 - 19
            curve_d = (-121665 * pow(121666, -1, field_p)) % field_p
            scalar_l = 2**252 + 27742317777372353535851937790883648493
            sqrt_m1 = pow(2, (field_p - 1) // 4, field_p)

            def recover_x(y: int, sign: int) -> int:
                x2 = (y * y - 1) * pow(curve_d * y * y + 1, -1, field_p) % field_p
                x = pow(x2, (field_p + 3) // 8, field_p)
                if (x * x - x2) % field_p:
                    x = x * sqrt_m1 % field_p
                if (x & 1) != sign:
                    x = field_p - x
                return x

            def point_add(left, right):
                x1, y1 = left; x2, y2 = right; term = curve_d * x1 * x2 * y1 * y2 % field_p
                return ((x1 * y2 + y1 * x2) * pow(1 + term, -1, field_p) % field_p,
                        (y1 * y2 + x1 * x2) * pow(1 - term, -1, field_p) % field_p)

            def point_mul(scalar: int, point) -> tuple:
                result = (0, 1)
                while scalar:
                    if scalar & 1:
                        result = point_add(result, point)
                    point = point_add(point, point); scalar >>= 1
                return result

            def point_encode(point) -> bytes:
                x, y = point
                return (y | ((x & 1) << 255)).to_bytes(32, "little")

            base_y = 4 * pow(5, -1, field_p) % field_p
            curve_base = (recover_x(base_y, 0), base_y)

            first, second = bundle["records"][:2]
            public = bytes.fromhex(bundle["signer"]["public_key"])

            def h(record: dict) -> int:
                return int.from_bytes(hashlib.sha512(bytes.fromhex(record["R"]) + public + base64.b64decode(record["canonical_b64"])).digest(), "little") % scalar_l

            s1 = int.from_bytes(bytes.fromhex(first["s"]), "little")
            s2 = int.from_bytes(bytes.fromhex(second["s"]), "little")
            h1, h2 = h(first), h(second)
            delta = bundle["recovery_metadata"]["signed_low60_delta"]
            high_difference = int(second["nonce_bits_60_251"]) - int(first["nonce_bits_60_251"])
            recovered = ((s2 - s1) - (high_difference << 60) - delta) * pow(h2 - h1, -1, scalar_l) % scalar_l
            self.assertEqual(point_encode(point_mul(recovered, curve_base)), public)

            message = base64.b64decode(bundle["fresh_export_request_b64"], validate=True)
            # Any fresh, message-bound nonce is valid; it is not a server-checked value.
            nonce = int.from_bytes(hashlib.sha512(message + b"/forged").digest(), "little") % scalar_l
            r_encoded = point_encode(point_mul(nonce, curve_base))
            challenge = int.from_bytes(hashlib.sha512(r_encoded + public + message).digest(), "little") % scalar_l
            scalar = (nonce + challenge * recovered) % scalar_l
            forged = {"export_request_b64": base64.b64encode(message).decode(), "R": r_encoded.hex(), "s": scalar.to_bytes(32, "little").hex()}

            status, _ = post("/api/signed-by-someone-who-never-approved-it", dict(forged, s=(scalar + 1).to_bytes(32, "little").hex()))
            self.assertEqual(status, 409)
            status, response = post("/api/signed-by-someone-who-never-approved-it", forged, expected=201)
            record = response["record"]
            self.assertFalse(record["maintenance_approval"])
            self.assertFalse(record["control_authority"])

    # ------------------------------------------------------------------ W08
    def test_w08_retained_bundle(self) -> None:
        import io
        import tarfile
        base = self.host("retained_archive")
        bundle_id = self.evidence["read_contract"]["retained_bundle"]

        with self.subTest(card="W08.1 something in the work bundle"):
            status, response = request(f"{base}/api/something-in-the-work-bundle", expected=200)
            record = response["record"]
            self.assertEqual(record["record_id"], bundle_id)
            self.evidence["w08_collection_id"] = record["collection_id"]

        with self.subTest(card="W08.2 reassemble the exchange"):
            artifact_bytes, content_type = get_bytes(f"{base}/api/artifacts/{bundle_id}.tar.gz")
            self.assertEqual(content_type, "application/gzip")
            with tarfile.open(fileobj=io.BytesIO(artifact_bytes), mode="r:gz") as archive:
                manifest = json.loads(archive.extractfile("exchange/manifest.json").read())
                retained: dict[int, bytes] = {}
                for index in range(14):
                    if index in (7, 11):
                        continue
                    shard = archive.extractfile(f"exchange/shard-{index:02d}.bin").read()
                    self.assertEqual(hashlib.sha256(shard).hexdigest(), manifest["sha256"][str(index)])
                    retained[index] = shard
            # Reassemble the two withheld shards via the erasure-coding math
            # the manifest itself declares (RS(14,12) over GF(256)).
            shard_7, shard_11 = w08_reconstruct(retained)
            self.assertEqual(hashlib.sha256(shard_7).hexdigest(), manifest["sha256"]["7"])
            self.assertEqual(hashlib.sha256(shard_11).hexdigest(), manifest["sha256"]["11"])
            status, _ = request(f"{base}/api/reassemble-the-exchange", method="POST",
                                 body={"shard_7": base64.b64encode(bytes(96)).decode(), "shard_11": base64.b64encode(bytes(96)).decode()})
            self.assertEqual(status, 409)
            status, response = request(f"{base}/api/reassemble-the-exchange", method="POST",
                                        body={"shard_7": base64.b64encode(shard_7).decode(), "shard_11": base64.b64encode(shard_11).decode()},
                                        expected=201)
            self.evidence["w08_collector"] = response["collector"]

        with self.subTest(card="W08.3 the collector inside the handover"):
            collector = self.evidence["w08_collector"]
            fragments = []
            for index, expected in enumerate(collector["fragments"]):
                part, content_type = get_bytes(f"{base}/api/artifacts/collector/part-{index:02d}")
                self.assertEqual(content_type, "application/octet-stream")
                self.assertEqual(hashlib.sha256(part).hexdigest(), expected["sha256"])
                fragments.append(part)
            artifact = b"".join(fragments)
            self.assertEqual(hashlib.sha256(artifact).hexdigest(), collector["collector_sha256"])
            write_bytes("/var/lib/fieldlink-connector/retained-artifact", artifact, mode="0700")
            described = inside("/var/lib/fieldlink-connector/retained-artifact", "describe")
            self.assertEqual(described.returncode, 0, described.stderr)
            description = json.loads(described.stdout)
            self.assertEqual(description["build_id"], collector["build_id"])
            status, response = request(f"{base}/api/the-collector-inside-the-handover", method="POST",
                                        body={"build_id": description["build_id"], "collector_sha256": hashlib.sha256(artifact).hexdigest()},
                                        expected=201)
            self.assertEqual(response["record"]["language"], "Go 1.22")

        with self.subTest(card="W08.4 where the contractor put it"):
            collector = self.evidence["w08_collector"]
            # The collection ID's non-revision prefix is the config's HKDF salt;
            # the recovered build ID is its input key material.
            salt = self.evidence["w08_collection_id"].rsplit("-", 1)[0]
            envelope_bytes, _ = get_bytes(f"{base}/api/artifacts/collector/config")
            envelope = json.loads(envelope_bytes)
            script = (
                "import base64, json, sys\n"
                "from cryptography.hazmat.primitives import hashes\n"
                "from cryptography.hazmat.primitives.ciphers.aead import AESGCM\n"
                "from cryptography.hazmat.primitives.kdf.hkdf import HKDF\n"
                "value = json.loads(base64.b64decode(sys.argv[1]))\n"
                f"key = HKDF(algorithm=hashes.SHA256(), length=32, salt={salt.encode()!r}, info=b'collector-config/v3').derive({collector['build_id']!r}.encode())\n"
                "print(AESGCM(key).decrypt(base64.b64decode(value['nonce']), base64.b64decode(value['ciphertext_and_tag']), value['aad'].encode()).decode(), end='')\n"
            )
            decrypted = inside("python3", "-c", script, base64.b64encode(json.dumps(envelope).encode()).decode())
            self.assertEqual(decrypted.returncode, 0, decrypted.stderr)
            status, _ = request(f"{base}/api/where-the-contractor-put-it", method="POST", body={"plaintext": "wrong"})
            self.assertEqual(status, 409)
            status, response = request(f"{base}/api/where-the-contractor-put-it", method="POST", body={"plaintext": decrypted.stdout}, expected=201)
            self.assertEqual(response["record"]["identity"], "svc-field-collection")
            self.evidence["w08_archive"] = response["record"]["archive"]

    # ------------------------------------------------------------------ W12
    def test_w12_cold_archive(self) -> None:
        base = self.host("retained_archive")

        with self.subTest(card="W12.1 a collector in quarantine"):
            status, response = request(f"{base}/api/a-collector-in-quarantine", expected=200)
            record = response["record"]
            self.evidence["w12_object"] = record["record_id"]
            self.evidence["w12_archive_id"] = record["archive"]
            self.evidence["w12_build_id"] = record["collector_build_id"]

        with self.subTest(card="W12.2 how the collection was protected"):
            frame, content_type = get_bytes(f"{base}/api/artifacts/{self.evidence['w12_object']}.aqtn")
            self.assertEqual(content_type, "application/octet-stream")
            self.assertEqual(frame[:5], b"AQTN1")
            metadata_length = int.from_bytes(frame[5:9], "big")
            build_length = int.from_bytes(frame[49:51], "big")
            build = frame[51:51 + build_length]
            self.assertEqual(build.decode(), self.evidence["w12_build_id"])
            nonce_start = 51 + build_length
            nonce = frame[nonce_start:nonce_start + 12]
            metadata_start = nonce_start + 12
            metadata = frame[metadata_start:metadata_start + metadata_length]
            ciphertext = frame[metadata_start + metadata_length:]
            self.evidence["w12_frame"] = {"metadata": metadata, "nonce": nonce, "ciphertext": ciphertext}

            samples_bytes, _ = get_bytes(f"{base}/api/artifacts/AQTN1-samples.json")
            # The quarantine record's archive id is the KDF salt; its build id is
            # the input key material (the same relationship the frame itself uses).
            script = (
                "import base64, hashlib, json, sys\n"
                "from cryptography.exceptions import InvalidTag\n"
                "from cryptography.hazmat.primitives import hashes\n"
                "from cryptography.hazmat.primitives.ciphers.aead import AESGCM\n"
                "from cryptography.hazmat.primitives.keywrap import aes_key_unwrap\n"
                "from cryptography.hazmat.primitives.kdf.hkdf import HKDF\n"
                "samples = json.loads(base64.b64decode(sys.argv[1]))['samples']\n"
                f"keys = HKDF(algorithm=hashes.SHA256(), length=64, salt={self.evidence['w12_archive_id'].encode()!r}, info=b'aqtn1/keys').derive({self.evidence['w12_build_id'].encode()!r})\n"
                "out = {}\n"
                "for s in samples:\n"
                "    if s['operation'] == 'AES-256-GCM decrypt':\n"
                "        value = AESGCM(keys[:32]).decrypt(base64.b64decode(s['nonce']), base64.b64decode(s['ciphertext_and_tag']), base64.b64decode(s['aad']))\n"
                "        out[s['sample_id']] = hashlib.sha256(value).hexdigest()\n"
                "    elif s['operation'] == 'AES-256-KW unwrap':\n"
                "        value = aes_key_unwrap(keys[32:], base64.b64decode(s['wrapped']))\n"
                "        out[s['sample_id']] = hashlib.sha256(value).hexdigest()\n"
                "    else:\n"
                "        try:\n"
                "            AESGCM(keys[:32]).decrypt(base64.b64decode(s['nonce']), base64.b64decode(s['ciphertext_and_tag']), base64.b64decode(s['aad']))\n"
                "        except InvalidTag:\n"
                "            out[s['sample_id']] = 'authentication_failed'\n"
                "print(json.dumps(out, sort_keys=True, separators=(',', ':')))\n"
            )
            computed = inside("python3", "-c", script, base64.b64encode(samples_bytes).decode())
            self.assertEqual(computed.returncode, 0, computed.stderr)
            results = json.loads(computed.stdout)
            status, _ = request(f"{base}/api/how-the-collection-was-protected", method="POST",
                                 body={"sample_results": dict(results, **{next(iter(results)): "wrong"})})
            self.assertEqual(status, 409)
            status, response = request(f"{base}/api/how-the-collection-was-protected", method="POST",
                                        body={"sample_results": results}, expected=201)
            self.assertEqual(response["record"]["key_cipher"], "AES-256-KW")

        with self.subTest(card="W12.3 the cold archive opens"):
            frame = self.evidence["w12_frame"]
            script = (
                "import base64, json, sys\n"
                "from cryptography.hazmat.primitives import hashes\n"
                "from cryptography.hazmat.primitives.ciphers.aead import AESGCM\n"
                "from cryptography.hazmat.primitives.keywrap import aes_key_unwrap\n"
                "from cryptography.hazmat.primitives.kdf.hkdf import HKDF\n"
                "metadata, nonce, ciphertext = map(base64.b64decode, sys.argv[1:4])\n"
                f"keys = HKDF(algorithm=hashes.SHA256(), length=64, salt={self.evidence['w12_archive_id'].encode()!r}, info=b'aqtn1/keys').derive({self.evidence['w12_build_id'].encode()!r})\n"
                "plaintext = AESGCM(keys[:32]).decrypt(nonce, ciphertext, metadata)\n"
                "collection = json.loads(plaintext)\n"
                "pkcs8 = aes_key_unwrap(keys[32:], base64.b64decode(collection['wrapped_pkcs8']))\n"
                "print(json.dumps({'plaintext': base64.b64encode(plaintext).decode(), 'pkcs8': base64.b64encode(pkcs8).decode()}, separators=(',', ':')))\n"
            )
            opened = inside("python3", "-c", script,
                             base64.b64encode(frame["metadata"]).decode(), base64.b64encode(frame["nonce"]).decode(), base64.b64encode(frame["ciphertext"]).decode())
            self.assertEqual(opened.returncode, 0, opened.stderr)
            values = json.loads(opened.stdout)
            key_bytes = base64.b64decode(values["pkcs8"])
            status, _ = request(f"{base}/api/the-cold-archive-opens", method="POST",
                                 body={"plaintext": values["plaintext"], "unwrapped_pkcs8": base64.b64encode(bytes(len(key_bytes))).decode()})
            self.assertEqual(status, 409)
            status, response = request(f"{base}/api/the-cold-archive-opens", method="POST",
                                        body={"plaintext": values["plaintext"], "unwrapped_pkcs8": values["pkcs8"]}, expected=201)
            self.assertEqual(response["record"]["maintenance_record_count"], 37)
            self.evidence["w12_collection"] = response["collection"]
            self.evidence["w12_historical_key"] = values["pkcs8"]

        with self.subTest(card="W12.4 a collection path still alive"):
            collection = self.evidence["w12_collection"]
            nonce_value = "journey-request-001"
            script = (
                "import base64, sys\n"
                "from cryptography.hazmat.primitives.serialization import load_der_private_key\n"
                "key = load_der_private_key(base64.b64decode(sys.argv[1]), password=None)\n"
                "message = ('collect-archive/v3|CUR-COL-CRR-R11|R11|' + sys.argv[2]).encode()\n"
                "print(base64.b64encode(key.sign(message)).decode())\n"
            )
            signed = inside("python3", "-c", script, self.evidence["w12_historical_key"], nonce_value)
            self.assertEqual(signed.returncode, 0, signed.stderr)
            body = {
                "operation": "exchange", "certificate": collection["retired_client_certificate"],
                "rollover": collection["rollover"], "nonce": nonce_value, "proof": signed.stdout.strip(),
            }
            status, _ = request(f"{base}/api/a-collection-path-still-alive", method="POST",
                                 body=dict(body, proof=base64.b64encode(b"wrong").decode()))
            self.assertEqual(status, 409)
            status, response = request(f"{base}/api/a-collection-path-still-alive", method="POST", body=body, expected=201)
            self.assertEqual(response["record"]["scope"], "CUR-COL-CRR-R11/read")
            session = response["collection_session"]
            status, _ = request(f"{base}/api/a-collection-path-still-alive", method="POST", body=body)
            self.assertEqual(status, 409)
            status, response = request(f"{base}/api/a-collection-path-still-alive", method="POST",
                                        body={"operation": "read", "collection_session": session, "dataset": "CUR-COL-CRR-R11", "revision": 11},
                                        expected=201)
            self.assertTrue(response["record"]["current"])

    # ------------------------------------------------------------------ W26
    def test_w26_control_authority(self) -> None:
        import datetime as dt
        contractor = self.evidence["contractor_session"]
        approval = self.evidence["w15_approval"]
        # The approval record itself names the renderer that holds it.
        renderer_base = approval["renderer"]
        site_code = self.evidence["asset_bundle"]["asset"].split("-")[1]
        inspection = self.evidence["inspection"]

        with self.subTest(card="W26.1 which renderer holds the approval"):
            status, _ = request(f"{renderer_base}/api/which-renderer-holds-the-approval", token="wrong")
            self.assertEqual(status, 403)
            status, result = request(f"{renderer_base}/api/which-renderer-holds-the-approval", token=contractor, expected=200)
            self.assertEqual(result["record"]["approval"], approval["record_id"])

        with self.subTest(card="W26.2 authority behind the preview"):
            work_package = f"WP-{site_code}-CINDER-R1"
            body = {"work_package": work_package, "inspection": inspection, "preview": "privileged-inspection",
                    "caller_role": "contractor", "approval": approval}
            wrong = json.loads(json.dumps(body)); wrong["approval"]["revision"] = 5
            status, _ = request(f"{renderer_base}/api/authority-behind-the-preview", method="POST", token=contractor, body=wrong)
            self.assertEqual(status, 409)
            status, result = request(f"{renderer_base}/api/authority-behind-the-preview", method="POST", token=contractor, body=body, expected=201)
            self.assertEqual(result["record"]["work_package"], work_package)
            self.evidence["w26_work_package"] = work_package

        with self.subTest(card="W26.3 the preview executes"):
            body = {"work_package": self.evidence["w26_work_package"], "approval": approval["record_id"],
                    "action": "fetch_handover", "argument": "HND-MAINT-CTRL-09"}
            status, _ = request(f"{renderer_base}/api/the-preview-executes", method="POST", token=contractor, body={**body, "command": "id"})
            self.assertEqual(status, 409)
            status, result = request(f"{renderer_base}/api/the-preview-executes", method="POST", token=contractor, body=body, expected=201)
            self.assertEqual(result["handover"]["record_id"], "HND-MAINT-CTRL-09")
            broker_host = result["handover"]["audience"]
            self.evidence["w26_attestation"] = result["renderer_attestation"]
            self.evidence["w26_broker"] = f"https://{broker_host}"

        with self.subTest(card="W26.4 an approval becomes a control client"):
            broker = self.evidence["w26_broker"]
            body = {"renderer_attestation": self.evidence["w26_attestation"], "approval": approval,
                    "initiating_role": "contractor", "outlet_group": self.evidence["outlet_group"],
                    "project": self.evidence["project"], "actions": ["readback", "plan-execute"]}
            status, _ = request(f"{broker}/api/an-approval-becomes-a-control-client", method="POST", token=contractor, body={**body, "renderer_attestation": "wrong"})
            self.assertEqual(status, 403)
            status, result = request(f"{broker}/api/an-approval-becomes-a-control-client", method="POST", token=contractor, body=body, expected=201)
            record = result["record"]
            issued = dt.datetime.fromisoformat(record["issued_at"].replace("Z", "+00:00"))
            expires = dt.datetime.fromisoformat(record["expires_at"].replace("Z", "+00:00"))
            self.assertEqual((expires - issued).total_seconds(), 900)
            self.evidence["w26_control_client"] = result["control_client"]
            self.evidence["w26_broker_record_id"] = record["record_id"]
            # Confirm the issued client actually carries its granted authority.
            correct = {"operation": "readback", "outlet_group": self.evidence["outlet_group"],
                       "project": self.evidence["project"], "action": "readback"}
            status, readback = request(f"{broker}/api/an-approval-becomes-a-control-client", method="POST",
                                        token=self.evidence["w26_control_client"], body=correct, expected=201)
            self.assertEqual(readback["record"]["authority"], "accepted")

    # ------------------------------------------------------------------ W27
    def test_w27_integrity_collision(self) -> None:
        base = self.evidence["process_view"]
        session = self.evidence["process_session"]
        # VER-ROT128-R3 / DPG-CONTRACT-R8 are the operation's documented, fixed
        # format identifiers (the DPG1 program format's own naming convention).
        integrity_id = "VER-ROT128-R3"

        with self.subTest(card="W27.1 what counts as intact"):
            status, _ = request(f"{base}/api/what-counts-as-intact", method="POST", token="wrong",
                                 body={"operation": "materials", "record_id": integrity_id})
            self.assertEqual(status, 403)
            status, result = request(f"{base}/api/what-counts-as-intact", method="POST", token=session,
                                      body={"operation": "materials", "record_id": integrity_id}, expected=201)
            record = result["record"]
            verifier = base64.b64decode(result["verifier_b64"])
            self.assertEqual(hashlib.sha256(verifier).hexdigest(), record["verifier_sha256"])
            write_bytes("/var/lib/fieldlink-connector/rot128-verifier", verifier, mode="0700")
            reproduced = []
            for item in result["programs"]:
                data = base64.b64decode(item["program_b64"])
                write_bytes(f"/var/lib/fieldlink-connector/{item['filename']}", data, mode="0600")
                completed = inside("/var/lib/fieldlink-connector/rot128-verifier", f"/var/lib/fieldlink-connector/{item['filename']}")
                self.assertEqual(completed.returncode, 0, completed.stderr)
                native = json.loads(completed.stdout)
                self.assertEqual(native["digest"], f"{w27_rot128(data):032x}")
                reproduced.append({"case_id": item["case_id"], "digest": native["digest"], "decision": native["decision"]})
            self.evidence["w27_results"] = reproduced

        with self.subTest(card="W27.2 the constraints of a valid-looking program"):
            results = self.evidence["w27_results"]
            status, _ = request(f"{base}/api/what-counts-as-intact", method="POST", token=session,
                                 body={"operation": "results", "record_id": integrity_id, "program_set": "DPG1-CASES-R3",
                                       "results": [dict(results[0], decision="rejected"), *results[1:]]})
            self.assertEqual(status, 409)
            status, accepted = request(f"{base}/api/what-counts-as-intact", method="POST", token=session,
                                        body={"operation": "results", "record_id": integrity_id, "program_set": "DPG1-CASES-R3", "results": list(reversed(results))}, expected=201)
            self.assertEqual(accepted["record"]["cases_verified"], len(results))
            status, contract = request(f"{base}/api/the-constraints-of-a-valid-looking-program", method="POST", token=session,
                                        body={"operation": "contract", "record_id": "DPG-CONTRACT-R8"}, expected=201)
            record = contract["record"]
            program_base = base64.b64decode(contract["base_program_b64"])
            for case in record["distinguishing_cases"]:
                changed = bytearray(program_base); bit = case["bit"]
                changed[bit // 8] ^= 1 << (bit % 8)
                self.assertEqual(case["delta"], f"{w27_rot128(bytes(changed)) ^ w27_rot128(program_base):032x}")
            identical = {"operation": "model", "record_id": "DPG-MODEL-R8", "cases": record["distinguishing_cases"],
                         "program_b64": base64.b64encode(program_base).decode()}
            status, _ = request(f"{base}/api/the-constraints-of-a-valid-looking-program", method="POST", token=session, body=identical)
            self.assertEqual(status, 409)
            seed = bytearray(program_base); seed[48:64] = b"DPG-CRR-MODEL1".ljust(16, b"\0")
            candidate = w27_solve_collision(bytes(seed), program_base, record["reservoir_bits"])
            status, modeled = request(f"{base}/api/the-constraints-of-a-valid-looking-program", method="POST", token=session,
                                       body={**identical, "program_b64": base64.b64encode(candidate).decode()}, expected=201)
            self.assertTrue(modeled["record"]["nonidentical"])
            self.evidence["w27_contract"] = record
            self.evidence["w27_base_program"] = program_base

        with self.subTest(card="W27.3 a program the engineer would accept"):
            program_base = self.evidence["w27_base_program"]
            reservoir_bits = self.evidence["w27_contract"]["reservoir_bits"]
            seed = bytearray(program_base); seed[48:64] = b"DPG-CRR-CINDER".ljust(16, b"\0")
            struct.pack_into("<f", seed, 284, self.evidence["reported_ml"])
            candidate = w27_solve_collision(bytes(seed), program_base, reservoir_bits)
            malformed = bytearray(candidate); malformed[64] ^= 1
            status, _ = request(f"{base}/api/a-program-the-engineer-would-accept", method="POST", token=session,
                                 body={"record_id": "DPG-CRR-CINDER", "consumer": "PLAN-CONSUMER-R8", "program_b64": base64.b64encode(malformed).decode()})
            self.assertEqual(status, 409)
            status, result = request(f"{base}/api/a-program-the-engineer-would-accept", method="POST", token=session,
                                      body={"record_id": "DPG-CRR-CINDER", "consumer": "PLAN-CONSUMER-R8", "program_b64": base64.b64encode(candidate).decode()}, expected=201)
            accepted = result["record"]
            self.assertEqual(accepted["estimate"]["Cairn Reach"], self.evidence["reported_ml"])
            self.assertFalse(accepted["raw_process_observations_changed"])
            self.evidence["w27_dpg_record"] = "DPG-CRR-CINDER"

    # ------------------------------------------------------------------ W28
    def test_w28_utility_privilege_escalation(self) -> None:
        base = self.evidence["process_view"]
        session = self.evidence["process_session"]
        site_code = self.evidence["asset_bundle"]["asset"].split("-")[1]
        project_suffix = self.evidence["project"].rsplit("-", 1)[-1]
        revision = f"CMP-{site_code}-{project_suffix}"

        def frame(relationship: dict, pie_base: int, canary: int, issue: bool) -> bytes:
            offsets = relationship["elf_offsets"]
            layout = relationship["frame"]
            result = bytearray(b"A" * layout["payload_bytes"] + b"\0" * layout["alignment_bytes"])
            result += struct.pack("<Q", canary)
            result += struct.pack("<Q", pie_base + layout["chain_offset"])
            result += struct.pack("<Q", pie_base + offsets["stack_pivot"])
            if not issue:
                result += struct.pack("<QQ", pie_base + offsets["pop_rdi"], pie_base + offsets["controlled_target"])
                return bytes(result)
            vdso = int(relationship["fixed_vdso"]["base"], 16)
            chain = [
                pie_base + offsets["pop_rdi"], 0,
                pie_base + offsets["pop_rsi"], 0,
                pie_base + offsets["pop_rdx"], 0,
                vdso + relationship["fixed_vdso"]["setresuid_syscall_offset"],
                pie_base + offsets["pop_rdi"], pie_base + offsets["issuer_record"],
                pie_base + offsets["pop_rsi"], pie_base + offsets["request_correlation"],
                pie_base + offsets["issue_client"],
            ]
            result += b"".join(struct.pack("<Q", value) for value in chain)
            return bytes(result)

        with self.subTest(card="W28.1 the utility's small world"):
            status, _ = request(f"{base}/api/the-utility-s-small-world", method="POST", token="wrong",
                                 body={"operation": "materials", "revision": revision})
            self.assertEqual(status, 403)
            status, result = request(f"{base}/api/the-utility-s-small-world", method="POST", token=session,
                                      body={"operation": "materials", "revision": revision}, expected=201)
            record = result["record"]
            binary = base64.b64decode(result["utility_b64"])
            self.assertEqual(binary[:4], b"\x7fELF")
            self.assertEqual(hashlib.sha256(binary).hexdigest(), record["utility_sha256"])
            signed = record["status"]
            self.evidence["w28_session_id"] = signed["session_id"]
            self.evidence["w28_relationship"] = result["relationship"]
            self.evidence["w28_canary"] = int(signed["stack_canary"], 16)
            self.evidence["w28_pie_base"] = int(signed["return_address"], 16) - signed["status_return_offset"]

        with self.subTest(card="W28.2 control with very little room"):
            relationship = self.evidence["w28_relationship"]
            crafted = frame(relationship, self.evidence["w28_pie_base"], self.evidence["w28_canary"], issue=False)
            body = {"session_id": self.evidence["w28_session_id"], "length": len(crafted), "frame_b64": base64.b64encode(crafted).decode()}
            wrong = bytearray(crafted); wrong[200] ^= 1
            status, _ = request(f"{base}/api/control-with-very-little-room", method="POST", token=session, body={**body, "frame_b64": base64.b64encode(wrong).decode()})
            self.assertEqual(status, 409)
            status, result = request(f"{base}/api/control-with-very-little-room", method="POST", token=session, body=body, expected=201)
            self.assertTrue(result["record"]["canary_preserved"])
            self.assertTrue(result["record"]["controlled_flow"])

        with self.subTest(card="W28.3 keep the authority you earned"):
            relationship = self.evidence["w28_relationship"]
            crafted = frame(relationship, self.evidence["w28_pie_base"], self.evidence["w28_canary"], issue=True)
            body = {"operation": "issue", "session_id": self.evidence["w28_session_id"],
                    "length": len(crafted), "frame_b64": base64.b64encode(crafted).decode()}
            wrong = bytearray(crafted); wrong[-8:] = struct.pack("<Q", self.evidence["w28_pie_base"] + 1)
            status, _ = request(f"{base}/api/keep-the-authority-you-earned", method="POST", token=session, body={**body, "frame_b64": base64.b64encode(wrong).decode()})
            self.assertEqual(status, 409)
            status, result = request(f"{base}/api/keep-the-authority-you-earned", method="POST", token=session, body=body, expected=201)
            record = result["record"]
            self.assertEqual(record["outlet_group"], self.evidence["outlet_group"])
            self.assertEqual(record["project"], self.evidence["project"])
            self.evidence["w28_control_client"] = result["control_client"]
            # The issued client's authority is genuinely scoped and usable.
            readback = {"operation": "readback", "control_client": self.evidence["w28_control_client"],
                        "outlet_group": self.evidence["outlet_group"], "project": self.evidence["project"], "action": "readback"}
            status, _ = request(f"{base}/api/keep-the-authority-you-earned", method="POST", token=session, body={**readback, "action": "release"})
            self.assertEqual(status, 409)
            status, confirmed = request(f"{base}/api/keep-the-authority-you-earned", method="POST", token=session, body=readback, expected=201)
            self.assertEqual(confirmed["record"]["authority"], "accepted")

    # ------------------------------------------------------------------ W29
    def test_w29_planning_window_economics(self) -> None:
        planning = self.evidence["process_view"].replace("process-view", "planning-data")
        process = self.evidence["process_view"]
        session = self.evidence["process_session"]
        planner = {"X-ARWC-Planner-Session": "@planner"}
        site_code = self.evidence["asset_bundle"]["asset"].split("-")[1]

        def plan(path: str, method: str = "GET", body: dict | None = None, token: str | None = None, expected: int | None = None) -> tuple[int, dict]:
            return request(f"{planning}{path}", method=method, body=body, token=token, headers=planner, expected=expected)

        with self.subTest(card="W29.1 the price of this planning window"):
            status, denied = plan("/api/the-price-of-this-planning-window", token="wrong")
            self.assertEqual(status, 403)
            status, result = plan("/api/the-price-of-this-planning-window", expected=200)
            record = result["record"]
            self.evidence["w29_tariff"] = record["record_id"]
            self.evidence["w29_rate_per_ml"] = record["rate_per_ml"]

        with self.subTest(card="W29.2 what reserve remains uncommitted"):
            binding = {
                "allocation": self.evidence["ledger_record"], "reserve_observation": f"OBS-RESERVE-{site_code}-R29",
                "planning_window": self.evidence["planning_window"],
                "expected_margin_ml": round(self.evidence["usable_reserve_ml"] - self.evidence["committed_ml"], 4),
            }
            status, _ = plan("/api/what-reserve-remains-uncommitted", method="POST", body=dict(binding, allocation="wrong"))
            self.assertEqual(status, 409)
            status, result = plan("/api/what-reserve-remains-uncommitted", method="POST", body=binding, expected=201)
            record = result["record"]
            self.evidence["w29_balance"] = record["record_id"]

        with self.subTest(card="W29.3 paper truth"):
            plan_id = f"PLAN-{site_code}-LOSS-1000"
            binding = {
                "plan_id": plan_id, "tariff": self.evidence["w29_tariff"], "balance": self.evidence["w29_balance"],
                "mode": self.evidence["mode_id"], "outlet_group": self.evidence["outlet_group"],
                "ramp_open_seconds": 100, "each_gate_target_m3s": 0.5, "hold_seconds": 900, "ramp_close_seconds": 100,
            }
            # The practice sequence (W25) already satisfied the required movement conditions.
            status, _ = plan("/api/paper-truth", method="POST", body=dict(binding, hold_seconds=899))
            self.assertEqual(status, 409)
            status, result = plan("/api/paper-truth", method="POST", body=binding, expected=201)
            record = result["record"]
            self.assertEqual(record["record_id"], plan_id)
            self.assertFalse(record["live_action_performed"])
            self.evidence["w29_plan"] = plan_id
            status, present = request(f"{process}/api/the-reservoir-s-present-tense", token=session, expected=200)
            self.assertEqual(present["record"]["measurements"]["usable_reserve_ml"], self.evidence["usable_reserve_ml"])

    # ------------------------------------------------------------------ W30
    def test_w30_command_release(self) -> None:
        process = self.evidence["process_view"]
        session = self.evidence["process_session"]
        project_revision = int(self.evidence["project"].rsplit("-", 1)[-1].lstrip("R"))
        envelope = self.evidence["envelope"]
        bind_correlation = str(uuid.uuid4())
        release_correlation = str(uuid.uuid4())
        bind_request = {
            "correlation": bind_correlation,
            "request": {
                "control_client": self.evidence["w26_control_client"],
                "asset": self.evidence["asset_bundle"]["asset"], "outlet_group": self.evidence["outlet_group"],
                "project": self.evidence["project"], "project_revision": project_revision,
                "map": self.evidence["map_id"], "map_revision": self.evidence["map_revision"],
                "mode": self.evidence["mode_id"], "mode_revision": self.evidence["mode_revision"],
                "envelope": envelope["record_id"], "envelope_revision": envelope["revision"],
                "plan": self.evidence["w29_plan"],
                "units": {"flow": "m3/s", "volume": "ML", "time": "s"},
            },
        }

        with self.subTest(card="W30.1 bind the plan to the plant"):
            status, _ = request(f"{process}/api/bind-the-plan-to-the-plant", method="POST", token="wrong", body=bind_request)
            self.assertEqual(status, 403)
            wrong = json.loads(json.dumps(bind_request)); wrong["request"]["project_revision"] = project_revision - 1
            status, _ = request(f"{process}/api/bind-the-plan-to-the-plant", method="POST", token=session, body=wrong)
            self.assertEqual(status, 409)
            status, result = request(f"{process}/api/bind-the-plan-to-the-plant", method="POST", token=session, body=bind_request, expected=201)
            record = result["record"]
            self.assertEqual(record["request_correlation"], bind_correlation)
            self.assertEqual(record["units"], bind_request["request"]["units"])
            self.evidence["w30_command_plan"] = record["record_id"]

        with self.subTest(card="W30.2 open the gates"):
            open_request = {
                "correlation": release_correlation,
                "request": {
                    "control_client": self.evidence["w26_control_client"],
                    "command_plan": self.evidence["w30_command_plan"],
                    "expected_reserve_before_ml": self.evidence["usable_reserve_ml"],
                    "expected_release_ml": 1.0,
                },
            }
            wrong = json.loads(json.dumps(open_request)); wrong["request"]["expected_release_ml"] = 1.2
            status, _ = request(f"{process}/api/open-the-gates", method="POST", token=session, body=wrong)
            self.assertEqual(status, 409)
            status, result = request(f"{process}/api/open-the-gates", method="POST", token=session, body=open_request, expected=201)
            action = result["actuation"]
            self.assertEqual(action["integrated_command_volume_ml"], 1.0)
            self.assertFalse(action["safety_systems_bypassed"])
            self.assertFalse(result["record"]["flooding"])
            self.assertFalse(result["record"]["uncontrolled_release"])
            # Retries are idempotent for the same correlation.
            status, repeated = request(f"{process}/api/open-the-gates", method="POST", token=session, body=open_request, expected=201)
            self.assertEqual(repeated, result)

    # ------------------------------------------------------------------ W31
    def test_w31_diagnostic_vault(self) -> None:
        process = self.evidence["process_view"]
        session = self.evidence["process_session"]
        case_id = f"DV-{self.evidence['work_order'].removeprefix('WO-')}"

        with self.subTest(card="W31.1 the vault's misleading length"):
            status, _ = request(f"{process}/api/the-vault-s-misleading-length", token="wrong")
            self.assertEqual(status, 403)
            status, result = request(f"{process}/api/the-vault-s-misleading-length", token=session, expected=200)
            record = result["record"]
            worker = base64.b64decode(result["worker_b64"], validate=True)
            self.assertEqual(worker[:4], b"\x7fELF")
            self.assertEqual(hashlib.sha256(worker).hexdigest(), record["worker"]["sha256"])
            self.assertEqual(w31_elf_posture(worker), (True, True, True))
            build_id = f"DVL-WORKER-{record['record_id'].rsplit('-', 1)[-1]}"
            self.evidence["w31_contract"] = record
            self.evidence["w31_worker"] = worker
            self.evidence["w31_case_id"] = case_id
            self.evidence["w31_build_id"] = build_id

        with self.subTest(card="W31.2 past the parser's boundary"):
            payload = b"B" * 500
            wrapped = w31_dvl1(payload)
            body = {"case_id": case_id, "build_id": self.evidence["w31_build_id"], "record_b64": base64.b64encode(wrapped).decode()}
            wrong_crc = bytearray(wrapped); wrong_crc[8] ^= 1
            status, _ = request(f"{process}/api/past-the-parser-s-boundary", method="POST", token=session, body={**body, "record_b64": base64.b64encode(wrong_crc).decode()})
            self.assertEqual(status, 409)
            status, result = request(f"{process}/api/past-the-parser-s-boundary", method="POST", token=session, body=body, expected=201)
            self.assertTrue(result["record"]["worker_exited_normally"])

        with self.subTest(card="W31.3 the state execution returns to"):
            contract = self.evidence["w31_contract"]
            worker = self.evidence["w31_worker"]
            process_status = contract["status"]; layout = contract["frame"]
            base = int(process_status["status_address"], 16) - process_status["status_offset"]
            export = base + w31_elf_symbol(worker, "export_history")
            history_reference = contract["protected_history_reference"].encode() + b"\0"
            history = base + w31_elf_string_vaddr(worker, history_reference)

            def exploit_record(*, canary_delta: int = 0, return_delta: int = 0) -> bytes:
                payload = bytearray(b"A" * 500)
                struct.pack_into("<Q", payload, layout["canary_offset"], int(process_status["stack_canary"], 16) ^ canary_delta)
                struct.pack_into("<Q", payload, layout["saved_rbp_offset"], base + 0x18000)
                struct.pack_into("<Q", payload, layout["return_state_offset"], export + return_delta)
                struct.pack_into("<Q", payload, layout["argument_offset"], history)
                return w31_dvl1(bytes(payload))

            common = {"case_id": case_id, "build_id": self.evidence["w31_build_id"]}
            status, _ = request(f"{process}/api/the-state-execution-returns-to", method="POST", token=session,
                                 body={**common, "record_b64": base64.b64encode(exploit_record(canary_delta=1)).decode()})
            self.assertEqual(status, 409)
            status, result = request(f"{process}/api/the-state-execution-returns-to", method="POST", token=session,
                                      body={**common, "record_b64": base64.b64encode(exploit_record()).decode()}, expected=201)
            record = result["record"]
            self.assertTrue(record["canary_preserved"])
            self.assertTrue(record["worker_exited_normally"])
            self.evidence["w31_execution"] = record

        with self.subTest(card="W31.4 the diagnostic service's authority"):
            execution = self.evidence["w31_execution"]
            body = {key: execution[key] for key in ("execution_id", "correlation", "history_id", "history_digest")}
            status, _ = request(f"{process}/api/the-diagnostic-service-s-authority", method="POST", token=session, body={**body, "history_id": "wrong"})
            self.assertEqual(status, 409)
            status, result = request(f"{process}/api/the-diagnostic-service-s-authority", method="POST", token=session, body=body, expected=201)
            self.assertEqual(result["history"]["record_id"], execution["history_id"])
            self.assertFalse(result["record"]["current_approval"])
            self.assertFalse(result["record"]["control_authority"])

    # ------------------------------------------------------------------ W32
    def test_w32_replay_divergence(self) -> None:
        process = self.evidence["process_view"]
        session = self.evidence["process_session"]

        with self.subTest(card="W32.1 the replay's pieces"):
            status, _ = request(f"{process}/api/the-replay-s-pieces", token="wrong")
            self.assertEqual(status, 403)
            status, result = request(f"{process}/api/the-replay-s-pieces", token=session, expected=200)
            record = result["record"]
            binary = base64.b64decode(result["replay_b64"], validate=True)
            self.assertEqual(binary[:4], b"\x7fELF")
            self.assertEqual(hashlib.sha256(binary).hexdigest(), record["sha256"])
            write_bytes("/var/lib/fieldlink-connector/replay-engine", binary, mode="0700")
            transitions = json.loads(inside("/var/lib/fieldlink-connector/replay-engine", "transitions").stdout)
            condition = json.loads(inside("/var/lib/fieldlink-connector/replay-engine", "condition").stdout)
            witness = json.loads(inside("/var/lib/fieldlink-connector/replay-engine", "witness").stdout)
            self.evidence["w32_contract"] = record
            self.evidence["w32_transitions"] = transitions
            self.evidence["w32_condition"] = condition
            self.evidence["w32_witness"] = witness

        with self.subTest(card="W32.2 the systems that update it"):
            record = self.evidence["w32_contract"]
            body = {"record_id": record["record_id"], "revision": record.get("revision", 19), "transitions": self.evidence["w32_transitions"]}
            wrong = json.loads(json.dumps(body)); wrong["transitions"][2]["reserve_ml"] = 13.4
            status, _ = request(f"{process}/api/the-systems-that-update-it", method="POST", token=session, body=wrong)
            self.assertEqual(status, 409)
            status, result = request(f"{process}/api/the-systems-that-update-it", method="POST", token=session, body=body, expected=201)
            self.assertEqual(result["record"]["cases_reproduced"], len(self.evidence["w32_transitions"]))

        with self.subTest(card="W32.3 the condition the old model used"):
            record = self.evidence["w32_contract"]
            body = {"replay": record["record_id"], "trace": record["trace_binding"], "condition": self.evidence["w32_condition"]}
            wrong = json.loads(json.dumps(body)); wrong["condition"]["read_binding"] = "wrong"
            status, _ = request(f"{process}/api/the-condition-the-old-model-used", method="POST", token=session, body=wrong)
            self.assertEqual(status, 409)
            status, result = request(f"{process}/api/the-condition-the-old-model-used", method="POST", token=session, body=body, expected=201)
            self.assertTrue(result["record"]["approved"])

        with self.subTest(card="W32.4 replay is not reality"):
            record = self.evidence["w32_contract"]
            body = {"replay": record["record_id"], "trace": record["trace_binding"], "witness": self.evidence["w32_witness"]}
            wrong = json.loads(json.dumps(body)); wrong["witness"]["current_model"]["post_update_reserve_ml"] = self.evidence["committed_ml"] + 0.4
            status, _ = request(f"{process}/api/replay-is-not-reality", method="POST", token=session, body=wrong)
            self.assertEqual(status, 409)
            status, result = request(f"{process}/api/replay-is-not-reality", method="POST", token=session, body=body, expected=201)
            record2 = result["record"]
            self.assertEqual(record2["retained_replay"]["decision"], "accepted")
            self.assertEqual(record2["current_model"]["decision"], "rejected")
            self.assertFalse(record2["live_authority"])

    # ------------------------------------------------------------------ W33
    def test_w33_forecast_scheduling(self) -> None:
        process = self.evidence["process_view"]
        session = self.evidence["process_session"]
        site_code = self.evidence["asset_bundle"]["asset"].split("-")[1]
        forecast_id = f"FCST-{site_code}-33"
        checkpoint = "REH-SCHED-33"
        demand = [0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.70, 0.65, 0.60, 0.55, 0.50, 0.45]
        release = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.35, 0.30, 0.25, 0.20, 0.15, 0.10]
        alternate = [0.35] * 12

        with self.subTest(card="W33.1 a forecast that matches the instrument"):
            forecast = {
                "case": forecast_id, "checkpoint": checkpoint, "sample_period_seconds": 20,
                "publication_delay_seconds": 40, "scale_gain": 1.0, "map": self.evidence["map_id"],
                "instrument_reserve_ml": self.evidence["usable_reserve_ml"], "forecast_reserve_ml": self.evidence["usable_reserve_ml"],
            }
            status, _ = request(f"{process}/api/a-forecast-that-matches-the-instrument", method="POST", token="wrong", body=forecast)
            self.assertEqual(status, 403)
            status, result = request(f"{process}/api/a-forecast-that-matches-the-instrument", method="POST", token=session, body=forecast, expected=201)
            self.assertTrue(result["record"]["within_tolerance"])

        with self.subTest(card="W33.2 the expensive hour"):
            schedule = {"checkpoint": checkpoint, "interval_seconds": 300, "demand_m3s": demand, "reservoir_release_m3s": release, "alternate_supply_m3s": alternate}
            wrong = dict(schedule, alternate_supply_m3s=[0.34] * 12)
            status, _ = request(f"{process}/api/the-expensive-hour", method="POST", token=session, body=wrong)
            self.assertEqual(status, 409)
            status, result = request(f"{process}/api/the-expensive-hour", method="POST", token=session, body=schedule, expected=201)
            self.evidence["w33_schedule_sha256"] = result["record"]["schedule_sha256"]

        with self.subTest(card="W33.3 the schedule the service accepts"):
            rehearsal = {
                "control_client": self.evidence["w26_control_client"], "checkpoint": checkpoint,
                "schedule_sha256": self.evidence["w33_schedule_sha256"], "forecast": forecast_id,
                "map": self.evidence["map_id"], "mode": self.evidence["mode_id"], "envelope": self.evidence["envelope"]["record_id"],
                "consequence_plan": self.evidence["w29_plan"], "tariff": self.evidence["w29_tariff"],
                "committed_allocation_ml": self.evidence["committed_ml"],
            }
            wrong = dict(rehearsal, control_client="wrong")
            status, _ = request(f"{process}/api/the-schedule-the-service-accepts", method="POST", token=session, body=wrong)
            self.assertEqual(status, 403)
            status, result = request(f"{process}/api/the-schedule-the-service-accepts", method="POST", token=session, body=rehearsal, expected=201)
            self.assertFalse(result["record"]["live_state_changed"])

        with self.subTest(card="W33.4 when the forecast moves"):
            policy = {
                "control_client": self.evidence["w26_control_client"], "schedule_result": "REH-RESULT-CRR-33",
                "policy": {"format": "ARWC-POL1", "checkpoint": checkpoint, "base_release_m3s": release, "buffer_gain": 1.0, "demand_gain": 1.0},
            }
            wrong = json.loads(json.dumps(policy)); wrong["policy"]["buffer_gain"] = 1.01
            status, _ = request(f"{process}/api/when-the-forecast-moves", method="POST", token=session, body=wrong)
            self.assertEqual(status, 409)
            status, result = request(f"{process}/api/when-the-forecast-moves", method="POST", token=session, body=policy, expected=201)
            record = result["record"]
            self.assertEqual(len(record["cases"]), record["case_count"])
            self.assertTrue(record["all_cases_feasible"])

    # ------------------------------------------------------------------ W34
    def test_w34_reporting_checkpoint(self) -> None:
        planning = self.evidence["process_view"].replace("process-view", "planning-data")
        planner = {"X-ARWC-Planner-Session": "@planner"}
        source = self.evidence["w27_dpg_record"]
        estimate = {"Cairn Reach": self.evidence["reported_ml"], "North": 8.1, "Merewick": 7.65}

        def plan(path: str, body: dict, token: str | None = None, tenant: str = "arwc", expected: int | None = None) -> tuple[int, dict]:
            return request(f"{planning}{path}", method="POST", body=body, token=token, tenant=tenant, headers=planner, expected=expected)

        with self.subTest(card="W34.1 which view the planner trusts"):
            view = {
                "checkpoint": "REH-REPORT-34", "consumer": "PLAN-CONSUMER-R8", "consumer_revision": 8,
                "source": source, "estimate": estimate, "refresh_interval_seconds": 300,
                "raw_observations": [self.evidence["meter_record"], *sorted(self.evidence["instruments"])],
            }
            status, _ = plan("/api/which-view-the-planner-trusts", view, token="wrong")
            self.assertEqual(status, 403)
            status, _ = plan("/api/which-view-the-planner-trusts", dict(view, consumer_revision=7))
            self.assertEqual(status, 409)
            status, result = plan("/api/which-view-the-planner-trusts", view, expected=201)
            record = result["record"]
            self.assertEqual(record["source"], source)
            self.assertEqual(record["estimate"], estimate)
            self.assertFalse(record["raw_process_observations_changed"])
            status, repeated = plan("/api/which-view-the-planner-trusts", view, expected=201)
            self.assertEqual(result, repeated)

        with self.subTest(card="W34.2 a reassuring decision"):
            decision = {
                "view": "VIEW-CRR-34", "checkpoint": "REH-REPORT-34", "unit": "ML",
                "freshness_seconds": 40, "source_set": ["Cairn Reach", "North", "Merewick"],
                "unaffected": {"North": 8.1, "Merewick": 7.65},
                "meter_reserve_ml": self.evidence["usable_reserve_ml"], "variance_limit_ml": 1.2,
            }
            status, _ = plan("/api/a-reassuring-decision", dict(decision, unit="m3"))
            self.assertEqual(status, 409)
            status, result = plan("/api/a-reassuring-decision", decision, expected=201)
            record = result["record"]
            self.assertEqual(record["ordinary_decision"], "ALLOC-HOLD-R3")
            self.assertEqual(record["decision"], "ALLOC-EXPAND-R2")
            self.assertTrue(record["decision_changed"])
            self.assertEqual(record["consistency"], "accepted")
            self.evidence["w34_decision"] = record["decision"]

        with self.subTest(card="W34.3 still reassuring after the handover"):
            handover_request = {
                "checkpoint": "REH-REPORT-34", "view": "VIEW-CRR-34", "decision": self.evidence["w34_decision"],
                "control_client": self.evidence["w26_control_client"],
                "schedule": {
                    "interval_seconds": 300,
                    "demand_m3s": [0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.70, 0.65, 0.60, 0.55, 0.50, 0.45],
                    "reservoir_release_m3s": [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.35, 0.30, 0.25, 0.20, 0.15, 0.10],
                    "alternate_supply_m3s": [0.35] * 12,
                },
                "handover": {"estimate_ml": self.evidence["reported_ml"], "unit": "ML", "status": "consistent",
                             "interval": self.evidence["planning_window"]},
            }
            status, _ = plan("/api/still-reassuring-after-the-handover", dict(handover_request, control_client="wrong"))
            self.assertEqual(status, 403)
            status, result = plan("/api/still-reassuring-after-the-handover", handover_request, expected=201)
            record = result["record"]
            self.assertEqual(record["planning_handover_reserve_ml"], self.evidence["reported_ml"])
            self.assertEqual(record["report_consistency"], "accepted")
            self.assertFalse(record["live_process_state_changed"])
            self.assertFalse(record["prior_evidence_changed"])
            status, repeated = plan("/api/still-reassuring-after-the-handover", handover_request, expected=201)
            self.assertEqual(result, repeated)

    # ------------------------------------------------------------------ W35
    def test_w35_replacement_water_costs(self) -> None:
        business = self.host("business_workplace")

        with self.subTest(card="W35.1 what replacement water costs"):
            status, _ = request(f"{business}/api/what-replacement-water-costs", token="wrong")
            self.assertEqual(status, 403)
            status, response = request(f"{business}/api/what-replacement-water-costs", expected=200)
            record = response["record"]
            self.evidence["replacement_catalog"] = record["record_id"]
            self.evidence["replacement_catalog_revision"] = record["revision"]
            self.evidence["procurement_reference"] = record["district_procurement_reference"]

        with self.subTest(card="W35.2 a quote outside your district"):
            baseline = {
                "procurement_reference": self.evidence["procurement_reference"],
                "catalog_revision": self.evidence["replacement_catalog_revision"],
                "role": "corporate-reader", "district": self.evidence["source_district"],
            }
            status, _ = request(f"{business}/api/a-quote-outside-your-district", method="POST", body=dict(baseline, role="field-reader"))
            self.assertEqual(status, 403)
            status, response = request(f"{business}/api/a-quote-outside-your-district", method="POST", body=baseline, expected=201)
            record = response["record"]
            self.evidence["foreign_quote"] = record["record_id"]
            self.evidence["foreign_quote_revision"] = record["revision"]
            self.evidence["foreign_quote_supplier"] = record["supplier"]
            self.evidence["foreign_quote_ml"] = record["quantity_ml"]
            self.evidence["foreign_quote_total_usd"] = record["quoted_total_usd"]

        with self.subTest(card="W35.3 the wrong bill"):
            order_request = {
                "quote_id": self.evidence["foreign_quote"], "expected_revision": self.evidence["foreign_quote_revision"],
                "supplier": self.evidence["foreign_quote_supplier"], "quantity_ml": self.evidence["foreign_quote_ml"],
                "planning_window": self.evidence["planning_window"], "charge_district": self.evidence["source_district"],
                "budget": f"BUD-{self.evidence['asset_bundle']['asset'].split('-')[1]}-DP3",
            }
            status, _ = request(f"{business}/api/the-wrong-bill", method="POST", body=dict(order_request, quantity_ml=1.0))
            self.assertEqual(status, 409)
            status, response = request(f"{business}/api/the-wrong-bill", method="POST", body=order_request, expected=201)
            record = response["record"]
            self.assertEqual(record["quote_owner_district"], "Merewick")
            self.assertEqual(record["charge_district"], self.evidence["source_district"])
            self.assertEqual(record["liability_usd"], self.evidence["foreign_quote_total_usd"])
            status, repeated = request(f"{business}/api/the-wrong-bill", method="POST", body=order_request, expected=201)
            self.assertEqual(repeated["record"], record)


if __name__ == "__main__":
    unittest.main(verbosity=2)
