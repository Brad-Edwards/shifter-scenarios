#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import struct
import sys


PATCHES = {
    0x006100720061006D: 0x00610069006C0065,
    0x006F00740073002E: 0x006F0076002E0073,
    0x0072002D0065006E: 0x0072002D006E0072,
}


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_review_helper.py ASSEMBLY")
    path = pathlib.Path(sys.argv[1])
    binary = bytearray(path.read_bytes())
    for original, replacement in PATCHES.items():
        needle = b"\x48\xb8" + struct.pack("<Q", original) + b"\xc3"
        patched = b"\x48\xb8" + struct.pack("<Q", replacement) + b"\xc3"
        count = binary.count(needle)
        if count != 1:
            raise SystemExit(f"native body pattern count is {count}, expected 1")
        binary = binary.replace(needle, patched)
    path.write_bytes(binary)


if __name__ == "__main__":
    main()
