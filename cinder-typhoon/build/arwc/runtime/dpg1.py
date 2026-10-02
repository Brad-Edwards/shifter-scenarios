#!/usr/bin/env python3
from __future__ import annotations

import struct


PROGRAM_SIZE = 512
HEADER = struct.Struct("<4sHHHHIIIIHH16s16s")
BLOCK = struct.Struct("<BBHIIhh16s")
INSTRUCTION = struct.Struct("<BBBBf")
OUTPUT = struct.Struct("<16s8sII")
IV = int("6a09e667f3bcc908bb67ae8584caa73b", 16)
MASK128 = (1 << 128) - 1
BASE_ID = "DPG-CRR-BASE-R8"
MODEL_ID = "DPG-CRR-MODEL1"
TARGET_ID = "DPG-CRR-CINDER"
INTEGRITY = b"VER-ROT128-R3"
TABLE_OFFSET = 64
CODE_OFFSET = 256
OUTPUT_OFFSET = 320
OPCODES = (0x10, 0x11, 0x12, 0x20, 0x20, 0x20)
RESERVOIR_BYTES = tuple(range(208, 224)) + tuple(range(240, 256))
RESERVOIR_BITS = tuple(byte * 8 + bit for byte in RESERVOIR_BYTES for bit in range(8))
CAIRN_VALUE_OFFSET = CODE_OFFSET + 3 * INSTRUCTION.size + 4


def padded(value: str | bytes, length: int) -> bytes:
    encoded = value.encode("ascii") if isinstance(value, str) else value
    if len(encoded) > length:
        raise ValueError("field is too long")
    return encoded + b"\0" * (length - len(encoded))


def rotl128(value: int, count: int) -> int:
    count %= 128
    return ((value << count) | (value >> (128 - count))) & MASK128


def rot128(data: bytes) -> int:
    unpadded_length = len(data)
    material = data + b"\x80"
    material += b"\0" * ((-len(material)) % 16)
    state = IV
    for offset in range(0, len(material), 16):
        block = int.from_bytes(material[offset:offset + 16], "little")
        state = rotl128(state, 17) ^ block ^ rotl128(block, 41)
    return (state ^ rotl128(state, 29) ^ unpadded_length) & MASK128


def digest_hex(data: bytes) -> str:
    return f"{rot128(data):032x}"


def build_program(program_id: str = BASE_ID, *, cairn_reserve: float = 12.4,
                  reservoir: bytes | None = None) -> bytes:
    if reservoir is None:
        reservoir = bytes(len(RESERVOIR_BYTES))
    if len(reservoir) != len(RESERVOIR_BYTES):
        raise ValueError("reservoir has the wrong size")
    program = bytearray(PROGRAM_SIZE)
    program[:HEADER.size] = HEADER.pack(
        b"DPG1", 1, HEADER.size, 6, BLOCK.size, TABLE_OFFSET,
        CODE_OFFSET, 6 * INSTRUCTION.size, OUTPUT_OFFSET, 3, OUTPUT.size,
        padded(INTEGRITY, 16), padded(program_id, 16),
    )
    reservoir_offset = 0
    instructions = (
        (0x10, 1, 0, 1, 0.0),
        (0x11, 2, 0, 1, 0.0),
        (0x12, 3, 0, 1, 0.0),
        (0x20, 1, 0, 1, cairn_reserve),
        (0x20, 2, 1, 1, 8.1),
        (0x20, 3, 2, 1, 7.65),
    )
    for index, instruction in enumerate(instructions):
        padding = bytes(16)
        if index >= 4:
            padding = reservoir[reservoir_offset:reservoir_offset + 16]
            reservoir_offset += 16
        start = TABLE_OFFSET + index * BLOCK.size
        program[start:start + BLOCK.size] = BLOCK.pack(
            instruction[0], instruction[2], 1, CODE_OFFSET + index * INSTRUCTION.size,
            INSTRUCTION.size, -100, 100, padding,
        )
        code = CODE_OFFSET + index * INSTRUCTION.size
        program[code:code + INSTRUCTION.size] = INSTRUCTION.pack(*instruction)
    outputs = (("Cairn Reach", "ML"), ("North", "ML"), ("Merewick", "ML"))
    for index, (district, unit) in enumerate(outputs):
        start = OUTPUT_OFFSET + index * OUTPUT.size
        program[start:start + OUTPUT.size] = OUTPUT.pack(
            padded(district, 16), padded(unit, 8), 1, 1,
        )
    return bytes(program)


