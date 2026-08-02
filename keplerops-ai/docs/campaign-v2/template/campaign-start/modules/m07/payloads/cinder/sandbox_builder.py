#!/usr/bin/env python3
"""Run the submitted artifact builder with fail-closed filesystem bounds."""

from __future__ import annotations

import argparse
import ctypes
import os
from pathlib import Path
import resource
import sys


LANDLOCK_CREATE_RULESET_VERSION = 1
LANDLOCK_RULE_PATH_BENEATH = 1
PR_SET_NO_NEW_PRIVS = 38
SYS_LANDLOCK_CREATE_RULESET = 444
SYS_LANDLOCK_ADD_RULE = 445
SYS_LANDLOCK_RESTRICT_SELF = 446

ACCESS_EXECUTE = 1 << 0
ACCESS_WRITE_FILE = 1 << 1
ACCESS_READ_FILE = 1 << 2
ACCESS_READ_DIR = 1 << 3
ACCESS_REMOVE_DIR = 1 << 4
ACCESS_REMOVE_FILE = 1 << 5
ACCESS_MAKE_CHAR = 1 << 6
ACCESS_MAKE_DIR = 1 << 7
ACCESS_MAKE_REG = 1 << 8
ACCESS_MAKE_SOCK = 1 << 9
ACCESS_MAKE_FIFO = 1 << 10
ACCESS_MAKE_BLOCK = 1 << 11
ACCESS_MAKE_SYM = 1 << 12
ACCESS_REFER = 1 << 13
ACCESS_TRUNCATE = 1 << 14
READ_ACCESS = ACCESS_READ_FILE | ACCESS_READ_DIR
WRITE_ACCESS = (
    ACCESS_WRITE_FILE | ACCESS_REMOVE_DIR | ACCESS_REMOVE_FILE | ACCESS_MAKE_CHAR
    | ACCESS_MAKE_DIR | ACCESS_MAKE_REG | ACCESS_MAKE_SOCK | ACCESS_MAKE_FIFO
    | ACCESS_MAKE_BLOCK | ACCESS_MAKE_SYM
)


class RulesetAttr(ctypes.Structure):
    _fields_ = [("handled_access_fs", ctypes.c_uint64)]


class PathBeneathAttr(ctypes.Structure):
    _fields_ = [("allowed_access", ctypes.c_uint64), ("parent_fd", ctypes.c_int)]


def restrict_filesystem(source_root: Path, output_root: Path) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    abi = libc.syscall(
        SYS_LANDLOCK_CREATE_RULESET, 0, 0, LANDLOCK_CREATE_RULESET_VERSION,
    )
    if abi < 1:
        raise RuntimeError("the Cinder runner kernel does not provide Landlock")
    handled = READ_ACCESS | WRITE_ACCESS | ACCESS_EXECUTE
    if abi >= 2:
        handled |= ACCESS_REFER
    if abi >= 3:
        handled |= ACCESS_TRUNCATE
    ruleset = libc.syscall(
        SYS_LANDLOCK_CREATE_RULESET,
        ctypes.byref(RulesetAttr(handled)),
        ctypes.sizeof(RulesetAttr),
        0,
    )
    if ruleset < 0:
        raise OSError(ctypes.get_errno(), "cannot create Landlock ruleset")

    def allow(path: Path, access: int) -> None:
        if not path.exists():
            return
        descriptor = os.open(path, os.O_PATH | os.O_CLOEXEC)
        try:
            rule = PathBeneathAttr(access, descriptor)
            if libc.syscall(
                SYS_LANDLOCK_ADD_RULE, ruleset, LANDLOCK_RULE_PATH_BENEATH,
                ctypes.byref(rule), 0,
            ) < 0:
                raise OSError(ctypes.get_errno(), f"cannot allow sandbox path: {path}")
        finally:
            os.close(descriptor)

    source_access = READ_ACCESS
    output_access = READ_ACCESS | WRITE_ACCESS
    if abi >= 2:
        output_access |= ACCESS_REFER
    if abi >= 3:
        output_access |= ACCESS_TRUNCATE
    allow(source_root, source_access)
    allow(output_root, output_access)
    for path in (Path("/usr"), Path("/lib"), Path("/lib64"), Path("/proc"), Path("/dev")):
        allow(path, READ_ACCESS)
    allow(Path("/etc/ld.so.cache"), ACCESS_READ_FILE)
    if libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "cannot set no_new_privs")
    if libc.syscall(SYS_LANDLOCK_RESTRICT_SELF, ruleset, 0) < 0:
        raise OSError(ctypes.get_errno(), "cannot apply Landlock ruleset")
    os.close(ruleset)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    source_root = source.parent
    output = args.output.resolve()
    output_root = output.parent.resolve(strict=True)
    if (source.name != "build_unsafe_model.py" or output.name != "orion-model.pkl"
            or output_root == source_root):
        raise SystemExit("builder source and isolated artifact output are invalid")
    code = compile(source.read_bytes(), str(source), "exec")
    resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    resource.setrlimit(resource.RLIMIT_FSIZE, (2 * 1024**3, 2 * 1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (300, 300))
    restrict_filesystem(source_root, output_root)
    sys.argv = [str(source), "--output", str(output)]
    namespace = {"__name__": "__main__", "__file__": str(source), "__package__": None}
    exec(code, namespace, namespace)


if __name__ == "__main__":
    main()
