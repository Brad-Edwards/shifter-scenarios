"""Deterministic readback checks for KeplerOps research export bundles."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import stat
from pathlib import Path
from typing import Any, Mapping

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


SHA256_PREFIX = "sha256:"
CHECKSUM = re.compile(r"^[0-9a-f]{64} {2}[A-Za-z0-9_.-]+$")
INVALID_RESEARCH_CONTRACT = "invalid research contract"


class ReadbackError(ValueError):
    """Raised when an exported research bundle cannot be reconstructed."""


def _canonical(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _sha256(path: Path) -> str:
    return SHA256_PREFIX + hashlib.sha256(path.read_bytes()).hexdigest()


def _owner_file(path: Path) -> bytes:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise ReadbackError(f"missing bundle member {path.name}") from exc
    if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        raise ReadbackError(f"invalid bundle member {path.name}")
    if metadata.st_mode & 0o077:
        raise ReadbackError(f"bundle member is not owner-only: {path.name}")
    return path.read_bytes()


def _json_member(path: Path) -> Any:
    try:
        return json.loads(_owner_file(path).decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ReadbackError(f"invalid JSON member {path.name}") from exc


def _jsonl_member(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in _owner_file(path).splitlines():
        try:
            row = json.loads(line.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ReadbackError(f"invalid JSONL member {path.name}") from exc
        if not isinstance(row, dict):
            raise ReadbackError(f"invalid JSONL row in {path.name}")
        rows.append(row)
    return rows


def _verify_directory(path: Path) -> Path:
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise ReadbackError("bundle path does not exist") from exc
    metadata = resolved.lstat()
    if not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        raise ReadbackError("bundle path is not a directory")
    if metadata.st_mode & 0o077:
        raise ReadbackError("bundle directory is not owner-only")
    return resolved


def _verify_checksums(bundle: Path) -> list[str]:
    checksums = _owner_file(bundle / "checksums.sha256").decode("ascii").splitlines()
    if not checksums:
        raise ReadbackError("empty checksum manifest")
    names = []
    for line in checksums:
        if CHECKSUM.fullmatch(line) is None:
            raise ReadbackError("invalid checksum line")
        digest, name = line.split("  ", 1)
        if name in names or name in {"", ".", ".."}:
            raise ReadbackError("duplicate or invalid checksum member")
        member = bundle / name
        if not member.is_file() or member.is_symlink():
            raise ReadbackError(f"checksum member missing: {name}")
        actual = hashlib.sha256(_owner_file(member)).hexdigest()
        if actual != digest:
            raise ReadbackError(f"checksum mismatch: {name}")
        names.append(name)
    return names


def _verify_manifest_members(bundle: Path, manifest: Mapping[str, Any]) -> None:
    members = manifest.get("members")
    if not isinstance(members, Mapping) or not members:
        raise ReadbackError("manifest has no members")
    for name, expected in members.items():
        if not isinstance(name, str) or not isinstance(expected, str):
            raise ReadbackError("invalid manifest member")
        if expected != _sha256(bundle / name):
            raise ReadbackError(f"manifest digest mismatch: {name}")


def _verify_required_members(bundle: Path, required: list[str]) -> None:
    missing = sorted(name for name in required if not (bundle / name).is_file())
    if missing:
        raise ReadbackError(f"missing required member(s): {', '.join(missing)}")


def _event_sort_key(event: Mapping[str, Any], ordering: list[str]) -> tuple[Any, ...]:
    try:
        return tuple(event[field] for field in ordering)
    except KeyError as exc:
        raise ReadbackError("event missing ordering field") from exc


def _timeline(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = (
        "occurred_at", "observed_at", "source_id", "source_sequence",
        "event_name", "module_id", "challenge_id", "status", "trace_id",
    )
    return [
        {field: event[field] for field in fields if field in event}
        for event in events
    ]


def _export_policy(contract: Mapping[str, Any]) -> tuple[list[str], list[str], set[str]]:
    export = contract.get("export")
    policy = contract.get("field_policy")
    if not isinstance(export, Mapping) or not isinstance(policy, Mapping):
        raise ReadbackError(INVALID_RESEARCH_CONTRACT)
    required = export.get("required_members")
    ordering = export.get("ordering")
    forbidden = policy.get("forbidden_operational_fields")
    if not isinstance(required, list) or not required:
        raise ReadbackError(INVALID_RESEARCH_CONTRACT)
    if not isinstance(ordering, list) or not ordering:
        raise ReadbackError(INVALID_RESEARCH_CONTRACT)
    if not isinstance(forbidden, list) or not forbidden:
        raise ReadbackError(INVALID_RESEARCH_CONTRACT)
    return required, ordering, set(forbidden)


def _verify_event_rows(
    events: list[dict[str, Any]],
    *,
    ordering: list[str],
    forbidden_fields: set[str],
) -> tuple[str, str, int]:
    if not events:
        raise ReadbackError("operational bundle has no events")
    if events != sorted(events, key=lambda event: _event_sort_key(event, ordering)):
        raise ReadbackError("events are not in contract order")
    if any(forbidden_fields & set(event) for event in events):
        raise ReadbackError("operational event contains forbidden field")
    sessions = {event.get("session_id") for event in events}
    runs = {event.get("study_run_id") for event in events}
    generations = {event.get("reset_generation") for event in events}
    if len(sessions) != 1 or len(runs) != 1 or len(generations) != 1:
        raise ReadbackError("bundle mixes research namespaces")
    return next(iter(sessions)), next(iter(runs)), next(iter(generations))


def _verify_bundle_metadata(
    bundle: Path,
    *,
    manifest: Any,
    missingness: Any,
    session_id: str,
) -> None:
    if not isinstance(manifest, Mapping) or not isinstance(missingness, Mapping):
        raise ReadbackError("invalid bundle metadata")
    _verify_manifest_members(bundle, manifest)
    if manifest.get("session_id") != session_id:
        raise ReadbackError("manifest session does not match events")
    if not isinstance(missingness.get("network_flow"), Mapping):
        raise ReadbackError("missing network flow completeness record")


def verify_operational_bundle(
    bundle_path: Path,
    *,
    contract: Mapping[str, Any],
    include_timeline: bool = False,
) -> dict[str, Any]:
    """Verify an operational export bundle and return a reconstructable summary."""

    bundle = _verify_directory(bundle_path)
    checksum_members = _verify_checksums(bundle)
    required, ordering, forbidden_fields = _export_policy(contract)
    _verify_required_members(bundle, required)
    manifest = _json_member(bundle / "manifest.json")
    missingness = _json_member(bundle / "missingness.json")
    events = _jsonl_member(bundle / "events.jsonl")
    flows = _jsonl_member(bundle / "network-flows.jsonl")
    session_id, study_run_id, generation = _verify_event_rows(
        events,
        ordering=ordering,
        forbidden_fields=forbidden_fields,
    )
    _verify_bundle_metadata(
        bundle,
        manifest=manifest,
        missingness=missingness,
        session_id=session_id,
    )
    summary = {
        "bundle_digest": _sha256(bundle / "checksums.sha256"),
        "event_count": len(events),
        "generation": generation,
        "member_count": len(checksum_members),
        "missingness_status": missingness.get("status"),
        "network_flow_count": len(flows),
        "session_id": session_id,
        "study_run_id": study_run_id,
    }
    if include_timeline:
        summary["timeline"] = _timeline(events)
    return summary


def _decode_content_row(row: Mapping[str, Any], content_key: bytes) -> bytes:
    try:
        nonce = base64.b64decode(str(row["nonce_b64"]), validate=True)
        ciphertext = base64.b64decode(str(row["ciphertext_b64"]), validate=True)
        return AESGCM(content_key).decrypt(nonce, ciphertext, None)
    except Exception as exc:
        raise ReadbackError("content decrypt failed") from exc


def _verify_content_metadata(manifest: Any, rows: list[dict[str, Any]]) -> str:
    if not isinstance(manifest, Mapping) or not rows:
        raise ReadbackError("invalid content bundle")
    if manifest.get("encryption") != "AES-256-GCM" or manifest.get("key_included") is not False:
        raise ReadbackError("invalid content encryption contract")
    if any(row.get("encryption") != "AES-256-GCM" for row in rows):
        raise ReadbackError("invalid content row encryption")
    sessions = {row.get("session_id") for row in rows}
    if len(sessions) != 1 or manifest.get("session_id") not in sessions:
        raise ReadbackError("content bundle mixes sessions")
    return next(iter(sessions))


def _decrypted_content_rows(
    rows: list[dict[str, Any]],
    *,
    content_key: bytes,
    include_content: bool,
) -> list[dict[str, Any]]:
    if not isinstance(content_key, bytes) or len(content_key) != 32:
        raise ReadbackError("invalid content key")
    decoded = []
    for row in rows:
        plaintext = _decode_content_row(row, content_key)
        decoded_row = {
            "byte_count": len(plaintext),
            "content_digest": SHA256_PREFIX + hashlib.sha256(plaintext).hexdigest(),
            "content_id": row["content_id"],
            "signal": row["signal"],
            "trace_id": row["trace_id"],
        }
        if include_content:
            decoded_row["content_b64"] = base64.b64encode(plaintext).decode("ascii")
        decoded.append(decoded_row)
    return decoded


def verify_content_bundle(
    bundle_path: Path,
    *,
    content_key: bytes | None = None,
    include_content: bool = False,
) -> dict[str, Any]:
    """Verify a separate encrypted full-content export bundle."""

    bundle = _verify_directory(bundle_path)
    checksum_members = _verify_checksums(bundle)
    manifest = _json_member(bundle / "manifest.json")
    rows = _jsonl_member(bundle / "content.jsonl")
    _verify_manifest_members(bundle, manifest)
    session_id = _verify_content_metadata(manifest, rows)
    summary = {
        "content_record_count": len(rows),
        "member_count": len(checksum_members),
        "session_id": session_id,
    }
    if content_key is not None:
        summary["decrypted_content"] = _decrypted_content_rows(
            rows,
            content_key=content_key,
            include_content=include_content,
        )
    return summary


def verify_export_bundle(
    bundle_path: Path,
    *,
    contract: Mapping[str, Any],
    include_timeline: bool = False,
    content_key: bytes | None = None,
    include_content: bool = False,
) -> dict[str, Any]:
    """Verify either an operational or encrypted-content research export."""

    bundle = _verify_directory(bundle_path)
    if (bundle / "content.jsonl").is_file():
        return verify_content_bundle(
            bundle,
            content_key=content_key,
            include_content=include_content,
        )
    return verify_operational_bundle(
        bundle,
        contract=contract,
        include_timeline=include_timeline,
    )
