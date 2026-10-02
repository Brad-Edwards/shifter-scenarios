#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys


SOURCE = pathlib.Path(sys.argv[1])
OUTPUT = pathlib.Path(sys.argv[2])
CLANG = os.environ.get("CLANG", "clang-18")
TARGET_TEXT = 16 * 1024


def compile_utility(pad: int) -> None:
    command = [
        CLANG, "-std=gnu17", "-O2", "-fstack-protector-strong", "-fPIE", "-pie",
        "-fcf-protection=none", f"-DTEXT_PAD_BYTES={pad}",
        "-Wl,-z,relro,-z,now,--build-id=none,--export-dynamic",
        "-Wl,--dynamic-linker=/opt/process-service/w28/lib64/ld-linux-x86-64.so.2",
        "-Wl,-rpath,/opt/process-service/w28/lib", "-o", str(OUTPUT), str(SOURCE),
    ]
    subprocess.run(command, check=True)


def executable_bytes() -> int:
    result = subprocess.run(
        ["readelf", "-SW", str(OUTPUT)], check=True, text=True, stdout=subprocess.PIPE,
    ).stdout
    total = 0
    for line in result.splitlines():
        match = re.match(
            r"\s*\[\s*\d+\]\s+\S+\s+\S+\s+[0-9a-fA-F]+\s+[0-9a-fA-F]+\s+"
            r"([0-9a-fA-F]+)\s+\S+\s+([A-Z]+)", line,
        )
        if match and "X" in match.group(2):
            total += int(match.group(1), 16)
    return total


OUTPUT.parent.mkdir(parents=True, exist_ok=True)
compile_utility(1)
baseline = executable_bytes()
pad = TARGET_TEXT - (baseline - 1)
if pad < 1:
    raise SystemExit(f"utility executable sections exceed 16 KiB: {baseline}")
for _ in range(4):
    compile_utility(pad)
    actual = executable_bytes()
    if actual == TARGET_TEXT:
        break
    pad += TARGET_TEXT - actual
else:
    raise SystemExit(f"could not size executable text: {actual}")

subprocess.run(["strip", "--strip-unneeded", str(OUTPUT)], check=True)
if executable_bytes() != TARGET_TEXT:
    raise SystemExit("strip changed the 16 KiB executable contract")

symbols: dict[str, int] = {}
nm = subprocess.run(
    ["nm", "-D", "--defined-only", str(OUTPUT)], check=True, text=True,
    stdout=subprocess.PIPE,
).stdout
for line in nm.splitlines():
    fields = line.split()
    if len(fields) == 3:
        symbols[fields[2]] = int(fields[0], 16)
required = {
    "ordinary_return", "gadget_pop_rdi", "gadget_pop_rsi", "gadget_pop_rdx",
    "gadget_stack_pivot", "controlled_target", "issue_client",
    "immutable_issuer_record", "request_correlation",
}
missing = required - symbols.keys()
if missing:
    raise SystemExit(f"missing exported utility symbols: {sorted(missing)}")

names = ["status", "dry-readback", "revision", "relation", "socket-check"]
ordinary = []
for name in names:
    completed = subprocess.run(
        [str(OUTPUT), "ordinary", name], check=True, text=True, stdout=subprocess.PIPE,
    )
    ordinary.append(json.loads(completed.stdout))

relationship = {
    "record_id": "REL-UTIL-ISSUER-4",
    "revision": 4,
    "utility": "UTIL-CRR-ISSUER-R4",
    "status_return_offset": symbols["ordinary_return"],
    "elf_offsets": {
        "pop_rdi": symbols["gadget_pop_rdi"],
        "pop_rsi": symbols["gadget_pop_rsi"],
        "pop_rdx": symbols["gadget_pop_rdx"],
        "stack_pivot": symbols["gadget_stack_pivot"],
        "controlled_target": symbols["controlled_target"],
        "issue_client": symbols["issue_client"],
        "issuer_record": symbols["immutable_issuer_record"],
        "request_correlation": symbols["request_correlation"],
    },
    "fixed_vdso": {"base": "0x7fff00000000", "setresuid_syscall_offset": 0x7B0},
    "frame": {
        "payload_bytes": 192, "alignment_bytes": 8, "canary_offset": 200,
        "saved_rbp_offset": 208, "saved_return_offset": 216,
        "chain_offset": 224, "maximum_copy_bytes": 384,
    },
}
(OUTPUT.parent / "relationship.json").write_text(
    json.dumps(relationship, sort_keys=True, separators=(",", ":")) + "\n",
    encoding="utf-8",
)
(OUTPUT.parent / "ordinary-invocations.json").write_text(
    json.dumps(ordinary, sort_keys=True, separators=(",", ":")) + "\n",
    encoding="utf-8",
)
relocations = subprocess.run(
    ["readelf", "-Wr", str(OUTPUT)], check=True, text=True, stdout=subprocess.PIPE,
).stdout
(OUTPUT.parent / "relocations.txt").write_text(relocations, encoding="utf-8")
(OUTPUT.parent / "seccomp-policy.json").write_text(json.dumps({
    "record_id": "SECCOMP-UTIL-R4",
    "architecture": "AUDIT_ARCH_X86_64",
    "default": "EPERM",
    "credential_syscalls": ["setresuid", "getuid", "geteuid"],
    "issuer_sequence": ["socket", "connect", "write", "read", "close"],
    "fixed_socket": "/run/arwc/control-issuer.sock",
    "termination": ["exit", "exit_group", "rt_sigreturn"],
}, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
(OUTPUT.parent / "build.json").write_text(json.dumps({
    "utility": "UTIL-CRR-ISSUER-R4",
    "compiler": "clang 18.1",
    "glibc": "2.39",
    "command": "clang-18 -O2 -fstack-protector-strong -fPIE -pie -fcf-protection=none -Wl,-z,relro,-z,now",
    "elf": "Linux x86_64 SysV PIE",
    "executable_text_bytes": TARGET_TEXT,
    "aslr": True,
    "cet": False,
    "file_capability": "cap_setuid=ep",
}, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
