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


def main() -> None:
    if len(sys.argv) != 3 or sys.argv[1] != "flash":
        raise SystemExit("usage: generate_process_artifacts.py flash OUTPUT")
    output = pathlib.Path(sys.argv[2])
    output.parent.mkdir(parents=True, exist_ok=True)
    make_flash(output)


if __name__ == "__main__":
    main()
