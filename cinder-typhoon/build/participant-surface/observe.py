#!/usr/bin/env python3
"""Observe a Cinder participant surface without privileged access.

A reduced probe plan is read from stdin. The observer emits only metadata and
content hashes; it never receives authored classifications, expected results,
card data or disclosure analysis, and never emits file contents, environment
values or credentials.
"""

from __future__ import annotations

import fnmatch
from concurrent.futures import ThreadPoolExecutor
import grp
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import socket
import stat
import sys
from typing import Any


def identity_name(identifier: int, *, group: bool = False) -> str:
    try:
        return grp.getgrgid(identifier).gr_name if group else pwd.getpwuid(identifier).pw_name
    except KeyError:
        return str(identifier)


def file_type(mode: int) -> str:
    if stat.S_ISREG(mode):
        return "file"
    if stat.S_ISDIR(mode):
        return "directory"
    if stat.S_ISLNK(mode):
        return "symlink"
    return "other"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def matches(relative: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(relative, pattern) for pattern in patterns)


def inventory(root_config: dict[str, Any]) -> dict[str, Any]:
    root = Path(root_config["path"])
    opaque = list(root_config.get("opaque", []))
    entries: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    def describe(path: Path, relative: str) -> tuple[dict[str, Any] | None, str | None]:
        try:
            metadata = path.lstat()
        except OSError as error:
            return None, error.__class__.__name__
        kind = file_type(metadata.st_mode)
        record: dict[str, Any] = {
            "path": relative,
            "type": kind,
            "mode": f"{stat.S_IMODE(metadata.st_mode):04o}",
            "owner": identity_name(metadata.st_uid),
            "group": identity_name(metadata.st_gid, group=True),
        }
        if kind == "file":
            record["size"] = metadata.st_size
            try:
                record["sha256"] = digest(path)
            except OSError as error:
                record["hash_error"] = error.__class__.__name__
        elif kind == "symlink":
            try:
                record["target"] = os.readlink(path)
            except OSError as error:
                record["target_error"] = error.__class__.__name__
        return record, None

    def visit(directory: Path) -> None:
        try:
            children = sorted(os.scandir(directory), key=lambda item: item.name)
        except OSError as error:
            errors.append({"path": directory.as_posix(), "error": error.__class__.__name__})
            return
        for child in children:
            path = Path(child.path)
            relative = path.relative_to(root).as_posix()
            record, error = describe(path, relative)
            if record is None:
                errors.append({"path": relative, "error": str(error)})
                continue
            entries.append(record)
            if record["type"] == "directory" and not matches(relative, opaque):
                visit(path)

    if root.is_dir():
        visit(root)
    elif root.exists() or root.is_symlink():
        record, error = describe(root, ".")
        if record is not None:
            entries.append(record)
        else:
            errors.append({"path": root.as_posix(), "error": str(error)})
    else:
        errors.append({"path": root.as_posix(), "error": "MissingRoot"})
    return {"path": root.as_posix(), "entries": entries, "errors": errors}


def observe_forbidden(path_value: str) -> dict[str, Any]:
    path = Path(path_value)
    try:
        path.lstat()
        visible = True
    except (FileNotFoundError, PermissionError):
        visible = False
    except OSError:
        visible = False
    return {
        "path": path_value,
        "visible": visible,
        "readable": os.access(path, os.R_OK),
    }


def resolve(name: str) -> list[str]:
    try:
        values = socket.getaddrinfo(name, None, socket.AF_INET, socket.SOCK_STREAM)
    except socket.gaierror:
        return []
    return sorted({item[4][0] for item in values})


def reachable(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except OSError:
        return False


def observe(manifest: dict[str, Any]) -> dict[str, Any]:
    expected = manifest["participant"]
    if os.geteuid() == 0:
        raise SystemExit("participant-surface observer refuses to run as uid 0")
    account = pwd.getpwuid(os.geteuid())
    primary_group = grp.getgrgid(os.getegid()).gr_name
    roots = [inventory(item) for item in manifest["filesystem"]["roots"]]
    forbidden = [observe_forbidden(item["path"]) for item in manifest["filesystem"]["forbidden_paths"]]
    tools = []
    for expected_tool in manifest["tools"]:
        located = shutil.which(expected_tool["name"])
        tools.append({
            "name": expected_tool["name"],
            "path": located,
            "executable": bool(located and os.access(located, os.X_OK)),
        })
    dns = [
        {"name": item["name"], "addresses": resolve(item["name"])}
        for item in manifest["network"]["dns"]
    ]
    listener_specs = manifest["network"]["listeners"]
    with ThreadPoolExecutor(max_workers=min(32, max(1, len(listener_specs)))) as executor:
        results = executor.map(lambda item: reachable(item["host"], item["port"]), listener_specs)
        listeners = [
            {"host": item["host"], "port": item["port"], "reachable": result}
            for item, result in zip(listener_specs, results)
        ]
    return {
        "schema_version": 1,
        "manifest_kind": "observed",
        "phase": manifest["phase"],
        "state": manifest["state"],
        "participant": {
            "user": account.pw_name,
            "uid": os.geteuid(),
            "group": primary_group,
            "gid": os.getegid(),
            "groups": sorted({identity_name(value, group=True) for value in os.getgroups()}),
            "home": account.pw_dir,
            "workdir": os.getcwd(),
        },
        "filesystem": {"roots": roots, "forbidden_paths": forbidden},
        "tools": tools,
        "network": {"dns": dns, "listeners": listeners},
        "security": {
            "unprivileged": os.geteuid() == expected["uid"] and os.geteuid() != 0,
            "docker_socket_readable": os.access("/var/run/docker.sock", os.R_OK | os.W_OK),
            "operator_tests_visible": Path("/opt/operator-tests").exists(),
        },
    }


def main() -> int:
    try:
        manifest = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise SystemExit(f"invalid observation plan on stdin: {error}") from error
    json.dump(observe(manifest), sys.stdout, sort_keys=True, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
