#!/usr/bin/env python3
"""Fail-open file-content recorder for the participant Kali workstation."""

from __future__ import annotations

import base64
import hashlib
import json
import queue
import time
from pathlib import Path

from keplerops_research_transport import start_sender


HOME_ROOT = Path("/home/kasm-user")
WATCH_ROOTS = (HOME_ROOT / "Desktop", HOME_ROOT / "Downloads", HOME_ROOT / "work")
EXCLUDED_PARTS = {".cache", ".config", ".local", ".vnc", ".mozilla", ".pki"}
MAX_QUEUE = 512
MAX_CONTENT_BYTES = 900_000
MAX_FILE_BYTES = 4_000_000
POLL_SECONDS = 2.0


EVENTS: queue.Queue[tuple[str, dict[str, object]] | None] = queue.Queue(MAX_QUEUE)


def _trace_id(path: str, digest: str) -> str:
    material = f"{time.time_ns()}:{path}:{digest}".encode()
    return hashlib.sha256(material).hexdigest()[:32]


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(HOME_ROOT))
    except ValueError:
        return str(path)


def _allowed(path: Path) -> bool:
    return not any(part in EXCLUDED_PARTS for part in path.parts)


def _walk_files() -> dict[str, tuple[int, int]]:
    observed: dict[str, tuple[int, int]] = {}
    for root in WATCH_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            try:
                if not path.is_file() or not _allowed(path):
                    continue
                stat = path.stat()
            except OSError:
                continue
            observed[str(path)] = (stat.st_size, stat.st_mtime_ns)
    return observed


def _read_file(path: Path, size: int) -> tuple[str, str | None, bool]:
    if size > MAX_FILE_BYTES:
        return "", None, True
    try:
        data = path.read_bytes()
    except OSError:
        return "", None, True
    return hashlib.sha256(data).hexdigest(), base64.b64encode(data).decode("ascii"), False


def _enqueue(signal: str, event: dict[str, object]) -> None:
    encoded = json.dumps(event, separators=(",", ":"), sort_keys=True).encode()
    if len(encoded) <= MAX_CONTENT_BYTES:
        try:
            EVENTS.put_nowait((signal, event))
        except queue.Full:
            return
        return
    payload = base64.b64encode(encoded).decode("ascii")
    chunks = [
        payload[index : index + MAX_CONTENT_BYTES]
        for index in range(0, len(payload), MAX_CONTENT_BYTES)
    ]
    for index, chunk in enumerate(chunks):
        try:
            EVENTS.put_nowait(
                (
                    signal,
                    {
                        "trace_id": event["trace_id"],
                        "timestamp_ns": event["timestamp_ns"],
                        "path": event["path"],
                        "event": event["event"],
                        "chunked": True,
                        "encoding": "base64-json",
                        "chunk_index": index,
                        "chunk_count": len(chunks),
                        "data": chunk,
                    },
                )
            )
        except queue.Full:
            return


def _emit_file(path_text: str, event_kind: str, size: int = 0, mtime_ns: int = 0) -> None:
    path = Path(path_text)
    digest, data, truncated = _read_file(path, size) if event_kind != "deleted" else ("", None, False)
    trace_id = _trace_id(_relative(path), digest or event_kind)
    event: dict[str, object] = {
        "trace_id": trace_id,
        "timestamp_ns": time.time_ns(),
        "path": _relative(path),
        "event": event_kind,
        "size": size,
        "mtime_ns": mtime_ns,
        "sha256": digest,
        "encoding": "base64",
        "truncated": truncated,
    }
    if data is not None:
        event["data"] = data
    _enqueue("file_content", event)


def _scan_once(previous: dict[str, tuple[int, int]]) -> dict[str, tuple[int, int]]:
    current = _walk_files()
    for path, metadata in current.items():
        if previous.get(path) != metadata:
            event = "created" if path not in previous else "modified"
            _emit_file(path, event, metadata[0], metadata[1])
    for path in set(previous) - set(current):
        _emit_file(path, "deleted")
    return current


def main() -> int:
    start_sender(EVENTS, "keplerops-file-sender", lambda event: str(event["trace_id"]))
    previous = _walk_files()
    while True:
        time.sleep(POLL_SECONDS)
        try:
            previous = _scan_once(previous)
        except Exception:
            continue


if __name__ == "__main__":
    raise SystemExit(main())