def _cstring(value: bytes) -> str:
    try:
        return value.split(b"\0", 1)[0].decode("ascii")
    except UnicodeDecodeError as error:
        raise ValueError("non-ASCII DPG1 field") from error


def parse_program(data: bytes) -> dict[str, object]:
    if len(data) != PROGRAM_SIZE:
        raise ValueError("DPG1 length is not 512 bytes")
    values = HEADER.unpack_from(data)
    expected_header = (b"DPG1", 1, HEADER.size, 6, BLOCK.size, TABLE_OFFSET,
                       CODE_OFFSET, 6 * INSTRUCTION.size, OUTPUT_OFFSET, 3, OUTPUT.size)
    if values[:11] != expected_header or values[11] != padded(INTEGRITY, 16):
        raise ValueError("DPG1 header or layout is invalid")
    program_id = _cstring(values[12])
    if program_id not in {BASE_ID, MODEL_ID, TARGET_ID}:
        raise ValueError("DPG1 program identity is not recognized")
    instructions: list[tuple[int, int, int, int, float]] = []
    for index, opcode in enumerate(OPCODES):
        start = TABLE_OFFSET + index * BLOCK.size
        entry = BLOCK.unpack_from(data, start)
        if entry[:7] != (opcode, 0 if index < 4 else index - 3, 1,
                         CODE_OFFSET + index * INSTRUCTION.size, INSTRUCTION.size, -100, 100):
            raise ValueError("DPG1 block table is invalid")
        if index < 4 and entry[7] != bytes(16):
            raise ValueError("DPG1 used an undeclared reservoir")
        instructions.append(INSTRUCTION.unpack_from(data, CODE_OFFSET + index * INSTRUCTION.size))
    fixed = ((0x10, 1, 0, 1), (0x11, 2, 0, 1), (0x12, 3, 0, 1),
             (0x20, 1, 0, 1), (0x20, 2, 1, 1), (0x20, 3, 2, 1))
    if any(item[:4] != expected for item, expected in zip(instructions, fixed)):
        raise ValueError("DPG1 mandatory instruction sequence changed")
    if any(instructions[index][4] != 0.0 for index in range(3)):
        raise ValueError("DPG1 sensor test constants changed")
    cairn, north, merewick = (float(instructions[index][4]) for index in range(3, 6))
    if not 0.0 <= cairn <= 20.0:
        raise ValueError("DPG1 Cairn constant is outside bounds")
    ordinary = build_program(program_id, cairn_reserve=cairn,
                             reservoir=bytes(data[index] for index in RESERVOIR_BYTES))
    for index, (actual, expected) in enumerate(zip(data, ordinary)):
        if index in RESERVOIR_BYTES or 48 <= index < 64 or CAIRN_VALUE_OFFSET <= index < CAIRN_VALUE_OFFSET + 4:
            continue
        if actual != expected:
            raise ValueError("DPG1 changed a fixed structural field")
    base = build_program(BASE_ID)
    base_values = [INSTRUCTION.unpack_from(base, CODE_OFFSET + index * INSTRUCTION.size)[4]
                   for index in range(3, 6)]
    if north != float(base_values[1]) or merewick != float(base_values[2]):
        raise ValueError("DPG1 changed an unaffected district output")
    return {
        "program_id": program_id,
        "format": "DPG1",
        "length": len(data),
        "integrity": INTEGRITY.decode(),
        "mandatory_sensor_tests": ["FIT-CRR-204A", "FIT-CRR-204B", "RESERVE-CONSISTENCY"],
        "outputs": {"Cairn Reach": round(cairn, 2), "North": round(north, 2),
                    "Merewick": round(merewick, 2)},
        "quality": "valid",
    }


def changed_only(data: bytes, *, purpose: str) -> bool:
    base = build_program(BASE_ID)
    allowed = set(RESERVOIR_BYTES) | set(range(48, 64))
    if purpose == "target":
        allowed.update(range(CAIRN_VALUE_OFFSET, CAIRN_VALUE_OFFSET + 4))
    return all(left == right or index in allowed
               for index, (left, right) in enumerate(zip(base, data)))
