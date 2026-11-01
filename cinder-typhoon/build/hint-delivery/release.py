#!/usr/bin/env python3
"""Validate and release one Cinder Typhoon hint level with a content-free audit."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import stat
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CATALOG_MODULE = ROOT / "challenges" / "catalog.py"
CATALOG_SPEC = importlib.util.spec_from_file_location("cinder_hint_catalog", CATALOG_MODULE)
if CATALOG_SPEC is None or CATALOG_SPEC.loader is None:
    raise RuntimeError("cannot load challenge catalog module")
catalog_module = importlib.util.module_from_spec(CATALOG_SPEC)
CATALOG_SPEC.loader.exec_module(catalog_module)

PHASES = ("training", "keplerops", "arwc")
PHASE_PREFIX = {"T": "training", "K": "keplerops", "W": "arwc"}
MANIFEST_ROOT = ROOT / "build" / "participant-surface" / "manifests"
ARWC_RUNTIME = ROOT / "build" / "arwc" / "runtime"
PLACEHOLDER = re.compile(
    r"(?i)\[(?:hint|todo|tbd)|hint\s+[123]\s+for|placeholder|lorem ipsum|"
    r"generated filler|the immediate evidence concerns|keep the analysis focused|"
    r"retain only evidence tied"
)
SENSITIVE = (
    re.compile(r"(?i)https?://|/api/"),
    re.compile(r"(?i)\bbearer\s+[a-z0-9._~-]+"),
    re.compile(r"(?i)\b(?:password|token|secret|credential)\s*[:=]\s*\S+"),
    re.compile(r"(?i)\b0x[0-9a-f]+\b"),
    re.compile(r"(?i)\b(?:opcode table|winning schedule|final answer|memory layout)\b"),
    re.compile(r"\{[^{}]{3,}\}"),
    re.compile(r"\b(?:AKIA[0-9A-Z]{16}|eyJ[A-Za-z0-9_-]{20,}|[0-9a-f]{32,})\b"),
)
ORIENTATION_WORDS = {
    "artifact", "client", "configuration", "contract", "directory", "document", "evidence",
    "archive", "file", "handover", "history", "interface", "notes", "package", "portal", "record",
    "profile", "records", "renderer", "repository", "service", "site", "source", "system", "workbench",
    "workflow", "workspace",
}
TECHNIQUE_WORDS = {
    "access", "analysis", "authentication", "authorization", "authority", "binding", "boundary", "classification",
    "collision", "comparison", "context", "contract", "correlation", "corruption", "credential",
    "credentials", "cryptographic", "data",
    "delegation", "encoding", "endpoint", "execution", "filter", "format", "history", "identity",
    "injection", "input", "integrity", "interface", "log", "manifest", "metadata", "model",
    "modeling", "normalization", "parser", "protocol", "publication", "reconciliation", "reconstruction",
    "recovery", "revision", "rollback", "route", "scope", "selection", "sequencing", "session",
    "specification", "stored", "structure",
    "structured", "trust", "validation", "version", "workflow",
}
ACTION_WORDS = {
    "capture", "check", "compare", "correlate", "extract", "fetch", "inspect", "join", "list",
    "invoke", "locate", "open", "publish", "query", "read", "record", "replay", "review", "submit",
    "test", "trace", "use", "verify",
}


class HintDeliveryError(ValueError):
    """Hint content, delivery metadata, or release state is invalid."""


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _normalized(value: str) -> str:
    return " ".join(value.split())


def _words(value: str) -> set[str]:
    return set(re.findall(r"[a-z]+", value.lower()))


def _participant_surfaces() -> dict[str, dict[str, Any]]:
    return {
        phase: json.loads((MANIFEST_ROOT / f"{phase}.json").read_text(encoding="utf-8"))
        for phase in PHASES
    }


def _published_references() -> dict[str, set[str]]:
    manifests = _participant_surfaces()
    client_routes = {
        route
        for disclosure in manifests["keplerops"]["disclosures"]
        if disclosure.get("kind") == "client-reference"
        for route in disclosure["exposes"]
    }
    for path in ARWC_RUNTIME.glob("*.py"):
        client_routes.update(
            re.findall(r'"key"\s*:\s*"([^"]+)"', path.read_text(encoding="utf-8"))
        )
    artifacts: set[str] = set()
    services: set[str] = set()
    starting_material: set[str] = set()
    for manifest in manifests.values():
        services.update(record["name"] for record in manifest["network"]["dns"])
        for root in manifest["filesystem"]["roots"]:
            artifacts.update(entry["path"] for entry in root["entries"])
        for disclosure in manifest["disclosures"]:
            starting_material.add(disclosure["id"])
            if disclosure.get("path"):
                artifacts.add(disclosure["path"])
    return {
        "client_route": client_routes,
        "participant_artifact": artifacts,
        "participant_service": services,
        "starting_material": starting_material,
    }


def _validate_text(
    card_id: str,
    level: str,
    text: str,
    title: str,
    seen_text: dict[tuple[str, str], list[str]],
) -> None:
    key = text.casefold()
    if len(text.split()) < 12 or len(text.split()) > 90:
        raise HintDeliveryError(f"{card_id} {level}: hint length is not substantive")
    if PLACEHOLDER.search(text):
        raise HintDeliveryError(f"{card_id} {level}: placeholder hint text")
    if any(pattern.search(text) for pattern in SENSITIVE):
        raise HintDeliveryError(f"{card_id} {level}: sensitive or over-direct hint literal")
    if key == title or (len(title.split()) >= 4 and key.startswith(title)):
        raise HintDeliveryError(f"{card_id} {level}: hint merely restates the title")
    shared = seen_text.setdefault((level, key), [])
    if shared and any(previous.split(".", 1)[0] != card_id.split(".", 1)[0] for previous in shared):
        raise HintDeliveryError(
            f"{card_id} {level}: generic duplicate outside its operation ({', '.join(shared)})"
        )
    shared.append(card_id)
    words = _words(text)
    if level == "h1" and not words.intersection(ORIENTATION_WORDS):
        raise HintDeliveryError(f"{card_id} h1: no credible system or evidence orientation")
    if level == "h2" and not words.intersection(TECHNIQUE_WORDS):
        raise HintDeliveryError(f"{card_id} h2: no technique or boundary class")
    if level == "h3" and not words.intersection(ACTION_WORDS):
        raise HintDeliveryError(f"{card_id} h3: no diagnostic next action")


def validate_authored_hints() -> dict[str, int]:
    """Fail closed on incomplete, unsafe, stale, or non-graduated hint content."""

    catalog = catalog_module.load_catalog()
    documents = catalog_module._hint_documents()
    expected = {card["id"]: card for card in catalog_module.catalog_cards(catalog)}
    references = _published_references()
    seen_cards: set[str] = set()
    seen_text: dict[tuple[str, str], list[str]] = {}
    seen_level_sets: dict[tuple[str, str, str], str] = {}
    hint_count = 0
    phase_counts: dict[str, int] = {}
    for phase, document in documents.items():
        phase_counts[phase] = len(document["hints"])
        for card_id, authored in document["hints"].items():
            if card_id in seen_cards or card_id not in expected or PHASE_PREFIX[card_id[0]] != phase:
                raise HintDeliveryError(f"{card_id}: duplicate, unknown, or wrong-phase hint card")
            seen_cards.add(card_id)
            title = _normalized(expected[card_id]["title"]).lower()
            for level in catalog_module.HINT_LEVELS:
                text = _normalized(authored[level])
                _validate_text(card_id, level, text, title, seen_text)
                hint_count += 1
            level_set = tuple(_normalized(authored[level]) for level in catalog_module.HINT_LEVELS)
            if level_set in seen_level_sets:
                raise HintDeliveryError(
                    f"{card_id}: all three levels duplicate {seen_level_sets[level_set]}"
                )
            seen_level_sets[level_set] = card_id
            for reference in authored["references"]:
                if reference["id"] not in references[reference["kind"]]:
                    raise HintDeliveryError(
                        f"{card_id}: stale {reference['kind']} reference {reference['id']}"
                    )
    if seen_cards != set(expected):
        raise HintDeliveryError(
            f"hint coverage differs; missing={sorted(set(expected) - seen_cards)}, "
            f"extra={sorted(seen_cards - set(expected))}"
        )
    if hint_count != 720:
        raise HintDeliveryError(f"expected 720 hint texts, found {hint_count}")
    manifest = catalog_module.load_hint_manifest()
    if manifest["summary"] != {"operation_count": 70, "card_count": 240, "hint_count": 720}:
        raise HintDeliveryError("hint manifest summary is incomplete")
    return {
        "card_count": len(seen_cards),
        "hint_count": hint_count,
        "operation_review_count": manifest["review"]["operation_count"],
        **{f"{phase}_card_count": count for phase, count in phase_counts.items()},
    }


def _manifest_item(card_id: str) -> dict[str, Any]:
    manifest = catalog_module.load_hint_manifest()
    for item in manifest["items"]:
        if item["card_id"] == card_id:
            return item
    raise HintDeliveryError(f"unknown card: {card_id}")


def _hint_text(card_id: str, level: int) -> str:
    phase = PHASE_PREFIX.get(card_id[:1])
    if phase is None or level not in {1, 2, 3}:
        raise HintDeliveryError("card or level is invalid")
    documents = catalog_module._hint_documents()
    try:
        text = _normalized(documents[phase]["hints"][card_id][f"h{level}"])
    except KeyError as error:
        raise HintDeliveryError(f"unknown card: {card_id}") from error
    item = _manifest_item(card_id)
    expected = next(record["sha256"] for record in item["levels"] if record["level"] == level)
    if hashlib.sha256(text.encode()).hexdigest() != expected:
        raise HintDeliveryError("hint text no longer matches the versioned manifest")
    return text


def _read_audit(handle, manifest_revision: str) -> list[dict[str, Any]]:
    handle.seek(0)
    events = []
    previous = None
    released: set[tuple[str, int]] = set()
    for number, line in enumerate(handle, start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as error:
            raise HintDeliveryError(f"audit line {number} is invalid JSON") from error
        event_id = event.pop("event_id", None)
        if event.get("manifest_revision") != manifest_revision:
            raise HintDeliveryError("audit belongs to a different hint manifest")
        if event.get("previous_event_id") != previous or event_id != _canonical_sha256(event):
            raise HintDeliveryError(f"audit line {number} breaks the event chain")
        key = (event.get("card_id"), event.get("level"))
        if key in released:
            raise HintDeliveryError(f"audit line {number} repeats a released hint")
        released.add(key)
        event["event_id"] = event_id
        previous = event_id
        events.append(event)
    return events


def _open_audit(path: Path, *, writable: bool):
    flags = os.O_RDWR | os.O_APPEND | os.O_CLOEXEC if writable else os.O_RDONLY | os.O_CLOEXEC
    if writable:
        flags |= os.O_CREAT
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError as error:
        raise HintDeliveryError(f"audit cannot be opened safely: {error}") from error
    try:
        mode = os.fstat(descriptor).st_mode
        if not stat.S_ISREG(mode):
            raise HintDeliveryError("audit must be a regular file")
        if writable:
            os.fchmod(descriptor, 0o600)
        elif stat.S_IMODE(mode) != 0o600:
            raise HintDeliveryError("audit permissions must be owner-only")
        return os.fdopen(descriptor, "a+" if writable else "r", encoding="utf-8")
    except Exception:
        os.close(descriptor)
        raise


def release_hint(
    audit_path: Path,
    *,
    card_id: str,
    level: int,
    actor: str,
    released_at: str | None = None,
) -> dict[str, Any]:
    """Release exactly one level and append metadata only to the chained audit."""

    validate_authored_hints()
    if not actor.strip() or len(actor) > 128 or "\n" in actor:
        raise HintDeliveryError("facilitator actor is invalid")
    text = _hint_text(card_id, level)
    manifest = catalog_module.load_hint_manifest()
    item = _manifest_item(card_id)
    content_sha256 = next(
        record["sha256"] for record in item["levels"] if record["level"] == level
    )
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with _open_audit(audit_path, writable=True) as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        events = _read_audit(handle, manifest["revision"])
        existing = next(
            (event for event in events if event["card_id"] == card_id and event["level"] == level),
            None,
        )
        if existing is None:
            event = {
                "schema": "cinder-typhoon.hint-release-event/v1",
                "manifest_revision": manifest["revision"],
                "previous_event_id": events[-1]["event_id"] if events else None,
                "card_id": card_id,
                "level": level,
                "actor": actor,
                "released_at": released_at or datetime.now(UTC).isoformat(),
                "content_sha256": content_sha256,
                "score_penalty": 0,
            }
            event["event_id"] = _canonical_sha256(event)
            handle.seek(0, os.SEEK_END)
            handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
            status = "released"
        else:
            event = existing
            status = "already_released"
    return {
        "status": status,
        "card_id": card_id,
        "level": level,
        "text": text,
        "event_id": event["event_id"],
        "manifest_revision": manifest["revision"],
        "score_penalty": 0,
    }


def release_status(audit_path: Path) -> dict[str, Any]:
    """Return released levels and event IDs without reading or returning hint text."""

    manifest = catalog_module.load_hint_manifest()
    if not os.path.lexists(audit_path):
        events: list[dict[str, Any]] = []
    else:
        with _open_audit(audit_path, writable=False) as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
            events = _read_audit(handle, manifest["revision"])
    return {
        "manifest_revision": manifest["revision"],
        "released": [
            {"card_id": event["card_id"], "level": event["level"], "event_id": event["event_id"]}
            for event in events
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("verify")
    release = subparsers.add_parser("release")
    release.add_argument("--audit", type=Path, required=True)
    release.add_argument("--card", required=True)
    release.add_argument("--level", type=int, choices=(1, 2, 3), required=True)
    release.add_argument("--actor", required=True)
    status = subparsers.add_parser("status")
    status.add_argument("--audit", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.command == "verify":
        result = validate_authored_hints()
    elif arguments.command == "release":
        result = release_hint(
            arguments.audit,
            card_id=arguments.card,
            level=arguments.level,
            actor=arguments.actor,
        )
    else:
        result = release_status(arguments.audit)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
