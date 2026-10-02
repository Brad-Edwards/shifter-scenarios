#!/usr/bin/env python3
from __future__ import annotations

import json
import pathlib
import sys

from dpg1 import BASE_ID, build_program, digest_hex, rot128


def main() -> None:
    output = pathlib.Path(sys.argv[1])
    output.mkdir(parents=True, exist_ok=True)
    base = build_program(BASE_ID)
    cases = [
        ("complete-r8", base),
        ("truncated-511", base[:-1]),
        ("extended-513", base + b"\0"),
        ("header-covered", bytes([base[0] ^ 1]) + base[1:]),
        ("reservoir-covered", base[:208] + bytes([base[208] ^ 1]) + base[209:]),
        ("little-endian-block", base[:16][::-1] + base[16:]),
    ]
    records = []
    for index, (name, program) in enumerate(cases, 1):
        filename = f"case-{index:02d}-{name}.dpg"
        (output / filename).write_bytes(program)
        records.append({"case_id": f"DPG1-CASE-{index:02d}", "name": name,
                        "filename": filename, "length": len(program),
                        "digest": digest_hex(program), "decision": "accepted" if program == base else "rejected"})
    (output / "base.dpg").write_bytes(base)
    approved = rot128(base)
    manifest = {"record_id": "VER-ROT128-R3", "revision": 3,
                "program_set": "DPG1-CASES-R3", "approved_digest": f"{approved:032x}",
                "cases": records}
    (output / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n")
    (output / "rot128_expected.h").write_text(
        f"#define ROT128_EXPECTED_HI UINT64_C(0x{approved >> 64:016x})\n"
        f"#define ROT128_EXPECTED_LO UINT64_C(0x{approved & ((1 << 64) - 1):016x})\n"
    )


if __name__ == "__main__":
    main()
