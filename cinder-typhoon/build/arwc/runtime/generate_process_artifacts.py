#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import pathlib
import struct
import sys


POLY = 0x82F63B78


def crc32c(data: bytes) -> int:
    value = 0xFFFFFFFF
    for byte in data:
        value ^= byte
        for _ in range(8):
            value = (value >> 1) ^ (POLY if value & 1 else 0)
    return value ^ 0xFFFFFFFF


def flash_record(sequence: int, status: int, payload: bytes, *, commit: int = 0) -> bytes:
    if len(payload) > 44:
        raise ValueError("payload is too large")
    record = bytearray(b"\xff" * 64)
    record[0:4] = b"F204"
    struct.pack_into("<I", record, 4, sequence)
    struct.pack_into("<H", record, 8, len(payload))
    record[10] = status
    record[11] = 0x01
    record[12:12 + len(payload)] = payload
    struct.pack_into("<I", record, 56, crc32c(record[:56]))
    record[63] = commit
    return bytes(record)


def make_flash(output: pathlib.Path) -> None:
    image = bytearray(b"\xff" * 8192)
    records = [
        flash_record(91, 2, b"CAL-FIT-204-R7" + b"\0" + b"FIT-CRR-204A" + b"\0" + b"2026-08-19"),
        flash_record(118, 1, b"INSP-FIT-204-118" + b"\0" + b"FIT-CRR-204B" + b"\0" + b"2026-09-18"),
    ]
    for index, record in enumerate(records):
        image[index * 64:(index + 1) * 64] = record
    output.write_bytes(image)
    (output.parent / "IMG-FIT-204-R6.json").write_text(json.dumps({
        "image_id": "IMG-FIT-204-R6",
        "sha256": hashlib.sha256(image).hexdigest(),
        "erase_page_bytes": 4096,
        "record_bytes": 64,
        "wear_map": {"record_id": "WEAR-FIT-204-R6", "page_counts": [17, 9], "limit": 24},
    }, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")


def instruction(opcode: int, dst: int = 0, src: int = 0, immediate: int = 0) -> bytes:
    return struct.pack("<HBBH", opcode, dst, src, immediate & 0xFFFF)


def run_vm(program: bytes) -> dict[str, object]:
    if len(program) % 6:
        raise ValueError("invalid program length")
    registers = [0, 0, 0, 0]
    memory = bytearray(256)
    zero = False
    pc = 0
    steps = 0
    while 0 <= pc < len(program) // 6 and steps < 4096:
        opcode, dst, src, immediate = struct.unpack_from("<HBBH", program, pc * 6)
        if dst > 3 or src > 3:
            raise ValueError("invalid register")
        steps += 1
        if opcode == 0x01:
            registers[dst] = immediate
            zero = registers[dst] == 0
            pc += 1
        elif opcode == 0x02:
            registers[dst] = memory[(registers[src] + immediate) & 0xFF]
            zero = registers[dst] == 0
            pc += 1
        elif opcode == 0x03:
            registers[dst] = (registers[dst] ^ registers[src] ^ immediate) & 0xFFFF
            zero = registers[dst] == 0
            pc += 1
        elif opcode == 0x04:
            registers[dst] = (registers[dst] + registers[src] + immediate) & 0xFFFF
            zero = registers[dst] == 0
            pc += 1
        elif opcode == 0x05:
            count = immediate & 15
            value = registers[src]
            registers[dst] = value if count == 0 else ((value << count) | (value >> (16 - count))) & 0xFFFF
            zero = registers[dst] == 0
            pc += 1
        elif opcode == 0x06:
            memory[(registers[dst] + immediate) & 0xFF] = registers[src] & 0xFF
            pc += 1
        elif opcode == 0x07:
            pc = pc + struct.unpack("<h", struct.pack("<H", immediate))[0] if not zero else pc + 1
        elif opcode == 0xFF:
            break
        else:
            raise ValueError("invalid opcode")
    if steps >= 4096:
        raise ValueError("instruction limit")
    return {"registers": registers, "memory": bytes(memory), "steps": steps}


def vm_public_result(result: dict[str, object]) -> dict[str, object]:
    memory = result["memory"]
    assert isinstance(memory, bytes)
    return {"registers": result["registers"],
            "memory_40_80_sha256": hashlib.sha256(memory[0x40:0x80]).hexdigest(),
            "steps": result["steps"]}


def make_sealed(output: pathlib.Path) -> None:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    output.mkdir(parents=True, exist_ok=True)
    material = hashlib.sha512(b"CRR-SEALED-PKG-R7/viewer-memory").digest()
    sealed = bytearray()
    for address, value in enumerate(material, 0x40):
        sealed += instruction(0x01, 0, 0, value)
        sealed += instruction(0x01, 1, 0, address)
        sealed += instruction(0x06, 1, 0, 0)
    for register, value in enumerate((0xC217, 0x21A5, 0x0F02, 0x7E11)):
        sealed += instruction(0x01, register, 0, value)
    sealed += instruction(0xFF)
    sealed_result = run_vm(bytes(sealed))

    cases = [
        instruction(0x01, 0, 0, 0xFFFE) + instruction(0x01, 1, 0, 5) +
        instruction(0x04, 0, 1, 2) + instruction(0xFF),
        instruction(0x01, 0, 0, 0x00A5) + instruction(0x01, 1, 0, 0x20) +
        instruction(0x06, 1, 0, 3) + instruction(0x02, 2, 1, 3) +
        instruction(0x03, 2, 0, 0x005A) + instruction(0x05, 3, 2, 5) + instruction(0xFF),
        instruction(0x01, 0, 0, 3) + instruction(0x01, 1, 0, 0xFFFF) +
        instruction(0x04, 1, 1, 1) + instruction(0x07, 0, 0, 2) +
        instruction(0x01, 2, 0, 0xDEAD) + instruction(0x01, 2, 0, 0xBEEF) + instruction(0xFF),
        instruction(0x01, 3, 0, 0) + instruction(0x07, 0, 0, 2) +
        instruction(0x01, 0, 0, 0x1234) + instruction(0xFF),
    ]
    registers = sealed_result["registers"]
    memory = sealed_result["memory"]
    assert isinstance(registers, list) and isinstance(memory, bytes)
    key_material = (b"CRR-SEALED-PKG-R7\0" + memory[0x40:0x80] +
                    b"".join(struct.pack("<H", value) for value in registers))
    key = hashlib.sha256(key_material).digest()
    plaintext = json.dumps({
        "record_id": "DEC-CRR-OG2-R7", "project": "CRR-CTRL-R21", "revision": 7,
        "decision": "Retain the commissioning flow-scale exception until independent field verification.",
        "review_helper": "REVIEWHELP-R4", "captured_session": "ARCHIVE-REVIEW-R7-ELIAS",
        "comparison": "CMP-CRR-R21-R7",
    }, sort_keys=True, separators=(",", ":")).encode()
    nonce = hashlib.sha256(b"CRR-SEALED-PKG-R7/nonce").digest()[:12]
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, b"CRR-SEALED-PKG-R7")
    (output / "viewer-program.bin").write_bytes(sealed)
    (output / "sealed-project.bin").write_bytes(nonce + ciphertext)
    (output / "sealed-metadata.json").write_text(json.dumps({
        "program_sha256": hashlib.sha256(sealed).hexdigest(),
        "package_sha256": hashlib.sha256(nonce + ciphertext).hexdigest(),
        "sealed_result": vm_public_result(sealed_result),
        "cases": [{"program_b64": __import__("base64").b64encode(case).decode(),
                   "result": vm_public_result(run_vm(case))} for case in cases],
    }, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 3 or sys.argv[1] not in {"flash", "sealed"}:
        raise SystemExit("usage: generate_process_artifacts.py {flash|sealed} OUTPUT")
    output = pathlib.Path(sys.argv[2])
    if sys.argv[1] == "flash":
        output.parent.mkdir(parents=True, exist_ok=True)
        make_flash(output)
    else:
        make_sealed(output)


if __name__ == "__main__":
    main()
