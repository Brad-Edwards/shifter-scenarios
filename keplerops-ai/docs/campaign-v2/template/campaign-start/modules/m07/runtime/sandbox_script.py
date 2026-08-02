#!/usr/bin/env python3
"""Execute one submitted Python source with read and write allowlists."""

from __future__ import annotations

import argparse
import ctypes
import os
from pathlib import Path
import resource
import sys


CREATE_RULESET_VERSION = 1
RULE_PATH_BENEATH = 1
READ_FILE = 1 << 2
READ_DIR = 1 << 3
READ_ACCESS = READ_FILE | READ_DIR
WRITE_ACCESS = sum(1 << bit for bit in (1, 4, 5, 6, 7, 8, 9, 10, 11, 12))


class RulesetAttr(ctypes.Structure):
    _fields_ = [("handled_access_fs", ctypes.c_uint64)]


class PathBeneathAttr(ctypes.Structure):
    _fields_ = [("allowed_access", ctypes.c_uint64), ("parent_fd", ctypes.c_int)]


def apply_landlock(read_roots: list[Path], write_root: Path) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    abi = libc.syscall(444, 0, 0, CREATE_RULESET_VERSION)
    if abi < 1:
        raise RuntimeError("the Airflow worker kernel does not provide Landlock")
    handled = (1 << 0) | READ_ACCESS | WRITE_ACCESS
    if abi >= 2:
        handled |= 1 << 13
    if abi >= 3:
        handled |= 1 << 14
    ruleset = libc.syscall(444, ctypes.byref(RulesetAttr(handled)), ctypes.sizeof(RulesetAttr), 0)
    if ruleset < 0:
        raise OSError(ctypes.get_errno(), "cannot create Landlock ruleset")

    def allow(path: Path, access: int) -> None:
        if not path.exists():
            return
        descriptor = os.open(path, os.O_PATH | os.O_CLOEXEC)
        try:
            rule = PathBeneathAttr(access, descriptor)
            if libc.syscall(445, ruleset, RULE_PATH_BENEATH, ctypes.byref(rule), 0) < 0:
                raise OSError(ctypes.get_errno(), f"cannot allow sandbox path: {path}")
        finally:
            os.close(descriptor)

    for root in read_roots:
        allow(root, READ_ACCESS)
    write_access = READ_ACCESS | WRITE_ACCESS
    if abi >= 2:
        write_access |= 1 << 13
    if abi >= 3:
        write_access |= 1 << 14
    allow(write_root, write_access)
    for root in (Path("/usr"), Path("/lib"), Path("/lib64"), Path("/proc"), Path("/dev")):
        allow(root, READ_ACCESS)
    allow(Path("/etc/ld.so.cache"), READ_FILE)
    if libc.prctl(38, 1, 0, 0, 0) != 0 or libc.syscall(446, ruleset, 0) < 0:
        raise OSError(ctypes.get_errno(), "cannot apply Landlock ruleset")
    os.close(ruleset)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--write-root", required=True, type=Path)
    parser.add_argument("--read-root", action="append", default=[], type=Path)
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    write_root = args.write_root.resolve(strict=True)
    read_roots = [source.parent, *(path.resolve(strict=True) for path in args.read_root)]
    code = compile(source.read_bytes(), str(source), "exec")
    resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    resource.setrlimit(resource.RLIMIT_FSIZE, (2 * 1024**3, 2 * 1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (300, 300))
    apply_landlock(read_roots, write_root)
    forwarded = args.arguments[1:] if args.arguments[:1] == ["--"] else args.arguments
    sys.path.insert(0, str(source.parent))
    sys.argv = [str(source), *forwarded]
    namespace = {"__name__": "__main__", "__file__": str(source), "__package__": None}
    exec(code, namespace, namespace)


if __name__ == "__main__":
    main()
