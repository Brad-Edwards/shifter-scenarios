#!/usr/bin/env python3
"""Dependency-free validation for participant-surface manifests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any


PHASES = {"training", "keplerops", "arwc"}
ENTRY_TYPES = {"directory", "file", "symlink"}
DELIVERY_STATES = {"observed", "not_materialized", "external_unverified", "versioned", "authored"}
SHA256 = re.compile(r"^[0-9a-f]{64}$")
MODE = re.compile(r"^[0-7]{4}$")


class ManifestError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ManifestError(message)


def exact_keys(value: dict[str, Any], required: set[str], optional: set[str], context: str) -> None:
    missing = required - set(value)
    extra = set(value) - required - optional
    require(not missing, f"{context}: missing keys: {sorted(missing)}")
    require(not extra, f"{context}: unexpected keys: {sorted(extra)}")


def validate_authored(value: dict[str, Any]) -> None:
    exact_keys(value, {
        "schema_version", "manifest_kind", "phase", "state", "participant",
        "filesystem", "tools", "network", "disclosures", "delivery",
    }, set(), "manifest")
    require(value["schema_version"] == 1, "manifest: schema_version must be 1")
    require(value["manifest_kind"] == "authored", "manifest: manifest_kind must be authored")
    require(value["phase"] in PHASES, "manifest: unknown phase")
    require(isinstance(value["state"], str) and value["state"], "manifest: state is required")
    participant = value["participant"]
    exact_keys(participant, {"user", "uid", "group", "gid", "groups", "home", "workdir"}, set(), "participant")
    require(participant["uid"] > 0 and participant["gid"] > 0, "participant: root identity is forbidden")
    require(isinstance(participant["groups"], list) and participant["groups"], "participant: groups are required")
    require(all(isinstance(item, str) and item for item in participant["groups"]), "participant: groups must be names")
    require(len(participant["groups"]) == len(set(participant["groups"])), "participant: duplicate groups")
    require(participant["home"].startswith("/") and participant["workdir"].startswith("/"), "participant: absolute paths required")

    filesystem = value["filesystem"]
    exact_keys(filesystem, {"roots", "forbidden_paths"}, set(), "filesystem")
    require(isinstance(filesystem["roots"], list) and filesystem["roots"], "filesystem: at least one root required")
    root_paths: set[str] = set()
    for root_index, root in enumerate(filesystem["roots"]):
        context = f"filesystem.roots[{root_index}]"
        exact_keys(root, {"path", "opaque", "entries"}, set(), context)
        require(root["path"].startswith("/"), f"{context}: absolute path required")
        require(root["path"] not in root_paths, f"{context}: duplicate root")
        root_paths.add(root["path"])
        require(len(root["opaque"]) == len(set(root["opaque"])), f"{context}: duplicate opaque paths")
        entry_paths: set[str] = set()
        for entry_index, entry in enumerate(root["entries"]):
            entry_context = f"{context}.entries[{entry_index}]"
            exact_keys(entry, {"path", "type", "mode", "owner", "group", "classification"}, {"size", "sha256", "target"}, entry_context)
            require(entry["path"] not in entry_paths, f"{entry_context}: duplicate path")
            entry_paths.add(entry["path"])
            require(entry["type"] in ENTRY_TYPES, f"{entry_context}: invalid type")
            require(bool(MODE.fullmatch(entry["mode"])), f"{entry_context}: invalid mode")
            if "sha256" in entry:
                require(entry["type"] == "file" and bool(SHA256.fullmatch(entry["sha256"])), f"{entry_context}: invalid sha256")
            if "size" in entry:
                require(entry["type"] == "file" and entry["size"] >= 0, f"{entry_context}: invalid size")
            if "target" in entry:
                require(entry["type"] == "symlink", f"{entry_context}: target belongs only to symlinks")
    forbidden = filesystem["forbidden_paths"]
    forbidden_names: set[str] = set()
    for index, item in enumerate(forbidden):
        exact_keys(item, {"path", "visible", "readable"}, set(), f"filesystem.forbidden_paths[{index}]")
        require(item["path"].startswith("/"), f"filesystem.forbidden_paths[{index}]: absolute path required")
        require(item["path"] not in forbidden_names, f"filesystem.forbidden_paths[{index}]: duplicate path")
        require(isinstance(item["visible"], bool) and isinstance(item["readable"], bool), f"filesystem.forbidden_paths[{index}]: booleans required")
        require(not item["readable"] or item["visible"], f"filesystem.forbidden_paths[{index}]: readable path must be visible")
        forbidden_names.add(item["path"])

    tool_names: set[str] = set()
    for index, tool in enumerate(value["tools"]):
        exact_keys(tool, {"name", "path"}, set(), f"tools[{index}]")
        require(tool["name"] not in tool_names, f"tools[{index}]: duplicate name")
        require(tool["path"].startswith("/"), f"tools[{index}]: absolute path required")
        tool_names.add(tool["name"])

    network = value["network"]
    exact_keys(network, {"dns", "listeners"}, set(), "network")
    dns_names: set[str] = set()
    for index, item in enumerate(network["dns"]):
        exact_keys(item, {"name", "addresses"}, set(), f"network.dns[{index}]")
        require(item["name"] not in dns_names, f"network.dns[{index}]: duplicate name")
        require(item["addresses"] and len(item["addresses"]) == len(set(item["addresses"])), f"network.dns[{index}]: addresses required and unique")
        dns_names.add(item["name"])
    listeners: set[tuple[str, int]] = set()
    for index, item in enumerate(network["listeners"]):
        exact_keys(item, {"host", "port", "reachable"}, set(), f"network.listeners[{index}]")
        key = (item["host"], item["port"])
        require(key not in listeners, f"network.listeners[{index}]: duplicate probe")
        require(1 <= item["port"] <= 65535 and isinstance(item["reachable"], bool), f"network.listeners[{index}]: invalid probe")
        listeners.add(key)

    disclosure_ids: set[str] = set()
    for index, item in enumerate(value["disclosures"]):
        exact_keys(item, {"id", "kind", "path", "exposes"}, set(), f"disclosures[{index}]")
        require(item["id"] not in disclosure_ids, f"disclosures[{index}]: duplicate id")
        if item["kind"] == "client-reference":
            require(item["path"].startswith("https://"), f"disclosures[{index}]: https URL required for client-reference")
        else:
            require(item["path"].startswith("/"), f"disclosures[{index}]: absolute path required")
        require(len(item["exposes"]) == len(set(item["exposes"])), f"disclosures[{index}]: duplicate exposure")
        disclosure_ids.add(item["id"])
    delivery = value["delivery"]
    exact_keys(delivery, {"cards", "hints"}, set(), "delivery")
    for name, item in delivery.items():
        # hints authored in this repo may include path and levels fields
        if name == "hints" and item.get("status") == "authored":
            exact_keys(item, {"status", "items", "path", "levels"}, set(), f"delivery.{name}")
        else:
            exact_keys(item, {"status", "items"}, set(), f"delivery.{name}")
        require(item["status"] in DELIVERY_STATES, f"delivery.{name}: invalid status")
        require(len(item["items"]) == len(set(item["items"])), f"delivery.{name}: duplicate items")


def validate_observed(value: dict[str, Any]) -> None:
    exact_keys(value, {
        "schema_version", "manifest_kind", "phase", "state", "participant",
        "filesystem", "tools", "network", "security",
    }, set(), "observed manifest")
    require(value["schema_version"] == 1 and value["manifest_kind"] == "observed", "observed manifest: invalid header")
    require(value["phase"] in PHASES, "observed manifest: unknown phase")
    require(isinstance(value["state"], str) and value["state"], "observed manifest: state is required")

    participant = value["participant"]
    require(isinstance(participant, dict), "observed participant: object required")
    exact_keys(participant, {"user", "uid", "group", "gid", "groups", "home", "workdir"}, set(), "observed participant")
    require(isinstance(participant["user"], str) and participant["user"], "observed participant: user required")
    require(isinstance(participant["uid"], int) and not isinstance(participant["uid"], bool) and participant["uid"] > 0, "observed participant: root identity is forbidden")
    require(isinstance(participant["group"], str) and participant["group"], "observed participant: group required")
    require(isinstance(participant["gid"], int) and not isinstance(participant["gid"], bool) and participant["gid"] > 0, "observed participant: root group is forbidden")
    require(isinstance(participant["groups"], list) and all(isinstance(item, str) and item for item in participant["groups"]), "observed participant: groups must be names")
    require(len(participant["groups"]) == len(set(participant["groups"])), "observed participant: duplicate groups")
    require(isinstance(participant["home"], str) and participant["home"].startswith("/"), "observed participant: absolute home required")
    require(isinstance(participant["workdir"], str) and participant["workdir"].startswith("/"), "observed participant: absolute workdir required")

    filesystem = value["filesystem"]
    require(isinstance(filesystem, dict), "observed filesystem: object required")
    exact_keys(filesystem, {"roots", "forbidden_paths"}, set(), "observed filesystem")
    require(isinstance(filesystem["roots"], list) and filesystem["roots"], "observed filesystem: roots required")
    root_paths: set[str] = set()
    for root_index, root in enumerate(filesystem["roots"]):
        context = f"observed filesystem.roots[{root_index}]"
        require(isinstance(root, dict), f"{context}: object required")
        exact_keys(root, {"path", "entries", "errors"}, set(), context)
        require(isinstance(root["path"], str) and root["path"].startswith("/"), f"{context}: absolute path required")
        require(root["path"] not in root_paths, f"{context}: duplicate root")
        root_paths.add(root["path"])
        require(isinstance(root["entries"], list), f"{context}: entries must be an array")
        entry_paths: set[str] = set()
        for entry_index, entry in enumerate(root["entries"]):
            entry_context = f"{context}.entries[{entry_index}]"
            require(isinstance(entry, dict), f"{entry_context}: object required")
            exact_keys(entry, {"path", "type", "mode", "owner", "group"}, {"size", "sha256", "target", "hash_error", "target_error"}, entry_context)
            require(isinstance(entry["path"], str) and entry["path"], f"{entry_context}: path required")
            require(entry["path"] not in entry_paths, f"{entry_context}: duplicate path")
            entry_paths.add(entry["path"])
            require(entry["type"] in ENTRY_TYPES | {"other"}, f"{entry_context}: invalid type")
            require(isinstance(entry["mode"], str) and bool(MODE.fullmatch(entry["mode"])), f"{entry_context}: invalid mode")
            require(isinstance(entry["owner"], str) and entry["owner"], f"{entry_context}: owner required")
            require(isinstance(entry["group"], str) and entry["group"], f"{entry_context}: group required")
            if "size" in entry:
                require(entry["type"] == "file" and isinstance(entry["size"], int) and not isinstance(entry["size"], bool) and entry["size"] >= 0, f"{entry_context}: invalid size")
            if "sha256" in entry:
                require(entry["type"] == "file" and isinstance(entry["sha256"], str) and bool(SHA256.fullmatch(entry["sha256"])), f"{entry_context}: invalid sha256")
            if "target" in entry:
                require(entry["type"] == "symlink" and isinstance(entry["target"], str), f"{entry_context}: invalid target")
            for error_name in ("hash_error", "target_error"):
                if error_name in entry:
                    require(isinstance(entry[error_name], str) and entry[error_name], f"{entry_context}: invalid {error_name}")
        require(isinstance(root["errors"], list), f"{context}: errors must be an array")
        for error_index, error in enumerate(root["errors"]):
            error_context = f"{context}.errors[{error_index}]"
            require(isinstance(error, dict), f"{error_context}: object required")
            exact_keys(error, {"path", "error"}, set(), error_context)
            require(all(isinstance(error[name], str) and error[name] for name in ("path", "error")), f"{error_context}: path and error required")

    require(isinstance(filesystem["forbidden_paths"], list), "observed filesystem: forbidden paths required")
    forbidden_paths: set[str] = set()
    for index, item in enumerate(filesystem["forbidden_paths"]):
        context = f"observed filesystem.forbidden_paths[{index}]"
        require(isinstance(item, dict), f"{context}: object required")
        exact_keys(item, {"path", "visible", "readable"}, set(), context)
        require(isinstance(item["path"], str) and item["path"].startswith("/"), f"{context}: absolute path required")
        require(item["path"] not in forbidden_paths, f"{context}: duplicate path")
        forbidden_paths.add(item["path"])
        require(isinstance(item["visible"], bool) and isinstance(item["readable"], bool), f"{context}: booleans required")
        require(not item["readable"] or item["visible"], f"{context}: readable path must be visible")

    require(isinstance(value["tools"], list), "observed tools: array required")
    tool_names: set[str] = set()
    for index, tool in enumerate(value["tools"]):
        context = f"observed tools[{index}]"
        require(isinstance(tool, dict), f"{context}: object required")
        exact_keys(tool, {"name", "path", "executable"}, set(), context)
        require(isinstance(tool["name"], str) and tool["name"], f"{context}: name required")
        require(tool["name"] not in tool_names, f"{context}: duplicate name")
        tool_names.add(tool["name"])
        require(tool["path"] is None or (isinstance(tool["path"], str) and tool["path"].startswith("/")), f"{context}: path must be absolute or null")
        require(isinstance(tool["executable"], bool), f"{context}: executable must be boolean")

    network = value["network"]
    require(isinstance(network, dict), "observed network: object required")
    exact_keys(network, {"dns", "listeners"}, set(), "observed network")
    require(isinstance(network["dns"], list), "observed network: DNS required")
    dns_names: set[str] = set()
    for index, item in enumerate(network["dns"]):
        context = f"observed network.dns[{index}]"
        require(isinstance(item, dict), f"{context}: object required")
        exact_keys(item, {"name", "addresses"}, set(), context)
        require(isinstance(item["name"], str) and item["name"], f"{context}: name required")
        require(item["name"] not in dns_names, f"{context}: duplicate name")
        dns_names.add(item["name"])
        require(isinstance(item["addresses"], list) and all(isinstance(address, str) and address for address in item["addresses"]), f"{context}: addresses must be strings")
        require(len(item["addresses"]) == len(set(item["addresses"])), f"{context}: duplicate address")
    require(isinstance(network["listeners"], list), "observed network: listeners required")
    listener_keys: set[tuple[str, int]] = set()
    for index, item in enumerate(network["listeners"]):
        context = f"observed network.listeners[{index}]"
        require(isinstance(item, dict), f"{context}: object required")
        exact_keys(item, {"host", "port", "reachable"}, set(), context)
        require(isinstance(item["host"], str) and item["host"], f"{context}: host required")
        require(isinstance(item["port"], int) and not isinstance(item["port"], bool) and 1 <= item["port"] <= 65535, f"{context}: invalid port")
        require(isinstance(item["reachable"], bool), f"{context}: reachable must be boolean")
        key = (item["host"], item["port"])
        require(key not in listener_keys, f"{context}: duplicate probe")
        listener_keys.add(key)

    security = value["security"]
    require(isinstance(security, dict), "observed security: object required")
    exact_keys(security, {"unprivileged", "docker_socket_readable", "operator_tests_visible"}, set(), "observed security")
    require(all(isinstance(security[name], bool) for name in security), "observed security: booleans required")


def validate(value: dict[str, Any]) -> None:
    kind = value.get("manifest_kind")
    if kind == "authored":
        validate_authored(value)
    elif kind == "observed":
        validate_observed(value)
    else:
        raise ManifestError("manifest_kind must be authored or observed")


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    require(isinstance(value, dict), f"{path}: top level must be an object")
    validate(value)
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifests", nargs="+", type=Path)
    arguments = parser.parse_args()
    for path in arguments.manifests:
        load(path)
        print(f"PASS: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
